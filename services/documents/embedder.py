import httpx
import numpy as np

from config import settings


class Embedder:
    def __init__(self):
        self.model_name = settings.OLLAMA_EMBED_MODEL
        self.base_url = settings.OLLAMA_BASE_URL

    def encode(self, texts: list[str]) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]
        embeddings = []
        for text in texts:
            response = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model_name, "input": text},
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            embeddings.append(data["embeddings"][0])
        return np.array(embeddings)


embedder = Embedder()
