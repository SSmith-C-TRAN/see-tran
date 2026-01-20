# app/agents/agency_agent.py
"""
Agency Agent - builds or updates transit agency records using LLM with web search.

Uses a two-step approach:
1. Research with web search (allows citations, natural language)
2. Extract structured data (clean JSON output)
"""

import json
import re
import time
from typing import Any

from .base import BaseAgent, AgentResult


# Schema for structured agency data extraction
AGENCY_SCHEMA = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string', 'description': 'Official agency name'},
        'short_name': {'type': 'string', 'description': 'Short name/acronym (e.g., WMATA, BART)'},
        'location': {'type': 'string', 'description': 'City and state (e.g., Portland, Oregon)'},
        'description': {'type': 'string', 'description': 'Brief description of the agency (1-2 sentences)'},
        'website': {'type': 'string', 'description': 'Official website URL'},
        'ceo': {'type': 'string', 'description': 'Current CEO/General Manager/Executive Director name'},
        'address_hq': {'type': 'string', 'description': 'Headquarters address'},
        'phone_number': {'type': 'string', 'description': 'Main phone number'},
        'contact_email': {'type': 'string', 'description': 'General contact email'},
        'transit_map_link': {'type': 'string', 'description': 'URL to system map'},
        'email_domain': {'type': 'string', 'description': 'Agency email domain (e.g., trimet.org)'},
    },
    'required': ['name'],
}


RESEARCH_SYSTEM_PROMPT = """You are a research assistant gathering information about public transit agencies.

Your task is to search the web for accurate, current information about the specified transit agency.

Research priorities:
1. Official name and common abbreviations
2. Headquarters location and full address  
3. Current leadership (CEO/General Manager/Executive Director) - verify this is current
4. Official website and contact information (phone, email)
5. Brief description of the transit system

Prioritize official sources (.gov domains, the agency's own website, official press releases) over third-party sources.

Summarize your findings clearly, noting the source for key facts like leadership names."""


EXTRACTION_SYSTEM_PROMPT = """You are a data extraction assistant. Your task is to extract structured data from research findings.

CRITICAL: Respond with ONLY a valid JSON object. No markdown code blocks, no explanation, no text before or after the JSON.

Only include fields where the research provides clear, reliable information. Omit fields that are uncertain or not found.

JSON Schema:
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
        Execute agency research and data extraction.
        
        Uses a two-step approach:
        1. Research with web search enabled (natural language response)
        2. Extract structured JSON from research findings
        
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
            # Step 1: Research with web search
            research_findings = self._research_agency(agency_name)
            
            if not research_findings:
                return self._create_result(
                    success=False,
                    error='Research step returned no findings',
                )
            
            # Step 2: Extract structured data
            draft = self._extract_structured_data(research_findings)
            
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
            
            # Save audit log
            self._save_audit_log(result, input_data)
            
            return result
            
        except Exception as e:
            self._log('error', {'stage': 'execution', 'error': str(e)})
            return self._create_result(
                success=False,
                error=str(e),
            )
    
    def _research_agency(self, agency_name: str) -> str:
        """
        Step 1: Research the agency using web search.
        
        Returns natural language findings that may include citations.
        """
        messages = [
            {
                'role': 'user',
                'content': f'Research the public transit agency "{agency_name}". Find their official name, current leadership, headquarters address, website, and contact information.',
            }
        ]
        
        self._log('decision', {'action': 'research_start', 'agency_name': agency_name})
        
        response = self._call_llm(messages, RESEARCH_SYSTEM_PROMPT, use_search=True)
        
        self._log('decision', {
            'action': 'research_complete',
            'response_length': len(response.content),
        })
        
        return response.content
    
    def _extract_structured_data(self, research_findings: str) -> dict:
        """
        Step 2: Extract structured JSON from research findings.
        
        Uses a separate LLM call without web search for cleaner output.
        """
        time.sleep(0.5)  # Brief pause to ensure separation between calls
        messages = [
            {
                'role': 'user',
                'content': f'Extract structured agency data from these research findings:\n\n{research_findings}',
            }
        ]
        
        self._log('decision', {'action': 'extraction_start'})
        
        # Use regular completion (no search) for clean JSON output
        response = self._call_llm(messages, EXTRACTION_SYSTEM_PROMPT, use_search=False)
        
        return self._extract_json_from_response(response.content)
    
    def _extract_json_from_response(self, content: str) -> dict:
        """
        Extract JSON from LLM response, handling various formats.
        
        Handles:
        - Clean JSON
        - JSON wrapped in markdown code blocks
        - JSON embedded in other text
        """
        content = content.strip()
        
        # Try direct parse first (ideal case)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Remove markdown code blocks
        if '```' in content:
            # Match ```json ... ``` or ``` ... ```
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    pass
        
        # Find JSON object in the response (between first { and last })
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
        
        # Fetch logo
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
        
        # Fetch header
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


# Singleton instance for easy import
agency_agent = AgencyAgent()