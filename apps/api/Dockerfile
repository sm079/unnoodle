# The API, the worker and the migrations share this image; deploy/compose.yml picks what each container runs.
FROM python:3.14-slim

# ffmpeg cuts uploaded clips and makes video posters (app.video)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /usr/local/bin/uv

# app.settings looks for .env three folders above app/, so the layout mirrors the repo's. There is no .env in the
# image; settings come from the container's environment.
WORKDIR /srv/apps/api

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    UNNOODLE_MEDIA_DIR=/data/media

# Dependencies first, so a code change doesn't reinstall them
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

RUN useradd --system --uid 10001 unnoodle && mkdir -p /data/media && chown unnoodle /data/media
USER unnoodle

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
