FROM python:3.12-slim

WORKDIR /app

COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/app.txt

COPY src/ src/
COPY app.py .

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.headless=true"]
