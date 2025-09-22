import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.server.main import app, SETTINGS


def test_flow_boundary_and_chat_refusal():
    client = TestClient(app)
    # Граница до Сократа
    SETTINGS.read_boundary_seq = 4
    r = client.post("/chat", json={"message": "Что говорит Сократ?"})
    assert r.status_code == 200
    data = r.json()
    assert "Вы ещё не дошли" in data["reply"]


def test_flow_export_note_to_tmp_vault(tmp_path: Path, monkeypatch):
    client = TestClient(app)
    # Временный vault
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    # Экспорт
    payload = {
        "reply": "Ответ",
        "citations": [{"file": str(tmp_path / "x.md"), "anchor": "a1", "title": "T", "quote": "Q"}],
        "title": "Coreader",
        "book": {"zotero_key": "XYZ789"},
    }
    r = client.post("/export", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    saved = Path(data["path"]).resolve()
    assert saved.exists() and saved.is_file()
    # Содержимое содержит source Zotero
    text = saved.read_text(encoding="utf-8")
    assert "zotero://select/library/items/XYZ789" in text


def test_settings_persistence_roundtrip():
    client = TestClient(app)
    # Получим текущие
    r = client.get("/settings")
    st = r.json()
    # Изменим
    st["socratic_level"] = 3
    st["reply_limit_chars"] = 420
    rr = client.post("/settings", json=st)
    assert rr.status_code == 200
    # Проверим
    r2 = client.get("/settings")
    st2 = r2.json()
    assert st2["socratic_level"] == 3
    assert st2["reply_limit_chars"] == 420
