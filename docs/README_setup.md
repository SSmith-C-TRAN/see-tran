# Deployment Guide

See-Tran is designed to deploy on [Railway](https://railway.com) with a managed PostgreSQL database. It also runs on any platform that supports Docker.

---

## Railway (recommended)

1. Create a new Railway project and connect your GitHub repo
2. Add a **PostgreSQL** service — Railway injects `DATABASE_URL` automatically
3. Set environment variables in Railway's dashboard:

```
SECRET_KEY=<random string>
CLAUDE_API_KEY=sk-ant-...        # Required for agent features
DB_TYPE=postgres
FLASK_ENV=production
```

4. Push to deploy — Railway builds the Dockerfile, runs `flask db upgrade`, and starts Gunicorn via `railway.toml`

The `healthcheckPath = "/health"` in `railway.toml` requires a `/health` route (returns 200). Add it to `run.py` if not present.

---

## Docker (self-hosted)

```bash
# Local development with PostgreSQL
docker compose up

# Production build
docker build -t see-tran .
docker run -p 8000:8000 \
  -e SECRET_KEY=your-secret \
  -e DATABASE_URL=postgresql://... \
  -e FLASK_ENV=production \
  see-tran
```

`docker-compose.yml` starts both a `postgres:16` container and the web app. The web container runs migrations at startup.

---

## Environment variables

See `.env.example` at the repo root for the full list. Minimum required:

| Variable | Required | Notes |
|----------|----------|-------|
| `SECRET_KEY` | Yes | Any random string |
| `DATABASE_URL` | Prod | PostgreSQL URL; defaults to SQLite in dev |
| `DB_TYPE` | Prod | Set to `postgres` when using PostgreSQL |
| `CLAUDE_API_KEY` | Agents | Anthropic API key for agent features |
| `FLASK_ENV` | Prod | Set to `production` |

---

## First-time setup

After deploying, run these once (or include in a Railway release command):

```bash
flask db upgrade    # Apply all migrations
flask seed all      # Optional: load sample data
```

---

## Local development

See `CONTRIBUTING.md` for the full local dev setup guide.
