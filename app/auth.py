# app/auth.py
from functools import wraps
from flask import request, jsonify, flash, Blueprint, redirect, url_for, session, render_template, current_app, abort, make_response
from authlib.integrations.flask_client import OAuth
import os
import secrets

auth_bp = Blueprint('auth', __name__)
_oauth = OAuth()

# Initialize providers lazily to allow app context config
@auth_bp.record_once
def setup_oauth(state):
    app = state.app
    _oauth.init_app(app)

    # Google OpenID Connect
    _oauth.register(
        name='google',
        server_metadata_url=app.config.get('OAUTH_GOOGLE_DISCOVERY_URL'),
        client_id=app.config.get('OAUTH_GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('OAUTH_GOOGLE_CLIENT_SECRET'),
        client_kwargs={'scope': 'openid email profile'}
    )

    # Microsoft (Azure AD common)
    _oauth.register(
        name='microsoft',
        server_metadata_url=app.config.get('OAUTH_MS_DISCOVERY_URL'),
        client_id=app.config.get('OAUTH_MS_CLIENT_ID'),
        client_secret=app.config.get('OAUTH_MS_CLIENT_SECRET'),
        client_kwargs={'scope': 'openid email profile'}
    )


def _get_next_url():
    nxt = request.args.get('next') or request.cookies.get('next_url')
    # Basic allowlist: only internal relative paths
    if nxt and nxt.startswith('/') and not nxt.startswith('//'):
        return nxt
    return url_for('main.index')


@auth_bp.route('/login')
def login_page():
    """Login page."""
    from flask import render_template
    return render_template('login.html')


@auth_bp.route('/login/google')
def login_google():
    state_token = secrets.token_urlsafe(16)
    session['oauth_state'] = state_token
    nonce = secrets.token_urlsafe(16)
    session['oauth_nonce'] = nonce
    redirect_uri = url_for('auth.auth_google_callback', _external=True)
    return _oauth.google.authorize_redirect(redirect_uri, state=state_token, nonce=nonce)


@auth_bp.route('/auth/google/callback')
def auth_google_callback():
    # Verify state
    expected = session.pop('oauth_state', None)
    received_state = request.args.get('state')
    if not expected or expected != received_state:
        flash('Invalid state parameter', 'error')
        return redirect(url_for('auth.login_page'))
    token = _oauth.google.authorize_access_token()
    nonce = session.pop('oauth_nonce', None)
    if not nonce:
        flash('Invalid login session', 'error')
        return redirect(url_for('auth.login_page'))
    userinfo = _oauth.google.parse_id_token(token, nonce=nonce)
    if not userinfo:
        flash('Google login failed', 'error')
        return redirect(url_for('auth.login_page'))

    email = userinfo.get('email')
    sub = userinfo.get('sub')
    name = userinfo.get('name') or email

    if not _email_allowed(email):
        # Store for registration flow later
        session['pending_email'] = email
        return redirect(url_for('auth.registration_required'))

    _establish_session(email=email, name=name, provider='google', sub=sub)
    return redirect(_get_next_url())


@auth_bp.route('/login/microsoft')
def login_microsoft():
    state_token = secrets.token_urlsafe(16)
    session['oauth_state'] = state_token
    # Add a nonce for MS as well
    nonce = secrets.token_urlsafe(16)
    session['oauth_nonce'] = nonce
    redirect_uri = url_for('auth.auth_ms_callback', _external=True)
    # Include the nonce and any optional prompt
    return _oauth.microsoft.authorize_redirect(
        redirect_uri,
        state=state_token,
        nonce=nonce,
        # optional but useful:
        prompt='select_account'  # helps users who have multiple work accounts
    )

@auth_bp.route('/auth/microsoft/callback')
def auth_ms_callback():
    expected_state = session.pop('oauth_state', None)
    received_state = request.args.get('state')
    if not expected_state or expected_state != received_state:
        flash('Invalid state parameter', 'error')
        return redirect(url_for('auth.login_page'))

    token = _oauth.microsoft.authorize_access_token()

    nonce = session.pop('oauth_nonce', None)
    if not nonce:
        flash('Invalid login session', 'error')
        return redirect(url_for('auth.login_page'))

    # Validate the ID token and nonce
    userinfo = _oauth.microsoft.parse_id_token(token, nonce=nonce)
    if not userinfo:
        flash('Microsoft login failed', 'error')
        return redirect(url_for('auth.login_page'))

    email = (userinfo.get('email')
             or userinfo.get('preferred_username')
             or userinfo.get('upn'))  # some tenants use upn
    sub = userinfo.get('sub')
    name = userinfo.get('name') or email

    if not _email_allowed(email):
        session['pending_email'] = email
        return redirect(url_for('auth.registration_required'))

    _establish_session(email=email, name=name, provider='microsoft', sub=sub)
    return redirect(_get_next_url())


@auth_bp.route('/registration-required')
def registration_required():
    email = session.get('pending_email')
    return render_template('registration_required.html', email=email)


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('main.index'))


