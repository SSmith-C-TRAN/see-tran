# app/agents/providers/anthropic.py
"""Anthropic Claude provider implementation."""

import json
import httpx
from . import LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""
    
    DEFAULT_MODEL = 'claude-sonnet-4-20250514'
    API_URL = 'https://api.anthropic.com/v1/messages'
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Anthropic API key is required")
        self.api_key = api_key
    
    @property
    def name(self) -> str:
        return 'anthropic'
    
    def _make_request(
        self,
        messages: list[dict],
        system_prompt: str,
        model: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> dict:
        """Make a request to the Anthropic API."""
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
        }
        
        payload = {
            'model': model or self.DEFAULT_MODEL,
            'max_tokens': max_tokens,
            'system': system_prompt,
            'messages': messages,
        }
        
        if tools:
            payload['tools'] = tools
        
        with httpx.Client(timeout=120.0) as client:
            response = client.post(self.API_URL, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    
    def _extract_text(self, response: dict) -> str:
        """Extract text content from response."""
        content = response.get('content', [])
        text_parts = []
        for block in content:
            if block.get('type') == 'text':
                text_parts.append(block.get('text', ''))
        return '\n'.join(text_parts)
    
    def complete(
        self,
        messages: list[dict],
        system_prompt: str,
        model: str | None = None,
    ) -> LLMResponse:
        """Basic completion without tools."""
        response = self._make_request(messages, system_prompt, model)
        
        return LLMResponse(
            content=self._extract_text(response),
            model=response.get('model', model or self.DEFAULT_MODEL),
            input_tokens=response.get('usage', {}).get('input_tokens', 0),
            output_tokens=response.get('usage', {}).get('output_tokens', 0),
            raw_response=response,
        )
    
    def complete_with_search(
        self,
        messages: list[dict],
        system_prompt: str,
        model: str | None = None,
    ) -> LLMResponse:
        """Completion with web search tool enabled."""
        # Anthropic's web search tool
        tools = [
            {
                'type': 'web_search_20250305',
                'name': 'web_search',
                'max_uses': 5,
            }
        ]
        
        response = self._make_request(messages, system_prompt, model, tools=tools)
        
        return LLMResponse(
            content=self._extract_text(response),
            model=response.get('model', model or self.DEFAULT_MODEL),
            input_tokens=response.get('usage', {}).get('input_tokens', 0),
            output_tokens=response.get('usage', {}).get('output_tokens', 0),
            raw_response=response,
        )
    
    def complete_structured(
        self,
        messages: list[dict],
        system_prompt: str,
        schema: dict,
        model: str | None = None,
    ) -> dict:
        """Completion that returns structured JSON."""
        # Add JSON instruction to system prompt
        json_system = f"""{system_prompt}

IMPORTANT: You must respond with ONLY valid JSON matching this schema:
{json.dumps(schema, indent=2)}

Do not include any text before or after the JSON. Do not use markdown code blocks."""
        
        response = self._make_request(messages, json_system, model)
        content = self._extract_text(response)
        
        # Clean up potential markdown formatting
        content = content.strip()
        if content.startswith('```'):
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # Return partial result with error flag
            return {
                '_parse_error': str(e),
                '_raw_content': content,
            }