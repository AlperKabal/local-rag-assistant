import os
import sqlite3
import math
import json
from foundry_local_sdk import Configuration, FoundryLocalManager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime
from contextlib import asynccontextmanager


connection = sqlite3.connect('rag_database.db', check_same_thread=False)
cursor = connection.cursor()
cursor.execute("PRAGMA foreign_keys = ON")

with connection: 
    cursor.execute("""CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, source_name TEXT, text_chunk TEXT, embedding TEXT)""")
print("Connected to the database!")

with connection:
    cursor.execute("""CREATE TABLE IF NOT EXISTS cache(question TEXT PRIMARY KEY, answer TEXT, embedding TEXT)""")
print("Created the cache table")

with connection:
    cursor.execute("""CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY, title TEXT, created_at TEXT)""")
print("Created the conversations table")

with connection:
    cursor.execute("""CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, conversation_id INTEGER, role TEXT, content TEXT, created_at TEXT, FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE)""")
print("Created the messages table")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedding_client, chat_client, doc_embeddings, all_chunks, embedding_model, chat_model
    # Initialize the SDK
    config = Configuration(app_name="foundry_local_rag")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance
   
    # Load the embedding model
    embedding_model = manager.catalog.get_model("qwen3-embedding-8b")
    embedding_model.download(
        lambda p: print(f"\rDownloading embedding model: {p:.1f}%", end="", flush=True)
    )
    print()
    embedding_model.load()
    embedding_client = embedding_model.get_embedding_client()

    # Embed all documents in a single batch call
    all_chunks = load_chunks()
    if not all_chunks:
        documents = load_documents("docs")
        chunked_documents = document_chunks(documents)
        all_text = [c["text"] for c in chunked_documents]
        response = embedding_client.generate_embeddings(all_text)
        for chunk, embed in zip(chunked_documents, response.data):
            chunk["embedding"] = embed.embedding
        save_chunks(chunked_documents)
        all_chunks = load_chunks()
        
    doc_embeddings = [chunk["embedding"] for chunk in all_chunks]
    print(f"Indexed {len(doc_embeddings)} paragraphs.")
    # Load the chat model
    chat_model = manager.catalog.get_model("phi-3.5-mini")
    chat_model.download(
        lambda p: print(f"\rDownloading chat model: {p:.1f}%", end="", flush=True)
    )
    print()
    chat_model.load()
    chat_client = chat_model.get_chat_client()

    print("\nModels loaded. Ready for questions.")

    yield

    embedding_model.unload()
    chat_model.unload()
    connection.close()
    print("Models unloaded. Done!")

app = FastAPI(lifespan=lifespan)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UpdateTitleRequest(BaseModel):
    title:str

class AskRequest(BaseModel):
    question:str
    conversation_id: int | None = None

