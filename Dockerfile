FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml .
RUN mkdir -p src/lunchbox && touch src/lunchbox/__init__.py && \
    pip install --no-cache-dir -e .

# Copy source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "lunchbox.main:app", "--host", "0.0.0.0", "--port", "8000"]
