# See-Tran: Agent-assisted data enrichment

See-Tran uses Claude-powered research agents to bootstrap and enrich transit agency data. Agents search the web, extract structured facts, and surface them for human review — nothing is written to the database automatically.

## How agents work

1. An admin triggers a run from the CLI or the Agent UI (`/admin/agents/agency`)
2. The agent calls Claude with web search enabled and extracts a structured JSON draft
3. The draft is returned for review — the admin can inspect the diff and commit or discard
4. Every run is appended to `logs/agent_audit.jsonl`

## Agency agent (implemented)

Researches a transit agency by name and proposes updates to core fields:

`name`, `short_name`, `location`, `description`, `website`, `ceo`, `address_hq`, `phone_number`, `contact_email`, `transit_map_link`, `email_domain`

**CLI usage:**

```bash
flask agent run agency --id 42            # Research and apply changes
flask agent run agency --id 42 --dry-run  # Preview only, no DB write
flask agent run agency --all --dry-run    # Preview all agencies
flask agent status                        # Show run history from audit log
```

**Admin UI:** `/admin/agents/agency` — pick an existing agency or enter a new name, run the agent, inspect the diff, then commit.

## Suggestion reviewer (implemented)

Agent-proposed changes can be routed to the `Suggestion` table for human review before being applied. Reviewers work through `/admin/suggestions` — accept applies the value directly to the entity, reject discards it. Batch accept/reject is supported.

## Vendor and component agents (Phase 2 — not yet implemented)

`vendor_agent.py` and `component_agent.py` exist as stubs. Running them returns a not-implemented error. Implementation is planned for Phase 2.

## Data quality principles

- Verifiable sources only — agents use web search and prefer official sites
- Omit uncertain fields rather than guessing
- Normalize names to match existing conventions (no marketing suffixes, consistent casing)
- Agents never auto-commit — all changes require human approval

## Architecture

Agents use the Anthropic SDK directly (`anthropic.messages.create`) with the `web_search_20250305` tool. No provider abstraction layer. Each agent module exposes:

- `run(record_id, *, dry_run=False)` — CLI entry point; applies diff if not dry-run
- `research(name, existing_record)` — Admin UI entry point; returns draft for review

Shared utilities (`app/agents/utils.py`): `AgentResult`, `LogEntry`, `log_agent_event()`.

See `docs/agent_architecture.md` for full implementation detail.
