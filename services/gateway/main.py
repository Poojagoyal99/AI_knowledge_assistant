"""
API Gateway — routes requests to the appropriate microservice
and handles cross-cutting concerns (auth validation, rate limiting).
"""

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from config import settings

app = FastAPI(title="AI Knowledge Assistant — Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared HTTP client
client = httpx.AsyncClient(timeout=180.0)


# ─── Health ───
@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}


# ─── Auth Proxy ───
@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_auth(request: Request, path: str):
    return await _proxy(request, f"{settings.AUTH_SERVICE_URL}/auth/{path}")


# ─── Document Proxy ───
@app.api_route("/api/upload/", methods=["POST"])
async def proxy_upload(request: Request):
    user = await _validate_token(request)
    if isinstance(user, JSONResponse):
        return user
    return await _proxy(request, f"{settings.DOCUMENT_SERVICE_URL}/documents/upload/")


@app.api_route("/api/list-pdfs/", methods=["GET"])
async def proxy_list_pdfs(request: Request):
    user = await _validate_token(request)
    if isinstance(user, JSONResponse):
        return user
    return await _proxy(request, f"{settings.DOCUMENT_SERVICE_URL}/documents/list/")


@app.api_route("/api/delete-pdf/", methods=["DELETE"])
async def proxy_delete_pdf(request: Request):
    user = await _validate_token(request)
    if isinstance(user, JSONResponse):
        return user
    return await _proxy(request, f"{settings.DOCUMENT_SERVICE_URL}/documents/delete/")


# ─── Chat Proxy ───
@app.api_route("/api/chat/", methods=["GET"])
async def proxy_chat(request: Request):
    user = await _validate_token(request)
    if isinstance(user, JSONResponse):
        return user
    return await _proxy(request, f"{settings.CHAT_SERVICE_URL}/chat/query/")


@app.api_route("/api/chat-stream/", methods=["GET"])
async def proxy_chat_stream(request: Request):
    user = await _validate_token(request)
    if isinstance(user, JSONResponse):
        return user
    url = f"{settings.CHAT_SERVICE_URL}/chat/stream/?{request.url.query}"
    headers = dict(request.headers)
    req = client.build_request("GET", url, headers=headers)
    resp = await client.send(req, stream=True)
    return StreamingResponse(
        resp.aiter_bytes(),
        status_code=resp.status_code,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.api_route("/api/global-search/", methods=["GET"])
async def proxy_global_search(request: Request):
    return await _proxy(request, f"{settings.CHAT_SERVICE_URL}/chat/global-search/")


@app.api_route("/api/export-chat/", methods=["POST"])
async def proxy_export_chat(request: Request):
    return await _proxy(request, f"{settings.CHAT_SERVICE_URL}/chat/export/")


# ─── Conversations Proxy ───
@app.api_route("/api/conversations/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_conversations(request: Request, path: str = ""):
    user = await _validate_token(request)
    if isinstance(user, JSONResponse):
        return user
    return await _proxy(request, f"{settings.CHAT_SERVICE_URL}/chat/conversations/{path}")


@app.api_route("/api/messages/{path:path}", methods=["PUT"])
async def proxy_messages(request: Request, path: str = ""):
    user = await _validate_token(request)
    if isinstance(user, JSONResponse):
        return user
    return await _proxy(request, f"{settings.CHAT_SERVICE_URL}/chat/messages/{path}")


# ─── Admin Proxy ───
@app.api_route("/api/admin/{path:path}", methods=["GET"])
async def proxy_admin(request: Request, path: str = ""):
    user = await _validate_token(request)
    if isinstance(user, JSONResponse):
        return user
    return await _proxy(request, f"{settings.AUTH_SERVICE_URL}/auth/admin/{path}")


# ─── Helpers ───
async def _validate_token(request: Request) -> dict | JSONResponse:
    """Validate token with auth service. Returns user dict or error response."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Token "):
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    try:
        resp = await client.get(
            f"{settings.AUTH_SERVICE_URL}/auth/me/",
            headers={"Authorization": auth_header},
        )
        if resp.status_code != 200:
            return JSONResponse({"error": "Invalid token"}, status_code=401)
        return resp.json()
    except httpx.RequestError:
        return JSONResponse({"error": "Auth service unavailable"}, status_code=503)


async def _proxy(request: Request, url: str) -> Response:
    """Forward a request to a downstream service."""
    query = str(request.url.query)
    if query:
        url = f"{url}?{query}"

    headers = dict(request.headers)
    headers.pop("host", None)

    body = await request.body()
    method = request.method

    try:
        resp = await client.request(method, url, headers=headers, content=body)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )
    except httpx.RequestError as e:
        return JSONResponse({"error": f"Service unavailable: {e}"}, status_code=503)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
