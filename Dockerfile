# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_PROFILE=brev \
    BACKEND_HOST=0.0.0.0 \
    BACKEND_PORT=8000 \
    DATA_DIR=/data \
    AI_STATE_DIR=/data/ai-private \
    MEETING_MODEL_DIR=/models \
    HF_HOME=/data/cache/huggingface \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    DO_NOT_TRACK=1
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgomp1 libsndfile1 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app \
    && mkdir -p /app /data /models \
    && chown app:app /data
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
COPY ai/requirements-brev.lock.txt ai/requirements-brev.lock.txt
RUN python -m pip install --requirement backend/requirements.txt --requirement ai/requirements-brev.lock.txt \
    && python -m pip check
COPY backend/ backend/
COPY ai/ ai/
COPY contracts/ contracts/
COPY scripts/manage.py scripts/manage.py
COPY deploy/container.py deploy/healthcheck.py deploy/
COPY --from=frontend /build/frontend/dist/ frontend/dist/
USER app
EXPOSE 8000
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "/app/deploy/healthcheck.py"]
ENTRYPOINT ["python", "/app/deploy/container.py"]
