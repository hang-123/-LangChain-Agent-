FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements-minimal.txt .
RUN pip install --no-cache-dir -r requirements-minimal.txt

# Application code
COPY . .

EXPOSE 9000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "9000"]
