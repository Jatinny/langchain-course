FROM python:3.11-slim AS builder
WORKDIR /app
COPY services/analytics_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY common/ /app/common/
COPY agents/ /app/agents/
COPY data/ /app/data/
COPY services/analytics_service/ /app/services/analytics_service/
ENV PYTHONPATH=/app
EXPOSE 8006
RUN adduser --disabled-password appuser && chown -R appuser /app
USER appuser
CMD ["uvicorn", "services.analytics_service.main:app", "--host", "0.0.0.0", "--port", "8006", "--workers", "2"]
