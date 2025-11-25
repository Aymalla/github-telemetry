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
help:
	@echo "GitHub Telemetry - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install production dependencies"
	@echo "  install-dev      Install development dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             Run linter (ruff check)"
	@echo "  format           Format code (ruff format)"
	@echo "  typecheck        Run type checker (mypy)"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run tests"
	@echo "  test-cov         Run tests with coverage report"
	@echo ""
	@echo "Docker:"
	@echo "  build-frontend   Build frontend Docker image"
	@echo "  build-backend    Build backend Docker image"
	@echo "  build            Build all Docker images"
	@echo ""
	@echo "Run Locally:"
	@echo "  run-frontend     Run frontend service locally"
	@echo "  run-backend      Run backend service locally"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean            Remove build artifacts and cache files"

# Setup
install:
	pip install .

install-dev:
	pip install -e ".[dev]"

# Code Quality
lint:
	ruff check src tests

format:
	ruff format src tests
	ruff check --fix src tests

typecheck:
	mypy src

# Testing
test:
	pytest

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term

# Docker
build-frontend:
	docker build -f src/frontend/Dockerfile -t gh-telemetry-frontend .

publish-frontend: # to container registry
	az acr login --name $(CONTAINER_REGISTRY)
	docker build -f src/frontend/Dockerfile -t $(CONTAINER_REGISTRY)/gh-telemetry-frontend:latest .
	docker push $(CONTAINER_REGISTRY)/gh-telemetry-frontend:latest

build-backend:
	docker build -f src/backend/Dockerfile -t gh-telemetry-backend .

publish-backend: # to container registry
	az acr login --name $(CONTAINER_REGISTRY)
	docker build -f src/backend/Dockerfile -t $(CONTAINER_REGISTRY)/gh-telemetry-backend:latest .
	docker push $(CONTAINER_REGISTRY)/gh-telemetry-backend:latest

build: build-frontend build-backend

# Run Locally
run-frontend:
	python -m uvicorn src.frontend.app:app --host 0.0.0.0 --port 8080 --reload

run-backend:
	python -m src.backend.app

# Cleanup
clean:
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .mypy_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
