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
        # Вернём один и тот же вектор запроса длины 2
        return [[1.0, 0.0] for _ in texts]


def test_retrieve_respects_max_seq_and_keywords():
    # Два чанка, один за пределом max_seq
    a = IndexedChunk(file="a.md", title="Речь Федра", anchor="x1", seq=0, embedding=[1.0, 0.0], quote="Федр ...")
    b = IndexedChunk(file="b.md", title="Речь Сократа", anchor="x2", seq=10, embedding=[0.0, 1.0], quote="Сократ ...")
    store = FakeStore([a, b])
    client = FakeClient()

    res = retrieve_top("Федра", store, client, top_k=5, max_seq=5)
    # Должен вернуться только первый документ в пределах max_seq
    assert len(res) >= 1
    assert all(r["file"] != "b.md" for r in res)
    # Проверим, что keyword-метрика положительна для совпадающего заголовка
    assert any(r["kw_ratio"] > 0 for r in res)
