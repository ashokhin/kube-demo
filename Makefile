# =============================================================================
# hadoop-demo Makefile
#
# All targets are designed to run from the repo root directory.
# Docker must be available on the host.
# MOCK_MODE=true is set in .env.example files — no real Hadoop/Oracle needed locally.
# =============================================================================

REGISTRY  := nexus.company.internal
PROJECT   := hadoop-demo

PYTHON_SERVICES := \
    002_risk-engine \
    003_spark-calculator \
    004_oracle-reporter \
    005_stream-ingestor

ALL_SERVICES := \
    001_risk-ui \
    002_risk-engine \
    003_spark-calculator \
    004_oracle-reporter \
    005_stream-ingestor

RUFF_IMAGE     := ghcr.io/astral-sh/ruff:latest
HADOLINT_IMAGE := hadolint/hadolint:latest

.PHONY: help lint lint-docker test build up down spark-job report logs

# Default target: print available targets with descriptions
help:
	@echo ""
	@echo "hadoop-demo — available targets:"
	@echo ""
	@echo "  help          Print this help message (default)"
	@echo "  lint          Run ruff linter on all Python service src/ directories"
	@echo "  lint-docker   Run hadolint on all Dockerfiles"
	@echo "  test          Build builder stage and run pytest for all Python services"
	@echo "  build         Build Docker images for all services"
	@echo "  up            Start risk-ui and risk-engine with docker compose (detached)"
	@echo "  down          Stop and remove all containers"
	@echo "  spark-job     Run spark-calculator as a one-off Docker container (simulates K8s Job)"
	@echo "  report        Run oracle-reporter as a one-off Docker container (simulates CronJob)"
	@echo "  logs          Tail logs from all running services"
	@echo ""

# Run ruff linter for each Python service.
lint:
	@for svc in $(PYTHON_SERVICES); do \
	    echo "==> Linting $$svc/src/"; \
	    docker run --rm \
	        -v "$$(pwd)/$$svc:/src" -w /src \
	        $(RUFF_IMAGE) \
	        check src/; \
	done

# Run hadolint on all Dockerfiles (including Dockerfile.migrate where present).
lint-docker:
	@for svc in $(ALL_SERVICES); do \
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

# Build the builder stage and run pytest for each Python service.
# 001_risk-ui is a Spring Boot app — tested separately via Maven.
test:
	@for svc in $(PYTHON_SERVICES); do \
	    img="$(REGISTRY)/$(PROJECT)/$$(basename $$svc | sed 's/^[0-9]*_//')"; \
	    sha="$$(git rev-parse --short HEAD 2>/dev/null || echo local)"; \
	    echo "==> Testing $$svc (image: $$img:test-$$sha)"; \
	    docker build \
	        --target builder \
	        --tag "$$img:test-$$sha" \
	        "$$svc"; \
	    docker run --rm \
	        --env MOCK_MODE=true \
	        "$$img:test-$$sha" \
	        sh -c "pytest tests/ -v --tb=short"; \
	    docker rmi "$$img:test-$$sha" || true; \
	done
	@echo "==> Testing 001_risk-ui (Maven)"
	@docker run --rm \
	    -v "$$(pwd)/001_risk-ui:/app" -w /app \
	    -v "$$HOME/.m2:/root/.m2" \
	    maven:3.9-eclipse-temurin-21 \
	    mvn test -q

# Build Docker images for all services (final production stage).
build:
	@for svc in $(ALL_SERVICES); do \
	    img="$(REGISTRY)/$(PROJECT)/$$(basename $$svc | sed 's/^[0-9]*_//')"; \
	    echo "==> Building $$svc -> $$img:latest"; \
	    docker build --tag "$$img:latest" "$$svc"; \
	done

# Start long-running services (risk-ui + risk-engine) in background.
# spark-calculator and oracle-reporter are not started here — use spark-job / report.
up:
	@docker compose up -d

# Stop all containers and remove networks.
down:
	@docker compose down

# Run spark-calculator as a one-off container, simulating a Kubernetes Job.
# Passes MOCK_MODE=true so no real Spark/Hive/Oracle is needed locally.
spark-job:
	@docker compose --profile jobs run --rm spark-calculator

# Run oracle-reporter as a one-off container, simulating a Kubernetes CronJob trigger.
report:
	@docker compose --profile reports run --rm oracle-reporter

# Follow logs from all running compose services.
logs:
	@docker compose logs -f
