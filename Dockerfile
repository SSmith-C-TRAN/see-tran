FROM python:3.12-slim

WORKDIR /app

# Install system deps + Node 20 LTS via NodeSource in one layer
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=run.py

EXPOSE 8000
# Run migrations then start — DATABASE_URL and PORT are injected by Railway
CMD flask db upgrade && gunicorn -w 4 -b 0.0.0.0:${PORT:-8000} run:app
