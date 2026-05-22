FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

FROM base AS builder
COPY services/employer_discovery/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM base AS runtime
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY common/ /app/common/
COPY agents/ /app/agents/
COPY services/employer_discovery/ /app/services/employer_discovery/
ENV PYTHONPATH=/app
EXPOSE 8001
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser
CMD ["uvicorn", "services.employer_discovery.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
