import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.server.main import app, SETTINGS


class FakeStore:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


@pytest.fixture()
def client():
    return TestClient(app)


def test_boundary_guard_refuses_when_asking_later_section(client, monkeypatch):
    # Подготовим стор с секциями: 0..4 — Федр; 5..9 — Павсан; 10..14 — Сократ
    items = []
    for i in range(0, 5):
        items.append(SimpleNamespace(title="Речь Федра", seq=i))
    for i in range(5, 10):
        items.append(SimpleNamespace(title="Речь Павсана", seq=i))
    for i in range(10, 15):
        items.append(SimpleNamespace(title="Речь Сократа", seq=i))
    monkeypatch.setattr("app.server.main.load_index", lambda: FakeStore(items))

    # Установим жёсткую границу до Сократа
    SETTINGS.read_boundary_seq = 4
    SETTINGS.offline = False

    r = client.post("/chat", json={"message": "Расскажите про Сократа"})
    assert r.status_code == 200
    data = r.json()
    assert "Вы ещё не дошли" in data["reply"]


def test_offline_returns_citations_without_generation(client, monkeypatch):
    # store не пустой
    items = [SimpleNamespace(title="Раздел", seq=0)]
    monkeypatch.setattr("app.server.main.load_index", lambda: FakeStore(items))
    # Подменим retriever на фиксированный набор попаданий
    def fake_retrieve_top(message, store, client, top_k=3, max_seq=None):
        return [
            {"file": "x.md", "anchor": "a1", "title": "T", "quote": "Q", "kw_ratio": 0.5, "cosine": 0.3}
        ]
    monkeypatch.setattr("app.server.main.retrieve_top", fake_retrieve_top)

    SETTINGS.read_boundary_seq = None
    SETTINGS.offline = True

    r = client.post("/chat", json={"message": "Вопрос"})
    assert r.status_code == 200
    data = r.json()
    # Оффлайн-ответ должен ссылаться на цитату (корректный фолбэк)
    # Допускаем разные формулировки, но ожидаем наличие самой цитаты
    assert '"Q"' in data["reply"]
    assert data["citations"] and isinstance(data["citations"], list)


def test_export_preview_includes_book_source(client):
    payload = {
        "reply": "Ответ",
        "citations": [{"file": "x.md", "anchor": "a1", "title": "T", "quote": "Q"}],
        "title": "Coreader",
        "book": {"zotero_key": "ABC123"},
    }
    r = client.post("/export/preview", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "suggested_path" in data
    content = data["content"]
    # Проверяем YAML-блок с источником Zotero
    assert "book:" in content
    assert "source: \"zotero://select/library/items/ABC123\"" in content
