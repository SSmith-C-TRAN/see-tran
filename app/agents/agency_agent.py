# app/agents/agency_agent.py
"""
Agency Agent - builds or updates transit agency records using LLM with web search.
"""

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
        'confidence': {
            'type': 'object',
            'description': 'Confidence scores (0-1) for each field',
            'properties': {
                'name': {'type': 'number'},
                'short_name': {'type': 'number'},
                'location': {'type': 'number'},
                'description': {'type': 'number'},
                'website': {'type': 'number'},
                'ceo': {'type': 'number'},
                'address_hq': {'type': 'number'},
                'phone_number': {'type': 'number'},
                'contact_email': {'type': 'number'},
                'transit_map_link': {'type': 'number'},
                'email_domain': {'type': 'number'},
            },
        },
    },
    'required': ['name', 'confidence'],
}


SEARCH_SYSTEM_PROMPT = """You are a research assistant gathering information about public transit agencies.

Your task is to find accurate, current information about the specified transit agency. Focus on:
1. Official name and common abbreviations
2. Headquarters location and address
3. Current leadership (CEO/General Manager/Executive Director)
4. Official website and contact information
5. System description

Use web search to find the most up-to-date information. Prioritize official sources (.gov domains, 
the agency's own website, official press releases) over third-party sources.

Be thorough but concise. If you cannot find certain information with confidence, note that."""


EXTRACTION_SYSTEM_PROMPT = """You are a data extraction assistant. Your job is to extract structured 
information about a transit agency from the provided research text.

Extract the following fields if available:
- name: The official full name of the agency
- short_name: Common abbreviation or acronym (e.g., BART, WMATA, TriMet)
- location: City and state where the agency is headquartered
- description: A brief 1-2 sentence description of what the agency operates
- website: The official website URL (must start with http:// or https://)
- ceo: The current CEO, General Manager, or Executive Director's full name
- address_hq: Full headquarters mailing address
- phone_number: Main contact phone number
- contact_email: General contact email address
- transit_map_link: URL to the system/route map
- email_domain: The domain used for agency emails (e.g., trimet.org)

For each field, also provide a confidence score from 0 to 1:
- 1.0: Found on official source, very confident
- 0.8-0.9: Found on reliable source, confident
- 0.5-0.7: Found but uncertain or potentially outdated
- Below 0.5: Guessed or very uncertain

If a field cannot be determined, omit it from the response (don't include null values).
Only include the confidence object with scores for fields you did include."""


class AgencyAgent(BaseAgent):
    """Agent for creating and updating transit agency records."""
    
    @property
    def agent_type(self) -> str:
        return 'agency'
    
    def execute(self, input_data: dict, existing_record: Any | None = None) -> AgentResult:
        """
        Execute agency research and data extraction.
        
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
            # Step 1: Research the agency using web search
            research_text = self._research_agency(agency_name)
            
            if not research_text:
                return self._create_result(
                    success=False,
                    error='Failed to gather agency information',
                )
            
            # Step 2: Extract structured data
            extracted = self._extract_agency_data(agency_name, research_text)
            
            if '_parse_error' in extracted:
                self._log('error', {
                    'stage': 'extraction',
                    'error': extracted.get('_parse_error'),
                })
                return self._create_result(
                    success=False,
                    error=f"Failed to parse extracted data: {extracted.get('_parse_error')}",
                )
            
            # Step 3: Apply confidence filtering
            confidences = extracted.pop('confidence', {})
            draft, skipped = self._filter_by_confidence(extracted, confidences)
            
            # Step 4: Try to fetch logo if we have a website
            if draft.get('website'):
                self._fetch_agency_images(draft)
            
            # Step 5: Compute diff if updating
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
                skipped_fields=skipped,
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
    
    def _research_agency(self, agency_name: str) -> str | None:
        """Use LLM with web search to research the agency."""
        messages = [
            {
                'role': 'user',
                'content': f"""Research the public transit agency: "{agency_name}"

Find and summarize:
1. Official name and any common abbreviations
2. Location (city, state)
3. What type of transit they operate (bus, rail, ferry, etc.)
4. Current CEO/General Manager/Executive Director
5. Official website
6. Headquarters address and contact information
7. Any other relevant details

Provide a comprehensive summary of your findings.""",
            }
        ]
        
        response = self._call_llm(messages, SEARCH_SYSTEM_PROMPT, use_search=True)
        return response.content if response else None
    
    def _extract_agency_data(self, agency_name: str, research_text: str) -> dict:
        """Extract structured data from research text."""
        messages = [
            {
                'role': 'user',
                'content': f"""Based on the following research about "{agency_name}", extract structured data.

RESEARCH:
{research_text}

Extract the agency information into the required JSON format with confidence scores.""",
            }
        ]
        
        return self._call_llm_structured(messages, EXTRACTION_SYSTEM_PROMPT, AGENCY_SCHEMA)
    
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