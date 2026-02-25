#!/bin/sh
# Entrypoint: arranca Ollama, descarga el modelo y lanza Streamlit.

ollama serve &

echo "Esperando a que Ollama esté listo..."
until ollama list > /dev/null 2>&1; do
  sleep 1
done

if ! ollama list | grep -q "qwen2.5:3b"; then
  echo "Descargando qwen2.5:3b..."
  ollama pull qwen2.5:3b
fi

echo "Ollama listo con qwen2.5:3b"

exec streamlit run app.py \
  --server.port=8080 \
  --server.address=0.0.0.0 \
  --server.headless=true
