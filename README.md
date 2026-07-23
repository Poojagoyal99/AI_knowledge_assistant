# AI Knowledge Assistant

A full-stack AI-powered knowledge assistant that lets you upload PDF documents and ask questions about their content. Uses FAISS for vector search, Ollama for LLM inference, and a React frontend.

## Architecture

- **Frontend** — React + Vite (port 5173)
- **Backend** — Django (port 8000) with a RAG pipeline (embeddings, FAISS vector store, chat memory)
- **LLM** — Ollama running `qwen2.5:3b` locally (port 11434)

## Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com/) installed

## 1. Start Ollama

```bash
# Start the Ollama server
ollama serve

# Pull the required model (in a separate terminal)
ollama pull qwen2.5:3b
```

> **Speed tip:** `qwen2.5:3b` offers good quality on most laptops. For even better answers, use `gemma2:9b` or `llama3:8b` by setting `OLLAMA_MODEL` before starting Django. For slower machines, `qwen2.5:0.5b` is lighter but less accurate.

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

# (Optional) Copy and edit the env file — works without it using defaults
cp ../.env.example ../.env

# Run migrations
python manage.py migrate

# Start the server
python manage.py runserver
```

### Production

```bash
# Set required env vars (or edit backend/.env)
# DEBUG=False
# DJANGO_SECRET_KEY=<generate-a-real-key>
# ALLOWED_HOSTS=yourdomain.com
# CORS_ALLOWED_ORIGINS=https://yourdomain.com
# EMAIL_HOST_USER=you@gmail.com
# EMAIL_HOST_PASSWORD=<app-password>

# Run with gunicorn instead of runserver
gunicorn server.wsgi:application --bind 0.0.0.0:8000
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

1. Make sure Ollama is running with the `qwen2.5:3b` model.
2. Start the backend server.
3. Start the frontend dev server.
4. Open `http://localhost:5173` in your browser.
5. Upload a PDF document.
6. Ask questions about the uploaded document in the chat.

---

## Microservices Architecture (Alternative)

The project also includes a full microservices version under `services/`.

### Architecture

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│ Frontend │────▶│   Gateway    │────▶│ Auth Service │
│  (React) │     │  (port 8080) │     │  (port 8001) │
└──────────┘     └──────┬───────┘     └──────────────┘
                        │
              ┌─────────┼─────────┐
              ▼                   ▼
     ┌────────────────┐  ┌──────────────┐
     │Document Service│  │ Chat Service │
     │  (port 8002)   │  │  (port 8003) │
     └────────────────┘  └──────────────┘
              │                   │
              ▼                   ▼
     ┌────────────────┐  ┌──────────────┐
     │  FAISS / Files │  │   Ollama     │
     └────────────────┘  └──────────────┘
```

### Run with Docker Compose

```bash
# Make sure Ollama is running on your host
ollama serve

# Start all services
docker-compose up --build

# Frontend: http://localhost:5173
# Gateway API: http://localhost:8080/api/
```

### Run Locally (without Docker)

```bash
# Install shared dependencies
pip install -r services/requirements-dev.txt

# Start all 4 services at once
python run_services.py

# In another terminal, start the frontend
cd frontend && npm run dev
```

### Services

| Service | Port | Responsibility |
|---------|------|----------------|
| Gateway | 8080 | Routing, auth validation, rate limiting |
| Auth | 8001 | Registration, login, tokens, OTP, admin |
| Documents | 8002 | Upload, parse, embed, FAISS vector search |
| Chat | 8003 | Conversations, LLM queries, streaming, export |
