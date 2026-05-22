FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY services/api_gateway/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

FROM base AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY common/ /app/common/
COPY agents/ /app/agents/
COPY services/api_gateway/ /app/services/api_gateway/
COPY scripts/ /app/scripts/
COPY data/ /app/data/
COPY database/ /app/database/
ENV PYTHONPATH=/app
EXPOSE 8000
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
