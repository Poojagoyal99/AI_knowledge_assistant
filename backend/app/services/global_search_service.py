import re
from urllib.parse import quote

import requests


SEARCH_TIMEOUT_SECONDS = 12
USER_AGENT = "ai-knowledge-assistant/1.0"


def _clean_query(query):
    query = re.sub(r"\s+", " ", query or "").strip()
    query = re.sub(
        r"^(what is|what are|who is|who are|tell me about|explain|define)\s+",
        "",
        query,
        flags=re.IGNORECASE,
    )
    return query.strip(" ?.")


def _trim_answer(text, max_sentences=4):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:max_sentences]).strip()


def _wikipedia_search(query):
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 1,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    results = response.json().get("query", {}).get("search", [])
    if not results:
        return None

    title = results[0]["title"]
    summary_response = requests.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
        headers={"User-Agent": USER_AGENT},
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    summary_response.raise_for_status()
    summary = summary_response.json()
    extract = _trim_answer(summary.get("extract", ""))
    if not extract:
        return None

    page_url = summary.get("content_urls", {}).get("desktop", {}).get("page", "")
    return {
        "answer": f"**Global search result**\n\n{extract}",
        "sources": [f"Wikipedia: {title}"],
        "source_links": [page_url] if page_url else [],
    }


def _duckduckgo_search(query):
    response = requests.get(
        "https://api.duckduckgo.com/",
        params={
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()

    text = _trim_answer(data.get("AbstractText", ""))
    url = data.get("AbstractURL", "")
    heading = data.get("Heading", query)

    if not text:
        for topic in data.get("RelatedTopics", []):
            if "Topics" in topic:
                topic = topic["Topics"][0] if topic["Topics"] else {}
            text = _trim_answer(topic.get("Text", ""))
            url = topic.get("FirstURL", "")
            heading = topic.get("Name", heading)
            if text:
                break

    if not text:
        return None

    return {
        "answer": f"**Global search result**\n\n{text}",
        "sources": [f"DuckDuckGo: {heading}"],
        "source_links": [url] if url else [],
    }


def global_search(query):
    clean_query = _clean_query(query)
    if not clean_query:
        return {
            "answer": "Please enter a question to search globally.",
            "sources": [],
            "source_links": [],
        }

    try:
        result = _wikipedia_search(clean_query) or _duckduckgo_search(clean_query)
    except requests.RequestException as exc:
        return {
            "answer": f"I could not search globally right now: {exc}",
            "sources": [],
            "source_links": [],
        }

    if not result:
        return {
            "answer": "I could not find a reliable global result for that question.",
            "sources": [],
            "source_links": [],
        }

    return result
