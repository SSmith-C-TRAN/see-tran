# See-Tran Refactor & Release Plan

> Goal: Release a clean, community-ready platform for transit technology benchmarking — with a vendor portal for monetization, and architecture that AI agents (Claude Code) can read, modify, and extend autonomously.

---

## Current State Assessment

**What works well:**
- Clear domain model: Agency → FunctionalArea → Function → Component → Configuration
- Solid Flask/SQLAlchemy foundation with Alembic migrations
- Agent infrastructure (base class, provider abstraction, audit logging) shows good intent
- HTMX + Tailwind for responsive UX without SPA complexity
- OAuth authentication with agency domain mapping

**What needs fixing:**
- Agent framework is over-engineered: custom BaseAgent, provider protocol, tool registry — all to wrap a single Anthropic API call in `agency_agent.py`; vendor and component agents are 3-line stubs
- No public API; no vendor self-service; no contribution workflow
- No deployment config (no Docker, no Procfile, no deploy guide)

---

## Phases

### Phase 0 — AI-Agent Foundation (Complete)

Make the project navigable and operable by Claude Code before touching anything else. Every subsequent phase becomes easier when Claude Code understands the project.

**0.1 — CLAUDE.md**

Create `CLAUDE.md` at the repo root. Include:
- Domain model map (entities, relationships, uniqueness constraints)
- Blueprint map: which blueprint owns which routes
- Flask CLI commands and what they do
- Conventions: how routes are named, how templates are named, how fragments work
- How to run tests, build CSS, load seed data
- Env vars required and their purpose
- What is intentionally out of scope (GTFS, C-TRAN-specific fields)

**0.2 — Agent-Callable CLI**

Ensure every data operation has a Flask CLI command. Claude Code and other agents invoke the app through the CLI, not by writing ad-hoc scripts.

Required commands (audit existing, add missing):
```
flask db upgrade              # Run migrations
flask seed <entity>           # Load seed data for an entity
flask agent run <agent_name>  # Run a named agent (agency, vendor, component)
flask agent status            # Show last run stats per agent
flask admin create-user       # Bootstrap an admin user
flask gtfs load <dir>         # GTFS loader (separate, not core)
```

**0.3 — MCP Server (new file: `app/mcp_server.py`)**

Expose core CRUD operations as MCP tools so Claude Code can directly inspect and update the database. This replaces the need for agents to have their own DB access logic.

MCP tools to expose:
- `list_agencies`, `get_agency`, `upsert_agency`
- `list_vendors`, `get_vendor`, `upsert_vendor`
- `list_components`, `get_component`, `upsert_component`
- `list_products`, `get_product`, `upsert_product`
- `list_configurations`, `get_configuration`, `upsert_configuration`
- `get_schema_summary` — returns model field names and types for all entities

Register in `mcp.json` at the repo root so Claude Code auto-discovers it.

---

### Phase 1 — Architecture Cleanup (complete)

> **Verification notes (2026-04-04):**
> - 1.1: bloat removed; `base.py` + `providers/` intentionally deferred to Phase 2 agent rewrite; `additional_metadata` present on Agency, Component, Product, Configuration — intentional flex columns
> - 1.2: `ServiceType` model seeded; `Fleet` enum removed ✓
> - 1.3: `agency.py` dead routes removed (blueprint prefix `/agencies` + full `/api/agencies/*` paths = wrong URL); `add_agency` POST endpoint added at `/agencies/new`; edit form bug fixed (`populate_from_agency` not `populate_agency`); full consolidation into `api.py` deferred to Phase 2
> - 1.4: forms remain in `app/forms/forms.py`; co-location deferred (mixing Flask-WTF into `tran.py` adds more noise than value)
> - 1.5: all `/api/` JSON routes use `api_ok`/`api_error` envelope ✓

Remove duplication and C-TRAN-specific artifacts. Establish consistent patterns.

**1.1 — Remove Bloat**

| Item | Action | Reason |
|------|--------|--------|
| `app/agents/vendor_agent.py` | Delete (3-line stub) | Rewrite from scratch in Phase 2 |
| `app/agents/component_agent.py` | Delete (3-line stub) | Rewrite from scratch in Phase 2 |
| `app/agents/tools/image_fetch.py` | Delete (disabled) | Not used, adds Pillow dependency for nothing |
| `app/agents/providers/` directory | Collapse (see Phase 2) | Over-abstraction for one API |
| `Fleet` enum in `tran.py` | C-TRAN fleet types (`vine`, `para`) are agency-specific | Generalize this using "Fixed" for fixed route, "Rail" for rail, "Para" for paratransit, and "Demand" for on-demand/microtransit
| GTFS models (`models/gtfs.py`, `gtfs_loader.py`) | Remove all GTFS related models, just the models and tools/functionaiity related to accessing GTFS data | no longer relevant outside of collecting the GTFS URLs for the various agency GTFS fields
| `additional_metadata` JSON columns | Audit and formalize | 3 models have open-ended JSON blobs; define what goes there |

