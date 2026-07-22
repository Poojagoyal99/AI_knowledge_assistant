import json
import re
import io
from datetime import datetime

from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
import sys
import os
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage

from .auth_views import get_user_from_token
from .models import Conversation, Message

# ---------------- PATH SETUP ----------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(BASE_DIR, "..", "app")
sys.path.append(os.path.abspath(APP_PATH))

from embeddings.embedder import Embedder
from vectorstore.faiss_store import FAISSStore
from utils.file_loader import load_document, SUPPORTED_EXTENSIONS
from utils.text_splitter import split_text
from services.llm_service import ask_llm, stream_llm
from services.global_search_service import global_search
from memory.chat_memory import ChatMemory

# ---------------- INIT ----------------
embedder = Embedder()

UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")

# ---------------- PER-USER STATE ----------------
# Stores per-user: { user_id: { "store": FAISSStore, "pdf_status_map": {}, "memory": ChatMemory } }
user_stores = {}

SEARCH_STOPWORDS = {
    "a", "an", "and", "are", "as", "about", "all", "based", "be", "by",
    "answer", "answers", "details", "document", "documents", "file", "for",
    "from", "how", "important", "in", "is", "it", "key", "list", "main",
    "many", "me", "most", "named", "notes", "of", "on", "or", "pdf",
    "point", "points", "present", "prepare", "question", "questions",
    "resume", "simple", "study", "summarize", "summary", "tell", "the",
    "this", "to", "topic", "what", "which", "with",
}
TERM_ALIASES = {
    "eduction": "education",
    "eductaion": "education",
    "educational": "education",
}


def _tokens(value):
    return re.findall(r"[a-z0-9+#.]+", value.lower())


def _content_tokens(value):
    return [
        TERM_ALIASES.get(token, token)
        for token in _tokens(value)
        if len(token) > 1 and token not in SEARCH_STOPWORDS
    ]


def _pdf_names(upload_folder):
    if not os.path.exists(upload_folder):
        return []
    return [f for f in os.listdir(upload_folder)
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS]


def _match_pdf_source(user_query, pdf_list):
    user_lower = user_query.lower()
    user_compact = " ".join(_tokens(user_query))
    user_tokens = set(_tokens(user_query))
    best_match = None
    best_score = 0

    for pdf_name in pdf_list:
        candidate = pdf_name.lower()
        stem = os.path.splitext(candidate)[0]
        stem_tokens = [token for token in _tokens(stem) if token not in {"pdf"}]
        stem_compact = " ".join(stem_tokens)

        if candidate in user_lower or stem in user_lower or stem_compact in user_compact:
            return pdf_name

        matched_tokens = set(stem_tokens) & user_tokens
        if not matched_tokens:
            continue

        score = len(matched_tokens) * 10
        score += sum(2 for token in matched_tokens if token not in {"sample", "document", "resume", "file"})

        if len(matched_tokens) >= 2:
            score += 10
        elif user_tokens & {"pdf", "document", "file"}:
            score += 5

        if score > best_score:
            best_score = score
            best_match = pdf_name

    return best_match if best_score >= 12 else None


def _sources_from_results(results):
    sources = set()
    for chunk in results:
        if chunk.startswith("[") and "]" in chunk:
            sources.add(chunk.split("]", 1)[0][1:])
    return sorted(sources)


def _lexical_score(query, chunk):
    query_terms = _content_tokens(query)
    if not query_terms:
        return 0

    chunk_lower = chunk.lower()
    score = 0

    for term in query_terms:
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", chunk_lower):
            score += 4
        elif term in chunk_lower:
            score += 1

    return score


def _rerank_results(query, results, limit):
    ranked = sorted(
        enumerate(results),
        key=lambda item: (_lexical_score(query, item[1]), -item[0]),
        reverse=True,
    )
    return [chunk for _, chunk in ranked[:limit]]


def _is_summary_query(query):
    query_lower = query.lower()
    return any(
        term in query_lower
        for term in [
            "summarize",
            "summary",
            "overview",
            "important point",
            "important points",
            "key point",
            "key points",
            "main point",
            "main points",
            "most important",
        ]
    )


