from __future__ import annotations

import os
from pathlib import Path
import json
from typing import Optional, List, Dict, Any
import random
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from app.server.dialog.logger import DialogLogger
from app.server.utils.error_logger import ErrorLogger
from app.server.utils.paths import ensure_dirs, DIALOG_DIR
from app.server.providers.openai_client import OpenAIClient
from app.server.rag.pipeline import rebuild_index, load_index
from app.server.rag.retriever import retrieve_top
from app.server.rag.reader import parse_markdown_file
from app.server.utils.paths import BOOK_DIR, CONTEXT_DIR

load_dotenv()

app = FastAPI(title="Coreader")
logger = DialogLogger()
error_logger = ErrorLogger()


# Optional hard order for Plato's Symposium speeches (domain-specific guardrail)
SPEAKER_ORDER = {
    "федр": 1,
    "павсан": 2,
    "эриксимах": 3,
    "аристофан": 4,
    "агафон": 5,
    "сократ": 6,
    "алкивиад": 7,
}


def _validate_env() -> None:
    """Проверка и предупреждения по переменным окружения.
    Не приводит к падению приложения; только логирует предупреждения.
    """
    msgs: List[str] = []
    if not os.getenv("OBSIDIAN_VAULT_PATH"):
        msgs.append("OBSIDIAN_VAULT_PATH не задан: экспорт в Obsidian недоступен.")
    if not os.getenv("OPENAI_API_KEY"):
        msgs.append("OPENAI_API_KEY не задан: генерация ответов в онлайне отключена.")
    if not os.getenv("ZOTERO_API_KEY"):
        msgs.append("ZOTERO_API_KEY не задан: поиск Zotero будет недоступен.")
    if not (os.getenv("ZOTERO_USER_ID") or os.getenv("ZOTERO_GROUP_ID")):
        msgs.append("Не задан ZOTERO_USER_ID/GROUP_ID: укажите хотя бы одно для доступа к библиотеке.")
    if msgs:
        warn = "; ".join(msgs)
        # В консоль
        print(f"[ENV WARNING] {warn}")
        # В error-лог (как предупреждение)
        try:
            error_logger.log(route="/startup", err=warn)
        except Exception:
            pass


def _auto_boundary_from_message(msg: str, store) -> Optional[int]:
    """Heuristic: detect phrases like 'начал читать/я читаю/только что прочитал' + speaker name
    and compute boundary seq from store titles.
    """
    import re

    text = msg.lower()
    # Known speakers/sections (expandable)
    speakers = [
        ("сократ", "сократ"),
        ("павсан", "павсан"),
        ("аристофан", "аристофан"),
        ("эриксимах", "эриксимах"),
        ("федр", "федр"),
        ("агафон", "агафон"),
        ("алкивиад", "алкивиад"),
    ]

    # Determine intent
    intent = None  # 'start', 'now', 'just'
    if re.search(r"начал[аио]?\s+читать", text):
        intent = 'start'
    elif re.search(r"только\s+что\s+прочитал[аио]?", text) or re.search(r"прочитал[аио]?", text):
        intent = 'just'
    elif re.search(r"я\s+читаю", text) or re.search(r"\bчитаю\b", text):
        intent = 'now'

    if not intent:
        return None

    # Find mentioned speaker
    target = None
    for key, stem in speakers:
        if stem in text:
            target = stem
            break
    if not target:
        return None

    # Scan store to find contiguous span(s) by title including target
    items = sorted(store.all(), key=lambda i: i.seq)
    matches = [it for it in items if target in (it.title or '').lower()]
    if not matches:
        return None
    # Determine span bounds
    min_seq = min(it.seq for it in matches)
    max_seq = max(it.seq for it in matches)

    if intent == 'start':
        return max(min_seq - 1, 0)
    else:  # 'now' or 'just'
        return max_seq

