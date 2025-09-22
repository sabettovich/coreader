# Python venv
.venv:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip

install: .venv
	.venv/bin/pip install -r requirements.txt

# Development server on port 45469
.PHONY: dev
dev: install
	.venv/bin/python -m uvicorn app.server.main:app --host 127.0.0.1 --port 45469 --reload

# Alternate run on port 8000
.PHONY: run
run:
	uvicorn app.server.main:app --host 127.0.0.1 --port 8000 --reload

# Tests
.PHONY: test
test: install
	.venv/bin/pytest -q

# Lint/format placeholders (wire to ruff/black later)
.PHONY: lint fmt
lint:
	@echo "No linter configured"

fmt:
	@echo "No formatter configured"
