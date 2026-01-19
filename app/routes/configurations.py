# app/routes/configurations.py
import csv
from io import StringIO
from flask import Blueprint, render_template, request, jsonify, Response
from app import db
from app.auth import login_required, get_updated_by
from app.models.tran import (
    Configuration, ConfigurationHistory, ConfigurationProduct,
    Product, ProductVersion, Agency, Function, Component, Vendor, FunctionalArea
)
from app.forms.forms import (
    ConfigurationForm, ConfigurationProductForm, ProductForm, ProductVersionForm
)
from sqlalchemy.orm import joinedload
from datetime import datetime

config_bp = Blueprint('configurations', __name__)

# --------- Helper / Advisory Stub ---------

def advisory_validate(configuration: Configuration, products):
    """Return non-blocking advisory warning dicts (stub)."""
    warnings = []
    # Placeholder examples
    # warnings.append({"code": "EOL_VERSION", "message": "One product version near end-of-life."})
    return warnings

# Helper: parse product_ids from args or form (supports repeated params and comma-separated)
def _parse_product_ids(arg_source) -> list[int]:
    ids: list[int] = []
    if hasattr(arg_source, 'getlist'):
        raw_list = arg_source.getlist('product_ids')
    else:
        raw_list = []
    # Also support comma-separated single value
    raw_single = arg_source.get('product_ids') if hasattr(arg_source, 'get') else None
    if raw_single and isinstance(raw_single, str) and ',' in raw_single:
        raw_list.extend(raw_single.split(','))
    elif raw_single and not raw_list:
        raw_list.append(raw_single)
    # Normalize & dedupe
    for pid in raw_list:
        try:
            pid_int = int(str(pid).strip())
            ids.append(pid_int)
        except (TypeError, ValueError):
            continue
    # unique preserve order
    seen = set()
    result = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            result.append(i)
    return result

# --------- Pages ---------

@config_bp.route('/configurations')
@login_required
def configurations_page():
    agencies = Agency.query.order_by(Agency.name.asc()).all()
    functions = Function.query.order_by(Function.name.asc()).all()
    return render_template('configurations.html', agencies=agencies, functions=functions, selected_agency_id=None)

@config_bp.route('/agencies/<int:agency_id>/configurations')
@login_required
def agency_configurations_page(agency_id):
    agency = Agency.query.get_or_404(agency_id)
    agencies = Agency.query.order_by(Agency.name.asc()).all()
    functions = Function.query.order_by(Function.name.asc()).all()
    return render_template('configurations.html', agency=agency, agencies=agencies, functions=functions, selected_agency_id=agency.id)

# --------- Configuration API ---------

@config_bp.route('/api/configurations/list')
@login_required
def configurations_list():
    agency_id = request.args.get('agency_id', type=int)
    function_id = request.args.get('function_id', type=int)
    status = (request.args.get('status') or '').strip()
    q = Configuration.query.options(
        joinedload(Configuration.agency),
        joinedload(Configuration.function).joinedload(Function.functional_area),
        joinedload(Configuration.component),
        joinedload(Configuration.products).joinedload(ConfigurationProduct.product).joinedload(Product.vendor),
        joinedload(Configuration.products).joinedload(ConfigurationProduct.product_version)
    )
    if agency_id:
        q = q.filter(Configuration.agency_id == agency_id)
    if function_id:
        q = q.filter(Configuration.function_id == function_id)
    if status:
        q = q.filter(Configuration.status == status)
    configs = q.order_by(Configuration.created_at.desc()).limit(250).all()
    return render_template('fragments/configuration_list.html', configurations=configs)

@config_bp.route('/api/configurations/<int:config_id>/row')
@login_required
def configuration_row(config_id):
    c = Configuration.query.get_or_404(config_id)
    return render_template('fragments/configuration_row.html', c=c)

@config_bp.route('/api/configurations/<int:config_id>/details')
@login_required
def configuration_details(config_id):
    c = Configuration.query.get_or_404(config_id)
    warnings = advisory_validate(c, [cp.product for cp in c.products])
    return render_template('fragments/configuration_details.html', c=c, warnings=warnings)

@config_bp.route('/api/configurations', methods=['POST'])
@login_required
def configuration_create():
    form = ConfigurationForm()
    if form.validate_on_submit():
        c = Configuration()
        form.populate_configuration(c)
        db.session.add(c)
        db.session.flush()
        hist = ConfigurationHistory(configuration_id=c.id, action='created', changed_by=get_updated_by(), new_values={})
        db.session.add(hist)
        db.session.commit()
        return render_template('fragments/configuration_row.html', c=c), 201
    return jsonify({'error': 'validation', 'messages': form.errors}), 400

