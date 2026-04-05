# app/agents/vendor_agent.py
"""
Vendor agent — Phase 2, not yet implemented.
"""

from .utils import AgentResult


def run(vendor_id: int, *, dry_run: bool = False) -> AgentResult:
    """Research a vendor by ID. Not yet implemented."""
    return AgentResult(
        success=False,
        error='vendor_agent is not yet implemented (Phase 2)',
    )
