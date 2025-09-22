from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Dict

from app.server.providers.openai_client import OpenAIClient
from app.server.rag.index_store import IndexStore, IndexedChunk


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def retrieve_top(query: str, store: IndexStore, client: OpenAIClient, top_k: int = 3, max_seq: int | None = None) -> List[Dict[str, str]]:
    """Гибрид: векторный косинус + BM25 (по title+quote) + keyword-boost."""
    if not store.all():
        return []
    q_emb = client.embed([query])[0]
    # Токенизация запроса
    q_tokens = [t for t in re.split(r"[^\wа-яА-ЯёЁ]+", query.lower()) if len(t) > 2]

    # Собираем корпус (учитываем max_seq)
    corpus: List[IndexedChunk] = [it for it in store.all() if (max_seq is None or it.seq <= max_seq)]

    # Токены документов и статистики для BM25
    def tokens_of(it: IndexedChunk) -> List[str]:
        text = f"{it.title or ''} {getattr(it, 'quote', '') or ''}".lower()
        return [t for t in re.split(r"[^\wа-яА-ЯёЁ]+", text) if len(t) > 2]

    doc_tokens = [tokens_of(it) for it in corpus]
    N = max(1, len(doc_tokens))
    df: Dict[str, int] = Counter()
    for toks in doc_tokens:
        for w in set(toks):
            df[w] += 1
    avgdl = (sum(len(toks) for toks in doc_tokens) / N) if N else 1.0
    k1, b = 1.5, 0.75

    def bm25_for_doc(toks: List[str]) -> float:
        if not q_tokens or not toks:
            return 0.0
        tf = Counter(toks)
        dl = len(toks)
        score = 0.0
        for q in set(q_tokens):
            n = df.get(q, 0)
            if n == 0:
                continue
            idf = max(0.0, math.log((N - n + 0.5) / (n + 0.5)))
            f = tf.get(q, 0)
            denom = f + k1 * (1 - b + b * (dl / (avgdl or 1.0)))
            score += idf * ((f * (k1 + 1)) / (denom or 1.0))
        return score

    bm25_scores_raw = [bm25_for_doc(toks) for toks in doc_tokens]
    if bm25_scores_raw:
        bm_min, bm_max = min(bm25_scores_raw), max(bm25_scores_raw)
        rng = (bm_max - bm_min) or 1.0
        bm25_scores = [(s - bm_min) / rng for s in bm25_scores_raw]
    else:
        bm25_scores = [0.0] * len(corpus)

    def kw_score(it: IndexedChunk) -> float:
        hay = f"{it.title or ''} {getattr(it, 'quote', '') or ''}".lower()
        if not q_tokens:
            return 0.0
        hits = sum(1 for t in q_tokens if t in hay)
        return hits / len(q_tokens)

    raw = []
    for idx, it in enumerate(corpus):
        c = _cosine(q_emb, it.embedding)
        k = kw_score(it)
        bm = bm25_scores[idx]
        # Гибридный скор: косинус 0.6, BM25 0.3, keywords 0.1
        score = 0.6 * c + 0.3 * bm + 0.1 * k
        raw.append((it, score, k, c, bm))

    # If query contains strong named tokens (e.g., 'павсаний'), prefer items with kw hits
    strong = any(t in ("павсаний", "паусаний", "эрот", "эроты", "число") for t in q_tokens)

    # Special targeting for Павсаний: require mention of павсан* in title/quote when present in query
    want_pausanias = any("павсан" in t for t in q_tokens)
    if want_pausanias:
        def has_pausanias(it: IndexedChunk) -> bool:
            hay = f"{it.title} {it.quote}".lower()
            return ("павсан" in hay) or ("паусан" in hay)
        # Hard filter; if empty after filter, fall back to kw-based filter
        filtered = [row for row in raw if has_pausanias(row[0])]
        if filtered:
            raw = filtered
        else:
            raw = [row for row in raw if row[2] > 0.0] or raw
        # Title exact boost
        boosted = []
        for it, score, k, c, bm in raw:
            title_l = it.title.lower()
            if "павсан" in title_l:
                score += 0.15
            boosted.append((it, score, k, c, bm))
        raw = boosted
    elif strong:
        raw = [row for row in raw if row[2] > 0.0] or raw

    scored = sorted(raw, key=lambda t: t[1], reverse=True)
    top = scored[: max(1, top_k)]
    results = []
    for it, score, k, c, bm in top:
        results.append({
            "file": it.file,
            "anchor": it.anchor,
            "title": it.title,
            "quote": it.quote,
            "score": float(score),
            "kw_ratio": float(k),
            "cosine": float(c),
            "bm25": float(bm),
        })
    return results
