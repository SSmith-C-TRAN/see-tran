"""
See-Tran MCP Server

Exposes core database read/write operations as MCP tools so Claude Code
and other agents can inspect and update the database directly.

Usage:
    python -m app.mcp_server

Or via mcp.json auto-discovery (see repo root mcp.json).
"""

import json
import sys
import os

# Allow running as a standalone script from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.tran import (
    Agency, Vendor, Component, Product, ProductVersion,
    Function, FunctionalArea, Configuration, ConfigurationProduct,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "mcp package not installed. Run: pip install mcp",
        file=sys.stderr,
    )
    sys.exit(1)

flask_app = create_app()
mcp = FastMCP("see-tran")


# ---------------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------------

@mcp.tool()
def get_schema_summary() -> dict:
    """Return field names and types for all core entities.

    Use this to understand the data model before writing or updating records.
    """
    def _cols(model):
        return {
            c.name: str(c.type)
            for c in model.__table__.columns
        }

    return {
        "Agency": _cols(Agency),
        "Vendor": _cols(Vendor),
        "Component": _cols(Component),
        "Product": _cols(Product),
        "ProductVersion": _cols(ProductVersion),
        "Function": _cols(Function),
        "FunctionalArea": _cols(FunctionalArea),
        "Configuration": _cols(Configuration),
        "ConfigurationProduct": _cols(ConfigurationProduct),
    }


# ---------------------------------------------------------------------------
# Agency
# ---------------------------------------------------------------------------

@mcp.tool()
def list_agencies(search: str = "", limit: int = 50) -> list[dict]:
    """List agencies, optionally filtered by name search.

    Args:
        search: Case-insensitive substring to filter agency names.
        limit: Max records to return (default 50).
    """
    with flask_app.app_context():
        q = Agency.query
        if search:
            q = q.filter(Agency.name.ilike(f"%{search}%"))
        rows = q.order_by(Agency.name).limit(limit).all()
        return [
            {
                "id": a.id, "name": a.name, "short_name": a.short_name,
                "location": a.location, "website": a.website,
                "email_domain": a.email_domain,
            }
            for a in rows
        ]


@mcp.tool()
def get_agency(id: int) -> dict:
    """Get full details for a single agency by ID."""
    with flask_app.app_context():
        a = Agency.query.get(id)
        if not a:
            return {"error": f"Agency {id} not found"}
        return {
            "id": a.id, "name": a.name, "short_name": a.short_name,
            "location": a.location, "description": a.description,
            "website": a.website, "email_domain": a.email_domain,
            "ceo": a.ceo, "address_hq": a.address_hq,
            "phone_number": a.phone_number, "contact_email": a.contact_email,
            "contact_phone": a.contact_phone, "contact_name": a.contact_name,
            "transit_map_link": a.transit_map_link,
            "additional_metadata": a.additional_metadata,
            "configuration_count": len(a.configurations),
        }


@mcp.tool()
def upsert_agency(name: str, fields: dict) -> dict:
    """Create or update an agency by name.

    Args:
        name: Official agency name (used for lookup; unique).
        fields: Dict of fields to set. Valid keys: short_name, location,
                description, website, email_domain, ceo, address_hq,
                phone_number, contact_email, contact_phone, contact_name,
                transit_map_link, additional_metadata.

    Returns:
        {"id": ..., "created": bool, "updated_fields": [...]}
    """
    allowed = {
        "short_name", "location", "description", "website", "email_domain",
        "ceo", "address_hq", "phone_number", "contact_email", "contact_phone",
        "contact_name", "transit_map_link", "additional_metadata",
    }
    with flask_app.app_context():
        a = Agency.query.filter_by(name=name).first()
        created = a is None
        if created:
            a = Agency(name=name)
            db.session.add(a)

        updated = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if getattr(a, k) != v:
                setattr(a, k, v)
                updated.append(k)

        db.session.commit()
        return {"id": a.id, "created": created, "updated_fields": updated}


# ---------------------------------------------------------------------------
# Vendor
# ---------------------------------------------------------------------------

@mcp.tool()
def list_vendors(search: str = "", limit: int = 50) -> list[dict]:
    """List vendors, optionally filtered by name search."""
    with flask_app.app_context():
        q = Vendor.query
        if search:
            q = q.filter(Vendor.name.ilike(f"%{search}%"))
        rows = q.order_by(Vendor.name).limit(limit).all()
        return [
            {
                "id": v.id, "name": v.name, "short_name": v.short_name,
                "website": v.website, "product_count": len(v.products),
            }
            for v in rows
        ]


