# run.py
from app import create_app, db
from app.models import (
    Agency, FunctionalArea, Vendor, Component, Function,
    IntegrationPoint, UserRole, UpdateLog, Standard, TagGroup, Tag,
    Product, ProductVersion, Configuration, ConfigurationProduct,
    ServiceType, Suggestion,
)
import os
import click

app = create_app()


@app.get('/health')
def health():
    return {'ok': True}, 200


@app.shell_context_processor
def make_shell_context():
    return {
        'app': app, 'db': db,
        'Agency': Agency, 'FunctionalArea': FunctionalArea, 'Function': Function,
        'Vendor': Vendor, 'Component': Component, 'IntegrationPoint': IntegrationPoint,
        'UserRole': UserRole, 'UpdateLog': UpdateLog, 'Standard': Standard,
        'TagGroup': TagGroup, 'Tag': Tag,
        'Product': Product, 'ProductVersion': ProductVersion,
        'Configuration': Configuration, 'ConfigurationProduct': ConfigurationProduct,
        'ServiceType': ServiceType, 'Suggestion': Suggestion,
    }


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

SEED_ORDER = [
    'functional-areas',
    'functions',
    'agencies',
    'vendors',
    'components',
    'integrations',
    'standards',
    'configurations',
]

SEED_SCRIPTS = {
    'agencies':        'scripts/load_agencies.py',
    'vendors':         'scripts/load_vendors.py',
    'components':      'scripts/load_components.py',
    'functional-areas': 'scripts/load_functional_areas.py',
    'functions':       'scripts/load_functions.py',
    'configurations':  'scripts/load_implementations.py',
    'integrations':    'scripts/load_integrations.py',
    'standards':       'scripts/load_standards.py',
}


def _run_seed_script(entity: str) -> bool:
    """Run the loader script for an entity. Returns True on success."""
    script = SEED_SCRIPTS.get(entity)
    if not script:
        click.echo(f"No seed script for '{entity}'. Valid: {', '.join(SEED_SCRIPTS)}")
        return False
    import runpy
    try:
        runpy.run_path(script, run_name='__main__')
        return True
    except SystemExit as e:
        return e.code == 0
    except Exception as e:
        click.echo(f"Error seeding {entity}: {e}")
        return False


@app.cli.group()
def seed():
    """Seed the database from JSON files in /data."""


@seed.command('all')
def seed_all():
    """Load all seed data in dependency order."""
    with app.app_context():
        for entity in SEED_ORDER:
            click.echo(f"Seeding {entity}...")
            ok = _run_seed_script(entity)
            if not ok:
                click.echo(f"Failed on {entity}. Stopping.")
                raise SystemExit(1)
        click.echo("Done.")


@seed.command('agencies')
def seed_agencies():
    """Seed agencies from data/agencies.json."""
    with app.app_context():
        _run_seed_script('agencies')


@seed.command('vendors')
def seed_vendors():
    """Seed vendors from data/vendors.json."""
    with app.app_context():
        _run_seed_script('vendors')


@seed.command('components')
def seed_components():
    """Seed components from data/components.json."""
    with app.app_context():
        _run_seed_script('components')


@seed.command('functional-areas')
def seed_functional_areas():
    """Seed functional areas from data/functional_areas.json."""
    with app.app_context():
        _run_seed_script('functional-areas')


@seed.command('functions')
def seed_functions():
    """Seed functions from data/functions.json."""
    with app.app_context():
        _run_seed_script('functions')


@seed.command('configurations')
def seed_configurations():
    """Seed configurations from data/implementations.json."""
    with app.app_context():
        _run_seed_script('configurations')


@seed.command('integrations')
def seed_integrations():
    """Seed integration points from data/integrations.json."""
    with app.app_context():
        _run_seed_script('integrations')


@seed.command('standards')
def seed_standards():
    """Seed standards from data/standards.json."""
    with app.app_context():
        _run_seed_script('standards')


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

VALID_AGENTS = ('agency', 'vendor', 'component')


@app.cli.group()
def agent():
    """Run AI research agents."""


