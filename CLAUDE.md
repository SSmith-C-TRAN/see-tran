# CLAUDE.md — See-Tran

Navigation guide for AI agents (Claude Code, etc.) working in this repository.

---

## What This App Does

See-Tran is an open-source web platform for modeling transit agency technology landscapes and benchmarking across agencies. Transit professionals document what systems they use (Configurations), enabling cross-agency comparison of vendors, products, and technology choices.

---

## Domain Model

Core hierarchy (read this before touching any models or routes):

```
Agency
  └── Configuration (Agency + Function + Component — the benchmark record)
        ├── ConfigurationProduct (links a Product/Version to a Configuration)
        └── ServiceType (M2M — Fixed, Rail, Paratransit, OnDemand)

FunctionalArea
  └── Function (criticality: high/medium/low)
        └── Component (system/subsystem that implements Functions — many-to-many)

Vendor
  └── Product (unique name)
        └── ProductVersion (unique per product+version string)

ServiceType  ←→  Configuration (many-to-many — which service modes a config applies to)
IntegrationPoint  ←→  Component, Product, Standard
Standard          ←→  IntegrationPoint
Tag / TagGroup    ←→  Component, IntegrationPoint

User              →   Agency (optional — agency staff)
VerifiedAgencyDomain → Agency (maps email domain to agency for auto-linking)
```

**Uniqueness constraints** (enforce these when seeding or upserting):
- `Agency.name` — unique
- `Vendor.name` — unique
- `Product.name` — unique
- `ProductVersion` — unique on `(product_id, version)`
- `Configuration` — unique on `(agency_id, function_id, component_id)`
- `VerifiedAgencyDomain.domain` — unique
- `ServiceType.name` — unique; pre-seeded with: Fixed, Rail, Paratransit, OnDemand

**Notable Agency fields:**
- `gtfs_feed_url` — public GTFS static feed URL (String, optional)
- `short_name` — used to build image file paths (e.g., `ctran` → `ctran_logo.png`)

**All models are in** [app/models/tran.py](app/models/tran.py). GTFS models are in [app/models/gtfs.py](app/models/gtfs.py) (optional, orthogonal to benchmarking).

---

## Blueprint Map

| Blueprint | File | URL prefix | Responsibility |
|-----------|------|-----------|----------------|
| `main` | [app/routes/main.py](app/routes/main.py) | `/` | Index, functional areas, components, vendors, print exports |
| `agency_bp` | [app/routes/agency.py](app/routes/agency.py) | `/agencies` | Agency detail, edit, configurations per agency |
| `config_bp` | [app/routes/configurations.py](app/routes/configurations.py) | `/configurations`, `/api/configurations` | Configuration CRUD + HTMX fragments |
| `integration_bp` | [app/routes/integrations.py](app/routes/integrations.py) | `/integrations`, `/standards` | Integration points and standards |
| `auth_bp` | [app/auth.py](app/auth.py) | `/login`, `/logout` | OAuth (Google + Microsoft), session management |
| `admin_bp` | [app/routes/admin.py](app/routes/admin.py) | `/admin` | Admin utilities, user management |

Fragment routes (HTMX partials) live inside their owning blueprint, not in a separate `/api/` blueprint.

---

## Flask CLI Commands

Run all commands from the repo root with `flask <command>`. Start the app first with `flask run`.

```bash
# Database
flask db upgrade              # Apply pending migrations
flask db migrate -m "msg"     # Generate migration from model changes

# Seeding (load JSON from /data into the database)
flask seed agencies           # Load data/agencies.json
flask seed vendors            # Load data/vendors.json
flask seed components         # Load data/components.json
flask seed functional-areas   # Load data/functional_areas.json
flask seed functions          # Load data/functions.json
flask seed configurations     # Load data/implementations.json
flask seed integrations       # Load data/integrations.json
flask seed standards          # Load data/standards.json
flask seed all                # Load all of the above in order

# Agents (research + update database records)
flask agent run agency --id <id>         # Run agency research agent for one record
flask agent run agency --all             # Run for all agencies (batch)
flask agent run vendor --id <id>         # Run vendor research agent
flask agent run component --id <id>      # Run component research agent
flask agent status                       # Show last run stats per agent type

# Admin
flask admin create-user --email <email> --admin   # Bootstrap an admin user

# GTFS (optional, separate from core benchmarking)
flask load-gtfs <directory>             # Load GTFS data from a directory
flask load-gtfs <directory> --clear     # Clear and reload
```

---

## Key Conventions

**Route naming:**
- Page routes render full Jinja templates: `/agencies/42`
- Fragment routes return HTMX partials (partial HTML): `/api/configurations/42/row`
- All JSON API endpoints live under `/api/` and return `{"ok": true, "data": {...}}`

