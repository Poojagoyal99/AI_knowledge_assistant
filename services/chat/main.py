"""
Chat Service — handles conversations, LLM queries, streaming, and export.
"""

import io
import json
import re
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse, Response
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from config import settings
from database import get_db, init_db
from models import Conversation, Message
from llm_service import ask_llm, stream_llm, NOT_FOUND_RESPONSE

app = FastAPI(title="Chat Service", version="1.0.0")
http_client = httpx.AsyncClient(timeout=60.0)


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "chat"}


# ─── Helpers ───
def _get_user_id_from_header(authorization: str, x_user_id: Optional[str]) -> Optional[int]:
    if x_user_id:
        return int(x_user_id)
    # Fallback: call auth service
    if not authorization or not authorization.startswith("Token "):
        return None
    try:
        resp = httpx.get(
            "http://localhost:8001/auth/me/",
            headers={"Authorization": authorization},
            timeout=5.0,
        )
        if resp.status_code == 200:
            return resp.json().get("id")
    except httpx.RequestError:
        pass
    return None


async def _get_context(user_id: int, query: str, k: int = 6, source_filter: str = None) -> dict:
    """Call document service to get relevant chunks."""
    try:
        resp = await http_client.post(
            f"{settings.DOCUMENT_SERVICE_URL}/documents/search/",
            json={"user_id": user_id, "query": query, "k": k, "source_filter": source_filter},
        )
        if resp.status_code == 200:
            return resp.json()
    except httpx.RequestError:
        pass
    return {"results": [], "sources": []}


async def _get_summary_chunks(user_id: int, source_filter: str = None, limit: int = 20) -> dict:
    """Get representative chunks for summary queries."""
    try:
        resp = await http_client.post(
            f"{settings.DOCUMENT_SERVICE_URL}/documents/chunks/",
            json={"user_id": user_id, "source_filter": source_filter, "limit": limit},
        )
        if resp.status_code == 200:
            return resp.json()
    except httpx.RequestError:
        pass
    return {"chunks": [], "sources": []}


async def _get_pdf_names(user_id: int, authorization: str) -> list[str]:
    """Get list of document names from document service."""
    try:
        resp = await http_client.get(
            f"{settings.DOCUMENT_SERVICE_URL}/documents/names/",
            headers={"X-User-Id": str(user_id), "Authorization": authorization},
        )
        if resp.status_code == 200:
            return resp.json().get("names", [])
    except httpx.RequestError:
        pass
    return []


def _is_summary_query(query: str) -> bool:
    return any(term in query.lower() for term in [
        "summarize", "summary", "overview", "important point",
        "key point", "main point", "most important",
    ])


def _match_pdf_source(query: str, pdf_list: list[str]) -> Optional[str]:
    """Simple source matching."""
    query_lower = query.lower()
    for pdf in pdf_list:
        stem = pdf.rsplit(".", 1)[0].lower()
        if stem in query_lower or pdf.lower() in query_lower:
            return pdf
    return None


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# ─── Chat Query ───
@app.get("/chat/query/")
async def chat_query(
    query: str = Query(default=""),
    conversation_id: Optional[int] = Query(default=None),
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
):
    user_id = _get_user_id_from_header(authorization, x_user_id)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    if not query:
        return JSONResponse({"error": "No query provided"}, status_code=400)

    # Get PDF names and match source
    pdf_names = await _get_pdf_names(user_id, authorization)
    source_filter = _match_pdf_source(query, pdf_names)
    full_query = query
    if source_filter:
        full_query = f"Use only content from the document named {source_filter} when answering. {query}"

    # Get context
    if _is_summary_query(query):
        ctx = await _get_summary_chunks(user_id, source_filter)
        context = "\n".join(ctx.get("chunks", []))
        sources = ctx.get("sources", [])
    else:
        ctx = await _get_context(user_id, query, k=6, source_filter=source_filter)
        context = "\n".join(ctx.get("results", []))
        sources = ctx.get("sources", [])

    if not context:
        answer = NOT_FOUND_RESPONSE
        return JSONResponse({"answer": answer, "sources": []})

    # Call LLM
    history = []
    if conversation_id:
        result = await db.execute(
            select(Message).where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc()).limit(4)
        )
        msgs = result.scalars().all()
        history = [{"role": m.role, "text": m.text} for m in reversed(msgs)]

    answer = ask_llm(context, full_query, history, source_hint=source_filter)

    # Save messages
    if conversation_id:
        db.add(Message(conversation_id=conversation_id, role="user", text=query))
        db.add(Message(conversation_id=conversation_id, role="bot", text=answer, sources=sources))
        await db.execute(
            update(Conversation).where(Conversation.id == conversation_id)
            .values(updated_at=datetime.utcnow())
        )
        # Auto-title
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conv = result.scalar_one_or_none()
        if conv and conv.title == "New Chat":
            conv.title = query[:100]
        await db.commit()

    return JSONResponse({"answer": answer, "sources": sources})


