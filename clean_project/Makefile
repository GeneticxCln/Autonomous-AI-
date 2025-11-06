PY=python3
PKG=src.agent_system

.PHONY: install dev lint format typecheck test cov ci run web api interactive help clean

install:
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r config/requirements.txt

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

# Run the agent with default goals
run:
	$(PY) -m src.agent_system

# Web dashboard
web:
	$(PY) -m src.agent_system fastapi_app

# API server
api:
	uvicorn src.agent_system.fastapi_app:app --reload

# Interactive terminal
interactive:
	$(PY) -m src.agent_system --interactive

# Clean build artifacts
clean:
	$(PY) -c "import shutil; shutil.rmtree('build', ignore_errors=True)"
	$(PY) -c "import shutil; shutil.rmtree('dist', ignore_errors=True)"
	$(PY) -c "import shutil; shutil.rmtree('*.egg-info', ignore_errors=True)"
	rm -rf __pycache__/
	rm -rf src/**/__pycache__/
	rm -rf tests/**/__pycache__/

# Show help
help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies"
	@echo "  dev         - Development installation"
	@echo "  lint        - Code linting"
	@echo "  format      - Code formatting"
	@echo "  typecheck   - Type checking"
	@echo "  test        - Run tests"
	@echo "  cov         - Test coverage"
	@echo "  ci          - Full CI pipeline"
	@echo "  run         - Run agent with default goals"
	@echo "  web         - Start web dashboard"
	@echo "  api         - Start API server"
	@echo "  interactive - Interactive terminal mode"
	@echo "  clean       - Clean build artifacts"
	@echo "  help        - Show this help"