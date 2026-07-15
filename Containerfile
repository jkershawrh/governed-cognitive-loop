# Stage 1: Build the frontend
FROM node:20-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.11-slim
WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY gcl/ gcl/
COPY config/ config/
COPY fixtures/ fixtures/
COPY --from=frontend-build /build/dist frontend/dist/

RUN useradd --uid 1001 --no-create-home appuser \
    && chown -R 1001:0 /app
USER 1001

EXPOSE 8000

# Cooldown, pending-outcome, and cycle state are process-local. Keep one worker
# until those safety controls are backed by shared durable storage.
CMD ["uvicorn", "gcl.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
