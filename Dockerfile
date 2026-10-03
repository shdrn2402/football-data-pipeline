FROM python:3.13.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

RUN groupadd -r ingest_group && useradd -m -r -g ingest_group --shell /bin/false ingest_user

WORKDIR /app

RUN chown -R ingest_user:ingest_group /app

USER ingest_user

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/src" \
    UV_CACHE_DIR="/tmp/.uv-cache"

COPY --chown=ingest_user:ingest_group "pyproject.toml" "uv.lock" ".python-version" ./

RUN uv sync --frozen --no-dev

COPY --chown=ingest_user:ingest_group configs/ configs/
COPY --chown=ingest_user:ingest_group src/ src/
