# TEMP workaround: ghcr.io unreachable from Docker daemon; revert to pinned ghcr.io/astral-sh/uv:0.5.26-python3.12-bookworm when reachable or a registry mirror is configured (see BACKLOG BL-01).
FROM astral/uv:python3.12-bookworm AS builder

WORKDIR /repo

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY contracts/ ./contracts/
COPY scripts/ ./scripts/
COPY ai-service/ ./ai-service/

WORKDIR /repo/ai-service
RUN uv pip install --system "pyyaml>=6.0,<7.0"
RUN rm -rf /repo/ai-service/src/corp_rag_ai/contracts/generated \
    && python /repo/scripts/generate_python_contracts.py \
    && python /repo/scripts/generate_constants.py

# TEMP workaround: ghcr.io unreachable from Docker daemon; revert to pinned ghcr.io/astral-sh/uv:0.5.26-python3.12-bookworm when reachable or a registry mirror is configured (see BACKLOG BL-01).
FROM astral/uv:python3.12-bookworm AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=builder /repo/ai-service/pyproject.toml /repo/ai-service/README.md ./
RUN uv sync --no-dev --no-install-project

COPY --from=builder /repo/ai-service/src ./src
COPY --from=builder /repo/ai-service/alembic.ini ./alembic.ini
COPY --from=builder /repo/ai-service/migrations ./migrations
RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "corp_rag_ai.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
