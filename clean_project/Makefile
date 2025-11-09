VENV?=.venv
PY?=$(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
DEV_REQ?=$(if $(wildcard requirements-dev.txt),requirements-dev.txt,../requirements-dev.txt)
PKG=src.agent_system
WORKER_QUEUE?=agent.jobs

.PHONY: venv install dev lint format typecheck test cov ci run web api interactive worker infra-up infra-down infra-logs infra-status health clean

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
	$(PY) -m ruff .

format:
	$(PY) -m black .

typecheck:
	$(PY) -m mypy $(PKG)

test:
	PYTHONPATH=src $(PY) -m pytest -q

cov:
	PYTHONPATH=src $(PY) -m coverage run -m pytest -q
	$(PY) -m coverage report -m

ci: lint typecheck test

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

# Infrastructure Management Commands
infra-up:
	@echo "🚀 Starting infrastructure with Docker Compose..."
	docker-compose -f config/docker-compose.yml up -d

infra-down:
	@echo "🛑 Stopping infrastructure..."
	docker-compose -f config/docker-compose.yml down

infra-logs:
	@echo "📋 Following infrastructure logs..."
	docker-compose -f config/docker-compose.yml logs -f

infra-status:
	@echo "📊 Infrastructure status:"
	@docker-compose -f config/docker-compose.yml ps

health:
	@echo "🏥 Health check:"
	@curl -s http://localhost:8000/health | jq '.' || echo "API not responding"
	@echo "Redis status:"
	@docker exec $$(docker ps -q -f name=agent_redis) redis-cli ping || echo "Redis not responding"

# Kubernetes Commands (when deployed to K8s)
k8s-deploy:
	@echo "☸️ Deploying to Kubernetes..."
	kubectl apply -f k8s/namespace/
	kubectl apply -f k8s/configmaps/
	kubectl apply -f k8s/deployments/
	kubectl apply -f k8s/services/
	kubectl apply -f k8s/ingress/

k8s-status:
	@echo "☸️ Kubernetes status:"
	@kubectl get pods -n agent-system
	@kubectl get services -n agent-system

k8s-logs:
	@echo "☸️ Kubernetes logs:"
	@kubectl logs -l app=agent-system -n agent-system --tail=100

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
	@echo "Infrastructure:"
	@echo "  infra-up    - Start infrastructure (Redis, workers, monitoring)"
	@echo "  infra-down  - Stop infrastructure"
	@echo "  infra-logs  - View infrastructure logs"
	@echo "  infra-status - Check infrastructure status"
	@echo "  health      - System health check"
	@echo ""
	@echo "Kubernetes:"
	@echo "  k8s-deploy  - Deploy to Kubernetes"
	@echo "  k8s-status  - Check K8s deployment status"
	@echo "  k8s-logs    - View K8s logs"
	@echo ""
	@echo "Utilities:"
	@echo "  clean       - Clean build artifacts"
	@echo "  help        - Show this help"
