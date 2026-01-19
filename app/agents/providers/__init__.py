# app/agents/providers/__init__.py
"""
LLM Provider abstraction layer.
Allows swapping between Anthropic, OpenAI, and other providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Standard response from any LLM provider."""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    raw_response: Any = None


class LLMProvider(ABC):
    """Protocol for LLM providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass
    
    @abstractmethod
    def complete(
        self,
        messages: list[dict],
        system_prompt: str,
        model: str | None = None,
    ) -> LLMResponse:
        """Basic completion without tools."""
        pass
    
    @abstractmethod
    def complete_with_search(
        self,
        messages: list[dict],
        system_prompt: str,
        model: str | None = None,
    ) -> LLMResponse:
        """Completion with web search capability."""
        pass
    
    @abstractmethod
    def complete_structured(
        self,
        messages: list[dict],
        system_prompt: str,
        schema: dict,
        model: str | None = None,
    ) -> dict:
        """Completion that returns structured JSON matching schema."""
        pass


def get_provider(provider_name: str) -> LLMProvider:
    """Factory function to get the appropriate provider."""
    from flask import current_app
    
    if provider_name == 'anthropic':
        from .anthropic import AnthropicProvider
        api_key = current_app.config.get('CLAUDE_API_KEY')
        return AnthropicProvider(api_key)
    
    elif provider_name == 'openai':
        from .openai import OpenAIProvider
        api_key = current_app.config.get('OPENAI_API_KEY')
        return OpenAIProvider(api_key)
    
    else:
        raise ValueError(f"Unknown provider: {provider_name}")