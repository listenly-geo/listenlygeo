FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data
# Railway/Render fournissent $PORT ; 8000 en local.
# Un seul worker : le verrou du stockage JSON n'est valable qu'à l'intérieur d'un process.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
