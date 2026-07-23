"""
Document Service — handles file uploads, parsing, embedding, and vector search.
"""

import os
import shutil
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Header, Query
from fastapi.responses import JSONResponse
import httpx

from config import settings
from database import init_db
from embedder import embedder
from faiss_store import FAISSStore
from file_loader import load_document, SUPPORTED_EXTENSIONS
from text_splitter import split_text

app = FastAPI(title="Document Service", version="1.0.0")

# In-memory store cache per user
_user_stores: dict[int, FAISSStore] = {}

MAX_FILE_SIZE_MB = 10
MAX_FILE_COUNT = 10


@app.on_event("startup")
async def startup():
    await init_db()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.FAISS_DIR, exist_ok=True)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "documents"}


# ─── Helpers ───
def _user_upload_dir(user_id: int) -> str:
    path = os.path.join(settings.UPLOAD_DIR, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def _user_faiss_dir(user_id: int) -> str:
    return os.path.join(settings.FAISS_DIR, str(user_id))


def _get_user_id(authorization: str) -> Optional[int]:
    """Extract user_id by calling auth service /auth/me/."""
    # In Docker, gateway already validated. We trust the forwarded header.
    # For direct access, validate with auth service.
    if not authorization or not authorization.startswith("Token "):
        return None
    try:
        resp = httpx.get(
            f"http://localhost:8001/auth/me/",
            headers={"Authorization": authorization},
            timeout=5.0,
        )
        if resp.status_code == 200:
            return resp.json().get("id")
    except httpx.RequestError:
        pass
    # Fallback: extract from X-User-Id header (set by gateway)
    return None


def _get_store(user_id: int) -> Optional[FAISSStore]:
    """Get or load FAISS store for user."""
    if user_id in _user_stores:
        return _user_stores[user_id]

    faiss_dir = _user_faiss_dir(user_id)
    store = FAISSStore.load(faiss_dir)
    if store:
        _user_stores[user_id] = store
    return store


def _build_store(user_id: int) -> Optional[FAISSStore]:
    """Rebuild FAISS index from all user documents."""
    upload_dir = _user_upload_dir(user_id)
    all_chunks = []

    for filename in os.listdir(upload_dir):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        file_path = os.path.join(upload_dir, filename)
        try:
            text = load_document(file_path)
            if not text.strip():
                continue
            chunks = split_text(text)
            chunks = [f"[{filename}] {chunk}" for chunk in chunks]
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    if all_chunks:
        embeddings = embedder.encode(all_chunks)
        dimension = len(embeddings[0])
        store = FAISSStore(dimension)
        store.add(embeddings, all_chunks)
        store.save(_user_faiss_dir(user_id))
        _user_stores[user_id] = store
        return store
    else:
        _user_stores.pop(user_id, None)
        faiss_dir = _user_faiss_dir(user_id)
        if os.path.exists(faiss_dir):
            shutil.rmtree(faiss_dir, ignore_errors=True)
        return None


# ─── Upload ───
@app.post("/documents/upload/")
async def upload_document(
    file: UploadFile = File(...),
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    user_id = int(x_user_id) if x_user_id else _get_user_id(authorization)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return JSONResponse(
            {"error": f"Unsupported file type. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"},
            status_code=400,
        )

    upload_dir = _user_upload_dir(user_id)

    # Check file count
    existing = [f for f in os.listdir(upload_dir) if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS]
    if len(existing) >= MAX_FILE_COUNT:
        return JSONResponse({"error": f"Upload limit reached. Maximum {MAX_FILE_COUNT} documents."}, status_code=400)

    # Check file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        return JSONResponse({"error": f"File too large. Maximum {MAX_FILE_SIZE_MB} MB."}, status_code=400)

    # Save file
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # Rebuild vector store
    _build_store(user_id)

    return JSONResponse({"message": "File uploaded successfully", "filename": file.filename})


# ─── List Documents ───
@app.get("/documents/list/")
async def list_documents(
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    user_id = int(x_user_id) if x_user_id else _get_user_id(authorization)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    upload_dir = _user_upload_dir(user_id)
    files = []
    for f in os.listdir(upload_dir):
        ext = os.path.splitext(f)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            files.append({"name": f, "has_text": True, "error": None})

    return JSONResponse({"files": files})


# ─── Delete Document ───
@app.delete("/documents/delete/")
async def delete_document(
    filename: str = Query(...),
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    user_id = int(x_user_id) if x_user_id else _get_user_id(authorization)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    safe_filename = os.path.basename(filename)
    file_path = os.path.join(_user_upload_dir(user_id), safe_filename)

    if not os.path.exists(file_path):
        return JSONResponse({"error": "File not found"}, status_code=404)

    os.remove(file_path)
    _build_store(user_id)
    return JSONResponse({"message": "File deleted successfully", "filename": safe_filename})


# ─── Search (internal API for chat service) ───
@app.post("/documents/search/")
async def search_documents(
    data: dict,
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    """
    Internal endpoint called by chat service.
    Body: { "user_id": int, "query": str, "k": int, "source_filter": str|null }
    """
    user_id = data.get("user_id") or (int(x_user_id) if x_user_id else _get_user_id(authorization))
    if not user_id:
        return JSONResponse({"error": "user_id required"}, status_code=400)

    query = data.get("query", "")
    k = data.get("k", 6)
    source_filter = data.get("source_filter")

    store = _get_store(user_id)
    if not store:
        # Try building
        store = _build_store(user_id)
    if not store:
        return JSONResponse({"results": [], "sources": []})

    query_embedding = embedder.encode([query])
    results = store.search(query_embedding, k=k, source_filter=source_filter)

    # Extract sources
    sources = sorted(set(
        chunk.split("]", 1)[0][1:]
        for chunk in results
        if chunk.startswith("[") and "]" in chunk
    ))

    return JSONResponse({"results": results, "sources": sources})


# ─── Get all chunks (for summary queries) ───
@app.post("/documents/chunks/")
async def get_chunks(
    data: dict,
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    """Return representative chunks for a user's documents."""
    user_id = data.get("user_id") or (int(x_user_id) if x_user_id else _get_user_id(authorization))
    if not user_id:
        return JSONResponse({"error": "user_id required"}, status_code=400)

    source_filter = data.get("source_filter")
    limit = data.get("limit", 20)

    store = _get_store(user_id)
    if not store:
        store = _build_store(user_id)
    if not store:
        return JSONResponse({"chunks": [], "sources": []})

    chunks = store.documents
    if source_filter:
        prefix = f"[{source_filter.lower()}]"
        chunks = [c for c in chunks if c.lower().startswith(prefix)]

    # Sample evenly
    if len(chunks) > limit:
        step = len(chunks) / limit
        chunks = [chunks[int(i * step)] for i in range(limit)]

    sources = sorted(set(
        chunk.split("]", 1)[0][1:]
        for chunk in chunks
        if chunk.startswith("[") and "]" in chunk
    ))

    return JSONResponse({"chunks": chunks, "sources": sources})


# ─── List PDF names (for source matching) ───
@app.get("/documents/names/")
async def get_document_names(
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    user_id = int(x_user_id) if x_user_id else _get_user_id(authorization)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    upload_dir = _user_upload_dir(user_id)
    names = [
        f for f in os.listdir(upload_dir)
        if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
    ]
    return JSONResponse({"names": names})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
