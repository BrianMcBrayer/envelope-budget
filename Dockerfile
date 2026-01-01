FROM python:3.12-alpine
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/
WORKDIR /app
ENV UV_NO_DEV=1
ENV UV_LINK_MODE=copy
RUN apk add --no-cache supervisor
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
ENV PATH="/app/.venv/bin:$PATH"
COPY docker/supervisord.conf /etc/supervisord.conf
COPY docker/cron/root /etc/crontabs/root
RUN chmod 0644 /etc/crontabs/root

EXPOSE 5000
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
