.PHONY: help install install-dev lint format test test-cov build-frontend build-backend build run-frontend run-backend clean

# Load environment file if exists
ENV_FILE := .env
ifeq ($(filter $(MAKECMDGOALS),config clean),)
	ifneq ($(strip $(wildcard $(ENV_FILE))),)
		ifneq ($(MAKECMDGOALS),config)
			include $(ENV_FILE)
			export
		endif
	endif
endif

# Default target
help: ## Show this help message
	@grep -h -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Setup
install: ## Install production dependencies
	pip install .

install-dev: ## Install development dependencies
	pip install -e ".[dev]"

# Code Quality
lint: ## Run linter (ruff check)
	ruff check src tests

format: ## Format code (ruff format)
	ruff format src tests
	ruff check --fix src tests

typecheck: ## Run type checker (mypy)
	mypy src

# Testing
test: ## Run tests
	pytest

test-cov: ## Run tests with coverage report
	pytest --cov=src --cov-report=html --cov-report=term

# Docker
build-frontend: ## Build frontend Docker image locally
	docker build -f src/frontend/Dockerfile -t gh-telemetry-frontend .

publish-frontend: ## Publish frontend image to container registry
	az acr login --name $(CONTAINER_REGISTRY)
	docker build -f src/frontend/Dockerfile -t $(CONTAINER_REGISTRY)/gh-telemetry-frontend:latest .
	docker push $(CONTAINER_REGISTRY)/gh-telemetry-frontend:latest

build-backend: ## Build backend Docker image locally
	docker build -f src/backend/Dockerfile -t gh-telemetry-backend .

publish-backend: ## Publish backend image to container registry
	az acr login --name $(CONTAINER_REGISTRY)
	docker build -f src/backend/Dockerfile -t $(CONTAINER_REGISTRY)/gh-telemetry-backend:latest .
	docker push $(CONTAINER_REGISTRY)/gh-telemetry-backend:latest

build: ## Build all Docker images locally
	make build-frontend
	make build-backend

publish: ## Publish both frontend and backend images
	make publish-frontend
	make publish-backend

# Run Locally
run-frontend: ## Run frontend service locally
	python -m uvicorn src.frontend.app:app --host 0.0.0.0 --port 8080 --reload

run-backend: ## Run backend service locally
	python -m src.backend.app

start-gh-workflows-success: ## Trigger GitHub test workflows
	for i in $(shell seq 1 10); do \
		gh workflow run test-telemetry-duration.yml; \
	done

start-gh-workflows-failures: ## Trigger GitHub test workflows
	for i in $(shell seq 1 10); do \
		gh workflow run test-telemetry-failures.yml; \
	done

clean: ## Remove build artifacts and cache files
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .mypy_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
