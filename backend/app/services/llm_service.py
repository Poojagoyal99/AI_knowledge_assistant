import json
import os
import re

import requests


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "512"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "10m")
RAG_CONTEXT_CHARS = int(os.getenv("RAG_CONTEXT_CHARS", "7000"))
NOT_FOUND = "Not found in document"
NOT_FOUND_RESPONSE = "Not found in uploaded PDFs. Do you want me to search globally outside the PDFs?"

STOPWORDS = {
    "a", "an", "and", "are", "as", "ask", "about", "all", "answer",
    "answers", "based", "be", "by", "can", "detail", "details", "doc",
    "docs", "document", "documents", "file", "for", "from", "give", "how",
    "frame", "i", "important", "in", "inside", "interview", "is", "it",
    "key", "list", "main", "me", "most", "named", "note", "notes", "of",
    "on", "or", "pdf", "please", "point", "points", "prepare", "q", "qa",
    "qs", "question", "questions", "simple", "study", "summarize",
    "summary", "resume", "tell", "the", "this", "to", "topic", "what",
    "which", "with", "write",
}

TERM_ALIASES = {
    "eduction": "education",
    "eductaion": "education",
}


def _normalize_space(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _clean_question(question):
    return re.sub(
        r"^use only content from the document named .+? when answering\.\s*",
        "",
        question or "",
        flags=re.IGNORECASE,
    ).strip()


def trim_context(context):
    context = context.strip()
    if len(context) <= RAG_CONTEXT_CHARS:
        return context

    return context[:RAG_CONTEXT_CHARS].rsplit("\n", 1)[0].strip()


def _strip_source_labels(context):
    return re.sub(r"\[[^\]]+\]\s*", " ", context).replace("\r", " ")


def _tokens(value):
    raw_tokens = re.findall(r"[a-z0-9+#.]+", (value or "").lower())
    return [TERM_ALIASES.get(token, token) for token in raw_tokens]


def _content_tokens(value):
    return [token for token in _tokens(value) if len(token) > 1 and token not in STOPWORDS]


def _split_sentences(text):
    cleaned = _normalize_space(_strip_source_labels(text))
    pieces = re.split(r"(?<=[.!?])\s+|\s+(?:\u2022|\u25cf|\*)\s+|\s+-\s+", cleaned)
    return [piece.strip(" :-\t") for piece in pieces if piece.strip(" :-\t")]


def _is_not_found(answer):
    return bool(
        re.search(
            r"not found in (?:the )?(?:document|uploaded pdfs)",
            (answer or "").strip(),
            flags=re.IGNORECASE,
        )
    )


def _task_type(question):
    question_lower = _clean_question(question).lower()
    if any(
        term in question_lower
        for term in [
            "summarize",
            "summary",
            "overview",
            "contain",
            "contains",
            "important point",
            "important points",
            "key point",
            "key points",
            "main point",
            "main points",
            "most important",
        ]
    ):
        return "summary"
    if any(
        term in question_lower
        for term in [
            "important question",
            "important q",
            "imp qs",
            "interview",
            "frame",
            "q&a",
            "question answer",
            "questions from",
        ]
    ):
        return "qa"
    if any(term in question_lower for term in ["note", "notes", "study", "prepare"]):
        return "notes"
    return "answer"


def _requested_count(question, default=5, maximum=10):
    match = re.search(r"\b(\d{1,2})\b", question or "")
    if not match:
        return default

    return max(1, min(maximum, int(match.group(1))))


def _is_count_query(question):
    question_lower = _clean_question(question).lower()
    return any(term in question_lower for term in ["how many", "number of", "count"])


def _friendly_source_name(source):
    return source.replace(".pdf", "").replace("_", " ").replace("-", " ")


def _answer_experience_count(context, question):
    question_lower = _clean_question(question).lower()
    if "experience" not in question_lower or not _is_count_query(question):
        return None

    text = _normalize_space(context)
    months = (
        "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|"
        "January|February|March|April|June|July|August|September|"
        "October|November|December"
    )
    date_pattern = rf"(?:{months})\s+\d{{4}}\s*[–-]\s*(?:Present|(?:{months})\s+\d{{4}})"
    date_matches = list(re.finditer(date_pattern, text, flags=re.IGNORECASE))
    entries = []

    for match in date_matches:
        prefix = text[max(0, match.start() - 180):match.start()]
        prefix = re.sub(r"\[[^\]]+\]\s*", " ", prefix)
        prefix = re.split(r"(?:\u2022|\u25cf|\.)\s+", prefix)[-1]
        entry_match = re.search(
            r"([A-Z][A-Za-z0-9&.,' ]{2,90}?)\s*-\s*([A-Za-z][A-Za-z0-9&/.,' ]{2,90})$",
            prefix.strip(),
        )
        if not entry_match:
            continue

        company = _normalize_space(entry_match.group(1))
        company = re.sub(r"^.*\bEXPERIENCE\s+", "", company, flags=re.IGNORECASE)
        role = _normalize_space(entry_match.group(2))
        period = _normalize_space(match.group(0))
        label = f"{company} - {role} ({period})"

        if company and role and label.lower() not in {existing.lower() for existing in entries}:
            entries.append(label)

    if not entries:
        snippets = _best_snippets(context, question, limit=3)
        if snippets:
            return "I found experience-related details, but could not confidently count separate entries:\n" + "\n".join(
                f"- {snippet}" for snippet in snippets
            )
        return None

    return f"The uploaded PDF mentions {len(entries)} experience entries:\n" + "\n".join(
        f"- {entry}" for entry in entries
    )


def _definition_topic(question):
    cleaned = _clean_question(question).lower().strip()
    cleaned = re.sub(r"^in\s+the\s+document\s+named\s+[^,]+,\s*", "", cleaned)

    patterns = [
        r"^what\s+(?:is|are|was|were)\s+(.+?)[?.!]*$",
        r"^(?:define|explain)\s+(.+?)[?.!]*$",
    ]

    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if not match:
            continue

        topic = re.split(r"\b(?:in|from|inside|within)\b", match.group(1), maxsplit=1)[0]
        topic = re.sub(r"\b(?:pdf|document|resume|file)\b", " ", topic)
        topic = _normalize_space(topic).strip(" .?!'\"")
        topic_tokens = _content_tokens(topic)

        if topic and 0 < len(topic_tokens) <= 5:
            return topic

    return None


def _has_definition_support(context, topic):
    text = _normalize_space(_strip_source_labels(context))
    topic_pattern = rf"(?<![a-z0-9]){re.escape(topic)}(?![a-z0-9])"
    if not re.search(topic_pattern, text, flags=re.IGNORECASE):
        return False

    definition_pattern = (
        rf"(?:{topic_pattern}\s+(?:is|are|was|were|means|refers\s+to|describes|enables|supports)|"
        rf"(?:is|are|was|were|means|refers\s+to|describes)\s+[^.?:;]{{0,120}}{topic_pattern}|"
        rf"{topic_pattern}\s*[:\-]\s*[^.?:;]{{10,}})"
    )
    return bool(re.search(definition_pattern, text, flags=re.IGNORECASE))


def _score_sentence(sentence, terms):
    sentence_lower = sentence.lower()
    score = 0
    for term in terms:
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", sentence_lower):
            score += 4
        elif term in sentence_lower:
            score += 1
    return score


def _clean_snippet_text(text):
    text = re.sub(r"\bCisco Confidential\b", " ", text)
    text = re.sub(r"\s*(?:\u2022|\u25cf|\*)\s*", " ", text)
    text = _normalize_space(text)
    return text.strip(" :-")


def _word_set(text):
    return {
        token
        for token in _content_tokens(text)
        if len(token) > 3
    }


def _is_too_similar(candidate, existing_items):
    candidate_words = _word_set(candidate)
    if not candidate_words:
        return False

    for existing in existing_items:
        existing_words = _word_set(existing)
        if not existing_words:
            continue
        overlap = len(candidate_words & existing_words) / min(len(candidate_words), len(existing_words))
        if overlap >= 0.65:
            return True

    return False


def _cut_trailing_heading(text):
    trailing_heading = re.search(r"\s+[A-Z][A-Z0-9 &/,-]{3,}?\s+[A-Z][a-z]", text[300:])
    if trailing_heading:
        return text[:300 + trailing_heading.start()].strip()
    return text


def _trim_around_terms(text, terms, max_chars=760):
    text = _normalize_space(text)
    if len(text) <= max_chars:
        return _cut_trailing_heading(text)

    lower_text = text.lower()
    positions = [
        lower_text.find(term)
        for term in terms
        if term and lower_text.find(term) >= 0
    ]

    if not positions:
        return text[:max_chars].rsplit(" ", 1)[0].strip() + "..."

    center = max(positions)
    start = max(0, center - max_chars // 4)
    end = min(len(text), start + max_chars)
    snippet = text[start:end]

    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet.rsplit(" ", 1)[0].strip() + "..."

    return _cut_trailing_heading(snippet)


def _best_snippets(context, question, limit=4, window_size=4):
    terms = _content_tokens(_clean_question(question))
    if not terms:
        return []

    snippets = []
    sentences = _split_sentences(context)
    for index, sentence in enumerate(sentences):
        score = _score_sentence(sentence, terms)
        if score:
            window = " ".join(sentences[index:index + window_size])
            snippets.append((score, window))

    snippets.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    selected = []
    seen = set()

    for _, sentence in snippets:
        sentence = _clean_snippet_text(_trim_around_terms(sentence, terms))
        key = sentence.lower()
        if key in seen:
            continue
        if _is_too_similar(sentence, selected):
            continue
        seen.add(key)
        selected.append(sentence[:700])
        if len(selected) >= limit:
            break

    return selected


def _fill_snippets(context, selected, limit):
    for sentence in _split_sentences(context):
        sentence = _clean_snippet_text(_trim_around_terms(sentence, _content_tokens(sentence), max_chars=520))
        if len(sentence) < 45:
            continue
        if _is_too_similar(sentence, selected):
            continue
        selected.append(sentence[:700])
        if len(selected) >= limit:
            break

    return selected


def _question_for_snippet(snippet):
    snippet_lower = snippet.lower()

    if "why learn" in snippet_lower:
        return "Why should someone learn this topic?"
    if "data structures" in snippet_lower or "data types" in snippet_lower:
        return "Which data structure topics are covered?"
    if "function" in snippet_lower:
        return "Which function concepts are covered?"
    if "job opportunities" in snippet_lower:
        return "What job opportunities are mentioned?"
    if "library" in snippet_lower or "framework" in snippet_lower:
        return "Which libraries or frameworks are mentioned?"
    if "python" in snippet_lower:
        return "What does the document say about Python?"

    return "What important point is mentioned in the document?"


def _extractive_summary(context, max_points=6):
    matches = list(re.finditer(r"\[([^\]]+)\]\s*", context))
    by_source = {}

    if matches:
        for index, match in enumerate(matches):
            source = match.group(1)
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(context)
            chunk = _normalize_space(context[start:end])
            if chunk:
                by_source.setdefault(source, []).append(chunk)
    else:
        by_source = {"Documents": [_normalize_space(context)]}

    points = []
    source_names = list(by_source.keys())
    max_source_chunks = max(len(chunks) for chunks in by_source.values()) if by_source else 0

    for chunk_index in range(max_source_chunks):
        for source in source_names:
            source_chunks = by_source[source]
            if chunk_index >= len(source_chunks):
                continue

            sentences = _split_sentences(source_chunks[chunk_index])
            if not sentences:
                continue

            point = next((sentence for sentence in sentences if len(sentence) >= 40), sentences[0])
            point = _clean_snippet_text(point)
            if len(point) > 260:
                point = point[:260].rsplit(" ", 1)[0].strip() + "..."
            point = f"**{_friendly_source_name(source)}:** {point}"

            if point.lower() not in {existing.lower() for existing in points}:
                points.append(point)

            if len(points) >= max_points:
                break

        if len(points) >= max_points:
            break

    if not points:
        return None

    return "\n".join(f"- {point}" for point in points)


def _extractive_fallback(context, question):
    question = _clean_question(question)
    task = _task_type(question)

    if task == "summary":
        return _extractive_summary(context)

    requested_count = _requested_count(question)
    snippets = _best_snippets(
        context,
        question,
        limit=requested_count if task == "qa" else 4,
        window_size=2 if task == "qa" else 4,
    )
    if task == "qa" and len(snippets) < requested_count:
        snippets = _fill_snippets(context, snippets, requested_count)

    if not snippets:
        return None

    if task == "qa":
        return "\n".join(
            f"{index}. Q: {_question_for_snippet(snippet)}\nA: {snippet}"
            for index, snippet in enumerate(snippets, start=1)
        )

    if task == "notes":
        return "\n".join(f"- {snippet}" for snippet in snippets)

    return "\n".join(f"- {snippet}" for snippet in snippets)


def build_task_note(question):
    task = _task_type(_clean_question(question))

    if task == "summary":
        return (
            "The user wants a summary. Summarize the available excerpts; do not require "
            "an explicit summary section. If multiple documents are present, cover each "
            "document briefly. Return 4 to 8 short bullets."
        )

    if task == "qa":
        return (
            "The user wants important questions and answers from the excerpts. Create "
            "useful study questions only from the provided content. Return numbered Q/A pairs."
        )

    if task == "notes":
        return (
            "The user wants study notes. Prepare simple notes from the provided excerpts "
            "with short headings or bullets. Keep the language easy to revise."
        )

    return (
        "Answer the user's specific question from the excerpts. If exact wording is not "
        "available but relevant details are present, answer from those details."
    )


def clean_answer(answer):
    filler_prefixes = [
        "Sure, here is a summary of the document:",
        "Sure, here's a summary of the document:",
        "Here is a summary of the document:",
        "Here's a summary of the document:",
        "Sure, here is the answer:",
        "Here is the answer:",
    ]

    cleaned = (answer or "").strip()
    if _is_not_found(cleaned):
        return NOT_FOUND

    for prefix in filler_prefixes:
        if cleaned.lower().startswith(prefix.lower()):
            return cleaned[len(prefix):].strip()

    if cleaned.lower().startswith("sure,"):
        return cleaned[5:].strip()

    return cleaned


def build_prompt(context, question, history, source_hint=None):
    source_note = ""
    if source_hint:
        source_note = f"Use only the content from {source_hint}.\n\n"

    context = trim_context(context)
    question = _clean_question(question)
    task_note = build_task_note(question)

    return f"""
You are a PDF knowledge assistant.
IMPORTANT RULES:
1. Use ONLY the document excerpts below. NEVER use outside knowledge.
2. If the question is about a topic NOT covered in the excerpts, reply EXACTLY: {NOT_FOUND}
3. Do NOT try to connect unrelated content to the question. If excerpts are about programming but the question is about cooking, reply: {NOT_FOUND}
4. For definition questions, define a term only if the excerpts actually explain that term.
5. Be strict: if the excerpts don't directly address the question, say {NOT_FOUND}
{task_note}

{source_note}Document excerpts:
{context}

Recent chat, for conversation continuity only:
{history}

Current question:
{question}
"""


def _ollama_payload(prompt, stream=False):
    return {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": stream,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {
            "temperature": 0.15,
            "top_p": 0.9,
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": OLLAMA_NUM_PREDICT,
        },
    }


def _ollama_error_message(exc):
    return (
        "Error contacting Ollama: "
        f"{exc}. The document search worked, but the local model did not answer in time. "
        "Try again, keep Ollama running, or use a smaller Ollama model."
    )


def _context_relevance_check(context, question):
    """Check if the retrieved context has meaningful relevance to the question.
    Returns True if context seems relevant, False otherwise."""
    question_terms = _content_tokens(_clean_question(question))
    if not question_terms:
        return True  # Can't judge, let LLM decide

    context_lower = _normalize_space(_strip_source_labels(context)).lower()

    # Count how many question terms appear in context
    matched = 0
    for term in question_terms:
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", context_lower):
            matched += 1

    # If none of the meaningful question terms appear in context, it's irrelevant
    if matched == 0:
        return False

    # If less than 30% of terms match for multi-term queries, likely irrelevant
    if len(question_terms) >= 3 and matched / len(question_terms) < 0.3:
        return False

    return True


def _pre_llm_guard(context, question):
    topic = _definition_topic(_clean_question(question))
    if topic and not _has_definition_support(context, topic):
        return NOT_FOUND_RESPONSE

    # Relevance guard: if context doesn't relate to the question at all, reject early
    if not _context_relevance_check(context, question):
        return NOT_FOUND_RESPONSE

    return None


def _post_llm_fallback(context, question, answer):
    question = _clean_question(question)
    fallback = _extractive_fallback(context, question)

    if answer and not _is_not_found(answer):
        # Final relevance check: if context isn't relevant to question, override LLM's answer
        if not _context_relevance_check(context, question):
            return NOT_FOUND_RESPONSE

        answer_lower = answer.lower()
        question_lower = question.lower()
        task = _task_type(question)
        prefers_exact_snippets = any(
            phrase in question_lower
            for phrase in ["details", "tell me about", "show me", "list"]
        )
        has_unsafe_filler = any(
            phrase in answer_lower
            for phrase in [
                "cannot provide a response",
                "does not contain this specific detail",
                "please note",
                "may vary",
                "depending on",
                "not provided",
                "not provided in the excerpt",
            ]
        )
        has_unseen_code = "```" in answer and "```" not in context
        is_raw_long_summary = task == "summary" and len(answer) > 1200

        if fallback and (prefers_exact_snippets or has_unsafe_filler or has_unseen_code or is_raw_long_summary):
            return fallback

        return answer

    return fallback or NOT_FOUND_RESPONSE


def ask_llm(context, question, history, source_hint=None):
    if not context.strip():
        return NOT_FOUND_RESPONSE

    direct_answer = _answer_experience_count(context, question)
    if direct_answer:
        return direct_answer

    task = _task_type(question)
    if task in {"summary", "qa", "notes"}:
        return _extractive_fallback(context, question) or NOT_FOUND_RESPONSE

    guarded = _pre_llm_guard(context, question)
    if guarded:
        return guarded

    prompt = build_prompt(context, question, history, source_hint)

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=_ollama_payload(prompt),
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        return _ollama_error_message(exc)

    answer = clean_answer(data.get("response", ""))
    return _post_llm_fallback(context, question, answer)


def stream_llm(context, question, history, source_hint=None):
    if not context.strip():
        yield NOT_FOUND_RESPONSE
        return

    direct_answer = _answer_experience_count(context, question)
    if direct_answer:
        yield direct_answer
        return

    task = _task_type(question)
    if task in {"summary", "qa", "notes"}:
        yield _extractive_fallback(context, question) or NOT_FOUND_RESPONSE
        return

    guarded = _pre_llm_guard(context, question)
    if guarded:
        yield guarded
        return

    prompt = build_prompt(context, question, history, source_hint)
    answer_parts = []

    try:
        with requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=_ollama_payload(prompt, stream=True),
            timeout=OLLAMA_TIMEOUT_SECONDS,
            stream=True,
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                token = data.get("response", "")
                if token:
                    answer_parts.append(token)

                if data.get("done"):
                    break
    except requests.RequestException as exc:
        yield _ollama_error_message(exc)
        return

    answer = clean_answer("".join(answer_parts))
    yield _post_llm_fallback(context, question, answer)
