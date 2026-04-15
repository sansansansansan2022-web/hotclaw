FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

COPY backend /app/backend

RUN chmod +x /app/backend/scripts/docker-entrypoint.sh \
    && python -m pip install --upgrade pip \
    && python -m pip install .

EXPOSE 8140

CMD ["sh", "/app/backend/scripts/docker-entrypoint.sh"]
