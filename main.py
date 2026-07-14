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



# Knowledge base — each string represents a document
documents = [
    "Foundry Local runs AI models directly on your device without cloud connectivity.",
    "The Foundry Local SDK supports Python, C#, JavaScript, and Rust.",
    "Embedding models convert text into numerical vectors for similarity search.",
    "Foundry Local uses ONNX Runtime for efficient model inference on CPUs and GPUs.",
    "The model catalog provides pre-optimized models that you can download and run locally.",
    "Retrieval-augmented generation grounds model responses in your own data.",
    "Vector similarity search finds documents that are semantically close to a query.",
    "Chat completions generate natural language responses from a prompt and context.",
]

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
    response = embedding_client.generate_embeddings(documents)
    doc_embeddings = [item.embedding for item in response.data]
    print(f"Indexed {len(doc_embeddings)} documents.")
    # Load the chat model
    chat_model = manager.catalog.get_model("qwen2.5-0.5b")
    chat_model.download(
        lambda p: print(f"\rDownloading chat model: {p:.1f}%", end="", flush=True)
    )
    print()
    chat_model.load()
    chat_client = chat_model.get_chat_client()

    print("\nModels loaded. Ready for questions.")
    print("\nThe knowledge base contains information about:")
    print("  - Foundry Local features and architecture")
    print("  - Supported programming languages")
    print("  - Embedding models and vector search")
    print("  - ONNX Runtime inference")
    print("  - The model catalog")
    print("  - RAG and chat completions")
    print("\nExample questions:")
    print('  "What programming languages does the SDK support?"')
    print('  "How does Foundry Local run models?"')
    print('  "What is retrieval-augmented generation?"')
    print('\nType "quit" to exit.\n')

    # Interactive query loop
    while True:
        query = input("Question: ").strip()
        if not query or query.lower() == "quit":
            break

        # Embed the query
        query_response = embedding_client.generate_embedding(query)
        query_embedding = query_response.data[0].embedding

        # Retrieve the most relevant documents
        results = find_relevant(query_embedding, doc_embeddings, top_k=2)
        context = "\n".join(f"- {documents[i]}" for i, _ in results)

        # Build the prompt with retrieved context
        # Build the prompt with retrieved context
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

        # Stream the response
        print("Answer: ", end="", flush=True)
        for chunk in chat_client.complete_streaming_chat(messages):
            # ADDED FIX: Check if choices actually exist before reading them
            if chunk.choices: 
                content = chunk.choices[0].delta.content
                if content:
                    print(content, end="", flush=True)
        print("\n")
    # Clean up
    embedding_model.unload()
    chat_model.unload()
    connection.close()
    print("Models unloaded. Done!")


if __name__ == "__main__":
    main()