def _extract_zotero_key_from_file(file_path: Optional[str]) -> Optional[str]:
    if not file_path:
        return None
    p = Path(file_path)
    if not p.exists():
        return None
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return None
    # Ищем в YAML-frontmatter
    import re
    # вариант 1: явное поле zotero_key: ABC123
    m = re.search(r"^---[\s\S]*?^zotero_key\s*:\s*([A-Za-z0-9]+)[\s\S]*?^---", text, re.M)
    if m:
        return m.group(1)
    # вариант 2: source: zotero://select/library/items/KEY
    m = re.search(r"^---[\s\S]*?^source\s*:\s*zotero://select/[^/]+/items/([A-Za-z0-9]+)[\s\S]*?^---", text, re.M)
    if m:
        return m.group(1)
    return None


def _detect_speaker(msg: str) -> Optional[str]:
    text = msg.lower()
    for stem in ("сократ", "павсан", "аристофан", "эриксимах", "федр", "агафон", "алкивиад"):
        if stem in text:
            return stem
    return None


def _span_for_speaker(store, stem: str) -> Optional[tuple[int, int]]:
    items = sorted(store.all(), key=lambda i: i.seq)
    hits = [it.seq for it in items if stem in (it.title or '').lower()]
    if not hits:
        return None
    return (min(hits), max(hits))


def _detect_current_stem(msg: str) -> Optional[str]:
    import re
    text = msg.lower()
    # pattern: (trigger) + anything + (name)
    triggers = r"(начал[аио]?\s+читать|я\s+читаю|\bчитаю\b|только\s+что\s+прочитал[аио]?)"
    names = r"(сократ|павсан\w*|аристофан|эриксимах|федр|агафон|алкивиад)"
    m = re.search(triggers + r"[^.\n]*?" + names, text)
    if m:
        stem = m.group(2)
        # normalize to base stems we use elsewhere
        for base in ("сократ", "павсан", "аристофан", "эриксимах", "федр", "агафон", "алкивиад"):
            if base in stem:
                return base
    return None


def _first_seq_for_stem(store, stem: str) -> Optional[int]:
    items = sorted(store.all(), key=lambda i: i.seq)
    for it in items:
        title_l = (it.title or '').lower()
        quote_l = (getattr(it, 'quote', '') or '').lower()
        if stem in title_l or stem in quote_l:
            return it.seq
    return None

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    citations: List[Dict[str, str]] = []


class Settings(BaseModel):
    offline: bool = False
    socratic_level: int = 2  # 1..3
    reply_limit_chars: int = 500
    obsidian_vault_path: Optional[str] = None
    read_boundary_seq: Optional[int] = None  # максимальный seq для ответов


SETTINGS = Settings(
    offline=os.getenv("OFFLINE", "false").lower() == "true",
    obsidian_vault_path=os.getenv("OBSIDIAN_VAULT_PATH"),
)


@app.on_event("startup")
async def on_startup() -> None:
    ensure_dirs()
    _validate_env()


@app.get("/settings", response_model=Settings)
async def get_settings() -> Settings:
    return SETTINGS


@app.post("/settings", response_model=Settings)
async def update_settings(new: Settings) -> Settings:
    global SETTINGS
    SETTINGS = new
    return SETTINGS