@app.post("/ask")
def post_message(request: AskRequest):
    question = request.question
    conversation_id = request.conversation_id
    was_initialized = False
    now_question = datetime.datetime.now().isoformat()
    cursor = connection.cursor()

    if conversation_id is None:
        with connection: 
            cursor.execute("""INSERT INTO conversations (title, created_at) VALUES (?,?)""", (question[:50], now_question))
            conversation_id = cursor.lastrowid
            was_initialized = True
    else: 
        exists = cursor.execute("""SELECT id FROM conversations WHERE id = ?""", (conversation_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
    history = [] if was_initialized else get_conversation_history(conversation_id, 6)

    with connection:
        cursor.execute("""INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?,?,?,?)""",(conversation_id, "user", question, now_question))
        message_id = cursor.lastrowid   
     
    try:
        answer = answer_query(question, embedding_client, chat_client, doc_embeddings, all_chunks, history=history)
    except Exception as e:
        print(f"Error answering question: {e}")
        answer = "Sorry, something went wrong while generating an answer. Please try again."
      
        now_answer = datetime.datetime.now().isoformat()
        with connection: 
            cursor.execute("""INSERT INTO messages (conversation_id, role, content,  created_at) VALUES (?,?,?,?)""",(conversation_id, "error-assistant", answer, now_answer))
            if was_initialized: 
                cursor.execute("""DELETE FROM conversations WHERE id = ?""", (conversation_id,))
                return {"answer": answer, "conversation_id": None, "error": True,}
            else:
                cursor.execute("""UPDATE messages SET role = ? WHERE id = ?""", ("error-user", message_id))
                return {"answer": answer, "conversation_id": conversation_id, "error": True}
    now_answer = datetime.datetime.now().isoformat()
    with connection: 
        cursor.execute("""INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?,?,?,?)""",(conversation_id, "assistant", answer, now_answer))

    return {"answer": answer, "conversation_id": conversation_id, "error": False}
        
    

@app.patch("/conversations/{conversation_id}")
def update_title(conversation_id: int, request: UpdateTitleRequest):
    cursor = connection.cursor()
    with connection: 
        cursor.execute("""UPDATE conversations SET title = ? WHERE id = ?""",(request.title, conversation_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
    return {"id": conversation_id, "title": request.title}

@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id:int):
    cursor = connection.cursor()
    with connection: 
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": conversation_id}
    

@app.get("/conversations")
def get_conversations():
    cursor = connection.cursor()
    with connection:
        conversations = cursor.execute("""SELECT id, title, created_at FROM conversations""").fetchall()
    return[{"title" : t, "id": i, "created_at" : c} for i,t,c in conversations]

@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id:int):
    cursor = connection.cursor()
    with connection:
        exists = cursor.execute("""SELECT id FROM conversations WHERE id = ? """, (conversation_id,)).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Conversation not found")
    with connection:
        conversation = cursor.execute("""SELECT role, content, created_at FROM messages WHERE conversation_id = ? AND role NOT IN ('error-user', 'error-assistant') ORDER BY created_at ASC""", (conversation_id,)).fetchall()
    return [{"content": content, "role": role, "created_at": created_at} for role, content, created_at in conversation] 

def get_conversation_history(conversation_id, limit=6):
    cursor = connection.cursor()
    with connection:
        rows = cursor.execute("""SELECT role, content FROM messages WHERE conversation_id = ? AND role NOT IN ('error-user', 'error-assistant') ORDER BY created_at DESC LIMIT ?""", (conversation_id,limit)).fetchall()
        rows.reverse()
    return [{"role": role, "content": content} for role,content in rows]

def get_cached_answer(query_embedding, threshold = 0.95):
    cursor = connection.cursor()
    with connection:
        rows = cursor.execute("""SELECT question, answer, embedding FROM cache""").fetchall()
    best_score = 0
    best_answer = None
    for _, cached_answer, cached_embedding_json in rows:
        cached_embedding = json.loads(cached_embedding_json)
        score = cosine_similarity(cached_embedding,query_embedding)
        if score > best_score:
            best_score = score
            best_answer = cached_answer
    print(f"Best cache similarity score: {best_score}")
    if best_score > threshold:
        return best_answer
    return None 
        
def save_cached_answer(question, answer, embedding):
    cursor = connection.cursor()
    with connection:
        cursor.execute("""INSERT OR REPLACE INTO cache (question, answer, embedding) VALUES (?,?,?)""",(question.lower().strip(), answer, json.dumps(embedding)))


def load_documents(folder_path = "docs"):
    
    documents = []
    if not os.path.exists(folder_path):
        print(f"Error: The folder '{folder_path}' does not exist! Please create it.")
        return documents
  
    for file_path in os.listdir(folder_path):
        filename = os.path.join(folder_path, file_path)
        if os.path.isfile(filename):
            try:
                with open(filename, "r", encoding="utf-8") as file:
                    content = file.read()
                    documents.append({"source": file_path, "text": content})
            except Exception as e: 
                print(f"Skipping {filename}, Reason: {e}")
    return documents
            
       
def document_chunks(documents):
    chunks = []
    for doc in documents:
        source = doc["source"]
        raw_text:str = doc["text"]
        paragraphs = raw_text.split("\n\n")
        stripped_paragraphs = [ p.strip() for p in paragraphs if p.strip()]
        chunks.extend([{"source": source, "text": text} for text in stripped_paragraphs])
    return chunks

def save_chunks(chunks_with_embeddings):
    cursor = connection.cursor()
    with connection:
        for chunk in chunks_with_embeddings:
            vector_string = json.dumps(chunk["embedding"])
            cursor.execute("""INSERT INTO chunks (source_name, text_chunk, embedding) VALUES (?,?,?)""", (chunk["source"], chunk["text"], vector_string))


def load_chunks():
    cursor = connection.cursor()
    with connection:
        all_rows = cursor.execute("""SELECT source_name, text_chunk, embedding FROM chunks""").fetchall()
    return [{"source": r[0], "text": r[1], "embedding": json.loads(r[2])} for r in all_rows]


def cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def find_relevant(query_embedding, doc_embeddings, top_k=5):
    """Return the indices and scores of the top-k most similar documents."""
    scores = []
    for i, doc_emb in enumerate(doc_embeddings):
        score = cosine_similarity(query_embedding, doc_emb)
        scores.append((i, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]  

def rewrite_query(question, history, chat_client):
    if not history:
        return question  # no history yet, nothing to rewrite against

    rewrite_prompt = [
        {
            "role": "system",
            "content": (
                "Rewrite the user's latest message into a standalone question that includes "
                "any context needed to understand it, based on the conversation history below. "
                "If the message is already a standalone question, return it unchanged. "
                "Output ONLY the rewritten question, with no explanation or extra text."
            ),
        },
        *history,
        {"role": "user", "content": question},
    ]

    response = chat_client.complete_chat(rewrite_prompt)  # non-streaming — just need the final text
    return response.choices[0].message.content.strip()  

def answer_query(query, embedding_client, chat_client, doc_embeddings, all_chunks, history = None):
    if history is None:
        history = []
    retrieval_query = rewrite_query(query, history, chat_client)
    
    # 1. Embed the query
    query_response = embedding_client.generate_embedding(retrieval_query)
    query_embedding = query_response.data[0].embedding

    

    # 2. Check the Semantic Cache
    if not history:
        cached_answer = get_cached_answer(query_embedding, threshold=0.95)
        if cached_answer: 
            return cached_answer# Exit the function early since we already answered!

    # 3. Retrieve the most relevant documents
    results = find_relevant(query_embedding, doc_embeddings, top_k=5)
    context = "\n".join(f"- {all_chunks[i]['text']} (source: {all_chunks[i]['source']})" for i, _ in results)
    # 4. Build the prompt
    messages = [
        {
            "role": "system",
            "content":  (
                "You are a strict technical support assistant. "
                "Carefully check whether the facts below contain information relevant to the user's question. "
                "If they do, answer the question using only those facts. "
                "If none of the facts are relevant, or if the user is greeting you or asking something unrelated to Foundry Local, "
                "respond with exactly this sentence and nothing else: "
                "\"I am sorry, but I can only answer questions about Foundry Local features based on my documentation.\"\n\n"
                f"Facts:\n{context}"
            ),
        },
        *history,
        {"role": "user", "content": query},
    ]



    full_answer = ""
    for chunk in chat_client.complete_streaming_chat(messages):
        if chunk.choices: 
            content = chunk.choices[0].delta.content
            if content:
                full_answer += content
    
    # 5. Save the new answer to the cache
    if not history:
        save_cached_answer(retrieval_query, full_answer, query_embedding)

   
    # 6. Return the full_answer
    return full_answer




        
