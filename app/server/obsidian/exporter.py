from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.server.utils.paths import DEFAULT_OBSIDIAN_SUBDIR


@dataclass
class BookMeta:
    key: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    tags: Optional[List[str]] = None


def validate_vault(vault_path: str | Path) -> Path:
    p = Path(vault_path).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise ValueError(f"Obsidian vault path is invalid: {p}")
    return p


def _slugify(text: str) -> str:
    import re
    t = text.lower().strip()
    t = re.sub(r"[^a-z0-9а-яё\-\s_]", "", t)
    t = re.sub(r"\s+", "-", t)
    t = re.sub(r"-+", "-", t)
    return t.strip("-") or "note"


def _yaml_escape(s: str) -> str:
    s = s.replace('"', '\\"')
    return s


def build_note_content(
    title: str,
    reply: str,
    citations: List[Dict[str, Any]],
    book: Optional[BookMeta] = None,
) -> str:
    created = datetime.now().strftime("%Y-%m-%d %H:%M")
    authors = ", ".join(book.authors) if book and book.authors else None
    tags = book.tags if book and book.tags else []

    # YAML front matter
    yaml_lines = ["---"]
    yaml_lines.append(f"title: \"{_yaml_escape(title)}\"")
    yaml_lines.append(f"created: \"{created}\"")
    if book:
        yaml_lines.append("book:")
        if book.key:
            # Ссылка на элемент Zotero в виде протокола
            yaml_lines.append(f"  source: \"zotero://select/library/items/{_yaml_escape(book.key)}\"")
        if book.title:
            yaml_lines.append(f"  title: \"{_yaml_escape(book.title)}\"")
        if authors:
            yaml_lines.append(f"  authors: \"{_yaml_escape(authors)}\"")
        if book.year:
            yaml_lines.append(f"  year: {book.year}")
        if tags:
            yaml_lines.append(f"  tags: [{', '.join(tags)}]")
    yaml_lines.append("---\n")

    # Body
    body = ["# Мысль\n", reply.strip(), "\n\n", "## Цитаты\n"]
    for i, c in enumerate(citations, 1):
        file = c.get("file", "")
        anchor = c.get("anchor", "")
        short = Path(file).name
        quote = (c.get("quote") or "").strip()
        title_line = c.get("title") or short
        link = f"/book?file={file}#{anchor}" if file and anchor else ""
        if link:
            body.append(f"- [{title_line} · #{anchor}]({link})\n")
        else:
            body.append(f"- {title_line} · #{anchor}\n")
        if quote:
            body.append(f"  > {quote}\n")
    return "\n".join(yaml_lines + body)


def export_note(
    vault_path: str | Path,
    reply: str,
    citations: List[Dict[str, Any]],
    title: Optional[str] = None,
    book_meta: Optional[Dict[str, Any]] = None,
    subdir: Optional[str] = None,
) -> Path:
    vp = validate_vault(vault_path)
    note_title = title or f"coreader-note"
    slug = _slugify(note_title)
    date_prefix = datetime.now().strftime("%Y%m%d-%H%M")
    folder = vp / (subdir or DEFAULT_OBSIDIAN_SUBDIR) / slug
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{date_prefix}-{slug}.md"

    bm = None
    if book_meta:
        bm = BookMeta(
            key=book_meta.get("zotero_key") or book_meta.get("key"),
            title=book_meta.get("title"),
            authors=book_meta.get("authors"),
            year=book_meta.get("year"),
            tags=book_meta.get("tags"),
        )

    content = build_note_content(note_title, reply, citations, book=bm)
    path.write_text(content, encoding="utf-8")
    return path
