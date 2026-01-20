# models/tran.py

from datetime import datetime
from app import db
import enum
import os

# Association Tables
component_integration = db.Table(
    'component_integration',
    db.Column('component_id', db.Integer, db.ForeignKey('components.id'), primary_key=True),
    db.Column('integration_point_id', db.Integer, db.ForeignKey('integration_points.id'), primary_key=True)
)

function_component = db.Table(
    'function_component',
    db.Column('function_id', db.Integer, db.ForeignKey('functions.id'), primary_key=True),
    db.Column('component_id', db.Integer, db.ForeignKey('components.id'), primary_key=True)
)

component_tag = db.Table(
    'component_tag',
    db.Column('component_id', db.Integer, db.ForeignKey('components.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

integration_tag = db.Table(
    'integration_tag',
    db.Column('integration_point_id', db.Integer, db.ForeignKey('integration_points.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

integration_standard = db.Table(
    'integration_standard',
    db.Column('integration_point_id', db.Integer, db.ForeignKey('integration_points.id'), primary_key=True),
    db.Column('standard_id', db.Integer, db.ForeignKey('standards.id'), primary_key=True)
)

product_integration = db.Table(
    'product_integration',
    db.Column('product_id', db.Integer, db.ForeignKey('products.id'), primary_key=True),
    db.Column('integration_point_id', db.Integer, db.ForeignKey('integration_points.id'), primary_key=True)
)

# Enums
class Criticality(enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"

class LifecycleStage(enum.Enum):
    planned = "planned"          # Identified / slated for adoption
    pilot = "pilot"              # Limited trial
    production = "production"    # Broad/standard use
    deprecated = "deprecated"    # Use discouraged; in transition
    retired = "retired"          # No longer in use/supported

# Core Models
class Agency(db.Model):
    __tablename__ = 'agencies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    location = db.Column(db.String(100))
    description = db.Column(db.String(500))
    website = db.Column(db.String(255))
    email_domain = db.Column(db.String(255))
    ceo = db.Column(db.String(128))
    address_hq = db.Column(db.String(256))
    phone_number = db.Column(db.String(64))
    transit_map_link = db.Column(db.String(256))
    contact_email = db.Column(db.String(255))
    contact_phone = db.Column(db.String(50))
    contact_name = db.Column(db.String(100))
    short_name = db.Column(db.String(50)) # use short name for constructing agency specific URLs for images, etc.
    additional_metadata = db.Column(db.JSON)
    __table_args__ = (
        db.UniqueConstraint('name', name='uq_transit_system_name'),
    )

    configurations = db.relationship('Configuration', back_populates='agency', cascade='all, delete-orphan')

    users = db.relationship('User', back_populates='agency', cascade='all, delete-orphan')
    verified_domains = db.relationship('VerifiedAgencyDomain', back_populates='agency', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Agency(name={self.name}, location={self.location})>"
    
    @property
    def logo_url(self):
        """Generate agency logo URL if file exists"""
        from flask import url_for, current_app
        if self.short_name:
            filename = f"{self.short_name.lower().replace(' ', '_')}_logo.png"
            full_path = os.path.join(current_app.static_folder, 'images', 'transit_logos', filename)
            if os.path.exists(full_path):
                return url_for('static', filename=f'images/transit_logos/{filename}')
        return None
    
    @property
    def header_url(self):
        """Generate agency header URL if file exists"""
        from flask import url_for, current_app
        if self.short_name:
            filename = f"{self.short_name.lower().replace(' ', '_')}_header.png"
            full_path = os.path.join(current_app.static_folder, 'images', 'transit_headers', filename)
            if os.path.exists(full_path):
                return url_for('static', filename=f'images/transit_headers/{filename}')
        return None

class FunctionalArea(db.Model):
    __tablename__ = 'functional_areas'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))

    functions = db.relationship('Function', back_populates='functional_area', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<FunctionalArea(name={self.name})>"

class Function(db.Model):
    __tablename__ = 'functions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    criticality = db.Column(db.Enum(Criticality), default=Criticality.medium, nullable=False)

    functional_area_id = db.Column(db.Integer, db.ForeignKey('functional_areas.id'), nullable=False)
    functional_area = db.relationship('FunctionalArea', back_populates='functions')

    components = db.relationship('Component', secondary='function_component', back_populates='functions')
    configurations = db.relationship('Configuration', back_populates='function', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Function(name={self.name}, criticality={self.criticality.value})>"

class Vendor(db.Model):
    __tablename__ = 'vendors'
    __table_args__ = (
        db.UniqueConstraint('name', name='uq_vendor_name'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    short_name = db.Column(db.String(50))
    website = db.Column(db.String(255))
    vendor_email = db.Column(db.String(255)) #TODO: Create field to store vendor email domain 
    vendor_phone = db.Column(db.String(50))
    description = db.Column(db.String(500))

    products = db.relationship('Product', back_populates='vendor', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Vendor(name={self.name})>"
    
    @property
    def logo_url(self):
        """Generate vendor logo URL if file exists"""
        from flask import url_for, current_app
        if self.short_name:
            filename = f"{self.short_name.lower().replace(' ', '_')}_logo.png"
            full_path = os.path.join(current_app.static_folder, 'images', 'vendor_logos', filename)
            if os.path.exists(full_path):
                return url_for('static', filename=f'images/vendor_logos/{filename}')
        return None
    
    @property
    def header_url(self):
        """Generate vendor header URL if file exists"""
        from flask import url_for, current_app
        if self.short_name:
            filename = f"{self.short_name.lower().replace(' ', '_')}_header.png"
            full_path = os.path.join(current_app.static_folder, 'images', 'vendor_headers', filename)
            if os.path.exists(full_path):
                return url_for('static', filename=f'images/vendor_headers/{filename}')
        return None

class Component(db.Model):
    __tablename__ = 'components'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(1000))
    short_description = db.Column(db.String(200))
    additional_metadata = db.Column(db.JSON)

    functions = db.relationship('Function', secondary='function_component', back_populates='components')
    integration_points = db.relationship('IntegrationPoint', secondary='component_integration', back_populates='components')
    tags = db.relationship('Tag', secondary='component_tag', back_populates='components')
    user_roles = db.relationship('UserRole', back_populates='component', cascade='all, delete-orphan')
    update_logs = db.relationship('UpdateLog', back_populates='component', cascade='all, delete-orphan')
    configurations = db.relationship('Configuration', back_populates='component', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Component(name={self.name})>" # UPDATED __repr__

class IntegrationPoint(db.Model):
    __tablename__ = 'integration_points'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    website = db.Column(db.String(255))

    standards = db.relationship('Standard', secondary=integration_standard, back_populates='integration_points')
    components = db.relationship('Component', secondary='component_integration', back_populates='integration_points')
    tags = db.relationship('Tag', secondary=integration_tag, back_populates='integration_points')
    products = db.relationship('Product', secondary='product_integration', back_populates='integration_points')

    def __repr__(self):
        return f"<IntegrationPoint(name={self.name})>"

class Standard(db.Model):
    __tablename__ = 'standards'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500))
    version = db.Column(db.String(50))
    standard_url = db.Column(db.String(255))

    integration_points = db.relationship('IntegrationPoint', secondary=integration_standard, back_populates='standards')

    def __repr__(self):
        return f"<Standard(name={self.name}, version={self.version})>"

class TagGroup(db.Model):
    __tablename__ = 'tag_groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500))

    tags = db.relationship('Tag', back_populates='tag_group', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<TagGroup(name={self.name})>"

class Tag(db.Model):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    color = db.Column(db.String(20))

    tag_group_id = db.Column(db.Integer, db.ForeignKey('tag_groups.id'), nullable=False)
    tag_group = db.relationship('TagGroup', back_populates='tags')

    components = db.relationship('Component', secondary='component_tag', back_populates='tags')
    integration_points = db.relationship('IntegrationPoint', secondary=integration_tag, back_populates='tags')

    def __repr__(self):
        return f"<Tag(name={self.name})>"


class User(db.Model):
    """Authenticated application user (backed by OAuth identity)."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    provider = db.Column(db.String(50), nullable=False)  # e.g. 'google', 'microsoft'
    sub = db.Column(db.String(255), nullable=False)      # provider subject / stable external id

    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    name = db.Column(db.String(255))

    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'), nullable=True, index=True)
    agency = db.relationship('Agency', back_populates='users')

    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint('provider', 'sub', name='uq_user_provider_sub'),
        db.Index('ix_user_provider_sub', 'provider', 'sub'),
    )

    def __repr__(self):
        return f"<User(email={self.email}, provider={self.provider})>"


class VerifiedAgencyDomain(db.Model):
    """Maps an email domain to an Agency for auto-association and access control."""

    __tablename__ = 'verified_agency_domains'

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), nullable=False, unique=True, index=True)

    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'), nullable=False, index=True)
    agency = db.relationship('Agency', back_populates='verified_domains')

    verified_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    verified_by = db.relationship('User', foreign_keys=[verified_by_user_id])

    def __repr__(self):
        return f"<VerifiedAgencyDomain(domain={self.domain}, agency_id={self.agency_id})>"
    
class UserRole(db.Model):
    __tablename__ = 'user_roles'

    id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))

    component_id = db.Column(db.Integer, db.ForeignKey('components.id'))
    component = db.relationship('Component', back_populates='user_roles')

    def __repr__(self):
        return f"<UserRole(role_name={self.role_name})>"

class UpdateLog(db.Model):
    __tablename__ = 'update_logs'

    id = db.Column(db.Integer, primary_key=True)
    component_id = db.Column(db.Integer, db.ForeignKey('components.id'), nullable=False)
    updated_by = db.Column(db.String(100), nullable=False)
    update_date = db.Column(db.DateTime, default=datetime.utcnow)
    change_summary = db.Column(db.String(1000))

    component = db.relationship('Component', back_populates='update_logs')

    def __repr__(self):
        return f"<UpdateLog(component_id={self.component_id}, updated_by={self.updated_by})>"

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True, index=True)
    description = db.Column(db.String(1000))
    parent_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    lifecycle_stage = db.Column(db.Enum(LifecycleStage), nullable=True)
    additional_metadata = db.Column(db.JSON)

    vendor = db.relationship('Vendor', back_populates='products')
    parent_product = db.relationship('Product', remote_side=[id], backref=db.backref('child_products', cascade='all, delete-orphan'))
    versions = db.relationship('ProductVersion', back_populates='product', cascade='all, delete-orphan')
    integration_points = db.relationship('IntegrationPoint', secondary='product_integration', back_populates='products')
    configuration_products = db.relationship('ConfigurationProduct', back_populates='product', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Product(name={self.name})>"

class ProductVersion(db.Model):
    __tablename__ = 'product_versions'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    version = db.Column(db.String(100), nullable=False)
    release_date = db.Column(db.Date, nullable=True)
    support_end_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.String(1000))

    product = db.relationship('Product', back_populates='versions')
    configuration_products = db.relationship('ConfigurationProduct', back_populates='product_version')

    __table_args__ = (
        db.UniqueConstraint('product_id', 'version', name='uq_product_version'),
        db.Index('ix_product_version_product_id_version', 'product_id', 'version'),
    )

    def __repr__(self):
        return f"<ProductVersion(product_id={self.product_id}, version={self.version})>"

class Configuration(db.Model):
    __tablename__ = 'configurations'
    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'), nullable=False, index=True)
    function_id = db.Column(db.Integer, db.ForeignKey('functions.id'), nullable=False, index=True)
    component_id = db.Column(db.Integer, db.ForeignKey('components.id'), nullable=False, index=True)
    status = db.Column(db.String(50), default='Active', nullable=False, index=True)
    deployment_date = db.Column(db.Date, nullable=True)
    version_label = db.Column(db.String(100))
    implementation_notes = db.Column(db.String(1000))
    security_review_date = db.Column(db.Date, nullable=True)
    additional_metadata = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    agency = db.relationship('Agency', back_populates='configurations')
    function = db.relationship('Function', back_populates='configurations')
    component = db.relationship('Component', back_populates='configurations')
    products = db.relationship('ConfigurationProduct', back_populates='configuration', cascade='all, delete-orphan')
    history_entries = db.relationship('ConfigurationHistory', back_populates='configuration', cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('agency_id', 'function_id', 'component_id', name='uq_configuration_agency_function_component'),
        db.Index('ix_configuration_agency_function', 'agency_id', 'function_id'),
        db.Index('ix_configuration_component', 'component_id'),
    )

    def __repr__(self):
        return f"<Configuration(agency_id={self.agency_id}, function_id={self.function_id}, component_id={self.component_id})>"

class ConfigurationProduct(db.Model):
    __tablename__ = 'configuration_products'
    id = db.Column(db.Integer, primary_key=True)
    configuration_id = db.Column(db.Integer, db.ForeignKey('configurations.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    product_version_id = db.Column(db.Integer, db.ForeignKey('product_versions.id'), nullable=True, index=True)
    status = db.Column(db.String(50), default='Active', nullable=False, index=True)
    deployment_date = db.Column(db.Date, nullable=True)
    settings = db.Column(db.JSON)  # free-form JSON for product-specific configuration
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    configuration = db.relationship('Configuration', back_populates='products')
    product = db.relationship('Product', back_populates='configuration_products')
    product_version = db.relationship('ProductVersion', back_populates='configuration_products')

    __table_args__ = (
        db.UniqueConstraint('configuration_id', 'product_id', name='uq_configuration_product'),
        db.Index('ix_configuration_product_product_version', 'product_id', 'product_version_id'),
    )

    def __repr__(self):
        return f"<ConfigurationProduct(configuration_id={self.configuration_id}, product_id={self.product_id}, version_id={self.product_version_id})>"

class ConfigurationHistory(db.Model):
    __tablename__ = 'configuration_history'
    id = db.Column(db.Integer, primary_key=True)
    configuration_id = db.Column(db.Integer, db.ForeignKey('configurations.id', ondelete='CASCADE'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True, nullable=False)
    action = db.Column(db.String(50), nullable=False)  # created, updated, status_change, product_added, product_removed, advisory_ack, deleted
    changed_by = db.Column(db.String(100))
    old_values = db.Column(db.JSON)
    new_values = db.Column(db.JSON)

    configuration = db.relationship('Configuration', back_populates='history_entries')

    def __repr__(self):
        return f"<ConfigurationHistory(configuration_id={self.configuration_id}, action={self.action}, timestamp={self.timestamp})>"
