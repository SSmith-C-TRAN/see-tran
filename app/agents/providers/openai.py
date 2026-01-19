# app/agents/providers/openai.py
"""OpenAI GPT provider implementation."""

import json
import httpx
from . import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""
    
    DEFAULT_MODEL = 'gpt-4o'
    API_URL = 'https://api.openai.com/v1/chat/completions'
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OpenAI API key is required")
        self.api_key = api_key
    
    @property
    def name(self) -> str:
        return 'openai'
    
    def _make_request(
        self,
        messages: list[dict],
        system_prompt: str,
        model: str | None = None,
        tools: list[dict] | None = None,
        response_format: dict | None = None,
        max_tokens: int = 4096,
    ) -> dict:
        """Make a request to the OpenAI API."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }
        
        # OpenAI uses system message in the messages array
        full_messages = [{'role': 'system', 'content': system_prompt}] + messages
        
        payload = {
            'model': model or self.DEFAULT_MODEL,
            'max_tokens': max_tokens,
            'messages': full_messages,
        }
        
        if tools:
            payload['tools'] = tools
        
        if response_format:
            payload['response_format'] = response_format
        
        with httpx.Client(timeout=120.0) as client:
            response = client.post(self.API_URL, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    
    def _extract_text(self, response: dict) -> str:
        """Extract text content from response."""
        choices = response.get('choices', [])
        if choices:
            return choices[0].get('message', {}).get('content', '')
        return ''
    
    def complete(
        self,
        messages: list[dict],
        system_prompt: str,
        model: str | None = None,
    ) -> LLMResponse:
        """Basic completion without tools."""
        response = self._make_request(messages, system_prompt, model)
        
        usage = response.get('usage', {})
        return LLMResponse(
            content=self._extract_text(response),
            model=response.get('model', model or self.DEFAULT_MODEL),
            input_tokens=usage.get('prompt_tokens', 0),
            output_tokens=usage.get('completion_tokens', 0),
            raw_response=response,
        )
    
    def complete_with_search(
        self,
        messages: list[dict],
        system_prompt: str,
        model: str | None = None,
    ) -> LLMResponse:
        """
        Completion with web search capability.
        
        OpenAI doesn't have native web search like Anthropic, so we enhance
        the prompt to instruct the model to indicate when it needs search.
        For now, this falls back to regular completion.
        """
        # OpenAI models with web search require different setup (Bing integration)
        # For simplicity, we use regular completion with enhanced prompt
        enhanced_prompt = f"""{system_prompt}

Note: Use your training knowledge to provide the most accurate and up-to-date 
information available. If you're uncertain about specific details, indicate 
your confidence level."""
        
        return self.complete(messages, enhanced_prompt, model)
    
    def complete_structured(
        self,
        messages: list[dict],
        system_prompt: str,
        schema: dict,
        model: str | None = None,
    ) -> dict:
        """Completion that returns structured JSON."""
        # Use OpenAI's JSON mode
        json_system = f"""{system_prompt}

You must respond with ONLY valid JSON matching this schema:
{json.dumps(schema, indent=2)}"""
        
        response = self._make_request(
            messages,
            json_system,
            model,
            response_format={'type': 'json_object'},
        )
        
        content = self._extract_text(response)
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            return {
                '_parse_error': str(e),
                '_raw_content': content,
            }