# AI Knowledge Assistant

A full-stack AI-powered knowledge assistant that lets you upload PDF documents and ask questions about their content. Uses FAISS for vector search, Ollama for LLM inference, and a React frontend.

## Architecture

- **Frontend** — React + Vite (port 5173)
- **Backend** — Django (port 8000) with a RAG pipeline (embeddings, FAISS vector store, chat memory)
- **LLM** — Ollama running `qwen2.5:0.5b` locally (port 11434)

## Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com/) installed

## 1. Start Ollama

```bash
# Start the Ollama server
ollama serve

# Pull the required model (in a separate terminal)
ollama pull qwen2.5:0.5b
```

> **Speed tip:** `qwen2.5:0.5b` is very small and free, so it is faster on normal laptops. For better answer quality, use a larger local model like `gemma:2b`, `gemma2:9b`, or `llama3:8b` by setting `OLLAMA_MODEL` before starting Django.

Ollama will run on `http://localhost:11434`.

## 2. Start the Backend (Django)

```bash
cd backend/server

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r ../requirements.txt

# Run migrations
python manage.py migrate

# Start the server
python manage.py runserver
```

The backend API will be available at `http://localhost:8000/api/`.

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/` | Send a question and get an answer |
| POST | `/api/upload/` | Upload a PDF document |
| GET | `/api/list-pdfs/` | List uploaded PDFs |
| DELETE | `/api/delete-pdf/` | Delete an uploaded PDF |

## 3. Start the Frontend (React)

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The frontend will be available at `http://localhost:5173`.

## Usage

1. Make sure Ollama is running with the `qwen2.5:0.5b` model.
2. Start the backend server.
3. Start the frontend dev server.
4. Open `http://localhost:5173` in your browser.
5. Upload a PDF document.
6. Ask questions about the uploaded document in the chat.