@app.get("/settings/info")
async def settings_info() -> JSONResponse:
    """Диагностика настроек: возвращает наличие ключей/ID провайдеров без раскрытия значений."""
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_zotero_key = bool(os.getenv("ZOTERO_API_KEY"))
    has_zotero_user = bool(os.getenv("ZOTERO_USER_ID"))
    has_zotero_group = bool(os.getenv("ZOTERO_GROUP_ID"))
    return JSONResponse({
        "openai_configured": has_openai,
        "zotero_configured": has_zotero_key and (has_zotero_user or has_zotero_group),
        "zotero_scope": "user" if has_zotero_user else ("group" if has_zotero_group else None),
    })


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    logger.log("user", req.message)
    # Try retrieval-only flow (no generation yet)
    try:
        store = load_index()
        if not store.all():
            msg = "Индекс пуст. Выполните переиндексацию в онлайне." if not SETTINGS.offline else "Оффлайн: индекс отсутствует."
            logger.log("assistant", msg, citations=[])
            return ChatResponse(reply=msg, citations=[])
        api_key = os.getenv("OPENAI_API_KEY")
        client = OpenAIClient(api_key=api_key, offline=SETTINGS.offline)
        # Auto boundary from message (if any), then apply the strictest
        auto_seq = _auto_boundary_from_message(req.message, store)
        max_seq = SETTINGS.read_boundary_seq
        if auto_seq is not None:
            max_seq = min(auto_seq, max_seq) if max_seq is not None else auto_seq

        # Если пользователь спрашивает про спикера, который идёт ПОСЛЕ границы — отвечаем отказом
        asked = _detect_speaker(req.message)
        current_stem = _detect_current_stem(req.message)
        if asked and max_seq is not None:
            span = _span_for_speaker(store, asked)
            asked_first = _first_seq_for_stem(store, asked)
            violate = False
            if span and span[0] > max_seq:
                violate = True
            elif asked_first is not None and asked_first > max_seq:
                violate = True
            # if user reading one speaker now and asks about another later one
            if not violate and current_stem and asked != current_stem:
                curr_span = _span_for_speaker(store, current_stem)
                if curr_span and asked_first is not None and asked_first > curr_span[1]:
                    violate = True
            # Additional order-based guard: if current speaker exists and is earlier than asked
            if not violate and current_stem and asked in SPEAKER_ORDER and current_stem in SPEAKER_ORDER:
                if SPEAKER_ORDER[current_stem] < SPEAKER_ORDER[asked]:
                    violate = True

            if violate:
                msg = (
                    "Вы ещё не дошли до этой части книги. Вопрос относится к последующим разделам. "
                    "Подсказка: снимите границу (кнопка ‘Сбросить’ в настройках сверху) и попробуйте ещё раз."
                )
                logger.log("assistant", msg, citations=[])
                return ChatResponse(reply=msg, citations=[])

        hits = retrieve_top(
            req.message,
            store,
            client,
            top_k=3,
            max_seq=max_seq,
        )
        # 8.3: confidence gating — фильтрация по простым порогам релевантности
        def is_confident(h: Dict[str, Any]) -> bool:
            kw = float(h.get("kw_ratio", 0.0))
            cs = float(h.get("cosine", 0.0))
            return (kw >= 0.15) or (cs >= 0.20)

        confident_hits = [h for h in hits if is_confident(h)]
        if not confident_hits:
            msg = (
                "Не могу ответить строго по книге: не нашёл точной цитаты по вашему вопросу. "
                "Уточните формулировку или место в книге."
            )
            logger.log("assistant", msg, citations=[])
            return ChatResponse(reply=msg, citations=[])

        # Анахронизмы: явные современные термины — корректный отказ
        anach = any(stem in req.message.lower() for stem in [
            "автомобил", "интернет", "смартфон", "компьютер", "ракет", "поезд", "телефон",
            "кибер", "электрон", "бензин", "двигател", "нефт", "спутник"
        ])
        if anach:
            msg = (
                "Не могу ответить строго по книге: в тексте нет упоминаний некоторых терминов из вопроса. "
                "Переформулируйте вопрос в терминах книги или уберите современные понятия."
            )
            logger.log("assistant", msg, citations=[])
            return ChatResponse(reply=msg, citations=[])

        citations = [{
            "file": h["file"],
            "anchor": h["anchor"],
            "title": h.get("title", ""),
            "quote": h.get("quote", "")
        } for h in confident_hits]
        reply = "Нашёл релевантные места в книге." if citations else "Не нашёл подходящих цитат."

        # 6.0: генерация краткого ответа на основе цитат (только если онлайн)
        if citations and not SETTINGS.offline and os.getenv("OPENAI_API_KEY"):
            # Собираем компактный контекст только из цитат
            ctx_lines = []
            for i, c in enumerate(citations, 1):
                title = c.get("title") or ""
                quote = c.get("quote") or ""
                ctx_lines.append(f"[{i}] {title}: \"{quote}\"")
            ctx = "\n".join(ctx_lines)
            approx_tokens = max(60, min(200, int(SETTINGS.reply_limit_chars / 4)))
            if SETTINGS.socratic_level == 1:
                style = "Дай прямой лаконичный ответ."
            elif SETTINGS.socratic_level == 3:
                style = "Сформулируй ответ через наводящий вопрос, максимум одно краткое утверждение."
            else:
                style = "Дай краткий ответ и один наводящий вопрос."

            prompt = (
                "Отвечай по-русски, строго по приведённым цитатам. "
                "Обязательно включи одну точную короткую цитату в кавычках вместе с пометкой источника в квадратных скобках, например: [1]. "
                f"{style}\n\n"
                f"Вопрос: {req.message}\n\nЦитаты:\n{ctx}\n\nКраткий ответ (<= {SETTINGS.reply_limit_chars} символов):"\
            )
            try:
                gen = client.chat(prompt, max_tokens=approx_tokens)
                if gen:
                    reply = gen.strip()
            except Exception:
                pass
        elif citations and SETTINGS.offline:
            # Офлайн-фолбэк: всегда возвращаем краткий ответ с кавычками вокруг цитаты
            shortest = sorted(citations, key=lambda c: len((c.get("quote") or "").strip()) or 1)[0]
            q = (shortest.get("quote") or "").strip()
            t = (shortest.get("title") or "").strip()
            reply = f"По книге: \"{q}\" [{t}]" if q else "По книге: см. цитату [1] в списке ссылок."
        logger.log("assistant", reply, citations=citations)
        return ChatResponse(reply=reply, citations=citations)
    except Exception as e:
        msg = f"Недоступно: {e}"
        error_logger.log(route="/chat", err=e)
        logger.log("assistant", msg, citations=[])
        return ChatResponse(reply=msg, citations=[])


