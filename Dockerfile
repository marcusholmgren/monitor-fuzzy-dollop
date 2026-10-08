FROM python:3.14-slim

# Prevent Python from writing bytecode and ensure stdout/stderr are unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src" \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install uv binary from the official image for fast, reliable package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency specifications first to leverage Docker layer caching
COPY pyproject.toml uv.lock* requirements*.txt ./

# Install dependencies (supports uv.lock, requirements.txt, or pyproject.toml)
RUN if [ -f uv.lock ]; then \
        uv sync --frozen --no-install-project; \
    elif [ -f requirements.txt ]; then \
        uv pip install --system --no-cache -r requirements.txt; \
    elif [ -f pyproject.toml ]; then \
        uv pip install --system --no-cache .; \
    fi

# Copy the application source code
COPY . .

# Finalize project installation if uv.lock or pyproject.toml is present
RUN if [ -f uv.lock ]; then \
        uv sync --frozen; \
    elif [ -f pyproject.toml ]; then \
        uv pip install --system --no-cache --no-deps .; \
    fi

# Ensure executables from uv virtualenv or system are on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose FastAPI default port
EXPOSE 8000

# Health check using Python's standard library
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# Default command to run FastAPI
CMD ["fastapi", "run", "src/monitor_fuzzy_dollop/main.py", "--host", "0.0.0.0", "--port", "8000"]
