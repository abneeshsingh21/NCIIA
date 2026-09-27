FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project definition
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY run_server.py ./

# Create data and logs directories
RUN mkdir -p data/db logs

# Install python package and dependencies
RUN pip install --no-cache-dir -e .

# Environment settings
ENV PORT=8000
ENV NCIIA_API_PORT=8000
ENV NCIIA_API_HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn nciia.api.server:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
