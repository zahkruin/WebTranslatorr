FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Incluir .env.example como referencia para usuarios de la imagen prebuilt
COPY .env.example /app/.env.example

# Puerto expuesto
EXPOSE 9811

# Comando de inicio: crea directorio data/ si no existe y arranca la app
CMD ["sh", "-c", "mkdir -p /app/data && python main.py"]
