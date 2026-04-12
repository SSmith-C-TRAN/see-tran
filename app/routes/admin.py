# app/routes/admin.py
"""
Admin routes including agent management UI.
"""

from flask import Blueprint, render_template, request, jsonify, session
from app import db
from app.auth import login_required, admin_required
from app.models.tran import Agency, Suggestion, User
from app.agents.agency_agent import research as agency_research, _apply_to_agency
from app.utils.errors import api_ok, api_error
from datetime import datetime


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
    from flask import current_app
    agencies = Agency.query.order_by(Agency.name.asc()).all()
    agent_model = current_app.config['AGENT_MODELS']['agency']
    return render_template('admin/agency_agent.html', agencies=agencies, agent_model=agent_model)


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
            return api_error('Agency not found', 404)
        if not agency_name:
            agency_name = existing_record.name

    if not agency_name:
        return api_error('Agency name is required', 400)
    
    result = agency_research(agency_name, existing_record=existing_record)
    
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
    
    return api_ok(response_dict)


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
        return api_error('No draft data provided', 400)

    if not draft.get('name'):
        return api_error('Agency name is required', 400)
    
    try:
        if agency_id:
            # Update existing
            agency = Agency.query.get(agency_id)
            if not agency:
                return api_error('Agency not found', 404)

            _apply_to_agency(agency, draft)
            db.session.commit()

            return api_ok({'message': f"Agency '{agency.name}' updated successfully", 'agency_id': agency.id})
        else:
            # Create new
            # Check for duplicate
            existing = Agency.query.filter(Agency.name.ilike(draft['name'])).first()
            if existing:
                return api_error(f"Agency '{draft['name']}' already exists (ID: {existing.id})", 409)

            agency = Agency()
            _apply_to_agency(agency, draft)
            db.session.add(agency)
            db.session.commit()

            return api_ok({'message': f"Agency '{agency.name}' created successfully", 'agency_id': agency.id})

    except Exception as e:
        db.session.rollback()
        return api_error(str(e), 500)



@admin_bp.route('/api/agents/agency/preview/<int:agency_id>')
@login_required
def preview_agency_update(agency_id):
    """Get current agency data for preview before running agent."""
    agency = Agency.query.get_or_404(agency_id)
    
    return api_ok({
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


# =============================================================================
# Suggestion Reviewer Routes
# =============================================================================

ENTITY_MODEL_MAP = {
    'agency': Agency,
}


@admin_bp.route('/suggestions')
@login_required
@admin_required
def suggestions_page():
    """Suggestion reviewer UI."""
    status_filter = request.args.get('status', 'pending')
    entity_filter = request.args.get('entity_type', '')

    q = Suggestion.query.order_by(Suggestion.created_at.desc())
    if status_filter and status_filter != 'all':
        q = q.filter(Suggestion.status == status_filter)
    if entity_filter:
        q = q.filter(Suggestion.entity_type == entity_filter)

    page = max(request.args.get('page', 1, type=int), 1)
    pagination = q.paginate(page=page, per_page=50, error_out=False)

    # Stats
    pending_count = Suggestion.query.filter_by(status='pending').count()
    accepted_count = Suggestion.query.filter_by(status='accepted').count()
    rejected_count = Suggestion.query.filter_by(status='rejected').count()

    return render_template(
        'admin/suggestions.html',
        suggestions=pagination.items,
        pagination=pagination,
        status_filter=status_filter,
        entity_filter=entity_filter,
        pending_count=pending_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
    )


@admin_bp.route('/api/suggestions/<int:suggestion_id>/review', methods=['POST'])
@login_required
@admin_required
def review_suggestion(suggestion_id):
    """Accept or reject a suggestion."""
    s = Suggestion.query.get(suggestion_id)
    if not s:
        return api_error('Suggestion not found', 404)

    data = request.get_json() or {}
    action = data.get('action')  # 'accept' or 'reject'
    note = data.get('note', '').strip()

    if action not in ('accept', 'reject'):
        return api_error("action must be 'accept' or 'reject'", 400)

    if s.status != 'pending':
        return api_error(f'Suggestion already {s.status}', 409)

    user_email = session.get('user', {}).get('email')
    reviewer = User.query.filter_by(email=user_email).first() if user_email else None

    if action == 'accept':
        # Apply the suggested value to the entity
        model_cls = ENTITY_MODEL_MAP.get(s.entity_type)
        if model_cls:
            entity = model_cls.query.get(s.entity_id)
            if entity and hasattr(entity, s.field):
                setattr(entity, s.field, s.suggested_value)

        s.status = 'accepted'
    else:
        s.status = 'rejected'

    s.reviewed_at = datetime.utcnow()
    s.reviewed_by_user_id = reviewer.id if reviewer else None
    s.review_note = note

    try:
        db.session.commit()
        return api_ok({'id': s.id, 'status': s.status})
    except Exception as e:
        db.session.rollback()
        return api_error(str(e), 500)


@admin_bp.route('/api/suggestions/batch', methods=['POST'])
@login_required
@admin_required
def batch_review_suggestions():
    """Accept or reject multiple suggestions at once."""
    data = request.get_json() or {}
    ids = data.get('ids', [])
    action = data.get('action')
    note = data.get('note', '').strip()

    if not ids:
        return api_error('No suggestion IDs provided', 400)
    if action not in ('accept', 'reject'):
        return api_error("action must be 'accept' or 'reject'", 400)

    user_email = session.get('user', {}).get('email')
    reviewer = User.query.filter_by(email=user_email).first() if user_email else None

    updated = 0
    for s in Suggestion.query.filter(Suggestion.id.in_(ids), Suggestion.status == 'pending').all():
        if action == 'accept':
            model_cls = ENTITY_MODEL_MAP.get(s.entity_type)
            if model_cls:
                entity = model_cls.query.get(s.entity_id)
                if entity and hasattr(entity, s.field):
                    setattr(entity, s.field, s.suggested_value)
            s.status = 'accepted'
        else:
            s.status = 'rejected'

        s.reviewed_at = datetime.utcnow()
        s.reviewed_by_user_id = reviewer.id if reviewer else None
        s.review_note = note
        updated += 1

    try:
        db.session.commit()
        return api_ok({'updated': updated})
    except Exception as e:
        db.session.rollback()
        return api_error(str(e), 500)