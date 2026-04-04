from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from app import db
from app.models.tran import Agency, Configuration, ConfigurationProduct, Product, Vendor, Function, FunctionalArea
from app.forms.forms import AgencyForm
from app.utils.errors import api_ok, api_form_errors
from sqlalchemy import func

agency_bp = Blueprint('agency', __name__, url_prefix='/agencies')

@agency_bp.route('/')
@agency_bp.route('/<int:page>/', methods=['GET'])
def index(page=1):
    per_page = 10
    agencies = Agency.query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('agencies.html', agencies=agencies)

# ---------- API: list (fragment) ----------
@agency_bp.route('/api/agencies/list')
def api_agencies_list():
    search = (request.args.get('search') or '').strip()
    q = Agency.query
    if search:
        q = q.filter(Agency.name.ilike(f"%{search}%"))
    agencies = q.order_by(Agency.name.asc()).all()
    return render_template('fragments/agency_list.html', agencies=agencies)

# ---------- API: stats ----------
@agency_bp.route('/api/agencies/stats')
def api_agencies_stats():
    total_agencies = Agency.query.count()
    active_cfgs = Configuration.query.count()
    avg_impl = round(active_cfgs / total_agencies, 1) if total_agencies else 0
    # Vendors per agency via products used in configurations
    # Count distinct vendor per agency, then average
    vendor_counts = db.session.query(
        Configuration.agency_id, func.count(func.distinct(Vendor.id)).label('v_count')
    ).join(ConfigurationProduct, ConfigurationProduct.configuration_id == Configuration.id)
    vendor_counts = vendor_counts.join(Product, Product.id == ConfigurationProduct.product_id)
    vendor_counts = vendor_counts.join(Vendor, Vendor.id == Product.vendor_id)
    vendor_counts = vendor_counts.group_by(Configuration.agency_id).all()
    avg_vendors = 0
    if vendor_counts:
        avg_vendors = round(sum(vc.v_count for vc in vendor_counts) / len(vendor_counts), 1)
    return api_ok({
        'active_implementations': active_cfgs,
        'avg_implementations_per_agency': avg_impl,
        'avg_vendors_per_agency': avg_vendors
    })

# ---------- API: insights ----------
@agency_bp.route('/api/agencies/insights')
def api_agencies_insights():
    # Tech leader: agency with most configurations
    tech_leader_row = db.session.query(
        Agency.name, func.count(Configuration.id).label('cfg_count')
    ).join(Configuration, Configuration.agency_id == Agency.id)
    tech_leader_row = tech_leader_row.group_by(Agency.id).order_by(func.count(Configuration.id).desc()).first()

    # Common area: functional area most represented in configurations
    area_row = db.session.query(
        FunctionalArea.name, func.count(Configuration.id).label('cfg_count')
    ).join(Function, Function.functional_area_id == FunctionalArea.id)
    area_row = area_row.join(Configuration, Configuration.function_id == Function.id)
    area_row = area_row.group_by(FunctionalArea.id).order_by(func.count(Configuration.id).desc()).first()

    # Top vendor: vendor whose products appear in most configurations
    top_vendor_row = db.session.query(
        Vendor.name, func.count(func.distinct(Configuration.id)).label('cfg_use')
    ).join(Product, Product.vendor_id == Vendor.id)
    top_vendor_row = top_vendor_row.join(ConfigurationProduct, ConfigurationProduct.product_id == Product.id)
    top_vendor_row = top_vendor_row.join(Configuration, Configuration.id == ConfigurationProduct.configuration_id)
    top_vendor_row = top_vendor_row.group_by(Vendor.id).order_by(func.count(func.distinct(Configuration.id)).desc()).first()

    return api_ok({
        'tech_leader': tech_leader_row.name if tech_leader_row else 'N/A',
        'common_area': area_row.name if area_row else 'N/A',
        'top_vendor': top_vendor_row.name if top_vendor_row else 'N/A'
    })

# ---------- API: details (fragment) ----------
@agency_bp.route('/api/agencies/<int:agency_id>/details')
def api_agency_details(agency_id):
    agency = Agency.query.get_or_404(agency_id)
    # Compute basic configuration usage summary
    cfg_count = db.session.query(func.count(Configuration.id)).filter(Configuration.agency_id == agency_id).scalar()
    # Top functional areas for this agency
    area_rows = db.session.query(
        FunctionalArea.name, func.count(Configuration.id).label('cfg_count')
    ).join(Function, Function.functional_area_id == FunctionalArea.id)
    area_rows = area_rows.join(Configuration, Configuration.function_id == Function.id)
    area_rows = area_rows.filter(Configuration.agency_id == agency_id)
    area_rows = area_rows.group_by(FunctionalArea.id).order_by(func.count(Configuration.id).desc()).limit(5).all()
    areas = [{'name': r.name, 'count': r.cfg_count} for r in area_rows]
    return render_template('fragments/agency_details.html', agency=agency, cfg_count=cfg_count, top_areas=areas)

# ---------- API: form (fragment) ----------
@agency_bp.route('/api/agencies/form')
def api_agency_form():
    form = AgencyForm()
    return render_template('fragments/agency_form.html', form=form, agency=None)

@agency_bp.route('/api/agencies/<int:agency_id>/form')
def api_agency_edit_form(agency_id):
    agency = Agency.query.get_or_404(agency_id)
    form = AgencyForm()
    form.populate_agency(agency)
    return render_template('fragments/agency_form.html', form=form, agency=agency)

# ---------- API: create/update ----------
@agency_bp.route('/api/agencies', methods=['POST'])
def api_create_agency():
    form = AgencyForm()
    if form.validate_on_submit():
        agency = Agency()
        form.populate_agency(agency)
        agency.short_name = request.form.get('short_name') or None
        db.session.add(agency)
        db.session.commit()
        return api_ok({'id': agency.id})
    return api_form_errors(form)

@agency_bp.route('/api/agencies/<int:agency_id>', methods=['POST'])
def api_update_agency(agency_id):
    agency = Agency.query.get_or_404(agency_id)
    form = AgencyForm()
    if form.validate_on_submit():
        form.populate_agency(agency)
        agency.short_name = request.form.get('short_name') or None
        db.session.commit()
        return api_ok({'id': agency.id})
    return api_form_errors(form)
