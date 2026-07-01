from embeddings.embedder import Embedder
from vectorstore.faiss_store import FAISSStore
from utils.file_loader import load_pdf
from utils.text_splitter import split_text
from services.llm_service import ask_llm
from memory.chat_memory import ChatMemory


def main():

    memory = ChatMemory()

    # 1 Load PDF
    text = load_pdf("../sample.pdf")
    print("PDF Loaded\n")

    # 2 Split into chunks
    chunks = split_text(text)
    print("Chunks Created:", len(chunks))

    # 3 Embeddings
    embedder = Embedder()
    embeddings = embedder.encode(chunks)

    # 4 Store
    dimension = len(embeddings[0])
    store = FAISSStore(dimension)
    store.add(embeddings, chunks)


    # ---------------- FIRST QUESTION ----------------

    q1 = "What is Python?"

    memory.add_message("User", q1)

    q1_embedding = embedder.encode([q1])

    results1, _ = store.search(q1_embedding, k=3)

    context1 = "\n".join(results1)

    answer1 = ask_llm(
        context1,
        q1,
        memory.get_history()
    )

    print("\nAnswer 1:\n")
    print(answer1)

    memory.add_message("Assistant", answer1)


    # ---------------- SECOND QUESTION ----------------

    q2 = "What frameworks does it have?"

    memory.add_message("User", q2)

    # -------- Query Rewriting (FIX) --------
    full_q2 = q2

    if "it" in q2.lower():
        full_q2 = f"In Python, {q2}"

    q2_embedding = embedder.encode([full_q2])

    results2, _ = store.search(q2_embedding, k=4)

    context2 = "\n".join(results2)

    answer2 = ask_llm(
        context2,
        full_q2,
        memory.get_history()
    )

    print("\nAnswer 2:\n")
    print(answer2)

    memory.add_message("Assistant", answer2)


if __name__ == "__main__":
    main()
