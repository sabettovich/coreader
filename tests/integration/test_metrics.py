import json
from pathlib import Path
from typing import List, Dict

from fastapi.testclient import TestClient

from app.server.main import app


def _write_jsonl(path: Path, rows: List[Dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_metrics_ratio_threshold_95(monkeypatch, tmp_path: Path):
    client = TestClient(app)
    # Подменим каталог логов
    monkeypatch.setattr("app.server.main.DIALOG_DIR", tmp_path)
    # Сформируем файл лога с 100 ответами ассистента, из них 97 с цитатой
    # Дата в имени важна для фильтра start/end: YYYY-MM-DD-HHMM.jsonl
    log_path = tmp_path / "2025-09-21-1200.jsonl"
    rows = []
    # Пользовательский вопрос перед каждым ответом
    for i in range(100):
        rows.append({"ts": f"2025-09-21T12:{i:02d}", "role": "user", "text": f"q{i}"})
        cites = [{"file": "a.md", "anchor": "x"}] if i < 97 else []
        rows.append({
            "ts": f"2025-09-21T12:{i:02d}",
            "role": "assistant",
            "text": f"r{i}",
            "citations": cites,
        })
    _write_jsonl(log_path, rows)

    r = client.get("/metrics", params={"start": "2025-09-21", "end": "2025-09-21"})
    assert r.status_code == 200
    data = r.json()
    assert data["total_assistant"] == 100
    assert data["with_citation"] == 97
    assert data["ratio"] >= 0.95


def test_samples_csv_basic(monkeypatch, tmp_path: Path):
    client = TestClient(app)
    monkeypatch.setattr("app.server.main.DIALOG_DIR", tmp_path)
    # Один лог с парой Q/A и цитатой
    log_path = tmp_path / "2025-09-22-0900.jsonl"
    rows = [
        {"ts": "2025-09-22T09:00", "role": "user", "text": "Вопрос?"},
        {
            "ts": "2025-09-22T09:00",
            "role": "assistant",
            "text": "Ответ",
            "citations": [{"file": "b.md", "anchor": "a1", "quote": "Короткая цитата"}],
        },
    ]
    _write_jsonl(log_path, rows)

    r = client.get("/samples.csv", params={"n": 1, "start": "2025-09-22", "end": "2025-09-22"})
    assert r.status_code == 200
    text = r.text.strip()
    # Проверим заголовок и наличие строки с ожидаемыми колонками
    lines = text.splitlines()
    assert lines[0] == "ts,question,reply,quote,file,anchor,link"
    assert any(
        (",Вопрос?," in line or ",\"Вопрос?\"," in line) and "b.md" in line and "a1" in line
        for line in lines[1:]
    )
