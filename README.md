# LOCAG — Local RAG Assistant

A fully offline Retrieval-Augmented Generation (RAG) chat assistant that answers questions using a local document knowledge base. Built with [Microsoft Foundry Local](https://learn.microsoft.com/en-us/azure/foundry-local/) for on-device LLM inference, so no internet connection or cloud API is required at runtime.

## Features

- **Fully offline RAG pipeline** — document ingestion, chunking, embedding, and retrieval all run locally via Foundry Local, with no data ever leaving the device.
- **Semantic search** — documents are split into chunks, embedded, and compared against user queries using cosine similarity.
- **Multi-turn conversations** — follow-up questions are automatically rewritten into standalone queries using conversation history, so vague follow-ups (e.g. "which one is fastest?") retrieve correctly.
- **Semantic caching** — a similarity-based cache reduces redundant LLM calls for repeated or near-identical first-turn questions.
- **Full conversation management** — create, rename, delete, and switch between multiple chat conversations, all persisted in SQLite.
- **Grounded, honest answers** — the assistant is instructed to answer only from retrieved facts, and to clearly decline when the answer isn't in the knowledge base, reducing hallucination.

## Tech Stack

| Layer | Technology |
|---|---|
| LLM runtime | Microsoft Foundry Local (on-device inference) |
| Chat model | Phi-3.5 Mini |
| Embedding model | Qwen3 Embedding |
| Backend | Python, FastAPI |
| Database | SQLite |
| Frontend | React (Vite), Tailwind CSS |

## Architecture

```
React (frontend)
   → FastAPI (REST API, /ask and conversation endpoints)
      → Foundry Local (embedding + chat models, in-process via SDK)
      → SQLite (documents, embeddings, conversations, messages, cache)
```

## Project Structure

```
.
├── main.py              # FastAPI backend: RAG pipeline, endpoints, DB logic
├── docs/                # Source documents for the knowledge base (.txt)
├── rag_database.db      # SQLite database (auto-created on first run)
└── rag-client-side/      # React frontend
    ├── src/
    │   ├── App.jsx
    │   ├── Header.jsx
    │   ├── SideBar.jsx
    │   ├── ChatWindow.jsx
    │   └── QueryForm.jsx
    └── ...
```

## Setup

### Prerequisites

- Python 3.10+
- Node.js and npm
- [Foundry Local](https://learn.microsoft.com/en-us/azure/foundry-local/get-started) installed on your machine

### Backend

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Add your knowledge base documents (.txt files) to the docs/ folder

uvicorn main:app --reload
```

On first run, the backend will download and load the embedding and chat models, then ingest and embed the documents in `docs/`. This may take a few minutes the first time.

### Frontend

In a separate terminal:

```bash
cd rag-client-side
npm install
npm run dev
```

Then open the printed local URL (typically `http://localhost:5173`) in your browser.

## How It Works

1. **Ingestion** — documents in `docs/` are split into paragraph-level chunks, embedded, and stored in SQLite.
2. **Query** — when a question is asked, it's embedded and compared against stored chunk embeddings using cosine similarity to retrieve the most relevant context.
3. **Multi-turn handling** — if the conversation has prior turns, the current question is first rewritten into a standalone version using the conversation history, so retrieval works correctly even for vague follow-ups.
4. **Generation** — the retrieved context, conversation history, and question are sent to the chat model, which is instructed to answer only from the provided facts or clearly decline if the answer isn't present.
5. **Caching** — first-turn answers are cached by question embedding similarity, so near-duplicate first questions can skip regeneration.

## Notes

- All models run on-device via Foundry Local — no API keys, no per-token costs, and no data sent to the cloud.
- The semantic cache is intentionally scoped to first-turn questions only, to avoid caching answers to context-dependent follow-ups incorrectly.
- Retrieval is a simple brute-force cosine similarity search, which is sufficient at this document scale; larger deployments would benefit from a dedicated vector index.
