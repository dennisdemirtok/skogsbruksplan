.PHONY: dev stop db-reset migrate shell logs test lint build clean help

# Default target
help: ## Show this help message
	@echo "SkogsplanSaaS - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""

dev: ## Start all services with build
	docker-compose up --build

dev-d: ## Start all services in background with build
	docker-compose up --build -d

stop: ## Stop all services
	docker-compose down

stop-v: ## Stop all services and remove volumes
	docker-compose down -v

build: ## Build all Docker images
	docker-compose build

db-reset: ## Drop and recreate the database
	docker-compose down -v
	docker volume rm -f skogsplanering_postgres_data 2>/dev/null || true
	docker-compose up -d db
	@echo "Waiting for database to be ready..."
	@sleep 5
	docker-compose exec db psql -U skogsplan -d skogsplan -f /docker-entrypoint-initdb.d/01-init.sql
	@echo "Database reset complete."

migrate: ## Run Alembic migrations
	docker-compose exec backend alembic upgrade head

migrate-create: ## Create a new Alembic migration (usage: make migrate-create MSG="description")
	docker-compose exec backend alembic revision --autogenerate -m "$(MSG)"

shell: ## Open psql shell to the database
	docker-compose exec db psql -U skogsplan -d skogsplan

shell-backend: ## Open a bash shell in the backend container
	docker-compose exec backend bash

shell-frontend: ## Open a sh shell in the frontend container
	docker-compose exec frontend sh

logs: ## Follow logs for all services
	docker-compose logs -f

logs-backend: ## Follow backend logs
	docker-compose logs -f backend

logs-frontend: ## Follow frontend logs
	docker-compose logs -f frontend

logs-db: ## Follow database logs
	docker-compose logs -f db

test: ## Run pytest in the backend container
	docker-compose exec backend python -m pytest tests/ -v

test-cov: ## Run pytest with coverage report
	docker-compose exec backend python -m pytest tests/ -v --cov=app --cov-report=term-missing

lint: ## Run linters (ruff for Python, eslint for TypeScript)
	docker-compose exec backend python -m ruff check app/ tests/
	docker-compose exec frontend npx eslint src/ --ext .ts,.tsx

lint-fix: ## Run linters with auto-fix
	docker-compose exec backend python -m ruff check app/ tests/ --fix
	docker-compose exec frontend npx eslint src/ --ext .ts,.tsx --fix

format: ## Format code (ruff for Python, prettier for TypeScript)
	docker-compose exec backend python -m ruff format app/ tests/
	docker-compose exec frontend npx prettier --write src/

clean: ## Remove all containers, volumes, and built images
	docker-compose down -v --rmi local
	docker system prune -f
