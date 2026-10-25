from __future__ import annotations

import json
import urllib.request

import numpy as np

from gerald import USER_AGENT

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class OpenAIEmbedder:
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        timeout: float = 30,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        request = urllib.request.Request(
            OPENAI_EMBEDDINGS_URL,
            data=json.dumps({"model": self.model, "input": texts}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read())
        except Exception as error:
            raise RuntimeError(
                f"Embedding request failed ({type(error).__name__})"
            ) from None
        data = result.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise RuntimeError("Embedding response did not contain all requested vectors")
        ordered = sorted(data, key=lambda item: item.get("index", 0))
        return np.asarray([item["embedding"] for item in ordered], dtype=np.float32)
