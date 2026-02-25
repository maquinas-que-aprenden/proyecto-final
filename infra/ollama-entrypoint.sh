#!/bin/sh
# Entrypoint: arranca Ollama, descarga el modelo y lanza Streamlit.

ollama serve &

echo "Esperando a que Ollama esté listo..."
WAIT_SECONDS=0
MAX_WAIT=60
until ollama list > /dev/null 2>&1; do
  if [ "$WAIT_SECONDS" -ge "$MAX_WAIT" ]; then
    echo "ERROR: Ollama no respondió después de ${MAX_WAIT}s. Abortando." >&2
    exit 1
  fi
  sleep 1
  WAIT_SECONDS=$((WAIT_SECONDS + 1))
done

if ! ollama list | grep -q "qwen2.5:3b"; then
  echo "Descargando qwen2.5:3b..."
  if ! ollama pull qwen2.5:3b; then
    echo "ERROR: No se pudo descargar qwen2.5:3b. Abortando." >&2
    exit 1
  fi
fi

echo "Ollama listo con qwen2.5:3b"

exec streamlit run app.py \
  --server.port=8080 \
  --server.address=0.0.0.0 \
  --server.headless=true
