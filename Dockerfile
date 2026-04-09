FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Node for CSS build
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
# Run migrations then start — DATABASE_URL and PORT are injected by Railway
CMD flask db upgrade && gunicorn -w 4 -b 0.0.0.0:${PORT:-8000} run:app
