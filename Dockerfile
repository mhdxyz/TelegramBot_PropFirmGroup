# Deployment-independent: this image runs the same way on Cloud Run, a
# plain VPS with Docker, or any other container-capable host. The only
# contract is "serve HTTP on $PORT" — nothing here assumes a specific
# platform.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:create_asgi_app --factory --host 0.0.0.0 --port ${PORT}"]