@config_bp.route('/api/configurations/<int:config_id>', methods=['POST'])
@login_required
def configuration_update(config_id):
    c = Configuration.query.get_or_404(config_id)
    form = ConfigurationForm()
    if form.validate_on_submit():
        old = { 'status': c.status, 'version_label': c.version_label }
        form.populate_configuration(c)
        hist = ConfigurationHistory(configuration_id=c.id, action='updated', changed_by=get_updated_by(), old_values=old, new_values={'status': c.status, 'version_label': c.version_label})
        db.session.add(hist)
        db.session.commit()
        return render_template('fragments/configuration_row.html', c=c)
    return jsonify({'error': 'validation', 'messages': form.errors}), 400

@config_bp.route('/api/configurations/<int:config_id>', methods=['DELETE'])
@login_required
def configuration_delete(config_id):
    c = Configuration.query.get_or_404(config_id)
    hist = ConfigurationHistory(configuration_id=c.id, action='deleted', changed_by=get_updated_by(), old_values={'id': c.id})
    db.session.add(hist)
    db.session.delete(c)
    db.session.commit()
    return jsonify({'status': 'deleted', 'id': config_id})

@config_bp.route('/api/configurations/<int:config_id>/history')
@login_required
def configuration_history(config_id):
    c = Configuration.query.get_or_404(config_id)
    history = ConfigurationHistory.query.filter_by(configuration_id=config_id).order_by(ConfigurationHistory.timestamp.desc()).all()
    return render_template('fragments/configuration_history.html', c=c, history=history)

# --------- ConfigurationProduct API ---------

@config_bp.route('/api/configurations/<int:config_id>/products/list')
@login_required
def configuration_products_list(config_id):
    c = Configuration.query.get_or_404(config_id)
    return render_template('fragments/configuration_products_list.html', c=c, products=c.products)

@config_bp.route('/api/configurations/<int:config_id>/products/form')
@login_required
def configuration_product_form(config_id):
    c = Configuration.query.get_or_404(config_id)
    form = ConfigurationProductForm()
    form.configuration_id.data = str(c.id)
    return render_template('fragments/configuration_product_form.html', form=form, configuration=c)

@config_bp.route('/api/configurations/<int:config_id>/products', methods=['POST'])
@login_required
def configuration_product_create(config_id):
    c = Configuration.query.get_or_404(config_id)
    form = ConfigurationProductForm()
    if form.validate_on_submit():
        cp = ConfigurationProduct()
        form.populate_configuration_product(cp)
        cp.configuration_id = c.id
        db.session.add(cp)
        db.session.flush()
        hist = ConfigurationHistory(configuration_id=c.id, action='product_added', changed_by=get_updated_by(), new_values={'configuration_product_id': cp.id})
        db.session.add(hist)
        db.session.commit()
        return render_template('fragments/configuration_products_list.html', c=c, products=c.products)
    return jsonify({'error': 'validation', 'messages': form.errors}), 400

@config_bp.route('/api/configuration-products/<int:cp_id>', methods=['POST'])
@login_required
def configuration_product_update(cp_id):
    cp = ConfigurationProduct.query.get_or_404(cp_id)
    form = ConfigurationProductForm()
    if form.validate_on_submit():
        old = {'status': cp.status}
        form.populate_configuration_product(cp)
        hist = ConfigurationHistory(configuration_id=cp.configuration_id, action='product_updated', changed_by=get_updated_by(), old_values=old, new_values={'status': cp.status})
        db.session.add(hist)
        db.session.commit()
        configuration = Configuration.query.get(cp.configuration_id)
        return render_template('fragments/configuration_products_list.html', c=configuration, products=configuration.products)
    return jsonify({'error': 'validation', 'messages': form.errors}), 400

@config_bp.route('/api/configuration-products/<int:cp_id>', methods=['DELETE'])
@login_required
def configuration_product_delete(cp_id):
    cp = ConfigurationProduct.query.get_or_404(cp_id)
    configuration_id = cp.configuration_id
    hist = ConfigurationHistory(configuration_id=configuration_id, action='product_removed', changed_by=get_updated_by(), old_values={'configuration_product_id': cp.id})
    db.session.add(hist)
    db.session.delete(cp)
    db.session.commit()
    configuration = Configuration.query.get(configuration_id)
    return render_template('fragments/configuration_products_list.html', c=configuration, products=configuration.products)