@app.post("/export")
async def export_note(payload: Dict[str, Any]) -> JSONResponse:
    from app.server.obsidian.exporter import export_note as do_export
    from app.server.zotero.client import ZoteroClient

    reply = (payload or {}).get("reply")
    citations = (payload or {}).get("citations") or []
    title = (payload or {}).get("title") or "Coreader"
    book_meta = (payload or {}).get("book")

    vault = SETTINGS.obsidian_vault_path or os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault:
        raise HTTPException(status_code=400, detail="Не настроен OBSIDIAN_VAULT_PATH")
    if not reply:
        raise HTTPException(status_code=400, detail="Пустой текст ответа для экспорта")

    # Попытка обогатить метаданные книги через Zotero: приоритет ключа из payload,
    # иначе — пробуем вытянуть из первой цитаты; при наличии API — дотягиваем поля
    try:
        zkey = (book_meta or {}).get("zotero_key")
        if not zkey and citations:
            zkey = _extract_zotero_key_from_file(citations[0].get("file"))
        if zkey:
            book_meta = {**(book_meta or {}), "zotero_key": zkey}
            if not SETTINGS.offline:
                zclient = ZoteroClient(
                    api_key=os.getenv("ZOTERO_API_KEY"),
                    user_id=os.getenv("ZOTERO_USER_ID"),
                    group_id=os.getenv("ZOTERO_GROUP_ID"),
                )
                zmeta = zclient.get_item(zkey)
                if zmeta:
                    book_meta = {**book_meta, **zmeta}
    except Exception:
        # Тихо игнорируем проблемы Zotero
        pass

    try:
        path = do_export(vault, reply=reply, citations=citations, title=title, book_meta=book_meta)
        return JSONResponse({"status": "ok", "path": str(path)})
    except Exception as e:
        error_logger.log(route="/export", err=e)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


def _iter_dialog_files_between(start: Optional[str], end: Optional[str]):
    """Генератор файлов журнала в диапазоне дат (строки YYYY-MM-DD)."""
    files = sorted([p for p in DIALOG_DIR.glob("*.jsonl") if p.is_file()])
    for p in files:
        name = p.name  # YYYY-MM-DD-HHMM.jsonl
        date = name.split("-")[:3]
        try:
            stamp = "-".join(date)
        except Exception:
            continue
        if start and stamp < start:
            continue
        if end and stamp > end:
            continue
        yield p