@agent.command('run')
@click.argument('agent_type', type=click.Choice(VALID_AGENTS))
@click.option('--id', 'record_id', type=int, default=None, help='Database ID of a single record.')
@click.option('--name', default=None, help='Name of a single record to look up.')
@click.option('--all', 'run_all', is_flag=True, help='Run for every record of this type.')
@click.option('--dry-run', is_flag=True, help='Research and print results without saving.')
def agent_run(agent_type, record_id, name, run_all, dry_run):
    """Run a research agent for one record or all records of a type.

    Examples:\n
      flask agent run agency --id 42\n
      flask agent run vendor --name "Cubic Transportation Systems"\n
      flask agent run agency --all --dry-run
    """
    with app.app_context():
        if agent_type == 'agency':
            from app.agents.agency_agent import run as run_agent
            model_cls = Agency
        elif agent_type == 'vendor':
            from app.agents.vendor_agent import run as run_agent
            model_cls = Vendor
        else:
            from app.agents.component_agent import run as run_agent
            model_cls = Component

        if run_all:
            records = model_cls.query.all()
        elif record_id:
            records = [model_cls.query.get_or_404(record_id)]
        elif name:
            record = model_cls.query.filter_by(name=name).first()
            if not record:
                click.echo(f"{agent_type.title()} '{name}' not found.")
                raise SystemExit(1)
            records = [record]
        else:
            click.echo("Provide --id, --name, or --all.")
            raise SystemExit(1)

        ok = err = 0
        for record in records:
            click.echo(f"Running {agent_type} agent for: {record.name}")
            result = run_agent(record.id, dry_run=dry_run)
            if result.success:
                ok += 1
                if dry_run:
                    import json
                    click.echo(json.dumps(result.draft, indent=2))
                else:
                    click.echo(f"  Updated: {list(result.diff.keys()) if result.diff else 'no changes'}")
            else:
                err += 1
                click.echo(f"  Error: {result.error}")

        click.echo(f"\nDone. {ok} succeeded, {err} failed.")


@agent.command('status')
def agent_status():
    """Show last run stats from the agent audit log."""
    import json
    from datetime import datetime

    log_path = os.path.join(app.root_path, '..', 'logs', 'agent_audit.jsonl')
    if not os.path.exists(log_path):
        click.echo("No audit log found. Agents have not been run yet.")
        return

    last_by_type = {}
    counts = {}
    with open(log_path) as f:
        for line in f:
            try:
                entry = json.loads(line)
                t = entry.get('agent_type', 'unknown')
                counts[t] = counts.get(t, 0) + 1
                last_by_type[t] = entry
            except json.JSONDecodeError:
                continue

    for agent_type, entry in sorted(last_by_type.items()):
        ts = entry.get('timestamp', 'unknown')
        summary = entry.get('result_summary', {})
        click.echo(
            f"{agent_type:12s}  runs={counts[agent_type]:4d}  "
            f"last={ts[:19]}  "
            f"success={summary.get('success')}  "
            f"fields_set={len(summary.get('fields_set', []))}"
        )


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.cli.group()
def admin():
    """Admin utilities."""


@admin.command('create-user')
@click.option('--email', required=True, help='User email address.')
@click.option('--name', default=None, help='Display name.')
@click.option('--is-admin', is_flag=True, help='Grant admin privileges.')
def admin_create_user(email, name, is_admin):
    """Bootstrap an admin user (bypasses OAuth for initial setup)."""
    with app.app_context():
        from app.models.tran import User
        existing = User.query.filter_by(email=email).first()
        if existing:
            existing.is_admin = is_admin
            if name:
                existing.name = name
            db.session.commit()
            click.echo(f"Updated existing user: {email} (admin={is_admin})")
        else:
            user = User(
                provider='local',
                sub=email,
                email=email,
                name=name or email.split('@')[0],
                is_admin=is_admin,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            click.echo(f"Created user: {email} (admin={is_admin}, id={user.id})")


if __name__ == '__main__':
    app.run(debug=True)
