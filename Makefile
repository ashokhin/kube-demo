# =============================================================================
# kube-demo Makefile
#
# All targets are designed to run from the repo root directory.
# Docker must be available on the host.
# =============================================================================

REGISTRY  := nexus.company.internal
PROJECT   := kube-demo

SERVICES  := \
    001_api-gateway \
    002_order-service \
    003_notification-service \
    004_db-migrator \
    005_report-generator

SERVICE_NAMES := \
    api-gateway \
    order-service \
    notification-service \
    db-migrator \
    report-generator

RUFF_IMAGE     := ghcr.io/astral-sh/ruff:latest
HADOLINT_IMAGE := hadolint/hadolint:latest

.PHONY: help lint lint-docker test build up down migrate report logs

# Default target: print available targets with descriptions
help:
	@echo ""
	@echo "kube-demo — available targets:"
	@echo ""
	@echo "  help          Print this help message (default)"
	@echo "  lint          Run ruff linter on all service src/ directories"
	@echo "  lint-docker   Run hadolint on all Dockerfiles"
	@echo "  test          Build builder stage and run pytest for all services"
	@echo "  build         Build Docker images for all services"
	@echo "  up            Start all services with docker compose (detached)"
	@echo "  down          Stop and remove all containers"
	@echo "  migrate       Run db-migrator one-off container (applies Alembic migrations)"
	@echo "  report        Run report-generator one-off container"
	@echo "  logs          Tail logs from all running services"
	@echo ""

# Run ruff code linter inside a Docker container for each service.
# No local Python installation required — matches the Jenkins Lint stage.
lint:
	@for svc in $(SERVICES); do \
	    echo "==> Linting $$svc/src/"; \
	    docker run --rm \
	        -v "$$(pwd)/$$svc:/src" -w /src \
	        $(RUFF_IMAGE) \
	        check src/; \
	done

# Run hadolint Dockerfile linter for each service.
# hadolint checks for Dockerfile best practices and common mistakes.
# Also lints Dockerfile.migrate in 002_order-service (golang-migrate init container image).
lint-docker:
	@for svc in $(SERVICES); do \
	    echo "==> Linting $$svc/Dockerfile"; \
	    docker run --rm \
	        -v "$$(pwd)/$$svc/Dockerfile:/Dockerfile" \
	        $(HADOLINT_IMAGE) \
	        hadolint /Dockerfile; \
	    if [ -f "$$svc/Dockerfile.migrate" ]; then \
	        echo "==> Linting $$svc/Dockerfile.migrate"; \
	        docker run --rm \
	            -v "$$(pwd)/$$svc/Dockerfile.migrate:/Dockerfile.migrate" \
	            $(HADOLINT_IMAGE) \
	            hadolint /Dockerfile.migrate; \
	    fi; \
	done

# Build the builder stage and run pytest inside it for each service.
# Matches the Jenkins Test stage: tests run in the same environment as the production image.
test:
	@for svc in $(SERVICES); do \
	    img="$(REGISTRY)/$(PROJECT)/$$(basename $$svc | sed 's/^[0-9]*_//')"; \
	    sha="$$(git rev-parse --short HEAD 2>/dev/null || echo local)"; \
	    echo "==> Testing $$svc (image: $$img:test-$$sha)"; \
	    docker build \
	        --target builder \
	        --tag "$$img:test-$$sha" \
	        "$$svc"; \
	    docker run --rm \
	        "$$img:test-$$sha" \
	        sh -c "pip install --no-cache-dir pytest pytest-asyncio respx && \
	               pytest tests/ -v --tb=short"; \
	    docker rmi "$$img:test-$$sha" || true; \
	done

# Build Docker images for all services (final production stage).
build:
	@for svc in $(SERVICES); do \
	    img="$(REGISTRY)/$(PROJECT)/$$(basename $$svc | sed 's/^[0-9]*_//')"; \
	    echo "==> Building $$svc -> $$img:latest"; \
	    docker build --tag "$$img:latest" "$$svc"; \
	done

# Start infrastructure and all long-running application services in the background.
up:
	@docker compose up -d

# Stop all containers and remove networks. Use `docker compose down -v` to also remove volumes.
down:
	@docker compose down

# Run db-migrator as a one-off container to apply Alembic migrations.
# Requires postgres to be running (`make up` first).
migrate:
	@docker compose --profile migration run --rm db-migrator

# Run report-generator as a one-off container.
# Requires postgres to be running (`make up` first).
report:
	@docker compose --profile reports run --rm report-generator

# Follow logs from all running compose services. Press Ctrl-C to stop.
logs:
	@docker compose logs -f
