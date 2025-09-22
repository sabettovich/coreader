from __future__ import annotations

import os
from typing import List

import httpx
import hashlib
import math


OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1")
FAKE_EMBEDDINGS = os.getenv("FAKE_EMBEDDINGS", "false").lower() == "true"


class OpenAIClient:
    def __init__(self, api_key: str | None, offline: bool = False) -> None:
        self.api_key = api_key
        self.offline = offline

    def _headers(self) -> dict:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def embed(self, texts: List[str]) -> List[List[float]]:
        if FAKE_EMBEDDINGS:
            return [self._fake_vector(t) for t in texts]
        if self.offline:
            raise RuntimeError("Offline mode: embeddings unavailable")
        payload = {"model": OPENAI_EMBEDDING_MODEL, "input": texts}
        with httpx.Client(timeout=60) as client:
            r = client.post(f"{OPENAI_API_URL}/embeddings", headers=self._headers(), json=payload)
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"OpenAI embeddings HTTP {e.response.status_code}: {e.response.text}") from e
            data = r.json()
            return [item["embedding"] for item in data["data"]]

    def chat(self, prompt: str, max_tokens: int = 300) -> str:
        if self.offline:
            raise RuntimeError("Offline mode: generation unavailable")
        # Use Chat Completions
        payload = {
            "model": OPENAI_CHAT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        with httpx.Client(timeout=60) as client:
            r = client.post(f"{OPENAI_API_URL}/chat/completions", headers=self._headers(), json=payload)
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"OpenAI chat HTTP {e.response.status_code}: {e.response.text}") from e
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _fake_vector(text: str, dim: int = 64) -> List[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # expand hash to dim floats deterministically
        vals = []
        while len(vals) < dim:
            h = hashlib.sha256(h).digest()
            vals.extend(h)
        vals = vals[:dim]
        # normalize to [0,1]
        vec = [v / 255.0 for v in vals]
        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
