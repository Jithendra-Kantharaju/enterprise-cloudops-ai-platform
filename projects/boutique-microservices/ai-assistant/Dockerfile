FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal; chromadb client is pure-python over HTTP.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