@mcp.tool()
def get_vendor(id: int) -> dict:
    """Get full details for a single vendor by ID."""
    with flask_app.app_context():
        v = Vendor.query.get(id)
        if not v:
            return {"error": f"Vendor {id} not found"}
        return {
            "id": v.id, "name": v.name, "short_name": v.short_name,
            "website": v.website, "vendor_email": v.vendor_email,
            "vendor_phone": v.vendor_phone, "description": v.description,
            "products": [
                {"id": p.id, "name": p.name, "lifecycle_stage": p.lifecycle_stage.value if p.lifecycle_stage else None}
                for p in v.products
            ],
        }


@mcp.tool()
def upsert_vendor(name: str, fields: dict) -> dict:
    """Create or update a vendor by name.

    Args:
        name: Vendor name (unique).
        fields: Dict of fields to set. Valid keys: short_name, website,
                vendor_email, vendor_phone, description.
    """
    allowed = {"short_name", "website", "vendor_email", "vendor_phone", "description"}
    with flask_app.app_context():
        v = Vendor.query.filter_by(name=name).first()
        created = v is None
        if created:
            v = Vendor(name=name)
            db.session.add(v)

        updated = []
        for k, val in fields.items():
            if k not in allowed:
                continue
            if getattr(v, k) != val:
                setattr(v, k, val)
                updated.append(k)

        db.session.commit()
        return {"id": v.id, "created": created, "updated_fields": updated}


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------

@mcp.tool()
def list_components(search: str = "", limit: int = 50) -> list[dict]:
    """List components, optionally filtered by name search."""
    with flask_app.app_context():
        q = Component.query
        if search:
            q = q.filter(Component.name.ilike(f"%{search}%"))
        rows = q.order_by(Component.name).limit(limit).all()
        return [
            {
                "id": c.id, "name": c.name,
                "short_description": c.short_description,
                "function_count": len(c.functions),
                "configuration_count": len(c.configurations),
            }
            for c in rows
        ]


@mcp.tool()
def get_component(id: int) -> dict:
    """Get full details for a single component by ID."""
    with flask_app.app_context():
        c = Component.query.get(id)
        if not c:
            return {"error": f"Component {id} not found"}
        return {
            "id": c.id, "name": c.name, "description": c.description,
            "short_description": c.short_description,
            "additional_metadata": c.additional_metadata,
            "functions": [{"id": f.id, "name": f.name} for f in c.functions],
            "tags": [{"id": t.id, "name": t.name} for t in c.tags],
        }


@mcp.tool()
def upsert_component(name: str, fields: dict) -> dict:
    """Create or update a component by name.

    Args:
        name: Component name.
        fields: Dict of fields to set. Valid keys: description,
                short_description, additional_metadata.
    """
    allowed = {"description", "short_description", "additional_metadata"}
    with flask_app.app_context():
        c = Component.query.filter_by(name=name).first()
        created = c is None
        if created:
            c = Component(name=name)
            db.session.add(c)

        updated = []
        for k, val in fields.items():
            if k not in allowed:
                continue
            if getattr(c, k) != val:
                setattr(c, k, val)
                updated.append(k)

        db.session.commit()
        return {"id": c.id, "created": created, "updated_fields": updated}


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

@mcp.tool()
def list_products(vendor_id: int | None = None, search: str = "", limit: int = 50) -> list[dict]:
    """List products, optionally filtered by vendor or name search."""
    with flask_app.app_context():
        q = Product.query
        if vendor_id:
            q = q.filter_by(vendor_id=vendor_id)
        if search:
            q = q.filter(Product.name.ilike(f"%{search}%"))
        rows = q.order_by(Product.name).limit(limit).all()
        return [
            {
                "id": p.id, "name": p.name, "vendor_id": p.vendor_id,
                "lifecycle_stage": p.lifecycle_stage.value if p.lifecycle_stage else None,
                "version_count": len(p.versions),
            }
            for p in rows
        ]


