# Agent Architecture

This document describes how the LLM research agent system is designed to work, what is currently implemented, and what remains to be built.

---

## What Agents Do

Agents automatically research and populate database records using the Claude API with web search. The workflow is:

1. An admin triggers an agent run (via the UI or CLI) with a record name or ID
2. The agent calls Claude with a web search tool enabled
3. Claude searches the web and returns a structured JSON draft of proposed field values
4. The draft is returned for **human review** — nothing is written to the database automatically
5. The admin reviews the diff and clicks "Commit" to apply, or discards it
6. Every run is appended to `logs/agent_audit.jsonl` for an audit trail

---

## Current Architecture

The current code uses a layered class hierarchy that the refactor plan (Phase 2) intends to replace:

```
AgencyAgent (BaseAgent)
  └── BaseAgent
        ├── _get_provider() → LLMProvider
        │     ├── AnthropicProvider  [active]
        │     └── OpenAIProvider     [implemented but not used for agents]
        └── _call_tool() → ToolRegistry
              └── (empty — no tools registered)
```

### Key files

| File | Role |
|------|------|
| [app/agents/base.py](../app/agents/base.py) | `BaseAgent` ABC, `AgentResult`, `LogEntry` dataclasses |
| [app/agents/agency_agent.py](../app/agents/agency_agent.py) | `AgencyAgent` implementation + singleton `agency_agent` |
| [app/agents/providers/\_\_init\_\_.py](../app/agents/providers/__init__.py) | `LLMProvider` protocol, `LLMResponse` dataclass, `get_provider()` factory |
| [app/agents/providers/anthropic.py](../app/agents/providers/anthropic.py) | Raw `httpx` implementation of Anthropic API (not using the official SDK) |
| [app/agents/providers/openai.py](../app/agents/providers/openai.py) | OpenAI implementation (web search is a no-op fallback — not used) |
| [app/agents/tools/\_\_init\_\_.py](../app/agents/tools/__init__.py) | `ToolRegistry`, `Tool` ABC, `ToolResult` — framework only, no tools registered |
| [app/routes/admin.py](../app/routes/admin.py) | HTTP endpoints: run, commit, preview |

### AgentResult shape

```python
@dataclass
class AgentResult:
    success: bool
    draft: dict           # proposed field values from LLM
    skipped_fields: dict  # fields below confidence threshold (unused currently)
    diff: dict | None     # old vs new values, if updating an existing record
    logs: list[LogEntry]  # per-step execution trace
    provider_used: str
    model_used: str
    is_update: bool
    error: str | None
```

---

## What Is Implemented and Working

### Agency agent

`AgencyAgent` in [app/agents/agency_agent.py](../app/agents/agency_agent.py) is fully functional:

- Takes `{'name': 'Agency Name'}` as input
- Makes a single call to the Anthropic API with `web_search_20250305` tool (max 3 searches)
- Extracts a JSON object from the response, with fallback parsing for markdown-wrapped or messy output
- Computes a diff against the existing record if an `agency_id` is passed
- Writes an audit entry to `logs/agent_audit.jsonl`
- Returns an `AgentResult` — does **not** write to the database

The module exposes a **singleton instance**: `agency_agent = AgencyAgent()` at the bottom of the file. The admin routes import and call this instance directly.

**Fields the agency agent populates:**

`name`, `short_name`, `location`, `description`, `website`, `ceo`, `address_hq`, `phone_number`, `contact_email`, `transit_map_link`, `email_domain`, `ridership` (metadata), `vehicles` (metadata)

Note: `_fetch_agency_images` is stubbed out with a TODO — image fetching is disabled.

### Admin UI

