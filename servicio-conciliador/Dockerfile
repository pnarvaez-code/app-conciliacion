# syntax=docker/dockerfile:1
# Imagen del servicio: Python con las dependencias del proyecto.
# El arranque aplica la migracion inicial si hace falta y levanta uvicorn.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
# El certificado es opcional: en entornos corporativos se monta solo durante
# esta capa de compilacion mediante BuildKit; nunca queda dentro de la imagen.
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -f /run/secrets/proxy_ca ]; then \
      PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "python -m app.inicio && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
