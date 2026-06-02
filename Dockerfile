# ============================================================
# Backend — FastAPI + LangGraph
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (layer caching)
COPY requirements-minimal.txt .
RUN pip install --no-cache-dir -r requirements-minimal.txt

# Application code (.dockerignore keeps out the junk)
COPY . .

# Non-root user
RUN groupadd -r bettafish && useradd -r -g bettafish bettafish \
    && mkdir -p /app/logs /app/var \
    && chown -R bettafish:bettafish /app
USER bettafish

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:9000/api/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "9000"]
