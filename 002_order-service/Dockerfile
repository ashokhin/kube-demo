FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --upgrade pip

# Copy requirements first so this layer is cached as long as requirements.txt
# does not change. Source code changes do not invalidate this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim AS runtime

RUN useradd --no-create-home --shell /bin/false appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY src/ ./src

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
