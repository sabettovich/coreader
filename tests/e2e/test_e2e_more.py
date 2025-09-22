from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.server.main import app, SETTINGS


class FakeStore:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


def test_e2e_no_confident_hits_refusal(monkeypatch):
    client = TestClient(app)
    # Непустой стор
    items = [SimpleNamespace(title="Раздел", seq=0)]
    monkeypatch.setattr("app.server.main.load_index", lambda: FakeStore(items))

    # Ретривер возвращает очень слабые хиты (ниже порогов kw>=0.15 и cosine>=0.20)
    def weak_retrieve_top(message, store, client, top_k=3, max_seq=None):
        return [
            {"file": "x.md", "anchor": "a1", "title": "T", "quote": "Q", "kw_ratio": 0.05, "cosine": 0.1}
        ]

    monkeypatch.setattr("app.server.main.retrieve_top", weak_retrieve_top)

    SETTINGS.offline = False
    SETTINGS.read_boundary_seq = None

    r = client.post("/chat", json={"message": "Вопрос"})
    assert r.status_code == 200
    data = r.json()
    assert "Не могу ответить строго по книге" in data["reply"]


def test_e2e_speaker_order_guard(monkeypatch):
    client = TestClient(app)
    # Секции по порядку Федр(0..4) -> Павсаний(5..9) -> Сократ(10..14)
    items = []
    for i in range(0, 5):
        items.append(SimpleNamespace(title="Речь Федра", seq=i))
    for i in range(5, 10):
        items.append(SimpleNamespace(title="Речь Павсания", seq=i))
    for i in range(10, 15):
        items.append(SimpleNamespace(title="Речь Сократа", seq=i))
    monkeypatch.setattr("app.server.main.load_index", lambda: FakeStore(items))

    # Сообщение: читаю Федра, но спрашиваю про Сократа → отказ по порядку SPEAKER_ORDER
    SETTINGS.offline = False
    SETTINGS.read_boundary_seq = None

    msg = "Я читаю Федра сейчас. Что говорит Сократ?"
    r = client.post("/chat", json={"message": msg})
    assert r.status_code == 200
    data = r.json()
    assert "Вы ещё не дошли" in data["reply"] or "вопрос относится к последующим разделам" in data["reply"].lower()
