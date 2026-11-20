# FinSight AI — Developer & Deployment Commands
# Usage: make <target>

.PHONY: help dev dev-llm prod test test-backend test-frontend build lint clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Local development ──────────────────────────────────────────────────────────

dev:  ## Start full local stack (backend + frontend + postgres)
	docker compose up --build

dev-llm:  ## Start local stack + Ollama for local LLM fallback
	docker compose --profile local-llm up --build

dev-bg:  ## Start local stack in the background
	docker compose up --build -d

logs:  ## Stream all service logs
	docker compose logs -f

# ── Testing ────────────────────────────────────────────────────────────────────

test-backend:  ## Run all 95 backend tests
	cd backend && .venv/Scripts/pytest -q --cov=app --cov-report=term-missing

test-frontend:  ## Run all 11 frontend tests + typecheck + build
	cd frontend && npx vitest run && npx tsc -b && npx vite build

test:  ## Run all tests (backend + frontend)
	$(MAKE) test-backend
	$(MAKE) test-frontend

llm-eval:  ## Run LLMOps reliability harness (simulates provider outages)
	cd backend && .venv/Scripts/python scripts/eval_llm_router.py

# ── Production ─────────────────────────────────────────────────────────────────

build:  ## Build all Docker images for production
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

prod:  ## Deploy production stack (requires .env.prod)
	docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build

prod-logs:  ## Stream production logs
	docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

prod-down:  ## Stop production stack
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down

prod-restart:  ## Rolling restart of production backend
	docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend

# ── Database ────────────────────────────────────────────────────────────────────

db-shell:  ## Open a psql shell in the local db container
	docker compose exec db psql -U finsight -d finsight

db-schema:  ## Re-apply schema to local db (idempotent)
	docker compose exec db psql -U finsight -d finsight -f /docker-entrypoint-initdb.d/01_schema.sql

# ── Utilities ───────────────────────────────────────────────────────────────────

clean:  ## Remove all containers, volumes and cached images
	docker compose down -v --remove-orphans
	docker image prune -f

lint:  ## Lint backend Python (ruff)
	cd backend && .venv/Scripts/ruff check app tests