# --------- Product & Versions API ---------

@config_bp.route('/products')
@login_required
def products_page():
    vendors = Vendor.query.order_by(Vendor.name.asc()).all()
    return render_template('products.html', vendors=vendors)

@config_bp.route('/api/products/list')
@login_required
def products_list():
    vendor_id = request.args.get('vendor_id', type=int)
    search = (request.args.get('q') or request.args.get('search') or '').strip()
    q = Product.query
    if vendor_id:
        q = q.filter(Product.vendor_id == vendor_id)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%"))
    products = q.order_by(Product.name.asc()).limit(250).all()
    return render_template('fragments/product_list.html', products=products)

# New: lightweight product picker endpoint for HTMX search suggestions
@config_bp.route('/api/products/picker')
@login_required
def products_picker():
    search = (request.args.get('q') or '').strip()
    vendor_id = request.args.get('vendor_id', type=int)
    configuration_id = request.args.get('configuration_id', type=int)
    q = Product.query
    if vendor_id:
        q = q.filter(Product.vendor_id == vendor_id)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%"))
    products = q.order_by(Product.name.asc()).limit(50).all()
    return render_template('fragments/product_picker_options.html', products=products, configuration_id=configuration_id)

@config_bp.route('/api/products/<int:product_id>/details')
@login_required
def product_details(product_id):
    p = Product.query.get_or_404(product_id)
    versions = ProductVersion.query.filter_by(product_id=product_id).order_by(ProductVersion.release_date.desc().nullslast()).all()
    return render_template('fragments/product_details.html', p=p, versions=versions)

@config_bp.route('/api/products/form')
@login_required
def product_form():
    form = ProductForm()
    vendors = Vendor.query.order_by(Vendor.name.asc()).all()
    try:
        # If vendor_id is a SelectField, set choices for validation/rendering
        form.vendor_id.choices = [(v.id, v.name) for v in vendors]
    except Exception:
        pass
    return render_template('fragments/product_form.html', form=form, vendors=vendors)

@config_bp.route('/api/products', methods=['POST'])
@login_required
def product_create():
    form = ProductForm()
    vendors = Vendor.query.order_by(Vendor.name.asc()).all()
    try:
        form.vendor_id.choices = [(v.id, v.name) for v in vendors]
    except Exception:
        pass
    if form.validate_on_submit():
        p = Product()
        form.populate_product(p)
        db.session.add(p)
        db.session.commit()
        return render_template('fragments/product_list.html', products=Product.query.order_by(Product.name.asc()).all()), 201
    return jsonify({'error': 'validation', 'messages': form.errors}), 400

@config_bp.route('/api/products/<int:product_id>/versions/list')
@login_required
def product_versions_list(product_id):
    p = Product.query.get_or_404(product_id)
    versions = ProductVersion.query.filter_by(product_id=product_id).order_by(ProductVersion.release_date.desc().nullslast()).all()
    return render_template('fragments/product_versions_list.html', p=p, versions=versions)

@config_bp.route('/api/products/<int:product_id>/versions/form')
@login_required
def product_version_form(product_id):
    p = Product.query.get_or_404(product_id)
    form = ProductVersionForm()
    form.product_id.data = str(p.id)
    return render_template('fragments/product_version_form.html', form=form, product=p)

@config_bp.route('/api/products/<int:product_id>/versions', methods=['POST'])
@login_required
def product_version_create(product_id):
    p = Product.query.get_or_404(product_id)
    form = ProductVersionForm()
    if form.validate_on_submit():
        pv = ProductVersion()
        form.populate_version(pv)
        pv.product_id = p.id
        db.session.add(pv)
        db.session.commit()
        versions = ProductVersion.query.filter_by(product_id=product_id).order_by(ProductVersion.release_date.desc().nullslast()).all()
        return render_template('fragments/product_versions_list.html', p=p, versions=versions), 201
    return jsonify({'error': 'validation', 'messages': form.errors}), 400

# --------- Wizard (Config) ---------

@config_bp.route('/api/wizard/config/step1')
@login_required
def wizard_config_step1():
    selected_agency_id = request.args.get('agency_id', type=int)
    agencies = Agency.query.order_by(Agency.name.asc()).all()
    functions = Function.query.order_by(Function.name.asc()).all()
    functional_areas = FunctionalArea.query.order_by(FunctionalArea.name.asc()).all()
    return render_template('fragments/wizard_config_step1.html', agencies=agencies, functions=functions, functional_areas=functional_areas, selected_agency_id=selected_agency_id)

