# Build context is the repository root: the API imports the `barca` package.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONUNBUFFERED=1

WORKDIR /srv
# Dependencies first so code changes do not invalidate the layer. Only the core
# and `api` extras are installed: the service reads the database, it never trains.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --extra api --no-install-project

COPY src ./src
COPY apps/api ./apps/api
RUN uv sync --frozen --no-dev --extra api

ENV PATH=/opt/venv/bin:$PATH
RUN useradd --system --no-create-home api
USER api
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
