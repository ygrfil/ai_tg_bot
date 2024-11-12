FROM python:3.13-slim

WORKDIR /app

# Install only required system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY bot/ bot/
COPY main.py .

# Create data directory for persistence
RUN mkdir -p data

# Run as non-root user for security
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

CMD ["python", "main.py"] 