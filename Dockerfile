FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PORT=8000

WORKDIR /app

# ── Layer 1: install dependencies only (cached until pyproject/lockfile change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ── Layer 2: copy source and install the project (creates the dishlist script)
COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

CMD ["sh", "-c", "dishlist serve --host 0.0.0.0 --port ${PORT:-8000} --no-reload"]
