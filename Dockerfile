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
ENV PORT=8000

EXPOSE 8000
# Start web server directly; run migrations separately as a one-off task/job
CMD echo BOOT source=Dockerfile && echo BOOT launch_gunicorn PORT=$PORT FLASK_ENV=$FLASK_ENV && exec gunicorn --workers 1 --bind 0.0.0.0:$PORT --timeout 120 --log-level info --access-logfile - --error-logfile - --capture-output run:app
