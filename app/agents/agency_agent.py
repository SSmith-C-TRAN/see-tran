# app/agents/agency_agent.py
"""
Agency Agent - builds or updates transit agency records using LLM with web search.
"""

import json
import re
from typing import Any

from .base import BaseAgent, AgentResult


SYSTEM_PROMPT = """You are a research assistant gathering information about public transit agencies.

Your task is to:
1. Search the web for accurate, current information about the specified transit agency
2. Return the findings as a JSON object with no other text or formatting

Research priorities:
1. Official name and common abbreviations
2. Headquarters location and full address  
3. Current leadership (CEO/General Manager/Executive Director) - verify this is current
4. Official website and contact information (phone, email)
5. Brief description of the transit system

Prioritize official sources (.gov domains, the agency's own website, official press releases).

CRITICAL: After researching, respond with ONLY a valid JSON object. No markdown, no explanation.

Only include fields where you found clear, reliable information. Omit uncertain fields.

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
  "email_domain": "domain.org"
}"""


class AgencyAgent(BaseAgent):
    """Agent for creating and updating transit agency records."""
    
    @property
    def agent_type(self) -> str:
        return 'agency'
    
    def execute(self, input_data: dict, existing_record: Any | None = None) -> AgentResult:
        """
        Execute agency research and data extraction in a single LLM call.
        
        Args:
            input_data: {'name': 'Agency Name'} - the agency to research
            existing_record: Optional Agency model instance for updates
            
        Returns:
            AgentResult with draft agency data
        """
        self._logs = []  # Reset logs for new execution
        
        agency_name = input_data.get('name', '').strip()
        if not agency_name:
            return self._create_result(
                success=False,
                error='Agency name is required',
            )
        
        self._log('decision', {'action': 'start', 'agency_name': agency_name})
        
        try:
            # Single call: research + extract
            draft = self._research_and_extract(agency_name)
            
            if '_parse_error' in draft:
                self._log('error', {
                    'stage': 'extraction',
                    'error': draft.get('_parse_error'),
                })
                return self._create_result(
                    success=False,
                    error=f"Failed to parse response: {draft.get('_parse_error')}",
                )
            
            # Try to fetch logo if we have a website
            if draft.get('website'):
                self._fetch_agency_images(draft)
            
            # Compute diff if updating
            diff = None
            is_update = existing_record is not None
            
            if is_update:
                existing_data = self._record_to_dict(existing_record)
                diff = self._compute_diff(existing_data, draft)
                self._log('decision', {
                    'action': 'computed_diff',
                    'changed_fields': list(diff.keys()),
                })
            
            result = self._create_result(
                success=True,
                draft=draft,
                skipped_fields={},
                diff=diff,
                is_update=is_update,
            )
            
            self._save_audit_log(result, input_data)
            
            return result
            
        except Exception as e:
            self._log('error', {'stage': 'execution', 'error': str(e)})
            return self._create_result(
                success=False,
                error=str(e),
            )
    
    def _research_and_extract(self, agency_name: str) -> dict:
        """
        Single LLM call: search the web and return structured JSON.
        """
        messages = [
            {
                'role': 'user',
                'content': f'Research the public transit agency "{agency_name}" and return the JSON data.',
            }
        ]
        
        response = self._call_llm(messages, SYSTEM_PROMPT, use_search=True)
        
        return self._extract_json_from_response(response.content)
    
    def _extract_json_from_response(self, content: str) -> dict:
        """Extract JSON from LLM response, handling various formats."""
        content = content.strip()
        
        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Remove markdown code blocks
        if '```' in content:
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    pass
        
        # Find JSON object between first { and last }
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError as e:
                return {
                    '_parse_error': f'Found JSON-like content but failed to parse: {e}',
                    '_raw_content': content[start:end + 1][:500],
                }
        
        return {
            '_parse_error': 'Could not find valid JSON in response',
            '_raw_content': content[:500],
        }
    
    def _fetch_agency_images(self, draft: dict) -> None:
        """Attempt to fetch logo and header images."""
        website = draft.get('website')
        short_name = draft.get('short_name') or draft.get('name', 'agency')
        
        logo_result = self._call_tool('image_fetch', {
            'entity_type': 'agency',
            'entity_name': draft.get('name', ''),
            'short_name': short_name,
            'website_url': website,
            'image_type': 'logo',
        })
        
        if logo_result.success:
            draft['_logo_fetched'] = True
            draft['_logo_path'] = logo_result.data.get('filepath')
        
        header_result = self._call_tool('image_fetch', {
            'entity_type': 'agency',
            'entity_name': draft.get('name', ''),
            'short_name': short_name,
            'website_url': website,
            'image_type': 'header',
        })
        
        if header_result.success:
            draft['_header_fetched'] = True
            draft['_header_path'] = header_result.data.get('filepath')
    
    def _record_to_dict(self, record) -> dict:
        """Convert an Agency model instance to a dict for comparison."""
        return {
            'name': record.name,
            'short_name': record.short_name,
            'location': record.location,
            'description': record.description,
            'website': record.website,
            'ceo': record.ceo,
            'address_hq': record.address_hq,
            'phone_number': record.phone_number,
            'contact_email': record.contact_email,
            'transit_map_link': record.transit_map_link,
            'email_domain': record.email_domain,
        }


# Singleton instance
agency_agent = AgencyAgent()