# Stage 1: Build Next.js frontend
FROM node:24-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install

COPY frontend/ .
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim AS runner
WORKDIR /app

# Install uv
RUN pip install uv --no-cache-dir

# Copy lockfile and project metadata first (layer caching)
COPY backend/pyproject.toml backend/uv.lock ./

# Install Python dependencies from lockfile (no dev deps)
RUN uv sync --frozen --no-dev

# Copy backend application code
COPY backend/ .

# Copy built Next.js static export into static/ so FastAPI can serve it
COPY --from=frontend-builder /app/frontend/out ./static

# Ensure db directory exists for SQLite volume mount
RUN mkdir -p /app/db

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