**1.2 — Generalize the Fleet Concept**

Replace the `Fleet` enum with a many-to-many `ServiceType` table that agencies define themselves. This removes C-TRAN-specific values from the shared schema. But it is important that we align service types with Fixed, Rail, Paratransit, and OnDemand

**1.3 — Consolidate Route Structure**

Current inconsistency: some routes are under `/api/`, some aren't; blueprints share responsibility for the same entities.

Adopt this convention:
```
/                        → main pages (main.py)
/agencies/<id>           → agency pages (agency.py)
/configurations          → configuration management (configurations.py)
/vendors                 → vendor pages
/components              → component pages
/integrations            → integration points (integrations.py)
/admin/                  → admin (admin.py)

/api/                    → all JSON API endpoints, one blueprint (api.py)
  /api/entities/         → generic CRUD endpoints
  /api/search            → search endpoint
  /api/agents/run        → trigger agent runs
```

Move all fragment endpoints (HTMX partials) into their owning blueprint. Fragment routes should not live in `api.py`.

**1.4 — Reduce Form Duplication**

WTForms field definitions duplicate SQLAlchemy model fields. For simple CRUD forms, consider generating forms from model metadata rather than hand-coding parallel field lists. At minimum, co-locate form class definitions with their model in the same file so they move together.

**1.5 — Unify Response Format**

All `/api/` routes should return JSON with a consistent envelope:
```json
{ "ok": true, "data": {...} }
{ "ok": false, "error": "message", "code": 422 }
```

---

### Phase 2 — Agent Rearchitecture

Replace the custom multi-provider framework with a lean, Anthropic-native approach. The goal is agents that Claude Code itself can read, run, and improve.

**Current Architecture (Problem)**
```
BaseAgent → LLMProvider protocol → AnthropicProvider | OpenAIProvider → ToolRegistry
```
- Adds ~300 lines of abstraction to wrap `anthropic.messages.create()`
- OpenAI branch is unused for agents (only planned for image processing)
- Tool registry exists but no tools are registered

**New Architecture**

Each agent is a single Python module with a clear function signature. Use the Anthropic SDK directly. No base class needed.

```python
# app/agents/agency_agent.py
import anthropic
from app.models.tran import Agency

def run(agency_id: int, *, dry_run: bool = False) -> AgentResult:
    client = anthropic.Anthropic()
    # Direct SDK call, tool use, structured output
    ...
```

**Agent result logging** stays (audit trail is valuable), but moves to a standalone `log_agent_event()` utility function rather than a base class method.

**Agents to implement:**

| Agent | Input | Output | Tools |
|-------|-------|--------|-------|
| `agency_agent` | Agency name or ID | Updated agency fields | `web_search`, `fetch_url` |
| `vendor_agent` | Vendor name or ID | Updated vendor + product list | `web_search`, `fetch_url` |
| `component_agent` | Component name or ID | Function mappings, description | `web_search` |
| `suggest_agent` | Entity type + ID | Suggestion record for human review | (calls other agents) |

**Suggestion workflow:**

Add a `Suggestion` model:
```python
class Suggestion(db.Model):
    id, entity_type, entity_id, field, suggested_value,
    current_value, source_url, confidence, status (pending/accepted/rejected),
    created_at, reviewed_at, reviewed_by_user_id
```

Agents write to `Suggestion` table. Humans review via `/admin/suggestions`. Accepted suggestions are applied to the entity. This replaces the planned "reviewer UI" with a concrete schema.

**Trigger agents from Claude Code:**
```bash
flask agent run agency --id 42
flask agent run vendor --name "Cubic Transportation Systems"
flask agent suggest --entity agency --all  # Batch mode
```

---

### Phase 3 — Vendor Portal

Allow vendors to claim and manage their own products. This is the monetization surface.

**3.1 — Vendor Auth**

Add a `VendorUser` model (or extend `User` with a `vendor_id` FK and `user_type` enum: `agency | vendor | admin`). Vendors register with their company email; domain matching auto-links them to a `Vendor` record (same pattern as agency domain matching).

**3.2 — Vendor Dashboard**

New blueprint: `app/routes/vendor_portal.py`

```
/vendor/dashboard          → vendor home, stats, recent configs mentioning their products
/vendor/products           → list/manage products and versions
/vendor/products/<id>/edit → edit product description, features, lifecycle
/vendor/products/new       → create new product
/vendor/integrations       → declare integration points
/vendor/analytics          → which agencies use which products (aggregated)
```

**3.3 — Product Ownership Model**

Add `claimed_by_vendor_user_id` to `Product`. Only claimed products can be edited by vendors. Unclaimed products remain editable by moderators.

Claim flow:
1. Vendor searches for their product
2. Clicks "Claim this product"
3. Moderator approves (or auto-approve if email domain matches vendor domain)

**3.4 — Tiered Access (Monetization)**

