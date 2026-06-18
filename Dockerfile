# ── Stage 1: build do SPA React (frontend/) ─────────────────────────────────────
FROM node:22-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: API Python + serve o SPA buildado ──────────────────────────────────
FROM python:3.12-slim
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# dist do React (servido por app/main.py em /)
COPY --from=frontend /web/dist ./frontend/dist
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
