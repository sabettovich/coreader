from __future__ import annotations

from pathlib import Path
from typing import List

from app.server.rag.reader import parse_markdown_dir, Chunk
from app.server.rag.index_store import IndexStore
from app.server.providers.openai_client import OpenAIClient
from app.server.utils.paths import BOOK_DIR, CONTEXT_DIR


def collect_chunks(book_dir: Path = BOOK_DIR, context_dir: Path = CONTEXT_DIR) -> List[Chunk]:
    chunks: List[Chunk] = []
    if book_dir.exists():
        chunks.extend(parse_markdown_dir(book_dir))
    if context_dir.exists():
        chunks.extend(parse_markdown_dir(context_dir))
    return chunks


def rebuild_index(client: OpenAIClient, store: IndexStore | None = None) -> IndexStore:
    store = store or IndexStore()
    chunks = collect_chunks()
    if not chunks:
        store.items = []
        store.save()
        return store
    # Limit per-input size to avoid model context overflow
    def limit_text(t: str, max_chars: int = 1500) -> str:
        if len(t) <= max_chars:
            return t
        # keep beginning; simple truncation is fine for embeddings
        return t[:max_chars]

    texts = [limit_text(c.text) for c in chunks]
    embeddings = client.embed(texts)
    store.rebuild(chunks, embeddings)
    return store


def load_index(store: IndexStore | None = None) -> IndexStore:
    store = store or IndexStore()
    store.load()
    return store
