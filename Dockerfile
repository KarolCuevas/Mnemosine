FROM node:24-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src
RUN npm run build

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STORAGE_ROOT=/data \
    SESSION_COOKIE_SECURE=true \
    MNEMOSINE_DROP_PRIVILEGES=1
WORKDIR /opt/mnemosine/backend
COPY backend/requirements.lock.txt ./
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.lock.txt \
    && groupadd --gid 10001 mnemosine \
    && useradd --uid 10001 --gid 10001 --no-create-home mnemosine
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY database/migrations /opt/mnemosine/database/migrations
COPY --from=frontend /build/frontend/dist /opt/mnemosine/frontend/dist
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8080')+'/api/ready',timeout=8)"
CMD ["python", "-m", "scripts.serve"]
