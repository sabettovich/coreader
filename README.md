# Coreader

[![CI](https://github.com/sabettovich/coreader/actions/workflows/ci.yml/badge.svg)](https://github.com/sabettovich/coreader/actions/workflows/ci.yml)

Локальный помощник для чтения: извлекает цитаты из Markdown-книги, отвечает строго по тексту, экспортирует заметки в Obsidian.

## Требования
- Python 3.10+
- Linux/macOS

## Установка
```bash
cd coreader
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Или через Makefile (если настроен):
```bash
make install
```

## Переменные окружения
Скопируйте `.env.example` в `.env` и заполните:
- `OPENAI_API_KEY` — генерация в онлайне (опц.).
- `ZOTERO_API_KEY` + `ZOTERO_USER_ID`/`ZOTERO_GROUP_ID` — метаданные (опц.).
- `OBSIDIAN_VAULT_PATH` — путь к вашему Obsidian vault (для экспорта заметок).
- `OFFLINE` — `true` отключает сеть (только поиск цитат).

При старте выполняется мягкая валидация: предупреждения в консоль и файл `data/coreader/errors/*.jsonl`.

## Запуск
Dev-сервер на 127.0.0.1:45469
```bash
. .venv/bin/activate
uvicorn app.server.main:app --host 127.0.0.1 --port 45469 --reload
# или
make dev
```

Prod (пример):
```bash
. .venv/bin/activate
uvicorn app.server.main:app --host 0.0.0.0 --port 8000
# или
make run
```

Откройте UI: http://127.0.0.1:45469

## Тесты
```bash
. .venv/bin/activate
pytest -q
# или
make test
```
Ожидаемо: все тесты зелёные.

## UI
Главная страница содержит:
- Диалог: ввод вопроса, лента ответов, цитаты.
- Прогресс чтения: выбор «границы» (заголовок/якорь).
- Настройки: офлайн, сократичность, лимит ответа, бейджи OpenAI/Zotero.
- Журнал: лента `user/assistant`, фильтр по роли/поиску.
- Метрики: доля ответов с цитатами, фильтр по датам, выгрузка CSV.

## Логи и метрики
- Диалоги: `data/coreader/dialog/YYYY-MM-DD-HHMM.jsonl`
- Ошибки: `data/coreader/errors/YYYY-MM-DD-HHMM.jsonl`

Эндпоинты:
- `GET /logs?role=&q=&limit=` — список записей и файлов лога.
- `GET /metrics?start=YYYY-MM-DD&end=YYYY-MM-DD` — JSON метрик (assistant, with_citation, ratio).
- `GET /metrics.csv?start=&end=` — CSV метрик по файлам.
- `GET /samples.csv?n=10&start=&end=` — выборка ответов ассистента для ручной проверки ссылок.

## Экспорт в Obsidian
- Предпросмотр: `POST /export/preview` — возвращает YAML+Markdown, не пишет на диск.
- Экспорт: `POST /export` — сохраняет файл в `${OBSIDIAN_VAULT_PATH}/{subdir}/`.

## Траблшутинг
- `make: Нет правила install` — обновите `Makefile` (цели `install/dev/test`) или ставьте напрямую `pip install -r requirements.txt`.
- Нет OpenAI/Zotero — работаем в офлайне: ответы строятся из найденных цитат.
- Пустые метрики — убедитесь, что в `data/coreader/dialog/` есть файлы .jsonl.
