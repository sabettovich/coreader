import json
from pathlib import Path

from app.server.rag.index_store import IndexStore, IndexedChunk
from app.server.rag.reader import Chunk


def test_index_store_save_and_load(tmp_path: Path):
    p = tmp_path / "index.json"
    store = IndexStore(path=p)
    chunks = [
        Chunk(file="a.md", title="T", text="X" * 300, anchor="aaa", seq=0),
        Chunk(file="b.md", title="U", text="Y", anchor="bbb", seq=1),
    ]
    # Зададим фиктивные эмбеддинги
    embs = [[0.0, 1.0], [1.0, 0.0]]
    store.rebuild(chunks, embs)
    assert p.exists()

    # Цитата для длинного текста усечена до <= 200 символов
    data = json.loads(p.read_text(encoding="utf-8"))
    q0 = data[0]["quote"]
    assert len(q0) <= 200

    # Перезагрузка загружает те же элементы
    store2 = IndexStore(path=p)
    store2.load()
    items = store2.all()
    assert len(items) == 2
    assert isinstance(items[0], IndexedChunk)
    assert items[0].file == "a.md"
    assert items[0].embedding == [0.0, 1.0]


def test_index_store_handles_missing_quote_on_load(tmp_path: Path):
    p = tmp_path / "index.json"
    # Сымитируем старый формат без поля quote
    legacy = [
        {"file": "a.md", "title": "T", "anchor": "a", "seq": 0, "embedding": [0, 1]},
    ]
    p.write_text(json.dumps(legacy), encoding="utf-8")
    store = IndexStore(path=p)
    store.load()
    items = store.all()
    assert len(items) == 1
    assert hasattr(items[0], "quote")
