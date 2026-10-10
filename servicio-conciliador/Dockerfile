# Imagen del servicio: Python con las dependencias del proyecto.
# El arranque aplica la migracion inicial si hace falta y levanta uvicorn.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "python -m app.inicio && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
