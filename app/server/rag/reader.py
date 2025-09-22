from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import hashlib


@dataclass
class Chunk:
    file: str
    title: str
    text: str
    anchor: str
    seq: int


def _hash_anchor(text: str) -> str:
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:10]


def parse_markdown_file(path: Path) -> List[Chunk]:
    """Very lightweight Markdown splitter: captures last seen heading as title
    and splits by blank lines into paragraph chunks.
    """
    chunks: List[Chunk] = []
    title = ""
    buf: List[str] = []
    seq = 0

    def flush_buf():
        nonlocal buf, title, seq
        if not buf:
            return
        text = "\n".join(buf).strip()
        if text:
            chunks.append(
                Chunk(
                    file=str(path),
                    title=title,
                    text=text,
                    anchor=_hash_anchor(text),
                    seq=seq,
                )
            )
            seq += 1
        buf = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            # new heading
            flush_buf()
            title = line.lstrip("# ").strip()
            continue
        if not line.strip():
            flush_buf()
        else:
            buf.append(line)

    flush_buf()
    return chunks


def parse_markdown_dir(directory: Path) -> List[Chunk]:
    all_chunks: List[Chunk] = []
    for p in sorted(directory.glob("**/*.md")):
        all_chunks.extend(parse_markdown_file(p))
    return all_chunks