| Tier | Access | Price |
|------|--------|-------|
| Free | Read-only, see which agencies use your product | $0 |
| Vendor Basic | Edit product descriptions, add versions | ~$99/mo |
| Vendor Pro | Full analytics: agency details, peer comparisons, leads | ~$299/mo |
| Agency Pro | Unlock private configurations, export reports | ~$199/mo |

Add `subscription_tier` to `VendorUser` and `User`. Gate features in route decorators.

---

### Phase 4 — Public Release Features

**4.1 — Public Read API**

Add unauthenticated read-only JSON endpoints:
```
GET /api/v1/agencies        → paginated agency list
GET /api/v1/agencies/<id>   → agency detail + configurations
GET /api/v1/vendors         → vendor list
GET /api/v1/components      → component list
GET /api/v1/functions       → function taxonomy
```

Document in `docs/api.md`. This enables third-party integrations and makes the data accessible to other tools.

**4.2 — Search**

Add `flask-sqlalchemy` full-text search or a lightweight SQLite FTS5 table for:
- Components by name/description
- Vendors and products
- Configurations by notes

Single `/api/search?q=<term>&type=<entity>` endpoint. No Elasticsearch needed at this scale.

**4.3 — Reviewer UI**

Admin page at `/admin/suggestions` that lists pending `Suggestion` records. Allow accept/reject/modify with a note. Batch actions for high-volume agent runs.

**4.4 — Contributing Workflow**

Add `CONTRIBUTING.md` covering:
- How to run locally
- How to seed data
- How to run agents
- PR conventions
- Data quality standards (from `README_agents.md`)

---

### Phase 5 — Deployment & Release

**5.1 — Containerize**

Add `Dockerfile` and `docker-compose.yml` for local dev with PostgreSQL. Production Dockerfile with Gunicorn.

**5.2 — Deploy Target**

Recommend [Fly.io](https://fly.io) as primary deploy target:
- Add `fly.toml`
- Add `Procfile` for Heroku/Render compatibility
- PostgreSQL via Fly managed Postgres or Supabase

**5.3 — Environment Rationalization**

Audit all env vars. Remove any that are unused (Twilio, AWS S3 if S3 isn't used). Document required vs. optional in `.env.example`.

**5.4 — License & Governance**

- Add `LICENSE` (MIT recommended for community adoption)
- Update root `README.md` with: what the app does, how to deploy, how to contribute, who it's for
- Tag `v0.1.0` after phases 0–2 are complete

---

## Execution Order

```
Phase 0 (CLAUDE.md, CLI, MCP)          ← unblocks AI-assisted execution of all other phases
Phase 1 (cleanup)                       ← reduces noise before adding features
Phase 2 (agents)                        ← enables data population at scale
Phase 3 (vendor portal)                 ← enables monetization
Phase 4 (public API + search + review)  ← enables community adoption
Phase 5 (deploy + release)              ← ships it
```

Phases 0 and 1 can be done in a single session. Phase 2 requires Anthropic API access and test data. Phases 3–5 are independent and can be parallelized.

---

## What to Carry Forward from README_next.md

| Item | Status | Decision |
|------|--------|----------|
| Fleet field on Configuration | Done (exists) | Generalize in Phase 1.2, remove C-TRAN values |
| Functional areas/functions UI | Done | No change |
| Agency lookup/search | Done | No change |
| Agency deep research agent | In progress | Simplify and complete in Phase 2 |
| Vendor product deep research | Not started | Implement in Phase 2 |
| Full-text search | Not started | Phase 4.2 |
| Advanced filtering | Partial | Extend in Phase 4 |
| Similar agencies recommendations | Not started | Post-v1 (requires usage data) |
| Technology stack comparison | Not started | Post-v1 |
| Integration compatibility matrix | Not started | Post-v1 |

---

## Files to Create

| File | Purpose |
|------|---------|
| `CLAUDE.md` | AI agent navigation guide |
| `mcp.json` | MCP server registration |
| `app/mcp_server.py` | MCP tool definitions |
| `app/routes/vendor_portal.py` | Vendor portal blueprint |
| `app/routes/api.py` | Consolidated public API |
| `app/models/suggestion.py` | Agent suggestion review model |
| `Dockerfile` | Container build |
| `docker-compose.yml` | Local dev with Postgres |
| `fly.toml` | Fly.io deployment |
| `Procfile` | Heroku/Render compatibility |
| `.env.example` | Required env var documentation |
| `LICENSE` | MIT license |
| `CONTRIBUTING.md` | Contribution guide |
| `docs/api.md` | Public API documentation |

## Files to Delete

| File | Reason |
|------|--------|
| `app/agents/vendor_agent.py` | 3-line stub, rewrite from scratch |
| `app/agents/component_agent.py` | 3-line stub, rewrite from scratch |
| `app/agents/tools/image_fetch.py` | Disabled, unused |
| `app/agents/providers/` (directory) | Collapsed into direct SDK usage |
| `app/agents/base.py` | Collapsed into per-agent modules + shared utility |
| `docs/README_next.md` | Superseded by this plan; items tracked here |
