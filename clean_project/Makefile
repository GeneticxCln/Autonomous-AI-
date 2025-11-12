VENV?=.venv
PY?=$(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
DEV_REQ?=$(if $(wildcard requirements-dev.txt),requirements-dev.txt,../requirements-dev.txt)
PKG=src.agent_system
WORKER_QUEUE?=agent.jobs

.PHONY: venv install dev lint format typecheck test cov ci run web api interactive worker infra-up infra-down infra-logs infra-status health clean \
	bootstrap-check grant-role provider-show provider-set-order provider-disable

venv:
	@if [ ! -d "$(VENV)" ]; then \
		python3 -m venv $(VENV); \
	fi
	@if [ ! -f "$(VENV)/.deps-installed" ]; then \
		$(VENV)/bin/pip install --upgrade pip; \
		$(VENV)/bin/pip install -r $(DEV_REQ); \
		touch $(VENV)/.deps-installed; \
	else \
		echo "Virtual environment already provisioned at $(VENV) (remove $(VENV)/.deps-installed to reinstall)."; \
	fi

install:
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r config/requirements.txt -c config/constraints.txt

dev:
	$(PY) -m pip install -e .[dev]

lint:
	$(PY) -m ruff check .

format:
	$(PY) -m black .
	$(PY) -m ruff check --fix .

typecheck:
	-$(PY) -m mypy src/agent_system | tee validation_results/mypy_report.txt ; exit 0

test:
	PYTHONPATH=src $(PY) -m pytest -q tests

cov:
	PYTHONPATH=src $(PY) -m coverage run -m pytest -q
	$(PY) -m coverage report -m

typecheck_strict:
	$(PY) -m mypy src/agent_system/security_validator.py

ci: lint typecheck_strict test

# Utilities
migrate-passwords:
	PYTHONPATH=src $(PY) scripts/migrate_password_hashes.py

auth-report-legacy:
	PYTHONPATH=src $(PY) scripts/auth_management.py report-legacy

auth-create-reset:
	PYTHONPATH=src $(PY) scripts/auth_management.py create-reset-tokens --limit $${LIMIT:-50} --output $${OUTPUT:-reset_tokens.csv}

# Run the agent with default goals
run:
	$(PY) -m src.agent_system

# Web dashboard
web:
	$(PY) -m src.agent_system fastapi_app

# API server
api:
	uvicorn src.agent_system.fastapi_app:app --reload

# Distributed worker
worker:
	PYTHONPATH=src $(PY) -m agent_system.worker --queue $(WORKER_QUEUE)

# Interactive terminal
interactive:
	$(PY) -m src.agent_system --interactive

# Infrastructure commands removed (no Docker Compose in this project)

health:
	@echo "🏥 Health check:"
	@curl -s http://localhost:8000/health | jq '.' || echo "API not responding"
	@echo "Redis status: skipping container check (no docker-compose); ensure REDIS_URL is configured if required"

# Readiness check
bootstrap-check:
	PYTHONPATH=src $(PY) scripts/bootstrap_check.py

# RBAC helper: grant role to a user (usage: make grant-role USER=alice ROLE=admin)
grant-role:
	@if [ -z "$(USER)" ] || [ -z "$(ROLE)" ]; then \
		echo "Usage: make grant-role USER=<username|email> ROLE=<admin|manager|user|guest>"; \
		exit 1; \
	fi
	PYTHONPATH=src $(PY) scripts/grant_role.py --username $(USER) --role $(ROLE)

# Provider configuration (CLI shortcuts)
provider-show:
	PYTHONPATH=src $(PY) scripts/search_providers_cli.py --show

# Set provider order: make provider-set-order ORDER=serpapi,bing,google
provider-set-order:
	@if [ -z "$(ORDER)" ]; then \
		echo "Usage: make provider-set-order ORDER=serpapi,bing,google"; \
		exit 1; \
	fi
	PYTHONPATH=src $(PY) scripts/search_providers_cli.py --set-order $(ORDER)

# Disable providers: make provider-disable DISABLE=google
provider-disable:
	@if [ -z "$(DISABLE)" ]; then \
		echo "Usage: make provider-disable DISABLE=google"; \
		exit 1; \
	fi
	PYTHONPATH=src $(PY) scripts/search_providers_cli.py --disable $(DISABLE)

# Kubernetes commands removed (no Kubernetes manifests in this project)

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
	@echo "Development:"
	@echo "  install     - Install dependencies"
	@echo "  dev         - Development installation"
	@echo "  lint        - Code linting"
	@echo "  format      - Code formatting"
	@echo "  typecheck   - Type checking"
	@echo "  test        - Run tests"
	@echo "  cov         - Test coverage"
	@echo "  ci          - Full CI pipeline"
	@echo ""
	@echo "Running:"
	@echo "  run         - Run agent with default goals"
	@echo "  web         - Start web dashboard"
	@echo "  api         - Start API server"
	@echo "  interactive - Interactive terminal mode"
	@echo ""
	@echo "Utilities:"
	@echo "  health      - System health check"
	@echo "  clean       - Clean build artifacts"
	@echo "  help        - Show this help"