# ─── Chat Stream ───
@app.get("/chat/stream/")
async def chat_stream(
    query: str = Query(default=""),
    conversation_id: Optional[int] = Query(default=None),
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
):
    user_id = _get_user_id_from_header(authorization, x_user_id)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    if not query:
        return JSONResponse({"error": "No query provided"}, status_code=400)

    pdf_names = await _get_pdf_names(user_id, authorization)
    source_filter = _match_pdf_source(query, pdf_names)
    full_query = query
    if source_filter:
        full_query = f"Use only content from the document named {source_filter} when answering. {query}"

    if _is_summary_query(query):
        ctx = await _get_summary_chunks(user_id, source_filter)
        context = "\n".join(ctx.get("chunks", []))
        sources = ctx.get("sources", [])
    else:
        ctx = await _get_context(user_id, query, k=6, source_filter=source_filter)
        context = "\n".join(ctx.get("results", []))
        sources = ctx.get("sources", [])

    history = []
    if conversation_id:
        result = await db.execute(
            select(Message).where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc()).limit(4)
        )
        msgs = result.scalars().all()
        history = [{"role": m.role, "text": m.text} for m in reversed(msgs)]

    def event_stream():
        if not context:
            yield _sse({"type": "sources", "sources": []})
            yield _sse({"type": "final", "answer": NOT_FOUND_RESPONSE, "sources": []})
            return

        answer_parts = []
        for token in stream_llm(context, full_query, history, source_hint=source_filter):
            answer_parts.append(token)
            yield _sse({"type": "token", "token": token})

        answer = "".join(answer_parts).strip() or "Not found in document"
        final_sources = sources if not answer.lower().startswith("not found") else []
        yield _sse({"type": "sources", "sources": final_sources})
        yield _sse({"type": "final", "answer": answer, "sources": final_sources})

    response = StreamingResponse(event_stream(), media_type="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


# ─── Global Search ───
@app.get("/chat/global-search/")
async def global_search(query: str = Query(default="")):
    """Search using Ollama without document context."""
    if not query:
        return JSONResponse({"answer": "", "sources": []})

    answer = ask_llm("", query, [], source_hint=None)
    return JSONResponse({"answer": answer, "sources": ["Web/General Knowledge"]})


# ─── Export Chat PDF ───
@app.post("/chat/export/")
async def export_chat(request: Request):
    try:
        body = await request.json()
        messages = body.get("messages", [])
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    if not messages:
        return JSONResponse({"error": "No messages to export"}, status_code=400)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()

    user_style = ParagraphStyle("UserMsg", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold")
    bot_style = ParagraphStyle("BotMsg", parent=styles["Normal"], fontSize=11, leftIndent=12)
    meta_style = ParagraphStyle("Meta", parent=styles["Normal"], fontSize=9, textColor=HexColor("#888888"))

    story = []
    story.append(Paragraph("InsightDocs — Chat Export", styles["Title"]))
    story.append(Paragraph(f"Exported on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", meta_style))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#dddddd")))
    story.append(Spacer(1, 12))

    for msg in messages:
        role = msg.get("role", "user")
        text = msg.get("text", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        if not text.strip():
            continue
        if role == "user":
            story.append(Paragraph(f"You: {text}", user_style))
        else:
            story.append(Paragraph(f"Assistant: {text}", bot_style))
        story.append(Spacer(1, 6))

    doc.build(story)
    buffer.seek(0)

    return Response(
        content=buffer.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="chat-export.pdf"'},
    )


# ─── Conversations CRUD ───
@app.get("/chat/conversations/")
async def list_conversations(
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
):
    user_id = _get_user_id_from_header(authorization, x_user_id)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    result = await db.execute(
        select(Conversation).where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()
    return JSONResponse({
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in convs
        ]
    })


@app.post("/chat/conversations/create/")
async def create_conversation(
    request: Request,
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
):
    user_id = _get_user_id_from_header(authorization, x_user_id)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    try:
        body = await request.json() if await request.body() else {}
    except Exception:
        body = {}

    title = (body.get("title", "New Chat") or "New Chat").strip()[:200]
    conv = Conversation(user_id=user_id, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return JSONResponse({
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
    }, status_code=201)


@app.get("/chat/conversations/{conversation_id}/")
async def get_conversation_messages(
    conversation_id: int,
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
):
    user_id = _get_user_id_from_header(authorization, x_user_id)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return JSONResponse({"error": "Conversation not found"}, status_code=404)

    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    msgs = result.scalars().all()

    return JSONResponse({
        "conversation_id": conv.id,
        "title": conv.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "text": m.text,
                "sources": m.sources or [],
                "highlights": m.highlights or [],
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ],
    })


@app.put("/chat/conversations/{conversation_id}/rename/")
async def rename_conversation(
    conversation_id: int,
    request: Request,
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
):
    user_id = _get_user_id_from_header(authorization, x_user_id)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return JSONResponse({"error": "Conversation not found"}, status_code=404)

    body = await request.json()
    title = (body.get("title", "") or "").strip()[:200]
    if not title:
        return JSONResponse({"error": "Title is required"}, status_code=400)

    conv.title = title
    await db.commit()
    return JSONResponse({"id": conv.id, "title": conv.title})


@app.delete("/chat/conversations/{conversation_id}/delete/")
async def delete_conversation(
    conversation_id: int,
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
):
    user_id = _get_user_id_from_header(authorization, x_user_id)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return JSONResponse({"error": "Conversation not found"}, status_code=404)

    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await db.delete(conv)
    await db.commit()
    return JSONResponse({"message": "Conversation deleted"})


# ─── Highlights ───
@app.put("/chat/messages/{message_id}/highlights/")
async def update_highlights(
    message_id: int,
    request: Request,
    authorization: str = Header(default=""),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
):
    user_id = _get_user_id_from_header(authorization, x_user_id)
    if not user_id:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        return JSONResponse({"error": "Message not found"}, status_code=404)

    # Verify ownership via conversation
    result = await db.execute(
        select(Conversation).where(Conversation.id == msg.conversation_id, Conversation.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        return JSONResponse({"error": "Message not found"}, status_code=404)

    body = await request.json()
    highlights = body.get("highlights", [])
    validated = []
    for h in highlights:
        if isinstance(h, dict) and isinstance(h.get("text"), str) and h["text"].strip():
            validated.append({"text": h["text"], "color": h.get("color", "yellow")})

    msg.highlights = validated
    await db.commit()
    return JSONResponse({"highlights": msg.highlights})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