def _is_broad_generation_query(query):
    query_lower = query.lower()
    return any(
        term in query_lower
        for term in [
            "summarize",
            "summary",
            "overview",
            "important point",
            "important points",
            "key point",
            "key points",
            "main point",
            "main points",
            "most important",
            "important question",
            "important q",
            "imp qs",
            "interview",
            "frame",
            "generate question",
            "make question",
            "questions from",
            "q&a",
            "question answer",
            "prepare notes",
            "simple notes",
            "study notes",
        ]
    )


def _chunks_for_source(store, source_filter=None):
    if not store:
        return []

    if not source_filter:
        return list(store.documents)

    source_prefix = f"[{source_filter.lower()}]"
    return [
        doc for doc in store.documents
        if doc.lower().startswith(source_prefix)
    ]


def _chunk_source(chunk):
    if chunk.startswith("[") and "]" in chunk:
        return chunk.split("]", 1)[0][1:]
    return "Documents"


def _sample_evenly(chunks, limit):
    if len(chunks) <= limit:
        return chunks

    if limit <= 1:
        return chunks[:1]

    step = (len(chunks) - 1) / (limit - 1)
    sampled = []
    used = set()

    for index in range(limit):
        chunk_index = round(index * step)
        if chunk_index in used:
            continue
        used.add(chunk_index)
        sampled.append(chunks[chunk_index])

    return sampled


