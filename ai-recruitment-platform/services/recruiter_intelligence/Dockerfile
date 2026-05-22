FROM python:3.11-slim AS builder
WORKDIR /app
COPY services/recruiter_intelligence/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY common/ /app/common/
COPY services/recruiter_intelligence/ /app/services/recruiter_intelligence/
ENV PYTHONPATH=/app
EXPOSE 8002
RUN adduser --disabled-password appuser && chown -R appuser /app
USER appuser
CMD ["uvicorn", "services.recruiter_intelligence.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "2"]