Three HTTP endpoints in [app/routes/admin.py](../app/routes/admin.py):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /admin/agents/agency` | GET | Agency agent UI page |
| `POST /admin/api/agents/agency/run` | POST | Execute agent, return draft |
| `POST /admin/api/agents/agency/commit` | POST | Apply draft to database |
| `GET /admin/api/agents/agency/preview/<id>` | GET | Fetch current record for comparison |

The run → review → commit flow is complete for agencies.

### CLI

[run.py](../run.py) has `flask agent run` and `flask agent status` commands. `flask agent run agency` works. The `vendor` and `component` branches will fail at import (see below).

### Audit log

Every agent run appends a JSON entry to `logs/agent_audit.jsonl`:

```json
{
  "timestamp": "...",
  "agent_type": "agency",
  "user_email": "admin@example.com",
  "input": {"name": "TriMet"},
  "result_summary": {
    "success": true,
    "is_update": true,
    "fields_set": ["name", "website", "ceo"],
    "fields_skipped": [],
    "error": null
  },
  "provider": "anthropic",
  "model": "claude-sonnet-4-20250514",
  "log_count": 4
}
```

`flask agent status` reads this file and displays last-run stats per agent type.

### Suggestion model

`Suggestion` is defined in [app/models/tran.py](../app/models/tran.py) (added in Phase 4). It stores proposed field changes for human review:

```
entity_type, entity_id, field, suggested_value, current_value,
source_url, confidence, status (pending/accepted/rejected),
review_note, created_at, reviewed_at, reviewed_by_user_id
```

The admin reviewer UI at `/admin/suggestions` supports accept/reject/batch actions. This is the intended destination for agent output once Phase 2 is complete — agents will write `Suggestion` records rather than returning drafts directly.

---

## What Needs to Be Built (Phase 2)

### 1. Replace the provider abstraction with direct Anthropic SDK

The current `AnthropicProvider` uses raw `httpx` calls. The plan is to replace the entire `BaseAgent` / `LLMProvider` / `ToolRegistry` stack with direct `anthropic` SDK usage per agent module:

```python
# Target pattern (per refactor_plan.md)
import anthropic

def run(agency_id: int, *, dry_run: bool = False) -> AgentResult:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=current_app.config['AGENT_MODELS']['agency'],
        tools=[{"type": "web_search_20250305", ...}],
        ...
    )
```

Files to delete when this is done: `base.py`, `providers/` directory, `tools/` directory (or repurpose the `AgentResult` dataclass into a standalone utility).

Audit logging (`_save_audit_log`) becomes a standalone `log_agent_event()` utility rather than a base class method.

### 2. Implement vendor_agent

`app/agents/vendor_agent.py` does not exist. The CLI will crash if you run `flask agent run vendor`. Needs to be written from scratch.

Target interface:
```python
def run(vendor_id: int, *, dry_run: bool = False) -> AgentResult:
    ...
```

Output: updated vendor fields + proposed `Product`/`ProductVersion` list.
Tools: `web_search`, `fetch_url`

### 3. Implement component_agent

`app/agents/component_agent.py` does not exist. Same situation as vendor_agent.

Target interface:
```python
def run(component_id: int, *, dry_run: bool = False) -> AgentResult:
    ...
```

Output: function mappings, description enrichment.
Tools: `web_search`

### 4. Implement suggest_agent

Not yet started. This is a meta-agent that calls the other agents and writes results to the `Suggestion` table rather than returning a draft for immediate commit:

```python
def run(entity_type: str, entity_id: int) -> AgentResult:
    ...
```

The batch workflow (`flask agent suggest --entity agency --all`) feeds from this.

### 5. Wire agents to write Suggestion records

Currently, `agency_agent.execute()` returns a draft in memory and the admin manually commits it. Phase 2 targets a flow where agents write `Suggestion` rows directly, and humans review via `/admin/suggestions` instead of the per-agent commit endpoint.

### 6. Admin UI for vendor and component agents

The run/review/commit UI exists only for agencies. Vendor and component agents will need equivalent pages under `/admin/agents/vendor` and `/admin/agents/component`.

---

## Mismatch Between Current Code and Target State

The `__init__.py` docstring already documents the Phase 2 interface:

```python
# app/agents/__init__.py (docstring)
from app.agents.agency_agent import run as run_agency_agent
result = run_agency_agent(agency_id=42)
```

But `agency_agent.py` does not expose a top-level `run()` function — it exposes `agency_agent.execute()` on a class instance. The CLI in `run.py` also imports `run` from each agent module (`from app.agents.agency_agent import run as run_agent`), which will fail for `agency_agent` since no such function exists. The CLI currently works only if it invokes the class method indirectly.

**The full gap summary:**

| Item | Status |
|------|--------|
| `AgencyAgent.execute()` — class-based | Working |
| `run(agency_id)` module-level function | Missing (CLI expects it) |
| Admin UI: agency run/commit | Working |
| `vendor_agent.py` | Missing entirely |
| `component_agent.py` | Missing entirely |
| `suggest_agent.py` | Missing entirely |
| Direct Anthropic SDK (replace httpx) | Not yet done |
| Agents writing to `Suggestion` table | Not yet done |
| Image fetch tool | Disabled (TODO) |
| Tool registry: no tools registered | Empty framework |
| OpenAI provider web search | No-op fallback only |
