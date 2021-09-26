FROM python:3.11-slim AS base

RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/
RUN mkdir -p reports && chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import yaml; print('ok')"

CMD ["python", "src/analyzer.py", "--config", "config/accounts.yaml"]
