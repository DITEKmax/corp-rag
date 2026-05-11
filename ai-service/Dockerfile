FROM ghcr.io/astral-sh/uv:0.5.26-python3.12-bookworm AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml README.md ./
RUN uv sync --no-dev --no-install-project

COPY src ./src
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "corp_rag_ai.main:app", "--host", "0.0.0.0", "--port", "8000"]
