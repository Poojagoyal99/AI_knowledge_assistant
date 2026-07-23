import os
import re

import requests


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))

SYSTEM_PROMPT = (
    "You are a helpful, accurate AI knowledge assistant. "
    "Answer the user's question clearly and concisely in a well-structured way. "
    "If the question asks for a definition, provide a clear definition. "
    "If it asks for a process or explanation, provide step-by-step details. "
    "If you are unsure or the question is unclear, say so honestly. "
    "Do not make up facts. Keep answers informative and to the point."
)


def global_search(query):
    """Answer the user's question directly using the LLM's own knowledge."""
    query = (query or "").strip()
    if not query or len(query) < 3:
        return {
            "answer": "Please ask a more specific question.",
            "sources": [],
            "source_links": [],
        }

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": query,
                "system": SYSTEM_PROMPT,
                "stream": False,
                "options": {
                    "num_predict": 512,
                    "temperature": 0.7,
                },
            },
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        answer = (data.get("response") or "").strip()
    except requests.RequestException as exc:
        return {
            "answer": f"Sorry, I couldn't generate an answer right now: {exc}",
            "sources": [],
            "source_links": [],
        }

    if not answer:
        return {
            "answer": "I could not generate an answer for that question.",
            "sources": [],
            "source_links": [],
        }

    return {
        "answer": f"**Global search result**\n\n{answer}",
        "sources": ["AI Knowledge Assistant"],
        "source_links": [],
    }