@config_bp.route('/api/wizard/config/step2')
@login_required
def wizard_config_step2():
    agency_id = request.args.get('agency_id', type=int)
    function_id = request.args.get('function_id', type=int)
    components = []
    if function_id:
        func = Function.query.get(function_id)
        if func:
            components = sorted(func.components, key=lambda c: c.name.lower())
    if not components:
        components = Component.query.order_by(Component.name.asc()).all()
    return render_template('fragments/wizard_config_step2.html', components=components, agency_id=agency_id, function_id=function_id)

@config_bp.route('/api/wizard/config/step3')
@login_required
def wizard_config_step3():
    agency_id = request.args.get('agency_id', type=int)
    function_id = request.args.get('function_id', type=int)
    component_id = request.args.get('component_id', type=int)
    products = Product.query.order_by(Product.name.asc()).all()
    return render_template('fragments/wizard_config_step3.html', products=products, agency_id=agency_id, function_id=function_id, component_id=component_id)

@config_bp.route('/api/wizard/config/step4')
@login_required
def wizard_config_step4():
    agency_id = request.args.get('agency_id', type=int)
    function_id = request.args.get('function_id', type=int)
    component_id = request.args.get('component_id', type=int)
    # selected products list (supports repeated params or comma-separated ids)
    ids = _parse_product_ids(request.args)
    selected_products = Product.query.filter(Product.id.in_(ids)).all() if ids else []
    fake_config = Configuration(agency_id=agency_id, function_id=function_id, component_id=component_id, status='Draft')
    warnings = advisory_validate(fake_config, selected_products)
    return render_template('fragments/wizard_config_step4.html', agency_id=agency_id, function_id=function_id, component_id=component_id, products=selected_products, product_ids=ids, warnings=warnings)

@config_bp.route('/api/wizard/config/confirm', methods=['POST'])
@login_required
def wizard_config_confirm():
    try:
        # Create configuration
        form = ConfigurationForm()
        if not form.validate_on_submit():
            return jsonify({'error': 'validation', 'messages': form.errors}), 400
        c = Configuration()
        form.populate_configuration(c)
        db.session.add(c)
        db.session.flush()
        db.session.add(ConfigurationHistory(configuration_id=c.id, action='created', changed_by=get_updated_by(), new_values={}))
        # Attach products if provided
        ids = _parse_product_ids(request.form)
        for pid in ids:
            cp = ConfigurationProduct(configuration_id=c.id, product_id=pid, status='Active')
            db.session.add(cp)
            db.session.flush()
            db.session.add(ConfigurationHistory(configuration_id=c.id, action='product_added', changed_by=get_updated_by(), new_values={'configuration_product_id': cp.id}))
        db.session.commit()
        return render_template('fragments/configuration_row.html', c=c), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'server', 'message': str(e)}), 500

@config_bp.route('/api/products/<int:product_id>/form')
@login_required
def product_edit_form(product_id):
    p = Product.query.get_or_404(product_id)
    form = ProductForm()
    vendors = Vendor.query.order_by(Vendor.name.asc()).all()
    try:
        form.vendor_id.choices = [(v.id, v.name) for v in vendors]
    except Exception:
        pass
    form.populate_from_product(p)
    return render_template('fragments/product_form.html', form=form, product=p, vendors=vendors)

@config_bp.route('/api/products/<int:product_id>', methods=['PUT'])
@login_required
def product_update(product_id):
    p = Product.query.get_or_404(product_id)
    form = ProductForm()
    vendors = Vendor.query.order_by(Vendor.name.asc()).all()
    try:
        form.vendor_id.choices = [(v.id, v.name) for v in vendors]
    except Exception:
        pass
    if form.validate_on_submit():
        form.populate_product(p)
        db.session.commit()
        products = Product.query.order_by(Product.name.asc()).limit(250).all()
        return render_template('fragments/product_list.html', products=products)
    return jsonify({'error': 'validation', 'messages': form.errors}), 400

@config_bp.route('/api/products/<int:product_id>', methods=['DELETE'])
@login_required
def product_delete(product_id):
    p = Product.query.get_or_404(product_id)
    # Guard: block deletion if used in any configuration
    usage = ConfigurationProduct.query.filter_by(product_id=product_id).first()
    if usage:
        return jsonify({'error': 'in_use', 'message': 'Cannot delete product; it is used in one or more configurations.'}), 400
    db.session.delete(p)
    db.session.commit()
    products = Product.query.order_by(Product.name.asc()).limit(250).all()
    return render_template('fragments/product_list.html', products=products)

