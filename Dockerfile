FROM python:3.10-slim

WORKDIR /app

# Prevenir generación de archivos .pyc e impresion inmediata de logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente del microservicio
COPY main.py .

# Puerto interno del contenedor
EXPOSE 8000

# Comando para ejecutar la API REST con Swagger activo
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
