FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/
COPY examples/ examples/
COPY README.md .

RUN pip install --no-cache-dir .

FROM python:3.12-slim

WORKDIR /app

# Non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/workspaces && \
    chown -R appuser:appuser /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "gitpilot.main", "--host", "0.0.0.0", "--port", "8000"]
