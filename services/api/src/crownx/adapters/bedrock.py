"""Amazon Bedrock embeddings: Titan Text Embeddings V2 (ADR-013). The model ID comes from config."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any


class TitanEmbedder:
    def __init__(
        self, client: Any, model_id: str, dimensions: int = 1024, max_workers: int = 4
    ) -> None:
        self._client = client  # bedrock-runtime; clients are thread-safe
        self._model_id = model_id
        self.dimensions = dimensions
        self._max_workers = max_workers

    def embed(self, texts: list[str], kind: str = "passage") -> list[list[float]]:
        del kind  # Titan V2 embeds queries and passages alike
        if len(texts) <= 1:
            return [self._embed_one(text) for text in texts]
        # Titan V2 takes one text per call; a small pool keeps ingestion inside the Lambda timeout.
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            return list(pool.map(self._embed_one, texts))

    def _embed_one(self, text: str) -> list[float]:
        response = self._client.invoke_model(
            modelId=self._model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"inputText": text, "dimensions": self.dimensions, "normalize": True}),
        )
        with response["body"] as body:
            payload = json.loads(body.read())
        vector = payload["embedding"]
        if len(vector) != self.dimensions:
            raise ValueError(f"expected {self.dimensions} dimensions, got {len(vector)}")
        return vector
