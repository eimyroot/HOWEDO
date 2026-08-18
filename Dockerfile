# syntax=docker/dockerfile:1

FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS runtime

ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system --gid 10001 howedo \
    && useradd \
        --system \
        --uid 10001 \
        --gid howedo \
        --home-dir /nonexistent \
        --shell /usr/sbin/nologin \
        howedo

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install '.[api]' \
    && python -m pip check

USER 10001:10001

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=3s \
    --start-period=5s \
    --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()" \
    || exit 1

CMD ["uvicorn", "howedo.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