@app.get("/metrics")
async def metrics(start: Optional[str] = None, end: Optional[str] = None) -> JSONResponse:
    """Метрики по журналам: доля ответов ассистента с хотя бы одной цитатой.
    Фильтр по датам (YYYY-MM-DD)."""
    try:
        total = 0
        with_cite = 0
        per_file: Dict[str, Dict[str, int]] = {}
        for p in _iter_dialog_files_between(start, end):
            t = 0
            w = 0
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if obj.get("role") == "assistant":
                        t += 1
                        cites = obj.get("citations") or []
                        if isinstance(cites, list) and len(cites) > 0:
                            w += 1
            if t:
                per_file[p.name] = {"assistant": t, "with_citation": w}
                total += t
                with_cite += w
        ratio = (with_cite / total) if total else 0.0
        return JSONResponse({
            "status": "ok",
            "start": start,
            "end": end,
            "total_assistant": total,
            "with_citation": with_cite,
            "ratio": round(ratio, 4),
            "per_file": per_file,
        })
    except Exception as e:
        error_logger.log(route="/metrics", err=e)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/metrics.csv")
async def metrics_csv(start: Optional[str] = None, end: Optional[str] = None) -> PlainTextResponse:
    """Экспорт метрик в CSV по дням/файлам."""
    try:
        lines = ["file,total_assistant,with_citation,ratio"]
        for p in _iter_dialog_files_between(start, end):
            t = 0
            w = 0
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if obj.get("role") == "assistant":
                        t += 1
                        if obj.get("citations"):
                            w += 1
            r = (w / t) if t else 0.0
            lines.append(f"{p.name},{t},{w},{r:.4f}")
        return PlainTextResponse("\n".join(lines), media_type="text/csv")
    except Exception as e:
        error_logger.log(route="/metrics.csv", err=e)
        return PlainTextResponse("error", status_code=500)


@app.post("/export/preview")
async def export_preview(payload: Dict[str, Any]) -> JSONResponse:
    from app.server.obsidian.exporter import build_note_content, BookMeta
    from app.server.utils.paths import DEFAULT_OBSIDIAN_SUBDIR
    import re
    from app.server.zotero.client import ZoteroClient

    reply = (payload or {}).get("reply")
    citations = (payload or {}).get("citations") or []
    title = (payload or {}).get("title") or "Coreader"
    book_meta = (payload or {}).get("book")

    if not reply:
        raise HTTPException(status_code=400, detail="Пустой текст ответа для предпросмотра")

    # Попытка обогатить метаданные книги через Zotero: приоритет ключа из payload,
    # иначе — пробуем вытянуть из первой цитаты; при наличии API — дотягиваем поля
    try:
        zkey = (book_meta or {}).get("zotero_key")
        if not zkey and citations:
            zkey = _extract_zotero_key_from_file(citations[0].get("file"))
        if zkey:
            book_meta = {**(book_meta or {}), "zotero_key": zkey}
            if not SETTINGS.offline:
                zclient = ZoteroClient(
                    api_key=os.getenv("ZOTERO_API_KEY"),
                    user_id=os.getenv("ZOTERO_USER_ID"),
                    group_id=os.getenv("ZOTERO_GROUP_ID"),
                )
                zmeta = zclient.get_item(zkey)
                if zmeta:
                    book_meta = {**book_meta, **zmeta}
    except Exception:
        error_logger.log(route="/export/preview", err="zotero enrichment failed")
        pass

    bm = None
    if isinstance(book_meta, dict):
        bm = BookMeta(
            key=book_meta.get("zotero_key") or book_meta.get("key"),
            title=book_meta.get("title"),
            authors=book_meta.get("authors"),
            year=book_meta.get("year"),
            tags=book_meta.get("tags"),
        )
    else:
        bm = book_meta
    content = build_note_content(title, reply, citations, book=bm)

    def slugify(text: str) -> str:
        t = text.lower().strip()
        t = re.sub(r"[^a-z0-9а-яё\-\s_]", "", t)
        t = re.sub(r"\s+", "-", t)
        t = re.sub(r"-+", "-", t)
        return t.strip("-") or "note"

    subdir = DEFAULT_OBSIDIAN_SUBDIR
    suggested = f"{subdir}/{slugify(title)}/YYYYMMDD-HHMM-{slugify(title)}.md"
    return JSONResponse({"status": "ok", "suggested_path": suggested, "content": content})


