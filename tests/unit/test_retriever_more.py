from types import SimpleNamespace

from app.server.rag.index_store import IndexedChunk
from app.server.rag.retriever import retrieve_top


class FakeStore:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeClient:
    def embed(self, texts):
        # Вернём фиксированный вектор запроса
        return [[1.0, 0.0] for _ in texts]


def test_retrieve_empty_store_returns_empty():
    store = FakeStore([])
    client = FakeClient()
    res = retrieve_top("любой", store, client)
    assert res == []


def test_retrieve_empty_query_still_returns_top_by_cosine():
    # Пустой запрос (после фильтра составит пустые токены), но косинус должен работать
    a = IndexedChunk(file="a.md", title="A", anchor="x1", seq=0, embedding=[1.0, 0.0], quote="...")
    b = IndexedChunk(file="b.md", title="B", anchor="x2", seq=1, embedding=[0.0, 1.0], quote="...")
    store = FakeStore([a, b])
    client = FakeClient()
    res = retrieve_top(" ", store, client, top_k=1)
    assert len(res) == 1
    # Должен выбрать документ с embedding ближе к [1,0]
    assert res[0]["file"] == "a.md"
