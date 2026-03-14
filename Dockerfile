FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (git for GitPython, curl for healthchecks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

# Install external dependencies first (layer-cached separately from source)
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Install local packages (indexing, api, workers, etc.) into site-packages
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
