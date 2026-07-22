import json
import os

import faiss
import numpy as np


class FAISSStore:
    def __init__(self, dimension):
        self.index = faiss.IndexFlatL2(dimension)
        self.documents = []

    def add(self, embeddings, docs):
        self.index.add(np.array(embeddings))
        self.documents.extend(docs)

    def save(self, directory):
        """Save FAISS index and documents to disk."""
        os.makedirs(directory, exist_ok=True)
        faiss.write_index(self.index, os.path.join(directory, "index.faiss"))
        with open(os.path.join(directory, "documents.json"), "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False)

    @classmethod
    def load(cls, directory):
        """Load FAISS index and documents from disk. Returns None if files don't exist."""
        index_path = os.path.join(directory, "index.faiss")
        docs_path = os.path.join(directory, "documents.json")

        if not os.path.exists(index_path) or not os.path.exists(docs_path):
            return None

        index = faiss.read_index(index_path)
        with open(docs_path, "r", encoding="utf-8") as f:
            documents = json.load(f)

        store = cls(index.d)
        store.index = index
        store.documents = documents
        return store

    def search(self, query_embedding, k=3, source_filter=None):
        if self.index.ntotal == 0:
            return [], []

        k = min(k, self.index.ntotal)
        distances, indices = self.index.search(
            np.array(query_embedding), k
        )

        results = []
        for i in indices[0]:
            if i < 0:
                continue
            doc = self.documents[i]
            if source_filter:
                if doc.lower().startswith(f"[{source_filter.lower()}]"):
                    results.append(doc)
            else:
                results.append(doc)

        if source_filter and not results:
            expanded_k = min(50, max(k, self.index.ntotal))
            distances, indices = self.index.search(np.array(query_embedding), expanded_k)
            for i in indices[0]:
                if i < 0:
                    continue
                doc = self.documents[i]
                if doc.lower().startswith(f"[{source_filter.lower()}]"):
                    results.append(doc)
                    if len(results) >= k:
                        break

        if source_filter and not results:
            return self.search(query_embedding, k=k, source_filter=None)

        return results[:k], distances

