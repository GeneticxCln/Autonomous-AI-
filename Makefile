## DEPRECATED: Use clean_project/Makefile for all tasks. This root Makefile is legacy.
PY=python3
PKG=agent_system

.PHONY: install dev lint format typecheck test cov ci

install:
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt

dev:
	$(PY) -m pip install -e .[dev]

lint:
	$(PY) -m ruff .

format:
	$(PY) -m black .

typecheck:
	$(PY) -m mypy $(PKG)

test:
	$(PY) -m pytest -q

cov:
	$(PY) -m coverage run -m pytest -q
	$(PY) -m coverage report -m

ci: lint typecheck test