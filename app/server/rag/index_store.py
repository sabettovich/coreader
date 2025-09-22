from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.server.rag.reader import Chunk
from app.server.utils.paths import DATA_ROOT

INDEX_PATH = DATA_ROOT / "index.json"


@dataclass
class IndexedChunk:
    file: str
    title: str
    anchor: str
    seq: int
    embedding: List[float]
    quote: str


class IndexStore:
    def __init__(self, path: Path = INDEX_PATH) -> None:
        self.path = path
        self.items: List[IndexedChunk] = []

    def load(self) -> None:
        if not self.path.exists():
            self.items = []
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        fixed = []
        for row in data:
            if "quote" not in row:
                row["quote"] = ""
            fixed.append(row)
        self.items = [IndexedChunk(**row) for row in fixed]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(i) for i in self.items]
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def rebuild(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        assert len(chunks) == len(embeddings)
        def make_quote(text: str, max_len: int = 200) -> str:
            t = " ".join(text.strip().split())
            return t if len(t) <= max_len else t[: max_len - 1] + "…"

        self.items = [
            IndexedChunk(
                file=c.file,
                title=c.title,
                anchor=c.anchor,
                seq=c.seq,
                embedding=emb,
                quote=make_quote(c.text),
            )
            for c, emb in zip(chunks, embeddings)
        ]
        self.save()

    def all(self) -> List[IndexedChunk]:
        return self.items
