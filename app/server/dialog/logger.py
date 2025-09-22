from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any

from app.server.utils.paths import dialog_log_path, ensure_dirs


@dataclass
class Citation:
    file: str
    anchor: str


@dataclass
class LogRecord:
    ts: str
    role: str
    text: str
    citations: List[Dict[str, str]] = field(default_factory=list)


class DialogLogger:
    def __init__(self) -> None:
        ensure_dirs()

    def log(self, role: str, text: str, citations: List[Citation] | List[Dict[str, str]] | None = None) -> None:
        record = LogRecord(
            ts=datetime.now().isoformat(timespec="seconds"),
            role=role,
            text=text,
            citations=[c if isinstance(c, dict) else {"file": c.file, "anchor": c.anchor} for c in (citations or [])],
        )
        path = dialog_log_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.__dict__, ensure_ascii=False) + "\n")