**Template naming:**
- Full pages: `templates/<entity>.html` or `templates/<entity>/<action>.html`
- Fragments: `templates/fragments/<entity>_<fragment>.html`

**Model field patterns:**
- `additional_metadata` (JSON column) — free-form extension fields; keep structured data in real columns
- `short_name` — used to construct static file paths for logos/headers (e.g., `ctran` → `ctran_logo.png`)
- `created_at` / `updated_at` — set automatically via SQLAlchemy defaults

**Agent results:**
- Each agent module exposes a `run(record_id, *, dry_run=False) -> AgentResult` function
- `AgentResult`: `success`, `draft` (proposed field values), `diff` (vs existing), `logs`, `error`
- Agents write audit entries to `logs/agent_audit.jsonl`
- Agents use the Anthropic SDK directly — no provider abstraction layer
- Model to use: `current_app.config['AGENT_MODELS']['agency']` (etc.) — defaults to `claude-sonnet-4-20250514`

**API response format** (all `/api/` JSON endpoints):
```python
# Success
{"ok": True, "data": {...}}
# Error
{"ok": False, "error": "message", "code": 400}
```
Use `api_ok()`, `api_error()`, `api_validation_error()` from `app/utils/errors.py`.

---

## Environment Variables

Required:
```
SECRET_KEY          Flask session secret (any random string for dev)
```

Optional but needed for full functionality:
```
FLASK_ENV           development | production | testing  (default: development)
DATABASE_URL        PostgreSQL URL (if DB_TYPE=postgres)
DB_TYPE             sqlite | postgres  (default: sqlite → instance/app.db)

CLAUDE_API_KEY      Anthropic API key (required for agents)
OPENAI_API_KEY      OpenAI API key (optional, unused by default)

OAUTH_GOOGLE_CLIENT_ID / OAUTH_GOOGLE_CLIENT_SECRET
OAUTH_MS_CLIENT_ID / OAUTH_MS_CLIENT_SECRET

POSTMARK_API_KEY / POSTMARK_SENDER_EMAIL   Email notifications
SUPER_ADMIN_EMAIL                           Bypass all auth checks

# Agent model overrides (default: claude-sonnet-4-20250514)
AGENCY_AGENT_MODEL
VENDOR_AGENT_MODEL
COMPONENT_AGENT_MODEL
```

Not currently used (safe to omit):
```
TWILIO_*    SMS (not integrated)
AWS_*       S3 (not integrated)
```

---

## How to Run Locally

```bash
pip install -r requirements.txt
npm install && npm run build      # Compile Tailwind CSS

# Set minimum env vars
export SECRET_KEY=dev-secret
export CLAUDE_API_KEY=sk-ant-...  # Only needed for agents

flask db upgrade                  # Create/migrate DB
flask seed all                    # Load sample data (optional)
flask run
```

App runs at http://localhost:5000.

---

## How to Run Tests

```bash
pytest tests/
```

---

## Project Structure

```
see-tran/
├── app/
│   ├── __init__.py         App factory, extension init, blueprint registration
│   ├── agents/             LLM research agents (Anthropic SDK, direct usage)
│   │   ├── agency_agent.py  Agency research (implemented)
│   │   ├── vendor_agent.py  Vendor research (Phase 2 — to be implemented)
│   │   └── component_agent.py  Component research (Phase 2 — to be implemented)
│   ├── auth.py             OAuth login/logout flows
│   ├── models/
│   │   └── tran.py         All core domain models (GTFS removed)
│   ├── routes/             Flask blueprints
│   ├── templates/          Jinja2 templates + HTMX fragments
│   ├── static/             CSS (compiled Tailwind), JS (HTMX), images
│   ├── forms/forms.py      WTForms
│   └── utils/              Error helpers, logging, AFI utilities
├── config.py               Flask config (Dev, Prod, Test classes)
├── run.py                  App entry point + Flask CLI commands
├── data/                   Seed JSON files
├── scripts/                Standalone data loader scripts
├── migrations/             Alembic migration files
├── tests/                  Pytest tests
├── logs/                   Agent audit logs (agent_audit.jsonl)
└── docs/                   Project documentation
```

---

## What Is Out of Scope

- **GTFS models**: The GTFS schedule models have been removed. The only GTFS field retained is `Agency.gtfs_feed_url` for storing the feed URL. Do not re-introduce GTFS table models.
- **C-TRAN-specific service types**: The old `Fleet` enum (`vine`, `para`, `current`) is gone. Use the `ServiceType` model (Fixed, Rail, Paratransit, OnDemand) instead.
- **SMS / AWS S3**: No longer in config. Not used.
