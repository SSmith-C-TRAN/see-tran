"""Regression tests for agency agent output sanitization."""

from types import SimpleNamespace

from app.agents.agency_agent import AGENCY_FIELDS, _apply_to_agency, _sanitize_draft


def _blank_agency():
    return SimpleNamespace(**{field: None for field in AGENCY_FIELDS})


def test_sanitize_draft_strips_citations_and_html_tags():
    draft = {
        'name': 'Intercity Transit',
        'description': '<cite index="2-1,2-2">Intercity Transit serves Olympia and surrounding areas.</cite>',
        'ceo': '<cite index="32-1">Emily Bergkamp, General Manager</cite>',
        'contact_email': '<cite index="31-1">customerservice@intercitytransit.com</cite>',
        'website': '<cite index="31-1">https://www.intercitytransit.com</cite> [1]',
        'unexpected_key': 'should not survive',
    }

    sanitized = _sanitize_draft(draft)

    assert sanitized['description'] == 'Intercity Transit serves Olympia and surrounding areas.'
    assert sanitized['ceo'] == 'Emily Bergkamp, General Manager'
    assert sanitized['contact_email'] == 'customerservice@intercitytransit.com'
    assert sanitized['website'] == 'https://www.intercitytransit.com'
    assert 'unexpected_key' not in sanitized


def test_sanitize_draft_normalizes_email_domain():
    draft = {
        'name': 'Example Transit',
        'email_domain': 'mailto:INFO@InterCityTransit.com',
    }

    sanitized = _sanitize_draft(draft)

    assert sanitized['email_domain'] == 'intercitytransit.com'


def test_apply_to_agency_sanitizes_commit_payload_values():
    agency = _blank_agency()

    _apply_to_agency(
        agency,
        {
            'description': '<b>Regional transit service</b> [1]',
            'website': 'Official site: <cite index="7">https://agency.example.org</cite>',
            'ceo': '<cite index="8">Alex Doe</cite>',
        },
    )

    assert agency.description == 'Regional transit service'
    assert agency.website == 'https://agency.example.org'
    assert agency.ceo == 'Alex Doe'