@app.post("/zotero/search")
async def zotero_search(payload: Dict[str, Any]) -> JSONResponse:
    from app.server.zotero.client import ZoteroClient
    if SETTINGS.offline:
        return JSONResponse({"status": "error", "message": "Оффлайн-режим"}, status_code=400)
    q = (payload or {}).get("q")
    author = (payload or {}).get("author")
    if not q:
        return JSONResponse({"status": "ok", "items": []})
    client = ZoteroClient(
        api_key=os.getenv("ZOTERO_API_KEY"),
        user_id=os.getenv("ZOTERO_USER_ID"),
        group_id=os.getenv("ZOTERO_GROUP_ID"),
    )
    try:
        items = client.search_items(q, limit=15) or []
    except Exception as e:
        error_logger.log(route="/zotero/search", err=e)
        items = []
    # Ранжирование: точное совпадение названия, затем включение, затем автор/теги
    def score(it: Dict[str, Any]) -> int:
        s = 0
        ttl = (it.get("title") or "").strip().lower()
        ql = (q or "").strip().lower()
        if ttl == ql:
            s += 30
        elif ql and ql in ttl:
            s += 10
        # авторское совпадение
        auths = it.get("authors") or []
        if isinstance(auths, list):
            joined = ", ".join(auths).lower()
            if author:
                al = str(author).lower()
                if al and al in joined:
                    s += 20
            # общая эвристика: платон
            if "платон" in joined:
                s += 10
        # теги
        tags = it.get("tags") or []
        if isinstance(tags, list):
            low = [str(t).lower() for t in tags]
            if author and str(author).lower() in low:
                s += 5
            if any(x in low for x in ["платон", "пир"]):
                s += 3
        # год — свежие ниже при равенстве
        year = it.get("year") or 0
        return s * 10000 + int(year)

    items_sorted = sorted(items, key=score, reverse=True)
    return JSONResponse({"status": "ok", "items": items_sorted})

@app.post("/admin/reindex")
async def admin_reindex() -> JSONResponse:
    if SETTINGS.offline:
        error_logger.log(route="/admin/reindex", err="offline mode")
        raise HTTPException(status_code=400, detail="Оффлайн-режим: переиндексация недоступна")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        error_logger.log(route="/admin/reindex", err="OPENAI_API_KEY missing")
        raise HTTPException(status_code=400, detail="Не задан OPENAI_API_KEY")
    try:
        client = OpenAIClient(api_key=api_key, offline=False)
        store = rebuild_index(client)
        return JSONResponse({"status": "ok", "items": len(store.all())})
    except Exception as e:
        # Вернуть ошибку для диагностики
        error_logger.log(route="/admin/reindex", err=e)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/progress")
async def get_progress() -> JSONResponse:
    """Вернуть список разделов (по title) с диапазоном seq.
    Используется для выбора «границы прочитанного» без чисел.
    """
    store = load_index()
    items = store.all()
    buckets: Dict[str, Dict[str, Any]] = {}
    for it in items:
        title = (it.title or "").strip()
        if not title:
            continue
        b = buckets.setdefault(title, {"title": title, "min_seq": it.seq, "max_seq": it.seq, "count": 0})
        b["min_seq"] = min(b["min_seq"], it.seq)
        b["max_seq"] = max(b["max_seq"], it.seq)
        b["count"] += 1
    sections = sorted(buckets.values(), key=lambda x: x["min_seq"])
    return JSONResponse({"status": "ok", "sections": sections, "current_seq": SETTINGS.read_boundary_seq})