@config_bp.route('/api/configurations/<int:config_id>/form')
@login_required
def configuration_edit_form(config_id):
    c = Configuration.query.get_or_404(config_id)
    form = ConfigurationForm()
    form.populate_from_configuration(c)
    agencies = Agency.query.order_by(Agency.name.asc()).all()
    functions = Function.query.order_by(Function.name.asc()).all()
    components = Component.query.order_by(Component.name.asc()).all()
    return render_template('fragments/configuration_edit_form.html', form=form, c=c, agencies=agencies, functions=functions, components=components)

# --------- Options (for HTMX dependent selects) ---------

@config_bp.route('/api/options/functional-areas')
@login_required
def option_functional_areas():
    areas = FunctionalArea.query.order_by(FunctionalArea.name.asc()).all()
    html = '<option value="">All Functional Areas</option>'
    for a in areas:
        html += f'<option value="{a.id}">{a.name}</option>'
    return html

@config_bp.route('/api/options/functions')
@login_required
def option_functions():
    # Support multiple param names from different UIs
    fa_id = request.args.get('qc-fa') or request.args.get('functional_area_id') or request.args.get('functional_area') or request.args.get('fa_id')
    try:
        fa_id = int(fa_id) if fa_id else None
    except (TypeError, ValueError):
        fa_id = None
    q = (request.args.get('q') or '').strip()

    qry = Function.query
    if fa_id:
        qry = qry.filter(Function.functional_area_id == fa_id)
    if q:
        qry = qry.filter(Function.name.ilike(f"%{q}%"))
    functions = qry.order_by(Function.name.asc()).limit(200).all()

    html = '<option value="">Select a function</option>'
    for f in functions:
        html += f'<option value="{f.id}">{f.name}</option>'
    return html

@config_bp.route('/api/options/components')
@login_required
def option_components():
    function_id = request.args.get('function_id', type=int)
    components = []
    if function_id:
        fn = Function.query.get(function_id)
        if fn:
            # fn.components is a list; sort case-insensitively
            components = sorted(fn.components, key=lambda c: (c.name or '').lower())
    if not components:
        components = Component.query.order_by(Component.name.asc()).limit(200).all()

    html = '<option value="">Select a component</option>'
    for c in components:
        html += f'<option value="{c.id}">{c.name}</option>'
    return html


# --------- CSV Import ---------

@config_bp.route('/configurations/import')
@login_required
def configurations_import_page():
    """Show CSV import form."""
    agencies = Agency.query.order_by(Agency.name.asc()).all()
    return render_template('configurations_import.html', agencies=agencies)


@config_bp.route('/api/configurations/import', methods=['POST'])
@login_required
def configurations_import():
    """Process CSV import of product configurations."""
    agency_id = request.form.get('agency_id', type=int)
    file = request.files.get('csv_file')

    if not file or not file.filename.endswith('.csv'):
        return jsonify({'error': 'Please upload a valid CSV file'}), 400

    try:
        content = file.stream.read().decode('utf-8')
        reader = csv.DictReader(StringIO(content))

        results = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}

        for row_num, row in enumerate(reader, start=2):
            try:
                result = _process_import_row(row, agency_id)
                if result == 'created':
                    results['created'] += 1
                elif result == 'updated':
                    results['updated'] += 1
                elif result == 'skipped':
                    results['skipped'] += 1
            except Exception as e:
                results['errors'].append(f"Row {row_num}: {str(e)}")

        db.session.commit()
        return jsonify(results)
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Import failed: {str(e)}'}), 500


