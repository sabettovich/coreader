from __future__ import annotations

import os
from pathlib import Path

# Base project directory (this file is in app/server/utils)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Data directories
DATA_ROOT = PROJECT_ROOT / "data" / "coreader"
BOOK_DIR = DATA_ROOT / "book"
CONTEXT_DIR = DATA_ROOT / "context"
DIALOG_DIR = DATA_ROOT / "dialog"
ERROR_DIR = DATA_ROOT / "errors"

# Obsidian defaults (can be overridden by env)
DEFAULT_OBSIDIAN_SUBDIR = "lit"


def ensure_dirs() -> None:
    """Ensure required data directories exist."""
    for p in (BOOK_DIR, CONTEXT_DIR, DIALOG_DIR, ERROR_DIR):
        p.mkdir(parents=True, exist_ok=True)


def dialog_log_path() -> Path:
    """Возвращает путь к файлу журнала в формате YYYY-MM-DD-HHMM.jsonl.
    Каждый вызов может возвращать имя по текущей минуте (простая ротация по времени).
    """
    from datetime import datetime

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    return DIALOG_DIR / f"{stamp}.jsonl"


def error_log_path() -> Path:
    """Возвращает путь к файлу журнала ошибок в формате YYYY-MM-DD-HHMM.jsonl."""
    from datetime import datetime

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    return ERROR_DIR / f"{stamp}.jsonl"
