See-Tran — Open source transit technology benchmarking
=======================================================

See-Tran is an open-source platform for modeling transit agency technology landscapes and benchmarking across agencies. Transit professionals document which systems they use, enabling cross-agency comparison of vendors, products, and technology choices.

**Who it's for:** Transit CIOs, IT managers, vendor managers, and analysts benchmarking capabilities and vendor presence across agencies.

---

## What it does

- **Catalog your tech stack** — agencies → functional areas → functions → components → configurations
- **Track vendor footprint** — link products and versions to each configuration
- **Benchmark across agencies** — compare who uses what, and where
- **AI-assisted enrichment** — Claude-powered agents research agency facts, with human review before any data is saved
- **Public read API** — unauthenticated JSON endpoints at `/api/v1/` for agencies, vendors, components, functions, and configurations
- **In-app documentation** — Markdown docs rendered at `/docs`

---

## Core domain model

```
Agency
  └── Configuration (Agency + Function + Component — the benchmark record)
        ├── ConfigurationProduct → Product → Vendor
        └── ServiceType (Fixed, Rail, Paratransit, OnDemand)

FunctionalArea → Function → Component
Vendor → Product → ProductVersion
```

---

## Key features

### Benchmarking
- Configurations tie an agency, function, and component together with status, dates, and notes
- Vendor pages show product usage across agencies grouped by functional area
- Print-optimized pages for functional areas and functions (`/functional-areas/print`, `/functions/print`)

### Public API (`/api/v1/`)
Unauthenticated read-only JSON:
```
GET /api/v1/agencies
GET /api/v1/agencies/<id>
GET /api/v1/vendors
GET /api/v1/vendors/<id>
GET /api/v1/components
GET /api/v1/components/<id>
GET /api/v1/functions
GET /api/v1/functions/<id>
GET /api/v1/configurations
GET /api/v1/configurations/<id>
GET /api/v1/search?q=<term>&type=agency,vendor,...
```

### AI agents
Claude-powered research agents (`app/agents/`) enrich database records using web search:

```bash
flask agent run agency --id 42            # Research an agency, apply diff
flask agent run agency --all --dry-run    # Preview changes for all agencies
flask agent status                        # Show run history
```

The agency agent is fully implemented. Vendor and component agents are planned for Phase 2.

Agents never auto-commit — all changes require human review. The `/admin/agents/agency` UI shows the proposed diff before committing. The `/admin/suggestions` page provides a reviewer workflow for batch review.

### Admin tools
- `/admin/agents/agency` — run agent, inspect diff, commit or discard
- `/admin/suggestions` — review, accept, or reject agent-proposed field changes
- `/admin/` — dashboard with links to all admin tools

---

## Getting started (local)

```bash
git clone https://github.com/your-org/see-tran.git
cd see-tran

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm install && npm run build

export SECRET_KEY=dev-secret
flask db upgrade
flask seed all   # optional sample data
flask run
```

Visit http://localhost:5000. See `CONTRIBUTING.md` for the full development guide.

---

## Deployment

Deploys to [Railway](https://railway.com) with a managed PostgreSQL database:

1. Create a Railway project, connect your repo, add a PostgreSQL service
2. Set `SECRET_KEY`, `DB_TYPE=postgres`, `FLASK_ENV=production`, `CLAUDE_API_KEY`
3. Push — Railway builds the Dockerfile, runs migrations, starts Gunicorn

See `docs/README_setup.md` for full instructions including Docker self-hosting.

---

## Architecture

| Layer | Stack |
|-------|-------|
| Backend | Flask, SQLAlchemy, Alembic |
| Frontend | Jinja2, Tailwind CSS, HTMX |
| Auth | OAuth (Google + Microsoft) |
| Agents | Anthropic SDK, web search tool |
| Database | PostgreSQL (production), SQLite (dev) |
| Deploy | Railway + Docker |

```
app/
  agents/         AI research agents (Anthropic SDK)
  models/tran.py  All domain models
  routes/         Flask blueprints
  templates/      Jinja2 + HTMX
  mcp_server.py   MCP tools for Claude Code
```

---

## Contributing

See `CONTRIBUTING.md` for setup, testing, seeding, agent usage, code conventions, and PR guidelines.

**Hosted instance:** See-Tran.org provides a community-sourced dataset enhanced by AI agents. Contact the maintainers to participate or pilot.
