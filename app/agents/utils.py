# app/agents/utils.py
"""
Shared utilities for all agents: result types and audit logging.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime

from flask import current_app, has_request_context, session


@dataclass
class LogEntry:
    """Single log entry for agent execution."""
    timestamp: str
    event_type: str  # 'llm_call', 'decision', 'error'
    details: dict
    duration_ms: int | None = None


@dataclass
class AgentResult:
    """Result from agent execution."""
    success: bool
    draft: dict = field(default_factory=dict)
    diff: dict | None = None
    logs: list[LogEntry] = field(default_factory=list)
    model_used: str = ''
    is_update: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            'success': self.success,
            'draft': self.draft,
            'diff': self.diff,
            'logs': [asdict(log) for log in self.logs],
            'model_used': self.model_used,
            'is_update': self.is_update,
            'error': self.error,
        }


def log_agent_event(result: AgentResult, input_data: dict, agent_type: str) -> None:
    """Append an audit entry to logs/agent_audit.jsonl."""
    log_dir = os.path.join(current_app.root_path, '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    user_email = 'cli'
    if has_request_context():
        user_email = session.get('user', {}).get('email', 'anonymous')

    entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'agent_type': agent_type,
        'user_email': user_email,
        'input': input_data,
        'result_summary': {
            'success': result.success,
            'is_update': result.is_update,
            'fields_set': list(result.draft.keys()),
            'error': result.error,
        },
        'model': result.model_used,
        'log_count': len(result.logs),
    }

    log_file = os.path.join(log_dir, 'agent_audit.jsonl')
    with open(log_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')
