# syntax=docker/dockerfile:1

# --- Build stage ---
    FROM python:3.13-slim AS builder

    WORKDIR /app
    
    # Install build dependencies including WeasyPrint requirements
    RUN apt-get update && apt-get install -y \
        build-essential \
        libpq-dev \
        netcat-openbsd \
        python3-dev \
        python3-cffi \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi-dev \
        shared-mime-info \
        && rm -rf /var/lib/apt/lists/*
    
    COPY requirements.txt ./requirements.txt
    
    RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt
    
    # --- Runtime stage ---
    FROM python:3.13-slim
    
    ENV PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1
    
    WORKDIR /app
    
    # System deps including WeasyPrint runtime dependencies
    RUN apt-get update && apt-get install -y \
        libpq-dev \
        netcat-openbsd \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        shared-mime-info \
        && rm -rf /var/lib/apt/lists/*
    
    # Copy installed packages from builder
    COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
    COPY --from=builder /usr/local/bin /usr/local/bin
    
    # Copy project files
    COPY . /app
    
    # Create static/media dirs
    RUN mkdir -p /app/staticfiles /app/media
    
    # Expose port (Daphne default 8000)
    EXPOSE 8000
    
    # Entrypoint script for migrations, collectstatic, etc.
    COPY docker/entrypoint.sh /entrypoint.sh
    RUN chmod +x /entrypoint.sh
    
    # Default: daphne for ASGI (channels), fallback to gunicorn for WSGI
    CMD ["/entrypoint.sh"]