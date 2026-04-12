# app/agents/agency_agent.py
"""
Agency agent — researches a transit agency using Claude with web search
and returns a draft of proposed field updates for human review.

Entry points:
    run(agency_id, *, dry_run=False)  — CLI: looks up by ID, applies if not dry_run
    research(name, existing_record)   — Admin UI: returns draft for human review
"""

import json
import html
import re
from datetime import datetime
from typing import Any

import anthropic
from flask import current_app

from .utils import AgentResult, LogEntry, log_agent_event


SYSTEM_PROMPT = """You are a research assistant gathering information about public transit agencies.

SEARCH STRATEGY:
- Search for "[agency name] official website" first
- Search for "[agency name] leadership CEO general manager"
- Search for "[agency name] contact headquarters address"
- Search for "[agency name] ridership statistics annual report"
- Search for "[agency name] GTFS feed" or "[agency name] developer data"

Keep searches focused. Return ONLY a JSON object with verified facts.
Do not include citation tags, HTML, XML, markdown, or source annotations in field values.
Omit fields where information is uncertain or unknown.

{
  "name": "Official agency name",
  "short_name": "Acronym like BART or WMATA",
  "location": "City, State",
  "description": "Brief 1-2 sentence description",
  "website": "https://...",
  "ceo": "Full name of current CEO/GM/Executive Director",
  "address_hq": "Full headquarters address",
  "phone_number": "Main phone number",
  "contact_email": "General contact email",
  "transit_map_link": "URL to system map",
  "email_domain": "domain.org",
  "gtfs_feed_url": "URL to the agency's public GTFS static feed if available",
  "annual_ridership": "Total annual ridership with year, e.g. '12.4 million (2023)'",
  "fleet_size": "Total revenue vehicles, e.g. '450 buses, 120 rail cars'",
  "service_area_population": "Population served, e.g. '1.2 million'",
  "ntd_id": "NTD (National Transit Database) ID if known, e.g. '90001'"
}"""

# Fields the agent can populate directly on Agency model columns
AGENCY_FIELDS = (
    'name', 'short_name', 'location', 'description', 'website',
    'ceo', 'address_hq', 'phone_number', 'contact_email',
    'transit_map_link', 'email_domain', 'gtfs_feed_url',
)

# Fields stored in Agency.additional_metadata under the 'ridership' key
METADATA_FIELDS = ('annual_ridership', 'fleet_size', 'service_area_population', 'ntd_id')

_TAG_RE = re.compile(r'</?[A-Za-z][^>]*>')
_CITE_RE = re.compile(r'</?cite\b[^>]*>', re.IGNORECASE)
_BRACKET_CITATION_RE = re.compile(r'\s*\[\d+(?:\s*,\s*\d+)*\]\s*')


def _sanitize_string(value: str) -> str:
    """Strip model citation/markup artifacts and normalize whitespace."""
    cleaned = html.unescape(value.strip())
    cleaned = _CITE_RE.sub('', cleaned)
    cleaned = _TAG_RE.sub('', cleaned)
    cleaned = _BRACKET_CITATION_RE.sub(' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _sanitize_field_value(field_name: str, value: Any) -> Any:
    """Normalize known agency fields and remove markup/citation artifacts."""
    if not isinstance(value, str):
        return value

    cleaned = _sanitize_string(value)
    if not cleaned:
        return None

    if field_name in ('website', 'transit_map_link', 'gtfs_feed_url'):
        url_match = re.search(r'https?://[^\s<>"\']+', cleaned, flags=re.IGNORECASE)
        if url_match:
            cleaned = url_match.group(0).rstrip('.,);')

    if field_name == 'contact_email':
        email_match = re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', cleaned)
        if email_match:
            cleaned = email_match.group(0)

    if field_name == 'email_domain':
        cleaned = cleaned.replace('mailto:', '').strip().lower()
        if '@' in cleaned:
            cleaned = cleaned.split('@', 1)[1]
        cleaned = cleaned.strip('/').strip()

    return cleaned or None


def _sanitize_draft(draft: dict) -> dict:
    """Keep only supported fields and sanitize string values."""
    sanitized: dict[str, Any] = {}
    for field_name in AGENCY_FIELDS:
        if field_name in draft:
            sanitized[field_name] = _sanitize_field_value(field_name, draft.get(field_name))
    for field_name in METADATA_FIELDS:
        if field_name in draft:
            sanitized[field_name] = _sanitize_string(draft[field_name]) if isinstance(draft[field_name], str) else draft[field_name]
    return sanitized


def run(agency_id: int, *, dry_run: bool = False) -> AgentResult:
    """
    CLI entry point. Looks up the agency by ID, researches it, and applies
    the diff to the database unless dry_run is True.
    """
    from app.models.tran import Agency
    from app import db

    agency = Agency.query.get(agency_id)
    if not agency:
        return AgentResult(success=False, error=f'Agency {agency_id} not found')

    result = research(agency.name, existing_record=agency)

    if result.success and not dry_run and result.diff:
        _apply_to_agency(agency, result.draft)
        db.session.commit()

    return result


def research(name: str, existing_record: Any = None) -> AgentResult:
    """
    Research an agency by name using Claude with web search.
    Returns a draft for human review — does not write to the database.
    """
    logs: list[LogEntry] = []
    model = current_app.config['AGENT_MODELS']['agency']

    logs.append(LogEntry(
        timestamp=datetime.utcnow().isoformat(),
        event_type='decision',
        details={'action': 'start', 'agency_name': name},
    ))

    try:
        draft, llm_log = _call_llm(name, model)
        logs.append(llm_log)

        if '_parse_error' in draft:
            logs.append(LogEntry(
                timestamp=datetime.utcnow().isoformat(),
                event_type='error',
                details={'stage': 'extraction', 'error': draft['_parse_error']},
            ))
            return AgentResult(
                success=False,
                logs=logs,
                model_used=model,
                error=f"Failed to parse response: {draft['_parse_error']}",
            )

        original_draft = dict(draft)
        draft = _sanitize_draft(draft)

        cleaned_fields = [
            field_name for field_name in (*AGENCY_FIELDS, *METADATA_FIELDS)
            if field_name in original_draft and original_draft.get(field_name) != draft.get(field_name)
        ]
        if cleaned_fields:
            logs.append(LogEntry(
                timestamp=datetime.utcnow().isoformat(),
                event_type='decision',
                details={'action': 'sanitized_fields', 'fields': cleaned_fields},
            ))

        diff = None
        is_update = existing_record is not None
        if is_update:
            diff = _compute_diff(existing_record, draft)
            logs.append(LogEntry(
                timestamp=datetime.utcnow().isoformat(),
                event_type='decision',
                details={'action': 'computed_diff', 'changed_fields': list(diff.keys())},
            ))

        result = AgentResult(
            success=True,
            draft=draft,
            diff=diff,
            logs=logs,
            model_used=model,
            is_update=is_update,
        )
        log_agent_event(result, {'name': name}, 'agency')
        return result

    except Exception as e:
        logs.append(LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event_type='error',
            details={'stage': 'execution', 'error': str(e)},
        ))
        return AgentResult(success=False, logs=logs, model_used=model, error=str(e))


