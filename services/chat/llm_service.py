"""
LLM Service — communicates with Ollama for generating answers.
"""

import json
import re
from typing import Generator

import httpx

from config import settings


NOT_FOUND_RESPONSE = "Not found in uploaded PDFs. Do you want me to search globally outside the PDFs?"


def _build_prompt(context: str, question: str, history: list[dict], source_hint: str = None) -> str:
    system = (
        "You are an AI assistant that answers questions based on the provided document context. "
        "If the answer is not in the context, say 'Not found in document'. "
        "Be concise and accurate."
    )

    messages_text = ""
    for msg in history[-4:]:
        role = msg.get("role", "user")
        messages_text += f"{role}: {msg.get('text', '')}\n"

    prompt = f"""System: {system}

Context from documents:
{context[:7000]}

{f"Source: {source_hint}" if source_hint else ""}

Conversation history:
{messages_text}

Question: {question}

Answer:"""
    return prompt


def ask_llm(context: str, question: str, history: list[dict], source_hint: str = None) -> str:
    """Synchronous LLM call."""
    prompt = _build_prompt(context, question, history, source_hint)

    try:
        response = httpx.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": settings.OLLAMA_NUM_CTX,
                    "num_predict": settings.OLLAMA_NUM_PREDICT,
                },
            },
            timeout=settings.OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        answer = data.get("response", "").strip()
        return answer if answer else "Not found in document"
    except Exception as e:
        return f"Error generating response: {e}"


def stream_llm(context: str, question: str, history: list[dict], source_hint: str = None):
    """Generator that yields tokens from Ollama streaming response."""
    prompt = _build_prompt(context, question, history, source_hint)

    try:
        with httpx.stream(
            "POST",
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "num_ctx": settings.OLLAMA_NUM_CTX,
                    "num_predict": settings.OLLAMA_NUM_PREDICT,
                },
            },
            timeout=settings.OLLAMA_TIMEOUT,
        ) as response:
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        yield f"[Error: {e}]"
