import os  # FIX: F821 - Import os

# Standard application configuration module


class Config:
    """Base configuration settings."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-secret')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # KAiSurf-specific settings
    SUPABASE_JWT_SECRET = os.environ.get(
        'SUPABASE_JWT_SECRET',
        'test-jwt-secret'
    )
    TRUSTED_SERVICE_API_KEY = os.environ.get(
        'TRUSTED_SERVICE_API_KEY',
        'test-api-key'
    )


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    # Use a file-based SQLite for easy inspection during development
    SQLALCHEMY_DATABASE_URI = 'sqlite:///kaisurf_dev.db'


class TestingConfig(Config):
    """Testing environment configuration (used by conftest.py)."""
    TESTING = True
    # CRITICAL: In-memory SQLite for guaranteed test isolation
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class ProductionConfig(Config):
    """Production environment configuration (e.g., Supabase, Heroku)."""
    # Disable debug for production safety
    DEBUG = False
    # Use environment variable for production database connection string
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://user:password@host:port/dbname'  # Placeholder /Postgres
    )
