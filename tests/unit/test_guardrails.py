from types import SimpleNamespace

from app.server.main import (
    _auto_boundary_from_message,
    _detect_speaker,
    _detect_current_stem,
    _span_for_speaker,
    _first_seq_for_stem,
)


class FakeItem(SimpleNamespace):
    pass


class FakeStore:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


def make_store():
    # Секции с последовательностью
    # 0..4 — Федр; 5..9 — Павсаний; 10..14 — Сократ
    items = []
    for i in range(0, 5):
        items.append(FakeItem(title="Речь Федра", seq=i))
    for i in range(5, 10):
        items.append(FakeItem(title="Речь Павсания", seq=i))
    for i in range(10, 15):
        items.append(FakeItem(title="Речь Сократа", seq=i))
    return FakeStore(items)


def test_detect_speaker_and_current():
    assert _detect_speaker("Расскажите про Сократа") == "сократ"
    assert _detect_speaker("Павсаний интересует") == "павсан"
    assert _detect_speaker("федр и павсаний") in {"федр", "павсан"}

    # current stem (я читаю ... Сократа)
    assert _detect_current_stem("Я читаю Сократа сейчас") == "сократ"
    assert _detect_current_stem("Начал читать Павсана") == "павсан"


def test_spans_and_first_seq():
    store = make_store()
    # Диапазон для Сократа 10..14
    span = _span_for_speaker(store, "сократ")
    assert span == (10, 14)
    # Первый seq для Федра — 0
    assert _first_seq_for_stem(store, "федр") == 0


def test_auto_boundary_from_message():
    store = make_store()
    # "начал читать Сократа" → граница до начала Сократа → 9
    b1 = _auto_boundary_from_message("Начал читать Сократа", store)
    assert b1 == 9
    # "только что прочитал Павсания" → граница на конец Павсания → 9
    b2 = _auto_boundary_from_message("Только что прочитал Павсания", store)
    assert b2 == 9
    # "я читаю Федра" → граница на конец Федра → 4
    b3 = _auto_boundary_from_message("Я читаю Федра", store)
    assert b3 == 4
