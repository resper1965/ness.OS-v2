# ================================================
# n.infraops — Dockerfile (Backend API)
# Multi-stage build: slim + sem root
# ================================================
FROM python:3.12-slim AS base

# Metadados
LABEL maintainer="ness. <ops@ness.com.br>"
LABEL description="n.infraops AIOps Backend"

# Variáveis de build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependências de sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Usuário não-root
RUN groupadd -r nessops && useradd -r -g nessops -d /app -s /sbin/nologin nessops

WORKDIR /app

# Instalar dependências Python (layer cache)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY backend/ .

# Trocar para usuário não-root
USER nessops

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Porta da API
EXPOSE 8000

# Comando padrão: uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
