from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from app.server.utils.paths import ensure_dirs, error_log_path


@dataclass
class ErrorRecord:
    ts: str
    route: str
    message: str
    extra: Optional[Dict[str, Any]] = None


class ErrorLogger:
    """JSONL-логгер ошибок без PII. Пишет в data/coreader/errors/YYYY-MM-DD-HHMM.jsonl"""

    def __init__(self) -> None:
        ensure_dirs()

    def log(self, route: str, err: Exception | str, extra: Optional[Dict[str, Any]] = None) -> None:
        # Без PII: только строка ошибки, маршрут и необязательные безопасные детали
        msg = str(err)
        rec = ErrorRecord(
            ts=datetime.now().isoformat(timespec="seconds"),
            route=route,
            message=msg,
            extra=extra if isinstance(extra, dict) else None,
        )
        path = error_log_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec.__dict__, ensure_ascii=False) + "\n")
