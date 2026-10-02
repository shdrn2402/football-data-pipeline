FROM python:3.13.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

RUN groupadd -r ingest_group && useradd -r -g ingest_group --no-create-home --shell /bin/false ingest_user

WORKDIR /app

RUN chown -R ingest_user:ingest_group /app

USER ingest_user

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --chown=ingest_user:ingest_group "pyproject.toml" "uv.lock" ".python-version" ./

RUN uv sync --frozen --no-dev --no-cache

COPY --chown=ingest_user:ingest_group configs/ configs/

COPY --chown=ingest_user:ingest_group src/ src/

# ENTRYPOINT ["python", "/app/src/ingest.py"]