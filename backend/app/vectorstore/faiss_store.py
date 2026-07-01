import faiss
import numpy as np

class FAISSStore:
    def __init__(self, dimension):
        self.index = faiss.IndexFlatL2(dimension)
        self.documents = []

    def add(self, embeddings, docs):
        self.index.add(np.array(embeddings))
        self.documents.extend(docs)

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
            # fallback to normal search if the source-specific search returns nothing
            return self.search(query_embedding, k=k, source_filter=None)

        return results[:k], distances

