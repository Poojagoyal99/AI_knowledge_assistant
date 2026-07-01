import os
import requests
import numpy as np

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


class Embedder:
    def __init__(self):
        self.model_name = OLLAMA_EMBED_MODEL

    def encode(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        embeddings = []
        for text in texts:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/embed",
                json={"model": self.model_name, "input": text},
            )
            response.raise_for_status()
            data = response.json()
            embeddings.append(data["embeddings"][0])
        return np.array(embeddings)
