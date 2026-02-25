FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema para Ollama
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Instalar Ollama (verificar integridad del script)
RUN curl -fsSL https://ollama.com/install.sh -o /tmp/ollama-install.sh && \
    sh /tmp/ollama-install.sh && \
    rm /tmp/ollama-install.sh

# Crear usuario no-root para runtime
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /usr/local/bin/ollama

COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/app.txt

COPY src/ src/
COPY app.py .
COPY infra/ollama-entrypoint.sh /ollama-entrypoint.sh
RUN chmod +x /ollama-entrypoint.sh

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=300s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/_stcore/health')" || exit 1

ENTRYPOINT ["/ollama-entrypoint.sh"]
