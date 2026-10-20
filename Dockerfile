# Imagen para Hugging Face Spaces, Azure App Service o cualquier servidor con Docker
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Hugging Face usa el puerto 7860; Azure y otros pueden cambiarlo con la variable PORT
ENV PORT=7860
EXPOSE 7860
CMD gunicorn app:server --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 --preload