# Helpers

def _email_domain(email: str) -> str | None:
    if not email or '@' not in email:
        return None
    return email.split('@', 1)[-1].strip().lower() or None


def _find_agency_id_for_domain(domain: str) -> int | None:
    """Return an agency_id for a verified domain, or None if no match.

    Checks VerifiedAgencyDomain first, then falls back to Agency.email_domain.
    """
    if not domain:
        return None

    try:
        from app.models.tran import Agency, VerifiedAgencyDomain

        mapping = VerifiedAgencyDomain.query.filter_by(domain=domain).first()
        if mapping:
            return mapping.agency_id

        agency = Agency.query.filter(Agency.email_domain.isnot(None)).filter_by(email_domain=domain).first()
        if agency:
            return agency.id

    except Exception:
        # If DB isn't ready yet (migrations/dev), fail closed by returning None.
        return None

    return None


def _upsert_user(*, email: str, name: str, provider: str, sub: str):
    """Create/update a DB User on login and (optionally) auto-associate an agency."""
    from datetime import datetime
    from app import db

    try:
        from app.models.tran import User
    except Exception:
        return None

    if not email:
        return None

    normalized_email = email.strip().lower()

    user = None
    if provider and sub:
        user = User.query.filter_by(provider=provider, sub=sub).first()
    if not user:
        user = User.query.filter_by(email=normalized_email).first()
    if not user:
        user = User(provider=provider, sub=sub)

    user.email = normalized_email
    user.name = name
    user.provider = provider
    user.sub = sub
    user.last_login_at = datetime.utcnow()

    domain = _email_domain(normalized_email)
    agency_id = _find_agency_id_for_domain(domain) if domain else None
    if agency_id and user.agency_id is None:
        user.agency_id = agency_id

    db.session.add(user)
    db.session.commit()
    return user

def _email_allowed(email: str) -> bool:
    if not email or '@' not in email:
        return False
    # Super admin bypass
    super_admin = (email.lower() == (current_app.config.get('SUPER_ADMIN_EMAIL') or '').lower())
    if super_admin:
        return True

    domain = _email_domain(email)
    if not domain:
        return False

    # Prefer DB-backed allowlist: verified domains and/or agency domain.
    # This lets you manage access without redeploying.
    if _find_agency_id_for_domain(domain):
        return True

    # Fallback: for MVP allow everything from public transit-like domains and your sample agencies
    allowed_domains = {
        'c-tran.com', 'trimet.org', 'spokanetransit.com', 'kingcounty.gov',
        'godurhamtransit.org', 'townofchapelhill.org', 'islandtransit.org', 'cota.com',
        'voice4equity.com', 'actransit.org', 'sfmta.com', 'bart.gov', 'mtc.ca.gov',
        'transit.511.org', 'septa.org', 'njtransit.com', 'mbta.com',
        'soundtransit.org', 'metro.net', 'rtams.org', 'rtd-denver.com',
        'trimet.org', 'actransit.org', 'wmata.com', 'metrotransit.org',
        'cityofchicago.org', 'chicagotransit.com', 'psta.net', 'pinellascounty.org',
        'hillsboroughcounty.org', 'hctransit.com', 'goforwardtampa.org', 'tampa-xway.com',
        'louisvilleky.gov', 'rtaonline.org', 'ridetarc.org', 'indianatransit.org',
        'indymetro.com', 'cityofevansville.org', 'go-metro.com', 'transitalliance.org',
        'cityofmadison.com', 'cityofmilwaukee.com'
    }
    return domain in allowed_domains


def _establish_session(*, email: str, name: str, provider: str, sub: str):
    # Persist minimal identity in session for now
    is_super_admin = (email.lower() == (current_app.config.get('SUPER_ADMIN_EMAIL') or '').lower())
    user = _upsert_user(email=email, name=name, provider=provider, sub=sub)
    session['user'] = {
        'email': email,
        'name': name,
        'provider': provider,
        'sub': sub,
        'is_super_admin': is_super_admin,
        'user_id': getattr(user, 'id', None),
    }
    session.permanent = True


def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            # For API routes, return JSON error
            if request.path.startswith('/api/') or request.path.startswith('/admin/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            # For page routes, redirect to login
            return redirect(url_for('auth.login_page', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login_page', next=request.url))
        
        user = session.get('user', {})
        if not user.get('is_super_admin'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Admin privileges required'}), 403
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = session.get('user')
        if not user:
            login_url = url_for('auth.login_page', next=request.path)
            if request.headers.get('HX-Request') == 'true':
                resp = make_response('', 401)
                resp.headers['HX-Redirect'] = login_url
                return resp
            return redirect(login_url)
        if not user.get('is_super_admin'):
            # For HTMX, return 403 so client can handle gracefully
            if request.headers.get('HX-Request') == 'true':
                return make_response('Forbidden', 403)
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def get_updated_by() -> str:
    """Get the current user's identifier for audit logging."""
    user = session.get('user', {})
    return user.get('email', 'anonymous')