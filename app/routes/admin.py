# app/routes/admin.py
"""
Admin routes including agent management UI.
"""

from flask import Blueprint, render_template, request, jsonify, session
from app import db
from app.auth import login_required, admin_required
from app.models.tran import Agency
from app.agents import agency_agent


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@login_required
def dashboard():
    """Admin dashboard."""
    return render_template('admin/dashboard.html')


# =============================================================================
# Agency Agent Routes
# =============================================================================

@admin_bp.route('/agents/agency')
@login_required
def agency_agent_page():
    """Agency agent UI page."""
    agencies = Agency.query.order_by(Agency.name.asc()).all()
    return render_template('admin/agency_agent.html', agencies=agencies)


@admin_bp.route('/api/agents/agency/run', methods=['POST'])
@login_required
def run_agency_agent():
    """Execute the agency agent."""
    data = request.get_json() or {}
    
    agency_name = data.get('name', '').strip()
    agency_id = data.get('agency_id')
    
    existing_record = None
    if agency_id:
        existing_record = Agency.query.get(agency_id)
        if not existing_record:
            return jsonify({'success': False, 'error': 'Agency not found'}), 404
        if not agency_name:
            agency_name = existing_record.name
    
    if not agency_name:
        return jsonify({'success': False, 'error': 'Agency name is required'}), 400
    
    result = agency_agent.execute(
        input_data={'name': agency_name},
        existing_record=existing_record,
    )
    
    # Convert to dict and sanitize for JSON serialization
    response_dict = result.to_dict()
    
    # Sanitize logs - truncate large entries and remove non-serializable content
    if 'logs' in response_dict:
        sanitized_logs = []
        for log in response_dict.get('logs', []):
            sanitized_log = {
                'event_type': log.get('event_type', ''),
                'timestamp': log.get('timestamp', ''),
            }
            # Truncate details to avoid huge payloads
            details = log.get('details', {})
            if isinstance(details, dict):
                sanitized_details = {}
                for k, v in details.items():
                    if isinstance(v, str) and len(v) > 200:
                        sanitized_details[k] = v[:200] + '...'
                    elif k not in ('raw_response', '_raw_content'):  # Skip large fields
                        sanitized_details[k] = v
                sanitized_log['details'] = sanitized_details
            sanitized_logs.append(sanitized_log)
        response_dict['logs'] = sanitized_logs
    
    # Remove raw_response from draft if present (can contain circular refs)
    if response_dict.get('draft'):
        response_dict['draft'].pop('_raw_content', None)
        response_dict['draft'].pop('raw_response', None)
    
    return jsonify(response_dict)


@admin_bp.route('/api/agents/agency/commit', methods=['POST'])
@login_required
def commit_agency_agent():
    """
    Commit the agent's proposed changes to the database.
    
    Request body:
        - draft: The proposed field values
        - agency_id: Existing agency ID (optional, for updates)
    """
    data = request.get_json() or {}
    
    draft = data.get('draft', {})
    agency_id = data.get('agency_id')
    
    if not draft:
        return jsonify({'success': False, 'error': 'No draft data provided'}), 400
    
    if not draft.get('name'):
        return jsonify({'success': False, 'error': 'Agency name is required'}), 400
    
    try:
        if agency_id:
            # Update existing
            agency = Agency.query.get(agency_id)
            if not agency:
                return jsonify({'success': False, 'error': 'Agency not found'}), 404
            
            _apply_draft_to_agency(agency, draft)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f"Agency '{agency.name}' updated successfully",
                'agency_id': agency.id,
            })
        else:
            # Create new
            # Check for duplicate
            existing = Agency.query.filter(Agency.name.ilike(draft['name'])).first()
            if existing:
                return jsonify({
                    'success': False,
                    'error': f"Agency '{draft['name']}' already exists (ID: {existing.id})",
                }), 409
            
            agency = Agency()
            _apply_draft_to_agency(agency, draft)
            db.session.add(agency)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f"Agency '{agency.name}' created successfully",
                'agency_id': agency.id,
            })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


def _apply_draft_to_agency(agency: Agency, draft: dict) -> None:
    """Apply draft fields to an Agency model."""
    # Map draft keys to model fields
    field_map = {
        'name': 'name',
        'short_name': 'short_name',
        'location': 'location',
        'description': 'description',
        'website': 'website',
        'ceo': 'ceo',
        'address_hq': 'address_hq',
        'phone_number': 'phone_number',
        'contact_email': 'contact_email',
        'transit_map_link': 'transit_map_link',
        'email_domain': 'email_domain',
    }
    
    for draft_key, model_field in field_map.items():
        if draft_key in draft:
            value = draft[draft_key]
            # Don't set empty strings
            if value == '':
                value = None
            setattr(agency, model_field, value)


@admin_bp.route('/api/agents/agency/preview/<int:agency_id>')
@login_required
def preview_agency_update(agency_id):
    """Get current agency data for preview before running agent."""
    agency = Agency.query.get_or_404(agency_id)
    
    return jsonify({
        'id': agency.id,
        'name': agency.name,
        'short_name': agency.short_name,
        'location': agency.location,
        'description': agency.description,
        'website': agency.website,
        'ceo': agency.ceo,
        'address_hq': agency.address_hq,
        'phone_number': agency.phone_number,
        'contact_email': agency.contact_email,
        'transit_map_link': agency.transit_map_link,
        'email_domain': agency.email_domain,
    })