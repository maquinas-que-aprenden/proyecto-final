FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema para Ollama
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates zstd && \
    rm -rf /var/lib/apt/lists/*

# Instalar Ollama (verificar integridad del script)
# Hash de install.sh v0.17.0 — actualizar si se sube de versión
RUN curl -fsSL https://ollama.com/install.sh -o /tmp/ollama-install.sh && \
    echo "25f64b810b947145095956533e1bdf56eacea2673c55a7e586be4515fc882c9f  /tmp/ollama-install.sh" | sha256sum -c - && \
    sh /tmp/ollama-install.sh && \
    rm /tmp/ollama-install.sh

# Crear usuario no-root para runtime
RUN useradd -m -u 1000 appuser && \
    mkdir -p /home/appuser/.ollama && \
    chown -R appuser:appuser /app /usr/local/bin/ollama /home/appuser/.ollama

COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/app.txt -r requirements/classifier.txt -r requirements/finetuning.txt
RUN python -m spacy download es_core_news_sm

COPY src/ src/
COPY app.py .
COPY infra/ollama-entrypoint.sh /ollama-entrypoint.sh
RUN chmod +x /ollama-entrypoint.sh

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=300s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/_stcore/health')" || exit 1

ENTRYPOINT ["/ollama-entrypoint.sh"]
