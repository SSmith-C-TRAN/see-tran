from flask import Blueprint, render_template, redirect, url_for, request
from app import db
from app.models.tran import Agency
from app.forms.forms import AgencyForm

agency_bp = Blueprint('agency', __name__, url_prefix='/agencies')


@agency_bp.route('/')
@agency_bp.route('/<int:page>/', methods=['GET'])
def index(page=1):
    per_page = 10
    agencies = Agency.query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('agencies.html', agencies=agencies)


@agency_bp.route('/new', methods=['POST'])
def add_agency():
    """Create a new agency (form POST, redirects on success)."""
    form = AgencyForm()
    if form.validate_on_submit():
        try:
            agency = Agency()
            form.populate_agency(agency)
            agency.short_name = request.form.get('short_name') or None
            db.session.add(agency)
            db.session.commit()
            return redirect(url_for('agency.index'))
        except Exception as e:
            db.session.rollback()
            return render_template('fragments/agency_form.html', form=form, agency=None)
    return render_template('fragments/agency_form.html', form=form, agency=None)
