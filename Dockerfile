FROM python:3.14-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml .
RUN mkdir -p src/lunchbox && touch src/lunchbox/__init__.py && \
    pip install --no-cache-dir .

# Copy source and reinstall without re-fetching deps (layer caching optimization)
COPY . .
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000

CMD ["uvicorn", "lunchbox.main:app", "--host", "0.0.0.0", "--port", "8000"]