@mcp.tool()
def get_product(id: int) -> dict:
    """Get full details for a single product by ID."""
    with flask_app.app_context():
        p = Product.query.get(id)
        if not p:
            return {"error": f"Product {id} not found"}
        return {
            "id": p.id, "name": p.name, "vendor_id": p.vendor_id,
            "description": p.description,
            "lifecycle_stage": p.lifecycle_stage.value if p.lifecycle_stage else None,
            "additional_metadata": p.additional_metadata,
            "versions": [
                {
                    "id": v.id, "version": v.version,
                    "release_date": str(v.release_date) if v.release_date else None,
                    "support_end_date": str(v.support_end_date) if v.support_end_date else None,
                }
                for v in p.versions
            ],
        }


@mcp.tool()
def upsert_product(name: str, vendor_id: int, fields: dict) -> dict:
    """Create or update a product by name.

    Args:
        name: Product name (unique globally).
        vendor_id: ID of the owning vendor.
        fields: Dict of fields to set. Valid keys: description,
                lifecycle_stage (planned/pilot/production/deprecated/retired),
                additional_metadata.
    """
    from app.models.tran import LifecycleStage
    allowed = {"description", "lifecycle_stage", "additional_metadata"}
    with flask_app.app_context():
        p = Product.query.filter_by(name=name).first()
        created = p is None
        if created:
            p = Product(name=name, vendor_id=vendor_id)
            db.session.add(p)

        updated = []
        for k, val in fields.items():
            if k not in allowed:
                continue
            if k == "lifecycle_stage" and val:
                val = LifecycleStage(val)
            if getattr(p, k) != val:
                setattr(p, k, val)
                updated.append(k)

        db.session.commit()
        return {"id": p.id, "created": created, "updated_fields": updated}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@mcp.tool()
def list_configurations(
    agency_id: int | None = None,
    component_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """List configurations, optionally filtered by agency or component."""
    with flask_app.app_context():
        q = Configuration.query
        if agency_id:
            q = q.filter_by(agency_id=agency_id)
        if component_id:
            q = q.filter_by(component_id=component_id)
        rows = q.limit(limit).all()
        return [
            {
                "id": c.id,
                "agency_id": c.agency_id, "agency_name": c.agency.name,
                "function_id": c.function_id, "function_name": c.function.name,
                "component_id": c.component_id, "component_name": c.component.name,
                "status": c.status,
                "deployment_date": str(c.deployment_date) if c.deployment_date else None,
            }
            for c in rows
        ]


@mcp.tool()
def get_configuration(id: int) -> dict:
    """Get full details for a single configuration by ID."""
    with flask_app.app_context():
        c = Configuration.query.get(id)
        if not c:
            return {"error": f"Configuration {id} not found"}
        return {
            "id": c.id,
            "agency": {"id": c.agency_id, "name": c.agency.name},
            "function": {"id": c.function_id, "name": c.function.name},
            "component": {"id": c.component_id, "name": c.component.name},
            "status": c.status,
            "deployment_date": str(c.deployment_date) if c.deployment_date else None,
            "version_label": c.version_label,
            "implementation_notes": c.implementation_notes,
            "additional_metadata": c.additional_metadata,
            "products": [
                {
                    "product_id": cp.product_id,
                    "product_name": cp.product.name,
                    "version": cp.product_version.version if cp.product_version else None,
                    "status": cp.status,
                }
                for cp in c.products
            ],
        }


@mcp.tool()
def upsert_configuration(
    agency_id: int,
    function_id: int,
    component_id: int,
    fields: dict,
) -> dict:
    """Create or update a configuration (unique on agency+function+component).

    Args:
        agency_id: Agency database ID.
        function_id: Function database ID.
        component_id: Component database ID.
        fields: Dict of fields to set. Valid keys: status, deployment_date
                (YYYY-MM-DD string), version_label, implementation_notes,
                additional_metadata.
    """
    from datetime import date
    allowed = {
        "status", "deployment_date", "version_label",
        "implementation_notes", "additional_metadata",
    }
    with flask_app.app_context():
        c = Configuration.query.filter_by(
            agency_id=agency_id,
            function_id=function_id,
            component_id=component_id,
        ).first()
        created = c is None
        if created:
            c = Configuration(
                agency_id=agency_id,
                function_id=function_id,
                component_id=component_id,
            )
            db.session.add(c)

        updated = []
        for k, val in fields.items():
            if k not in allowed:
                continue
            if k == "deployment_date" and isinstance(val, str):
                val = date.fromisoformat(val)
            if getattr(c, k) != val:
                setattr(c, k, val)
                updated.append(k)

        db.session.commit()
        return {"id": c.id, "created": created, "updated_fields": updated}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
