FROM python:3.13-slim

WORKDIR /app

# Limit memory usage for Render (512MB RAM free tier)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 \
    TORCH_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2 \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU-only build first (only ~140MB vs 2.5GB CUDA packages)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Bind dynamically to $PORT provided by Render or default to 8000
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