def _process_import_row(row: dict, default_agency_id: int = None) -> str:
    """Process a single CSV row. Returns 'created', 'updated', or 'skipped'."""

    # --- Resolve Agency ---
    agency_name = (row.get('agency_name') or '').strip()
    if agency_name:
        agency = Agency.query.filter(Agency.name.ilike(agency_name)).first()
        if not agency:
            raise ValueError(f"Agency '{agency_name}' not found")
    elif default_agency_id:
        agency = Agency.query.get(default_agency_id)
        if not agency:
            raise ValueError(f"Default agency ID {default_agency_id} not found")
    else:
        raise ValueError("No agency specified")

    # --- Resolve FunctionalArea and Function ---
    fa_name = (row.get('functional_area') or '').strip()
    func_name = (row.get('function') or '').strip()
    if not fa_name or not func_name:
        raise ValueError("functional_area and function are required")

    fa = FunctionalArea.query.filter(FunctionalArea.name.ilike(fa_name)).first()
    if not fa:
        raise ValueError(f"Functional area '{fa_name}' not found")

    function = Function.query.filter(
        Function.name.ilike(func_name),
        Function.functional_area_id == fa.id
    ).first()
    if not function:
        raise ValueError(f"Function '{func_name}' not found in '{fa_name}'")

    # --- Resolve or create Component ---
    comp_name = (row.get('component') or '').strip()
    if not comp_name:
        raise ValueError("component is required")

    component = Component.query.filter(Component.name.ilike(comp_name)).first()
    if not component:
        component = Component(name=comp_name)
        db.session.add(component)
        db.session.flush()

    # --- Find or create Configuration ---
    config = Configuration.query.filter_by(
        agency_id=agency.id,
        function_id=function.id,
        component_id=component.id
    ).first()

    action = 'updated' if config else 'created'

    if not config:
        config = Configuration(
            agency_id=agency.id,
            function_id=function.id,
            component_id=component.id
        )
        db.session.add(config)
        db.session.flush()
        db.session.add(ConfigurationHistory(
            configuration_id=config.id,
            action='created',
            changed_by=get_updated_by(),
            new_values={'source': 'csv_import'}
        ))

    # --- Update configuration fields ---
    status_val = (row.get('status') or '').strip()
    if status_val:
        config.status = status_val

    deployment_str = (row.get('deployment_date') or '').strip()
    if deployment_str:
        try:
            config.deployment_date = datetime.strptime(deployment_str, '%Y-%m-%d').date()
        except ValueError:
            pass  # ignore invalid dates

    notes_val = (row.get('notes') or '').strip()
    if notes_val:
        config.implementation_notes = notes_val

    version_label_val = (row.get('version_label') or '').strip()
    if version_label_val:
        config.version_label = version_label_val

    # --- Handle Product attachment ---
    product_name = (row.get('product') or '').strip()
    vendor_name = (row.get('vendor') or '').strip()

    if product_name:
        # Resolve or create Vendor
        vendor = None
        if vendor_name:
            vendor = Vendor.query.filter(Vendor.name.ilike(vendor_name)).first()
            if not vendor:
                vendor = Vendor(name=vendor_name)
                db.session.add(vendor)
                db.session.flush()

        # Resolve or create Product (match by name + vendor if vendor specified)
        product_q = Product.query.filter(Product.name.ilike(product_name))
        if vendor:
            # Exact match: same name AND same vendor
            product_q = product_q.filter(Product.vendor_id == vendor.id)
        else:
            # No vendor specified: prefer products without a vendor, else take any match
            product_q = product_q.order_by(Product.vendor_id.asc().nullsfirst())
        product = product_q.first()

        if not product:
            product = Product(name=product_name, vendor_id=vendor.id if vendor else None)
            db.session.add(product)
            db.session.flush()

        # Resolve ProductVersion if specified
        version_str = (row.get('product_version') or '').strip()
        product_version = None
        if version_str:
            product_version = ProductVersion.query.filter_by(
                product_id=product.id,
                version=version_str
            ).first()
            if not product_version:
                product_version = ProductVersion(product_id=product.id, version=version_str)
                db.session.add(product_version)
                db.session.flush()

        # Link product to configuration (upsert)
        cp = ConfigurationProduct.query.filter_by(
            configuration_id=config.id,
            product_id=product.id
        ).first()

        if not cp:
            cp = ConfigurationProduct(
                configuration_id=config.id,
                product_id=product.id,
                status='Active'
            )
            db.session.add(cp)
            db.session.add(ConfigurationHistory(
                configuration_id=config.id,
                action='product_added',
                changed_by=get_updated_by(),
                new_values={'product_id': product.id, 'source': 'csv_import'}
            ))

        cp.product_version_id = product_version.id if product_version else None

    return action


@config_bp.route('/api/configurations/export-template')
@login_required
def configurations_export_template():
    """Download a sample CSV template for import."""
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'agency_name', 'functional_area', 'function', 'component',
        'product', 'vendor', 'product_version', 'status', 'deployment_date', 'version_label', 'notes'
    ])
    # Example row
    writer.writerow([
        'Metro Transit', 'Operations', 'Real-time Tracking', 'AVL System',
        'TransitMaster', 'Trapeze', '5.2.1', 'Active', '2023-06-15', 'v5.2.1-prod', 'Primary AVL system'
    ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=configurations_import_template.csv'}
    )

