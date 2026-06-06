# Multi-stage build for Ella's web layer — no local Node/npm needed.
# Stage 1 builds the React/React Flow canvas; stage 2 serves it together with the
# FastAPI backend (ella-web). Build context is the repo root.

# --- stage 1: build the frontend ---
FROM node:22-alpine AS frontend
WORKDIR /app
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/frontend/ ./
RUN npm run build

# --- stage 2: backend that serves the API + the built canvas ---
FROM python:3.12-slim
WORKDIR /srv
COPY ingestion/ /srv/ingestion/
RUN pip install --no-cache-dir -e "/srv/ingestion[web,feeds]"
COPY --from=frontend /app/dist /srv/static
COPY web/entrypoint.sh /srv/entrypoint.sh
RUN chmod +x /srv/entrypoint.sh
ENV ELLA_WEB_STATIC=/srv/static \
    ELLA_WEB_HOST=0.0.0.0 ELLA_WEB_PORT=8099 \
    OLLAMA_URL=http://host.docker.internal:11434 \
    QDRANT_URL=http://host.docker.internal:6333
EXPOSE 8099
ENTRYPOINT ["/srv/entrypoint.sh"]
