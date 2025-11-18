FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  UV_LINK_MODE=copy \
  PORT=8000

WORKDIR /app

# Install project dependencies using uv
COPY pyproject.toml uv.lock ./ 
RUN uv sync --frozen --no-dev

# Copy the rest of the application code
COPY . .

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
