# app/utils/errors.py
from flask import jsonify, render_template_string


# ---------------------------------------------------------------------------
# JSON API responses — use these for all /api/ endpoints
# ---------------------------------------------------------------------------

def api_ok(data=None, status=200):
    """Standard success envelope: {"ok": true, "data": {...}}"""
    return jsonify({"ok": True, "data": data}), status


def api_error(message: str, status=400, details=None):
    """Standard error envelope: {"ok": false, "error": "...", "code": N}"""
    body = {"ok": False, "error": message, "code": status}
    if details:
        body["details"] = details
    return jsonify(body), status


def api_validation_error(errors: dict):
    """Validation error with per-field details (422)."""
    return jsonify({"ok": False, "error": "Validation failed", "code": 422, "fields": errors}), 422


def api_form_errors(form):
    """Convert a WTForms form's errors into a 422 validation response."""
    errors = {
        field: errs[0] if errs else "Invalid"
        for field, errs in form.errors.items()
    }
    return api_validation_error(errors)


# ---------------------------------------------------------------------------
# Legacy helpers — kept for existing HTMX fragment routes
# ---------------------------------------------------------------------------

def json_error_response(message, status_code=400, details=None):
    return api_error(message, status_code, details)


def json_success_response(message="Success", data=None):
    return api_ok(data)


def json_validation_error_response(message="Validation failed", errors=None):
    return api_validation_error(errors or {})


def json_form_error_response(form):
    return api_form_errors(form)


def html_error_fragment(message, title="Error"):
    template = '''
    <div class="bg-red-900/20 border border-red-700/30 rounded-lg p-4 mb-4">
        <div class="flex items-center space-x-3">
            <svg class="w-5 h-5 text-red-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
            </svg>
            <div>
                <h4 class="text-red-300 font-medium">{{ title }}</h4>
                <p class="text-red-200 text-sm">{{ message }}</p>
            </div>
        </div>
    </div>
    '''
    return render_template_string(template, title=title, message=message)


def html_success_fragment(message, title="Success"):
    template = '''
    <div class="bg-green-900/20 border border-green-700/30 rounded-lg p-4 mb-4">
        <div class="flex items-center space-x-3">
            <svg class="w-5 h-5 text-green-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
            </svg>
            <div>
                <h4 class="text-green-300 font-medium">{{ title }}</h4>
                <p class="text-green-200 text-sm">{{ message }}</p>
            </div>
        </div>
    </div>
    '''
    return render_template_string(template, title=title, message=message)
