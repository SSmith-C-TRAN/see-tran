from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
import os

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()

def create_app(test_config=None):
    app = Flask(__name__)
    
    if test_config:
        app.config.update(test_config)
    else:
        # Import config classes
        from config import DevelopmentConfig, ProductionConfig, TestConfig
        
        # Use DevelopmentConfig by default, or based on environment
        flask_env = os.environ.get('FLASK_ENV', 'development')
        if flask_env == 'production':
            app.config.from_object(ProductionConfig)
        elif flask_env == 'testing':
            app.config.from_object(TestConfig)
        else:
            app.config.from_object(DevelopmentConfig)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    # Import models so Flask-Migrate can detect them
    with app.app_context():
        from app.models import tran
    
    # register blueprints
    from app.routes.main import main as main_bp
    app.register_blueprint(main_bp)

    from app.routes.agency import agency_bp
    app.register_blueprint(agency_bp)
    from app.routes.integrations import integration_bp
    app.register_blueprint(integration_bp)

    # Register auth routes
    from app.auth import auth_bp
    app.register_blueprint(auth_bp)

    # Register admin routes
    from app.routes import admin as admin_bp
    app.register_blueprint(admin_bp)
    
    # Phase 4 new blueprint
    from app.routes.configurations import config_bp
    app.register_blueprint(config_bp)
    
    return app
