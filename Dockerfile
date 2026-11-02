FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --no-dev --no-install-project

COPY alembic.ini ./
COPY src ./src
COPY seeds ./seeds
COPY normalizacao ./normalizacao
COPY curadoria ./curadoria
RUN uv sync --no-dev

# Processo padrão: API. O worker sobrescreve o comando (ver docker-compose.yml).
CMD ["uvicorn", "votosbr.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
