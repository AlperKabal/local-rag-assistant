import os
import sqlite3
import math
import json
from foundry_local_sdk import Configuration, FoundryLocalManager

connection = sqlite3.connect('rag_database.db')

cursor = connection.cursor()
with connection: 
    cursor.execute("""CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, source_name TEXT, text_chunk TEXT, embedding TEXT)""")
print("Connected to the database!")

with connection:
    cursor.execute("""CREATE TABLE IF NOT EXISTS cache(question TEXT PRIMARY KEY, answer TEXT, embedding TEXT)""")
print("Created the cache table")


def get_cached_answer(query_embedding, threshold = 0.92):
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
    if best_score > threshold:
        return best_answer
    return None 
        
def save_cached_answer(question, answer, embedding):
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
    with connection:
        for chunk in chunks_with_embeddings:
            vector_string = json.dumps(chunk["embedding"])
            cursor.execute("""INSERT INTO chunks (source_name, text_chunk, embedding) VALUES (?,?,?)""", (chunk["source"], chunk["text"], vector_string))


def load_chunks():
    with connection:
        all_rows = cursor.execute("""SELECT source_name, text_chunk, embedding FROM chunks""").fetchall()
    return [{"source": r[0], "text": r[1], "embedding": json.loads(r[2])} for r in all_rows]


def cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def find_relevant(query_embedding, doc_embeddings, top_k=2):
    """Return the indices and scores of the top-k most similar documents."""
    scores = []
    for i, doc_emb in enumerate(doc_embeddings):
        score = cosine_similarity(query_embedding, doc_emb)
        scores.append((i, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]    

def answer_query(query, embedding_client, chat_client, doc_embeddings, all_chunks):
    # 1. Embed the query
    query_response = embedding_client.generate_embedding(query)
    query_embedding = query_response.data[0].embedding

    # 2. Check the Semantic Cache
    cached_answer = get_cached_answer(query_embedding, threshold=0.92)
    if cached_answer: 
        print(f"Answer (cached): {cached_answer}\n")
        return # Exit the function early since we already answered!

    # 3. Retrieve the most relevant documents
    results = find_relevant(query_embedding, doc_embeddings, top_k=3)
    context = "\n".join(f"- {all_chunks[i]['text']} (source: {all_chunks[i]['source']})" for i, _ in results)

    # 4. Build the prompt
    messages = [
        {
            "role": "system",
            "content": (
                "You are a strict technical support assistant. "
                "Answer the user's question using ONLY the facts provided below. "
                "If the answer cannot be found in the text below, or if the user is greeting you/asking off-topic questions, reply exactly with: 'I am sorry, but I can only answer questions about Foundry Local features based on my documentation.'\n\n"
                f"Facts:\n{context}"
            ),
        },
        {"role": "user", "content": query},
    ]

    # 5. Stream the response
    print("Answer: ", end="", flush=True)
    full_answer = ""
    for chunk in chat_client.complete_streaming_chat(messages):
        if chunk.choices: 
            content = chunk.choices[0].delta.content
            if content:
                print(content, end="", flush=True)
                full_answer += content
    print("\n")
    
    # 6. Save the new answer to the cache
    save_cached_answer(query, full_answer, query_embedding)

def main():
    # Initialize the SDK
    config = Configuration(app_name="foundry_local_rag")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance

    # Load the embedding model
    embedding_model = manager.catalog.get_model("qwen3-embedding-0.6b")
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
    print(f"Indexed {len(doc_embeddings)} documents.")
    # Load the chat model
    chat_model = manager.catalog.get_model("phi-3.5-mini")
    chat_model.download(
        lambda p: print(f"\rDownloading chat model: {p:.1f}%", end="", flush=True)
    )
    print()
    chat_model.load()
    chat_client = chat_model.get_chat_client()

    print("\nModels loaded. Ready for questions.")
    print('\nType "quit" to exit.\n')

    # Interactive query loop
    while True:
        query = input("Question: ").strip()
        if not query or query.lower() == "quit":
            break
        answer_query(query, embedding_client, chat_client, doc_embeddings, all_chunks)
        
    # Clean up
    embedding_model.unload()
    chat_model.unload()
    connection.close()
    print("Models unloaded. Done!")


if __name__ == "__main__":
    main()