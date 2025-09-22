import json
import os
import re
from pathlib import Path

from app.server.utils.paths import ensure_dirs, dialog_log_path, DIALOG_DIR
from app.server.dialog.logger import DialogLogger


def test_dialog_log_path_format():
    ensure_dirs()
    p = dialog_log_path()
    assert p.parent == DIALOG_DIR
    assert re.match(r"^\d{4}-\d{2}-\d{2}-\d{4}\.jsonl$", p.name)


def test_logger_writes_line(tmp_path):
    ensure_dirs()
    # Логгер пишет в файл текущей минуты
    logger = DialogLogger()
    logger.log("user", "hello", citations=[{"file": "x.md", "anchor": "a1"}])
    # Ищем по всем файлам (на случай смены минуты между вызовами)
    files = sorted(DIALOG_DIR.glob("*.jsonl"))
    assert files, "Журналы не созданы"
    found = False
    for f in reversed(files):
        lines = f.read_text(encoding="utf-8").strip().splitlines()
        for line in lines:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("role") == "user" and obj.get("text") == "hello":
                assert isinstance(obj.get("citations"), list)
                found = True
                break
        if found:
            break
    assert found, "Не найдена запись пользователя 'hello' в журнале"
