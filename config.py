# config.py

import os
from dotenv import load_dotenv
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # Core Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DEBUG = os.environ.get('FLASK_ENV') == 'development'
    
    # Database settings - SQLite support
    DB_TYPE = os.environ.get('DB_TYPE', 'sqlite')
    
    if DB_TYPE == 'postgres':
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    else:
        # SQLite database
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'instance', 'app.db')}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    
    # Security settings
    CSRF_ENABLED = True
    
    # Application paths and cookies
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_REFRESH_EACH_REQUEST = True

    WTF_CSRF_TIME_LIMIT = 24 * 3600  # 24 hours in seconds
    WTF_CSRF_SSL_STRICT = False
    
    # File upload settings
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB limit
    
    # Email settings
    POSTMARK_API_KEY = os.getenv('POSTMARK_API_KEY')
    POSTMARK_SENDER_EMAIL = os.getenv('POSTMARK_SENDER_EMAIL')
    POSTMARK_NOTIFY_EMAIL = os.getenv('POSTMARK_NOTIFY_EMAIL')

    SUPER_ADMIN_EMAIL = os.getenv('SUPER_ADMIN_EMAIL')

    # LLM API Keys
    CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')
    CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages'
    CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL', 'claude-3-5-haiku-20241022')
    
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    
    # Agent Configuration
    AGENT_PROVIDERS = {
        'agency': {
            'provider': os.environ.get('AGENCY_AGENT_PROVIDER', 'anthropic'),
            'model': os.environ.get('AGENCY_AGENT_MODEL', 'claude-sonnet-4-20250514'),
        },
        'vendor': {
            'provider': os.environ.get('VENDOR_AGENT_PROVIDER', 'anthropic'),
            'model': os.environ.get('VENDOR_AGENT_MODEL', 'claude-sonnet-4-20250514'),
        },
        'component': {
            'provider': os.environ.get('COMPONENT_AGENT_PROVIDER', 'anthropic'),
            'model': os.environ.get('COMPONENT_AGENT_MODEL', 'claude-sonnet-4-20250514'),
        },
        'image_fetch': {
            'provider': os.environ.get('IMAGE_AGENT_PROVIDER', 'openai'),
            'model': os.environ.get('IMAGE_AGENT_MODEL', 'gpt-4o'),
        },
    }
    
    AGENT_CONFIDENCE_THRESHOLD = float(os.environ.get('AGENT_CONFIDENCE_THRESHOLD', '0.7'))
    
    # AWS settings
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
    S3_BUCKET = os.environ.get('S3_BUCKET', 'well-app')
    
    # Application URLs
    SMS_BASE_URL = os.environ.get('SMS_BASE_URL', 'https://see-tran.com')
    
    @staticmethod
    def get_s3_prefix(tenant_id):
        """Generate S3 key prefix for tenant isolation"""
        return f'tenant_{tenant_id}'
    
    # SMS settings
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM_NUMBER')

    SMS_TEST_PHONE_NUMBER = os.environ.get('SMS_TEST_PHONE_NUMBER', '+18084649192')

    # OAuth settings
    OAUTH_GOOGLE_CLIENT_ID = os.environ.get('OAUTH_GOOGLE_CLIENT_ID')
    OAUTH_GOOGLE_CLIENT_SECRET = os.environ.get('OAUTH_GOOGLE_CLIENT_SECRET')
    OAUTH_GOOGLE_DISCOVERY_URL = os.environ.get('OAUTH_GOOGLE_DISCOVERY_URL')

    OAUTH_MS_CLIENT_ID = os.environ.get('OAUTH_MS_CLIENT_ID')
    OAUTH_MS_CLIENT_SECRET = os.environ.get('OAUTH_MS_CLIENT_SECRET')
    OAUTH_MS_DISCOVERY_URL = 'https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration'

class DevelopmentConfig(Config):
    """Development configuration."""
    FLASK_ENV = 'development'
    DEBUG = True
    DEVELOPMENT = True
    
    # More permissive session cookie settings for development
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_DOMAIN = None  # Allow all domains in development

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    DEVELOPMENT = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_FILE_DIR = '/home/ubuntu/see-tran/flask_session'

class TestConfig(Config):
    """Test configuration."""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False