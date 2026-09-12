import os
import urllib.parse
from datetime import timedelta

class Config:
    """Configuración base de la aplicación MediotecVial"""

    # Flask Config
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('FLASK_ENV') == 'development'

    # Credenciales de Azure SQL Database
    _db_server = os.environ.get('AZURE_SQL_SERVER')
    _db_name = os.environ.get('AZURE_SQL_DATABASE')
    _db_user = os.environ.get('AZURE_SQL_ADMIN_USER') or os.environ.get('AZURE_SQL_USER')
    _db_password = os.environ.get('AZURE_SQL_ADMIN_PASSWORD') or os.environ.get('AZURE_SQL_PASSWORD')

    # Codificación segura de credenciales para URLs SQLAlchemy
    _constructed_url = None
    if all([_db_server, _db_name, _db_user, _db_password]):
        _quoted_user = urllib.parse.quote_plus(_db_user)
        _quoted_pass = urllib.parse.quote_plus(_db_password)
        _constructed_url = (
            f'mssql+pyodbc://{_quoted_user}:{_quoted_pass}@{_db_server}:1433/{_db_name}'
            '?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30'
        )

    # Si se especificó DATABASE_URL en .env, sanitizar o usar construida
    _raw_db_url = os.environ.get('DATABASE_URL')
    if _raw_db_url and '@' in _raw_db_url:
        _db_url = _raw_db_url
    else:
        _db_url = _constructed_url

    # Verificación de disponibilidad del driver ODBC en el entorno de ejecución
    _odbc_available = False
    try:
        import pyodbc
        _odbc_available = True
    except (ImportError, Exception):
        _odbc_available = False

    # En entornos sin driver ODBC del sistema (como desarrollo local sin unixodbc instalado),
    # o si se solicita explícitamente USE_SQLITE, fallback a SQLite para desarrollo/pruebas.
    if not _db_url and not os.environ.get('WEBSITE_INSTANCE_ID'):
        _db_url = os.environ.get('LOCAL_DATABASE_URL') or 'sqlite:///mediotec.db'

    SQLALCHEMY_DATABASE_URI = _db_url or 'sqlite:///mediotec.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Engine options adaptativas
    if SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'echo': False,
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'echo': False,
            'pool_pre_ping': True,
            'pool_recycle': 3600,
            'pool_size': 5,
            'max_overflow': 10,
        }

    # JWT Config
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    # Azure Storage Config
    AZURE_STORAGE_ACCOUNT_NAME = os.environ.get('AZURE_STORAGE_ACCOUNT_NAME') or 'mediotec72209'
    AZURE_STORAGE_ACCOUNT_URL = os.environ.get('AZURE_STORAGE_ACCOUNT_URL') or \
        f'https://{AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net'
    AZURE_STORAGE_ACCOUNT_KEY = os.environ.get('AZURE_STORAGE_ACCOUNT_KEY')
    AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    AZURE_CONTAINER_NAME = os.environ.get('AZURE_CONTAINER_NAME') or 'mediotec-plans'

    # Upload Config
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
    UPLOAD_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'gif'}

    # Session Config
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Configuración para producción en Azure App Service"""
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Configuración aislada para ejecución de tests"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'echo': False,
    }
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
