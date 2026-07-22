import re
from urllib.parse import quote

import requests


SEARCH_TIMEOUT_SECONDS = 12
USER_AGENT = "InsightDocsApp/1.0 (AI Knowledge Assistant; educational project; contact: user@localhost)"


def _clean_query(query):
    query = re.sub(r"\s+", " ", query or "").strip()
    # Strip common question prefixes to extract the actual topic
    prefixes = [
        r"^i\s+want\s+to\s+know\s+(?:about\s+|the\s+)?",
        r"^(?:what\s+is\s+mean(?:t)?\s+by|what\s+do\s+you\s+mean\s+by)\s+",
        r"^(?:what\s+is|what\s+are|who\s+is|who\s+are)\s+(?:a\s+|an\s+|the\s+)?",
        r"^(?:tell\s+me\s+about|explain\s+me|explain|define|describe)\s+(?:a\s+|an\s+|the\s+)?",
        r"^(?:give\s+me\s+(?:the\s+)?(?:definition|meaning|info|information)\s+(?:of|about|on)\s+)",
        r"^(?:i\s+(?:want|need)\s+(?:to\s+know\s+)?(?:the\s+)?(?:definition|meaning)\s+(?:of|about)\s+)",
        r"^(?:how\s+to|how\s+do\s+(?:i|you|we))\s+",
    ]
    for prefix in prefixes:
        query = re.sub(prefix, "", query, flags=re.IGNORECASE)

    # Strip trailing noise
    query = re.sub(r"\s+(definition|meaning|explain|details)$", "", query, flags=re.IGNORECASE)
    return query.strip(" ?.,")


def _trim_answer(text, max_sentences=4):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:max_sentences]).strip()


def _is_result_relevant(title, extract, query):
    """Check if a Wikipedia result is actually relevant to the query."""
    query_lower = query.lower()
    title_lower = title.lower()
    extract_lower = (extract or "").lower()

    # Extract key terms from the query (words > 2 chars)
    query_terms = [w for w in re.findall(r"[a-z]+", query_lower) if len(w) > 2]
    if not query_terms:
        return True

    # Check if the title contains the main query terms
    title_match = sum(1 for term in query_terms if term in title_lower)
    if title_match >= len(query_terms) * 0.5:
        return True

    # Check if the extract discusses the query topic
    extract_match = sum(1 for term in query_terms if term in extract_lower)
    if extract_match >= len(query_terms) * 0.6:
        return True

    # Check if query appears as a phrase in the extract
    if query_lower in extract_lower or query_lower in title_lower:
        return True

    return False


def _wikipedia_search(query):
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 5,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    results = response.json().get("query", {}).get("search", [])
    if not results:
        return None

    # Try each result until we get a relevant summary
    for result in results:
        title = result["title"]
        try:
            summary_response = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
                headers={"User-Agent": USER_AGENT},
                timeout=SEARCH_TIMEOUT_SECONDS,
            )
            summary_response.raise_for_status()
            summary = summary_response.json()
            extract = _trim_answer(summary.get("extract", ""))
            if extract and len(extract) > 30 and _is_result_relevant(title, extract, query):
                page_url = summary.get("content_urls", {}).get("desktop", {}).get("page", "")
                return {
                    "answer": f"**Global search result**\n\n{extract}",
                    "sources": [f"Wikipedia: {title}"],
                    "source_links": [page_url] if page_url else [],
                }
        except requests.RequestException:
            continue

    # Fallback: use search snippet if relevant
    for result in results:
        snippet = re.sub(r"<[^>]+>", "", result.get("snippet", ""))
        title = result["title"]
        if snippet and _is_result_relevant(title, snippet, query):
            page_url = f"https://en.wikipedia.org/wiki/{quote(title)}"
            return {
                "answer": f"**Global search result**\n\n{snippet}",
                "sources": [f"Wikipedia: {title}"],
                "source_links": [page_url],
            }

    return None


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
