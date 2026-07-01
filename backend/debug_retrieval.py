import os
import sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, 'app'))
from server.chat.views import build_store, store, UPLOAD_FOLDER
from embeddings.embedder import Embedder
from vectorstore.faiss_store import FAISSStore
from utils.file_loader import load_pdf
from utils.text_splitter import split_text
from services.llm_service import ask_llm

# rebuild store for current files
build_store()

query = 'frame 3 qs based on this Pooja_Goyal_Resume.pdf'
print('QUERY:', query)

pdf_names = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith('.pdf')]
print('PDFS:', pdf_names)
full_query = query
for pdf_name in pdf_names:
    if pdf_name.lower() in query.lower():
        full_query = f'Focus on the document named {pdf_name}. {query}'
        break
print('FULL_QUERY:', full_query)
emb = Embedder().encode([full_query])
results, dists = store.search(emb, k=4, source_filter='Pooja_Goyal_Resume.pdf')
print('RESULTS COUNT:', len(results))
for i, r in enumerate(results, 1):
    print('--- RESULT', i)
    print(r[:500])
    print()
print('SOURCES:', set([chunk.split(']')[0][1:] for chunk in results]))
context = '\n'.join(results)
print('CONTEXT LENGTH:', len(context))
print('ASKING MODEL...')
# comment out actual ask_llm to avoid dependency, just print prompt
prompt = f"""
You are a helpful assistant.

Answer using only the provided document context and chat history. Do not add information that is not in the context.

Document chunks are marked with filenames in square brackets at the start of each chunk, like [filename.pdf].

If the answer exists in the context:
→ answer directly and mention the relevant details.
If the answer does not exist in the context:
→ say \"Not found in document\".

Chat History:

Context:
{context}

Question:
{query}
"""
print(prompt[:2000])
