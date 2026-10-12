FROM python:3.11.14-slim-bookworm

ARG UV_VERSION=0.11.27
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /workspace
RUN pip install --no-cache-dir "uv==${UV_VERSION}"
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --all-extras --frozen --no-dev
COPY migrations ./migrations
COPY alembic.ini ./
COPY demo ./demo

ENTRYPOINT ["uv", "run", "--frozen"]
