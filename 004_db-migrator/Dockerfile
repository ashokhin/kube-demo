FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --upgrade pip && \
    pip install --no-cache-dir "poetry-core>=1.0.0"

COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir --prefix=/install .


FROM python:3.12-slim AS runtime

RUN useradd --no-create-home --shell /bin/false appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /build/src ./src

USER appuser

# Job: runs alembic migrations and exits
CMD ["alembic", "--config", "src/alembic.ini", "upgrade", "head"]
