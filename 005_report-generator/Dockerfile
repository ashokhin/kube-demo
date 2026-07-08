FROM python:3.12-slim AS builder

WORKDIR /build

# hadolint ignore=DL3013
RUN pip install --upgrade --no-cache-dir pip && \
    pip install --no-cache-dir pdm-backend

COPY pyproject.toml .
COPY src/ ./src/
COPY tests/ ./tests/
RUN pip install --no-cache-dir --prefix=/install .


FROM python:3.12-slim AS runtime

RUN useradd --no-create-home --shell /bin/false appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /build/src ./src

USER appuser

# CronJob: generates report and exits
ENTRYPOINT ["python", "-m", "src.main"]