@app.get("/book")
async def view_book(file: str) -> HTMLResponse:
    # Безопасность: разрешаем только внутри каталогов книг/контекста
    p = Path(file).resolve()
    allowed = [BOOK_DIR.resolve(), CONTEXT_DIR.resolve()]
    if not any(str(p).startswith(str(a) + os.sep) or str(p) == str(a) for a in allowed):
        error_logger.log(route="/book", err="invalid path", extra={"file": str(p)})
        raise HTTPException(status_code=400, detail="Недопустимый путь файла")
    if not p.exists() or p.suffix.lower() != ".md":
        error_logger.log(route="/book", err="file not found", extra={"file": str(p)})
        raise HTTPException(status_code=404, detail="Файл не найден")

    chunks = parse_markdown_file(p)
    title = p.name
    # Простой HTML с якорями на каждый абзац
    body_parts = [
        "<style>body{font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#0b0d10;color:#e6e6e6;padding:24px;}",
        "a{color:#60a5fa}",
        "h1{margin-top:0}",
        "section{margin:18px 0;padding:12px;border:1px solid #232833;border-radius:8px;background:#0f1217}",
        "h2{margin:0 0 8px 0;color:#9fb3c8}",
        "p{white-space:pre-wrap;line-height:1.6}",
        ".meta{font-size:12px;color:#9fb3c8;margin-bottom:6px}",
        "</style>",
        f"<h1>{title}</h1>",
    ]
    for ch in chunks:
        sec = [
            "<section>",
            f"<div class=\"meta\">{ch.title or ''} · <code>#{ch.anchor}</code></div>",
            f"<p id=\"{ch.anchor}\">{ch.text}</p>",
            "</section>",
        ]
        body_parts.extend(sec)
    html = "".join(body_parts)
    return HTMLResponse(html)


@app.get("/logs")
async def get_logs(file: Optional[str] = None, role: Optional[str] = None, q: Optional[str] = None, limit: int = 200) -> JSONResponse:
    """Возвращает записи журнала из последнего файла или указанного. Поддерживает фильтры."""
    try:
        # список доступных файлов
        files = sorted([p for p in DIALOG_DIR.glob("*.jsonl") if p.is_file()], key=lambda p: p.name, reverse=True)
        files_list = [p.name for p in files]
        target = None
        if file:
            candidate = DIALOG_DIR / file
            if candidate.exists():
                target = candidate
        if target is None and files:
            target = files[0]
        entries = []
        if target and target.exists():
            with open(target, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if role and obj.get("role") != role:
                        continue
                    if q:
                        text = (obj.get("text") or "")
                        if q.lower() not in text.lower():
                            continue
                    entries.append(obj)
        # ограничим количество последних записей
        entries = entries[-max(10, min(1000, int(limit))):]
        return JSONResponse({
            "status": "ok",
            "file": target.name if target else None,
            "files": files_list,
            "entries": entries,
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/samples.csv")
async def samples_csv(n: int = 10, start: Optional[str] = None, end: Optional[str] = None) -> PlainTextResponse:
    try:
        rows: List[Dict[str, str]] = []
        for p in _iter_dialog_files_between(start, end):
            last_user: Optional[str] = None
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    role = obj.get("role")
                    if role == "user":
                        last_user = obj.get("text") or ""
                        continue
                    if role == "assistant":
                        reply = obj.get("text") or ""
                        ts = obj.get("ts") or ""
                        cites = obj.get("citations") or []
                        file = anchor = link = quote = ""
                        if isinstance(cites, list) and len(cites) > 0:
                            c0 = cites[0]
                            file = c0.get("file") or ""
                            anchor = c0.get("anchor") or ""
                            quote = (c0.get("quote") or "").replace("\n", " ")
                            if file and anchor:
                                link = f"/book?file={file}#{anchor}"
                        rows.append({
                            "ts": ts,
                            "question": (last_user or "").replace("\n", " "),
                            "reply": reply.replace("\n", " "),
                            "quote": quote,
                            "file": file,
                            "anchor": anchor,
                            "link": link,
                        })
        random.shuffle(rows)
        sample = rows[: max(1, min(int(n), 500))]
        out = ["ts,question,reply,quote,file,anchor,link"]
        def esc(s: str) -> str:
            if any(ch in s for ch in [',', '"', '\n']):
                return '"' + s.replace('"', '""') + '"'
            return s
        for r in sample:
            out.append(
                ",".join(esc(str(r.get(k, ""))) for k in [
                    "ts", "question", "reply", "quote", "file", "anchor", "link"
                ])
            )
        return PlainTextResponse("\n".join(out), media_type="text/csv")
    except Exception as e:
        error_logger.log(route="/samples.csv", err=e)
        return PlainTextResponse("error", status_code=500)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = PROJECT_ROOT / "app" / "web"
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
