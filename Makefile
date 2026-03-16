.PHONY: help setup setup-compose install lint format typecheck test run list-tasks doctor \
        compose-up compose-down compose-logs clean

# ---------------------------------------------------------------------------
# Default target
# ---------------------------------------------------------------------------
help:
	@echo ""
	@echo "strands-multi-engineer-agent — available targets"
	@echo "─────────────────────────────────────────────────"
	@echo "  setup          Bootstrap: create .venv, copy .env, install deps (native)"
	@echo "  setup-compose  Bootstrap + Docker/Docker Compose checks"
	@echo "  install        Install deps into .venv (pip or uv)"
	@echo "  lint           Run ruff linter"
	@echo "  format         Run ruff formatter"
	@echo "  typecheck      Run mypy"
	@echo "  test           Run pytest"
	@echo "  run            Run the agent with DEFAULT_PROVIDER"
	@echo "  list-tasks     List available engineering tasks"
	@echo "  doctor         Validate environment and config"
	@echo "  compose-up     Start Ollama service (build agent image)"
	@echo "  compose-down   Stop all Docker Compose services"
	@echo "  compose-logs   Tail Docker Compose logs"
	@echo "  clean          Remove build artifacts and caches"
	@echo ""

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
setup:
	@bash scripts/bootstrap.sh --runtime native

setup-compose:
	@bash scripts/bootstrap.sh --runtime compose

install:
	@if command -v uv > /dev/null 2>&1; then \
		echo "→ Installing with uv into .venv"; \
		uv pip install --python .venv/bin/python -e ".[dev]"; \
	else \
		echo "→ Installing with pip into .venv"; \
		.venv/bin/pip install -e ".[dev]"; \
	fi

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------
lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy agent providers tools tasks eval

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
test:
	pytest -v

# ---------------------------------------------------------------------------
# Agent CLI shortcuts
# ---------------------------------------------------------------------------
run:
	agent run

list-tasks:
	agent list-tasks

doctor:
	agent doctor

# ---------------------------------------------------------------------------
# Docker Compose
# ---------------------------------------------------------------------------
compose-up:
	docker compose up ollama -d --build

compose-down:
	docker compose down

compose-logs:
	docker compose logs -f ollama

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/
	@echo "→ Clean done"
