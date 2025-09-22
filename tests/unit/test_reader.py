from pathlib import Path

from app.server.rag.reader import parse_markdown_file, parse_markdown_dir


def write(tmp: Path, name: str, text: str) -> Path:
    p = tmp / name
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_markdown_file_headings_and_paragraphs(tmp_path: Path):
    md = """# Заголовок A

Абзац 1, строка 1.
Строка 2.

# Заголовок B

Абзац 2.

Абзац 3.
"""
    p = write(tmp_path, "a.md", md)
    chunks = parse_markdown_file(p)

    # Ожидаем 3 чанка (по абзацам)
    assert len(chunks) == 3

    # Первый чанк под первым заголовком
    assert chunks[0].title == "Заголовок A"
    assert "Абзац 1" in chunks[0].text
    assert chunks[0].seq == 0
    assert len(chunks[0].anchor) == 10

    # Второй и третий под заголовком B
    assert chunks[1].title == "Заголовок B"
    assert chunks[2].title == "Заголовок B"
    assert chunks[1].seq == 1
    assert chunks[2].seq == 2

    # Якоря должны отличаться между разными абзацами
    assert chunks[0].anchor != chunks[1].anchor != chunks[2].anchor


def test_parse_markdown_file_ignores_empty_and_trims(tmp_path: Path):
    md = """
# T

 
\n
Текст
 
"""
    p = write(tmp_path, "b.md", md)
    chunks = parse_markdown_file(p)
    # Один нормальный абзац
    assert len(chunks) == 1
    assert chunks[0].title == "T"
    assert chunks[0].text == "Текст"


def test_parse_markdown_dir_collects_all(tmp_path: Path):
    md1 = """# H1
A

B
"""
    md2 = """# H2
C
"""
    d = tmp_path / "docs"
    d.mkdir()
    write(d, "z.md", md2)
    write(d, "a.md", md1)

    chunks = parse_markdown_dir(d)
    # Для md1: 2 абзаца, для md2: 1 абзац → всего 3
    assert len(chunks) == 3
    # Проверим, что file указывает на соответствующий абсолютный путь
    assert chunks[0].file.endswith("a.md") or chunks[0].file.endswith("z.md")
