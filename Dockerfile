# Render.com uchun Dockerfile (LibreOffice bilan)
FROM python:3.11-slim

# Tizim paketlarini o'rnatish (LibreOffice PDF konvertatsiya uchun)
RUN apt-get update && apt-get install -y \
    libreoffice \
    libxml2-dev \
    libxslt-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependency larni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kodni nusxalash
COPY . .

# Port
EXPOSE 10000

# Ishga tushirish (Production server uchun, gunicorn orqali uzun timeout bilan)
CMD ["gunicorn", "--workers", "2", "--timeout", "120", "--bind", "0.0.0.0:10000", "app:app"]
