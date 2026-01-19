# app/agents/base.py
"""
Base agent class and common utilities.
"""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from flask import current_app, session

from .providers import get_provider, LLMProvider, LLMResponse
from .tools import get_tool_registry, ToolContext, ToolResult


@dataclass
class LogEntry:
    """Single log entry for agent execution."""
    timestamp: str
    event_type: str  # 'llm_call', 'tool_call', 'decision', 'error'
    details: dict
    duration_ms: int | None = None


@dataclass
class AgentResult:
    """Result from agent execution."""
    success: bool
    draft: dict = field(default_factory=dict)
    skipped_fields: dict = field(default_factory=dict)
    diff: dict | None = None
    logs: list[LogEntry] = field(default_factory=list)
    provider_used: str = ''
    model_used: str = ''
    is_update: bool = False
    error: str | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'draft': self.draft,
            'skipped_fields': self.skipped_fields,
            'diff': self.diff,
            'logs': [asdict(log) for log in self.logs],
            'provider_used': self.provider_used,
            'model_used': self.model_used,
            'is_update': self.is_update,
            'error': self.error,
        }


class BaseAgent(ABC):
    """
    Base class for all agents.
    
    Provides:
    - LLM provider access
    - Tool registry access
    - Audit logging
    - Confidence threshold filtering
    """
    
    def __init__(self):
        self._logs: list[LogEntry] = []
        self._provider: LLMProvider | None = None
        self._model: str | None = None
    
    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Agent type identifier (e.g., 'agency', 'vendor')."""
        pass
    
    @property
    def confidence_threshold(self) -> float:
        """Get configured confidence threshold."""
        return current_app.config.get('AGENT_CONFIDENCE_THRESHOLD', 0.7)
    
    def _get_config(self) -> dict:
        """Get agent-specific configuration."""
        providers = current_app.config.get('AGENT_PROVIDERS', {})
        return providers.get(self.agent_type, {
            'provider': 'anthropic',
            'model': 'claude-sonnet-4-20250514',
        })
    
    def _get_provider(self) -> LLMProvider:
        """Get the configured LLM provider for this agent."""
        if self._provider is None:
            config = self._get_config()
            provider_name = config.get('provider', 'anthropic')
            self._provider = get_provider(provider_name)
            self._model = config.get('model')
        return self._provider
    
    def _log(self, event_type: str, details: dict, duration_ms: int | None = None) -> None:
        """Add a log entry."""
        entry = LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            details=details,
            duration_ms=duration_ms,
        )
        self._logs.append(entry)
    
    def _call_llm(
        self,
        messages: list[dict],
        system_prompt: str,
        use_search: bool = False,
    ) -> LLMResponse:
        """Make an LLM call with logging."""
        provider = self._get_provider()
        start = datetime.utcnow()
        
        try:
            if use_search:
                response = provider.complete_with_search(messages, system_prompt, self._model)
            else:
                response = provider.complete(messages, system_prompt, self._model)
            
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            self._log('llm_call', {
                'provider': provider.name,
                'model': response.model,
                'use_search': use_search,
                'input_tokens': response.input_tokens,
                'output_tokens': response.output_tokens,
                'prompt_preview': messages[0]['content'][:200] if messages else '',
            }, duration_ms=duration)
            
            return response
            
        except Exception as e:
            self._log('error', {'stage': 'llm_call', 'error': str(e)})
            raise
    
    def _call_llm_structured(
        self,
        messages: list[dict],
        system_prompt: str,
        schema: dict,
    ) -> dict:
        """Make a structured LLM call with logging."""
        provider = self._get_provider()
        start = datetime.utcnow()
        
        try:
            result = provider.complete_structured(messages, system_prompt, schema, self._model)
            
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            self._log('llm_call', {
                'provider': provider.name,
                'model': self._model,
                'structured': True,
                'schema_keys': list(schema.get('properties', {}).keys()),
                'has_parse_error': '_parse_error' in result,
            }, duration_ms=duration)
            
            return result
            
        except Exception as e:
            self._log('error', {'stage': 'llm_structured_call', 'error': str(e)})
            raise
    
    def _call_tool(self, tool_name: str, params: dict) -> ToolResult:
        """Execute a tool with logging."""
        registry = get_tool_registry()
        start = datetime.utcnow()
        
        config = self._get_config()
        context = ToolContext(
            params=params,
            provider_name=config.get('provider', 'anthropic'),
            model=config.get('model'),
        )
        
        result = registry.execute(tool_name, context)
        
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)
        
        self._log('tool_call', {
            'tool': tool_name,
            'params': {k: v for k, v in params.items() if k != 'api_key'},  # Don't log secrets
            'success': result.success,
            'confidence': result.confidence,
            'error': result.error,
        }, duration_ms=duration)
        
        return result
    
    def _filter_by_confidence(self, data: dict, confidences: dict) -> tuple[dict, dict]:
        """
        Filter fields by confidence threshold.
        
        Returns:
            (high_confidence_fields, skipped_fields)
        """
        threshold = self.confidence_threshold
        kept = {}
        skipped = {}
        
        for key, value in data.items():
            conf = confidences.get(key, 1.0)
            if conf >= threshold:
                kept[key] = value
            else:
                skipped[key] = {
                    'value': value,
                    'confidence': conf,
                    'reason': f'Below threshold ({conf:.2f} < {threshold:.2f})',
                }
        
        self._log('decision', {
            'action': 'confidence_filter',
            'kept_fields': list(kept.keys()),
            'skipped_fields': list(skipped.keys()),
            'threshold': threshold,
        })
        
        return kept, skipped
    
    def _compute_diff(self, existing: dict, proposed: dict) -> dict:
        """Compute diff between existing and proposed values."""
        diff = {}
        all_keys = set(existing.keys()) | set(proposed.keys())
        
        for key in all_keys:
            old_val = existing.get(key)
            new_val = proposed.get(key)
            
            if old_val != new_val and new_val is not None:
                diff[key] = {'old': old_val, 'new': new_val}
        
        return diff
    
    def _save_audit_log(self, result: AgentResult, input_data: dict) -> None:
        """Save execution log to append-only JSON file."""
        log_dir = os.path.join(current_app.root_path, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, 'agent_audit.jsonl')
        
        user = session.get('user', {})
        
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'agent_type': self.agent_type,
            'user_email': user.get('email', 'anonymous'),
            'input': input_data,
            'result_summary': {
                'success': result.success,
                'is_update': result.is_update,
                'fields_set': list(result.draft.keys()),
                'fields_skipped': list(result.skipped_fields.keys()),
                'error': result.error,
            },
            'provider': result.provider_used,
            'model': result.model_used,
            'log_count': len(result.logs),
        }
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    @abstractmethod
    def execute(self, input_data: dict, existing_record: Any | None = None) -> AgentResult:
        """
        Execute the agent.
        
        Args:
            input_data: Input parameters (e.g., agency name)
            existing_record: Optional existing database record for updates
            
        Returns:
            AgentResult with draft data for review
        """
        pass
    
    def _create_result(
        self,
        success: bool,
        draft: dict | None = None,
        skipped_fields: dict | None = None,
        diff: dict | None = None,
        is_update: bool = False,
        error: str | None = None,
    ) -> AgentResult:
        """Create an AgentResult with current state."""
        config = self._get_config()
        
        return AgentResult(
            success=success,
            draft=draft or {},
            skipped_fields=skipped_fields or {},
            diff=diff,
            logs=self._logs.copy(),
            provider_used=config.get('provider', 'anthropic'),
            model_used=config.get('model', ''),
            is_update=is_update,
            error=error,
        )