def _call_llm(agency_name: str, model: str) -> tuple[dict, LogEntry]:
    """Call Claude with web search and return parsed JSON + a log entry."""
    api_key = current_app.config.get('CLAUDE_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)

    start = datetime.utcnow()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{
            'role': 'user',
            'content': f'Research the public transit agency "{agency_name}" and return the JSON data.',
        }],
        tools=[{
            'type': 'web_search_20250305',
            'name': 'web_search',
            'max_uses': 5,
        }],
    )
    duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

    # Extract text from response (ignoring tool_use / tool_result blocks)
    text = ''.join(
        block.text for block in response.content
        if hasattr(block, 'type') and block.type == 'text'
    )

    log_entry = LogEntry(
        timestamp=start.isoformat(),
        event_type='llm_call',
        details={
            'model': response.model,
            'input_tokens': response.usage.input_tokens,
            'output_tokens': response.usage.output_tokens,
        },
        duration_ms=duration_ms,
    )

    return _extract_json(text), log_entry


def _extract_json(content: str) -> dict:
    """Extract a JSON object from an LLM response string."""
    content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    if '```' in content:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(content[start:end + 1])
        except json.JSONDecodeError as e:
            return {'_parse_error': f'Found JSON-like content but failed to parse: {e}'}

    return {'_parse_error': 'Could not find valid JSON in response'}


def _compute_diff(existing_record: Any, proposed: dict) -> dict:
    """Return a dict of {field: {old, new}} for fields that differ."""
    diff = {}
    for field_name in AGENCY_FIELDS:
        old = getattr(existing_record, field_name, None)
        new = proposed.get(field_name)
        if new is not None and old != new:
            diff[field_name] = {'old': old, 'new': new}
    # Include metadata fields in diff
    existing_meta = getattr(existing_record, 'additional_metadata', None) or {}
    existing_ridership = existing_meta.get('ridership', {})
    for field_name in METADATA_FIELDS:
        new = proposed.get(field_name)
        if new is not None:
            old = existing_ridership.get(field_name)
            if old != new:
                diff[field_name] = {'old': old, 'new': new}
    return diff


def _apply_to_agency(agency: Any, draft: dict) -> None:
    """Write draft field values onto an Agency instance (does not commit)."""
    for field_name in AGENCY_FIELDS:
        if field_name in draft:
            value = _sanitize_field_value(field_name, draft[field_name])
            setattr(agency, field_name, value)
    # Write metadata fields into additional_metadata['ridership']
    meta_values = {f: draft[f] for f in METADATA_FIELDS if f in draft and draft[f]}
    if meta_values:
        existing_meta = agency.additional_metadata or {}
        existing_meta = dict(existing_meta)  # ensure mutable copy
        existing_meta['ridership'] = {**existing_meta.get('ridership', {}), **meta_values}
        agency.additional_metadata = existing_meta
