UV ?= uv
APP ?= abel_cap_server.main:app
HOST ?= 0.0.0.0
PORT ?= 8000

.PHONY: help install init-env run dev test test-verbose lint format check clean

help: ## Show available targets
	@awk 'BEGIN {FS = ": ## "}; /^[a-zA-Z0-9_-]+: ## / {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install project and dev dependencies with uv
	$(UV) sync --dev

init-env: ## Create .env from .env.example if it does not exist
	@test -f .env || cp .env.example .env

run: ## Run the API with the project entrypoint
	$(UV) run python -m abel_cap_server.main

dev: ## Run the API with auto-reload
	$(UV) run uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

test: ## Run the test suite
	$(UV) run pytest -q

test-verbose: ## Run the test suite with full output
	$(UV) run pytest

lint: ## Run Ruff checks
	$(UV) run ruff check .

format: ## Format the codebase with Ruff
	$(UV) run ruff format .

check: ## Run lint and tests
	$(MAKE) lint
	$(MAKE) test

clean: ## Remove local caches
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist htmlcov cap_reference.egg-info .coverage
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