def _representative_chunks(store, source_filter=None, limit=20):
    chunks = _chunks_for_source(store, source_filter)
    if len(chunks) <= limit:
        return chunks

    by_source = {}
    for chunk in chunks:
        by_source.setdefault(_chunk_source(chunk), []).append(chunk)

    per_source_limit = max(1, limit // max(1, len(by_source)))
    sampled = []
    for source_chunks in by_source.values():
        sampled.extend(_sample_evenly(source_chunks, per_source_limit))

    if len(sampled) < limit:
        remaining = [chunk for chunk in chunks if chunk not in sampled]
        sampled.extend(_sample_evenly(remaining, limit - len(sampled)))

    return sampled[:limit]


def _sse(payload):
    return f"data: {json.dumps(payload)}\n\n"


def _answer_sources(answer, sources):
    if answer.lower().startswith("not found"):
        return []
    return sources


def _prepare_chat(query, user):
    if not query:
        return {"error": "No query provided", "status": 400}

    user_data = _get_user_data(user)
    store = user_data["store"]
    upload_folder = _user_upload_folder(user)

    if not store:
        build_store_for_user(user)
        user_data = _get_user_data(user)
        store = user_data["store"]

    if not store:
        return {
            "ready": False,
            "answer": "No documents uploaded. Not found in uploaded PDFs. Do you want me to search globally outside the PDFs?",
            "sources": []
        }

    pdf_names = _pdf_names(upload_folder)
    source_filter = _match_pdf_source(query, pdf_names)
    full_query = query

    if source_filter:
        full_query = f"Use only content from the document named {source_filter} when answering. {query}"

    top_k = int(os.getenv("RAG_TOP_K", "6"))
    candidate_k = int(os.getenv("RAG_CANDIDATE_K", "20"))

    query_terms = _content_tokens(query)
    broad_generation = _is_broad_generation_query(query)

    if _is_summary_query(query) or (broad_generation and (source_filter or not query_terms)):
        summary_k = int(os.getenv("RAG_SUMMARY_K", "20"))
        results = _representative_chunks(store, source_filter, summary_k)
    else:
        query_embedding = embedder.encode([query])
        results, _ = store.search(query_embedding, k=max(top_k, candidate_k), source_filter=source_filter)
        results = _rerank_results(query, results, top_k)
        if not source_filter and not broad_generation and results:
            best_lexical_score = max(_lexical_score(query, result) for result in results)
            # A score of 0 means no term appeared at all.
            # A very low score (< 4) means the term appeared only as a
            # passing mention (e.g. "C++" in a skills list) rather than the
            # chunk actually being *about* that topic — treat as irrelevant.
            min_relevance = 4 if len(query_terms) <= 2 else 2
            if query_terms and best_lexical_score < min_relevance:
                results = []

            # Even with a lexical match, check if the topic is substantively
            # discussed vs merely listed.  For short queries (1-2 terms),
            # require the term to appear multiple times across the top results
            # or to have surrounding explanatory context.
            if results and len(query_terms) <= 2:
                combined = " ".join(results).lower()
                term_pattern = re.escape(query_terms[0])
                occurrences = len(re.findall(rf"(?<![a-z0-9]){term_pattern}(?![a-z0-9])", combined))
                # If the term appears only 1-2 times in all top chunks,
                # it's likely just listed (e.g. in a skills section) not discussed.
                if occurrences <= 2:
                    # Check if any chunk has >80 chars within 200 chars of the term mention
                    has_substance = False
                    for result in results:
                        for match in re.finditer(rf"(?<![a-z0-9]){term_pattern}(?![a-z0-9])", result.lower()):
                            surrounding = result[max(0, match.start() - 100):match.end() + 100]
                            # If surrounding text is long enough it's likely explained
                            if len(surrounding.split()) > 20:
                                has_substance = True
                                break
                        if has_substance:
                            break
                    if not has_substance:
                        results = []

    return {
        "ready": True,
        "query": query,
        "full_query": full_query,
        "source_filter": source_filter,
        "context": "\n".join(results),
        "sources": _sources_from_results(results)
    }


def _user_upload_folder(user):
    """Get upload folder path for a specific user."""
    folder = os.path.join(UPLOAD_ROOT, str(user.id))
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder


def _user_faiss_folder(user):
    """Get FAISS index folder path for a specific user."""
    return os.path.join(UPLOAD_ROOT, str(user.id), ".faiss_index")


def _get_user_data(user):
    """Get or initialize per-user store data. Tries to load from disk first."""
    uid = user.id
    if uid not in user_stores:
        user_stores[uid] = {
            "store": None,
            "pdf_status_map": {},
            "memory": ChatMemory(max_pairs=2),
        }
        # Try loading persisted FAISS index from disk
        faiss_folder = _user_faiss_folder(user)
        loaded_store = FAISSStore.load(faiss_folder)
        if loaded_store and loaded_store.index.ntotal > 0:
            user_stores[uid]["store"] = loaded_store
            print(f"User {user.username}: Loaded FAISS index from disk ({loaded_store.index.ntotal} vectors).")
    return user_stores[uid]


def build_store_for_user(user):
    global user_stores
    user_data = _get_user_data(user)
    user_data["pdf_status_map"] = {}
    upload_folder = _user_upload_folder(user)

    all_chunks = []
    doc_files = []

    for file in os.listdir(upload_folder):
        ext = os.path.splitext(file)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            doc_files.append(file)
            file_path = os.path.join(upload_folder, file)
            file_info = {"has_text": False, "chunks": 0, "error": None}

            try:
                text = load_document(file_path)
                if not text.strip():
                    file_info["error"] = "No extractable text"
                    user_data["pdf_status_map"][file] = file_info
                    print(f"No extractable text found in {file}. Skipping.")
                    continue

                chunks = split_text(text)
                if not chunks:
                    file_info["error"] = "No chunks created"
                    user_data["pdf_status_map"][file] = file_info
                    print(f"No chunks created for {file}. Skipping.")
                    continue

                chunks = [f"[{file}] {chunk}" for chunk in chunks]
                all_chunks.extend(chunks)
                file_info["has_text"] = True
                file_info["chunks"] = len(chunks)
                user_data["pdf_status_map"][file] = file_info
            except Exception as e:
                file_info["error"] = str(e)
                user_data["pdf_status_map"][file] = file_info
                print(f"Error loading {file}: {e}")

    if all_chunks:
        embeddings = embedder.encode(all_chunks)
        dimension = len(embeddings[0])
        user_data["store"] = FAISSStore(dimension)
        user_data["store"].add(embeddings, all_chunks)
        # Persist to disk
        user_data["store"].save(_user_faiss_folder(user))
        print(f"User {user.username}: Built & saved {len(doc_files)} document(s) with {len(all_chunks)} chunks.")
    else:
        user_data["store"] = None
        # Remove old index if no documents left
        faiss_folder = _user_faiss_folder(user)
        if os.path.exists(faiss_folder):
            import shutil
            shutil.rmtree(faiss_folder, ignore_errors=True)
        print(f"User {user.username}: No documents found to build the store.")


# ---------------- AUTH HELPER ----------------
def _require_auth(request):
    """Return user or None. If None, caller should return the error response."""
    user = get_user_from_token(request)
    return user


# ---------------- FILE UPLOAD ----------------
MAX_FILE_SIZE_MB = 10
MAX_FILE_COUNT = 10
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt"}

@csrf_exempt
def upload_pdf(request):
    user = _require_auth(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    if request.method == "POST" and request.FILES.get("file"):
        upload_folder = _user_upload_folder(user)

        file = request.FILES["file"]
        ext = os.path.splitext(file.name)[1].lower()

        # Check allowed file type
        if ext not in ALLOWED_EXTENSIONS:
            return JsonResponse(
                {"error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"},
                status=400
            )

        # Check file count limit
        existing_count = 0
        if os.path.exists(upload_folder):
            existing_count = len([f for f in os.listdir(upload_folder)
                                  if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS])
        if existing_count >= MAX_FILE_COUNT:
            return JsonResponse(
                {"error": f"Upload limit reached. Maximum {MAX_FILE_COUNT} documents allowed per user."},
                status=400
            )

        # Check file size limit
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            return JsonResponse(
                {"error": f"File too large. Maximum size is {MAX_FILE_SIZE_MB} MB."},
                status=400
            )

        print(f"Uploading file: {file.name} for user: {user.username}")

        fs = FileSystemStorage(location=upload_folder)
        filename = fs.save(file.name, file)
        print(f"File saved as: {filename}")

        # Rebuild the vector store so uploaded documents are immediately available.
        build_store_for_user(user)

        return JsonResponse({
            "message": "File uploaded successfully",
            "filename": filename
        })

    return JsonResponse({"error": "No file uploaded"})


# ---------------- LIST UPLOADED DOCUMENTS ----------------
@csrf_exempt
def list_pdfs(request):
    user = _require_auth(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    upload_folder = _user_upload_folder(user)
    user_data = _get_user_data(user)
    pdf_status_map = user_data["pdf_status_map"]

    if not os.path.exists(upload_folder):
        return JsonResponse({"files": []})

    doc_files = []
    for f in os.listdir(upload_folder):
        ext = os.path.splitext(f)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            status = pdf_status_map.get(f, {})
            doc_files.append({
                "name": f,
                "has_text": status.get("has_text", False),
                "error": status.get("error")
            })

    return JsonResponse({"files": doc_files})


# ---------------- CHAT ----------------
def _get_or_create_conversation(user, request):
    """Get conversation from query param or create a new one."""
    conversation_id = request.GET.get("conversation_id")
    if conversation_id:
        try:
            return Conversation.objects.get(id=int(conversation_id), user=user)
        except (Conversation.DoesNotExist, ValueError):
            pass
    return None


def _save_message(conversation, role, text, sources=None):
    """Save a message to the conversation."""
    if conversation:
        Message.objects.create(
            conversation=conversation,
            role=role,
            text=text,
            sources=sources or []
        )
        # Auto-title: use first user message as title if still default
        if role == "user" and conversation.title == "New Chat":
            conversation.title = text[:100]
            conversation.save()


def chat_view(request):
    user = _require_auth(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    query = request.GET.get("query")
    conversation = _get_or_create_conversation(user, request)
    prepared = _prepare_chat(query, user)

    if prepared.get("error"):
        return JsonResponse({"error": prepared["error"]}, status=prepared.get("status", 400))

    if not prepared.get("ready"):
        return JsonResponse({
            "answer": prepared["answer"],
            "sources": prepared["sources"]
        })

    user_data = _get_user_data(user)
    memory = user_data["memory"]
    memory.add_message("User", query)

    answer = ask_llm(
        prepared["context"],
        prepared["full_query"],
        memory.get_history(),
        source_hint=prepared["source_filter"]
    )

    memory.add_message("Assistant", answer)

    # 🔥 Extract unique filenames
    sources = _answer_sources(answer, prepared["sources"])

    # Save to conversation
    _save_message(conversation, "user", query)
    _save_message(conversation, "bot", answer, sources)

    return JsonResponse({
        "answer": answer,
        "sources": sources
    })


def chat_stream_view(request):
    user = _require_auth(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    query = request.GET.get("query")
    conversation = _get_or_create_conversation(user, request)
    prepared = _prepare_chat(query, user)

    if prepared.get("error"):
        return JsonResponse({"error": prepared["error"]}, status=prepared.get("status", 400))

    def event_stream():
        if not prepared.get("ready"):
            yield _sse({
                "type": "sources",
                "sources": prepared.get("sources", [])
            })
            yield _sse({
                "type": "final",
                "answer": prepared["answer"],
                "sources": prepared["sources"]
            })
            return

        user_data = _get_user_data(user)
        memory = user_data["memory"]
        memory.add_message("User", query)
        answer_parts = []

        for token in stream_llm(
            prepared["context"],
            prepared["full_query"],
            memory.get_history(),
            source_hint=prepared["source_filter"]
        ):
            answer_parts.append(token)
            yield _sse({
                "type": "token",
                "token": token
            })

        answer = "".join(answer_parts).strip() or "Not found in document"
        memory.add_message("Assistant", answer)
        final_sources = _answer_sources(answer, prepared["sources"])

        # Save to conversation
        _save_message(conversation, "user", query)
        _save_message(conversation, "bot", answer, final_sources)

        yield _sse({
            "type": "sources",
            "sources": final_sources
        })
        yield _sse({
            "type": "final",
            "answer": answer,
            "sources": final_sources
        })

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def global_search_view(request):
    query = request.GET.get("query", "")
    conversation_id = request.GET.get("conversation_id")

    user = _require_auth(request)
    result = global_search(query)

    # Save the global search result to the conversation if provided
    if user and conversation_id and result.get("answer"):
        try:
            conversation = Conversation.objects.get(id=int(conversation_id), user=user)
            _save_message(conversation, "bot", result["answer"], result.get("sources", []))
        except (Conversation.DoesNotExist, ValueError, TypeError):
            pass

    return JsonResponse(result)


# ---------------- DELETE UPLOADED PDF ----------------
@csrf_exempt
def delete_pdf(request):
    user = _require_auth(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    filename = request.GET.get("filename")

    if not filename:
        return JsonResponse({"error": "No filename provided"}, status=400)

    safe_filename = os.path.basename(filename)
    upload_folder = _user_upload_folder(user)
    file_path = os.path.join(upload_folder, safe_filename)

    if not os.path.exists(file_path):
        return JsonResponse({"error": "File not found"}, status=404)

    try:
        os.remove(file_path)
        print(f"Deleted PDF: {safe_filename}")
        build_store_for_user(user)
        return JsonResponse({"message": "File deleted successfully", "filename": safe_filename})
    except Exception as e:
        print(f"Error deleting {safe_filename}: {e}")
        return JsonResponse({"error": str(e)}, status=500)


# ---------------- EXPORT CHAT AS PDF ----------------
@csrf_exempt
def export_chat_pdf(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        messages = body.get("messages", [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    if not messages:
        return JsonResponse({"error": "No messages to export"}, status=400)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ChatTitle",
        parent=styles["Title"],
        fontSize=18,
        spaceAfter=12,
    )
    user_style = ParagraphStyle(
        "UserMsg",
        parent=styles["Normal"],
        fontSize=11,
        leftIndent=0,
        textColor=HexColor("#1a1a1a"),
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    bot_style = ParagraphStyle(
        "BotMsg",
        parent=styles["Normal"],
        fontSize=11,
        leftIndent=12,
        textColor=HexColor("#333333"),
        spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=HexColor("#888888"),
        spaceAfter=16,
    )

    story = []
    story.append(Paragraph("InsightDocs — Chat Export", title_style))
    story.append(Paragraph(f"Exported on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", meta_style))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#dddddd")))
    story.append(Spacer(1, 12))

    for msg in messages:
        role = msg.get("role", "user")
        text = msg.get("text", "").strip()
        if not text:
            continue

        # Escape XML-special characters for reportlab
        safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_text = safe_text.replace("\n", "<br/>")

        if role == "user":
            story.append(Paragraph(f"You: {safe_text}", user_style))
        else:
            story.append(Paragraph(f"Assistant: {safe_text}", bot_style))

        sources = msg.get("sources", [])
        if sources:
            src_text = ", ".join(sources)
            story.append(Paragraph(f"Sources: {src_text}", meta_style))

        story.append(Spacer(1, 6))

    doc.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="chat-export.pdf"'
    return response


# ---------------- CONVERSATIONS ----------------
@csrf_exempt
def list_conversations(request):
    user = _require_auth(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    conversations = Conversation.objects.filter(user=user).values(
        "id", "title", "created_at", "updated_at"
    )
    return JsonResponse({
        "conversations": [
            {
                "id": c["id"],
                "title": c["title"],
                "created_at": c["created_at"].isoformat(),
                "updated_at": c["updated_at"].isoformat(),
            }
            for c in conversations
        ]
    })


@csrf_exempt
def create_conversation(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    user = _require_auth(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    title = body.get("title", "New Chat").strip()[:200]
    conversation = Conversation.objects.create(user=user, title=title)

    return JsonResponse({
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }, status=201)


@csrf_exempt
def get_conversation_messages(request, conversation_id):
    user = _require_auth(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        conversation = Conversation.objects.get(id=conversation_id, user=user)
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found"}, status=404)

    messages = conversation.messages.values("id", "role", "text", "sources", "highlights", "created_at")
    return JsonResponse({
        "conversation_id": conversation.id,
        "title": conversation.title,
        "messages": [
            {
                "id": m["id"],
                "role": m["role"],
                "text": m["text"],
                "sources": m["sources"],
                "highlights": m["highlights"] or [],
                "created_at": m["created_at"].isoformat(),
            }
            for m in messages
        ]
    })


@csrf_exempt
def rename_conversation(request, conversation_id):
    if request.method != "PUT":
        return JsonResponse({"error": "PUT required"}, status=405)

    user = _require_auth(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        conversation = Conversation.objects.get(id=conversation_id, user=user)
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found"}, status=404)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    title = body.get("title", "").strip()[:200]
    if not title:
        return JsonResponse({"error": "Title is required"}, status=400)

    conversation.title = title
    conversation.save()

    return JsonResponse({"id": conversation.id, "title": conversation.title})


@csrf_exempt
def delete_conversation(request, conversation_id):
    if request.method != "DELETE":
        return JsonResponse({"error": "DELETE required"}, status=405)

    user = _require_auth(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        conversation = Conversation.objects.get(id=conversation_id, user=user)
    except Conversation.DoesNotExist:
        return JsonResponse({"error": "Conversation not found"}, status=404)

    conversation.delete()
    return JsonResponse({"message": "Conversation deleted"})


# ---------------- HIGHLIGHTS ----------------
@csrf_exempt
def update_highlights(request, message_id):
    """Update highlights for a specific message."""
    if request.method != "PUT":
        return JsonResponse({"error": "PUT required"}, status=405)

    user = _require_auth(request)
    if not user:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        message = Message.objects.select_related("conversation").get(
            id=message_id, conversation__user=user
        )
    except Message.DoesNotExist:
        return JsonResponse({"error": "Message not found"}, status=404)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    highlights = body.get("highlights", [])
    # Validate: each highlight must have "text" string
    validated = []
    for h in highlights:
        if isinstance(h, dict) and isinstance(h.get("text"), str) and h["text"].strip():
            validated.append({
                "text": h["text"],
                "color": h.get("color", "yellow"),
            })

    message.highlights = validated
    message.save(update_fields=["highlights"])

    return JsonResponse({"highlights": message.highlights})
