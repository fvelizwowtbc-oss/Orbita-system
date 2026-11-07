# config.py
# Configuracion de produccion web para Orbita System.
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def _env_path(key, default):
    val = os.environ.get(key)
    if val:
        return Path(val).resolve()
    return (PROJECT_ROOT / default).resolve()


DATA_DIR = _env_path("DATA_DIR", "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

INSTANCE_DIR = DATA_DIR / "instance"
UPLOAD_FOLDER = DATA_DIR / "uploads"
FACTURAS_DIR = DATA_DIR / "facturas"
LOG_DIR = DATA_DIR / "logs"

for _d in (INSTANCE_DIR, UPLOAD_FOLDER, FACTURAS_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY no definida. Ejecuta setup_produccion.py o agrega "
            "SECRET_KEY al .env"
        )

    # ============ IMAGEKIT (IMAGENES) ============
    IMAGEKIT_PUBLIC_KEY = os.environ.get("IMAGEKIT_PUBLIC_KEY")
    IMAGEKIT_PRIVATE_KEY = os.environ.get("IMAGEKIT_PRIVATE_KEY")
    IMAGEKIT_URL_ENDPOINT = os.environ.get("IMAGEKIT_URL_ENDPOINT")

    # ============ BASE DE DATOS ============
    _db_url = os.environ.get('DATABASE_URL', '')
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = _db_url or f"sqlite:///{INSTANCE_DIR / 'sistema_gestion.db'}"
    
    # ✅ FIX: Si estamos en Render (produccion) y no hay DATABASE_URL, es un error fatal
    import os as _os
    if _os.environ.get('RENDER') and not _db_url:
        raise RuntimeError("FATAL: DATABASE_URL no está configurada en Render. La app no puede usar SQLite en producción.")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Opciones del motor: solo aplicamos check_same_thread a SQLite
    if SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "connect_args": {
                "check_same_thread": False,
                "timeout": 30,
            },
        }
    else:
        # Para PostgreSQL, solo pre_ping
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
        }

    UPLOAD_FOLDER = str(UPLOAD_FOLDER)
    FACTURAS_DIR = str(FACTURAS_DIR)
    LOG_DIR = str(LOG_DIR)

    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    SESSION_COOKIE_SECURE = os.environ.get("HTTPS", "0") == "1"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 3600 * 8

    TASA_CACHE_TTL = int(os.environ.get("TASA_CACHE_TTL", 3600))
    TASA_FALLBACK = float(os.environ.get("TASA_FALLBACK", 50.0))
    TASA_CACHE_FILE = str(DATA_DIR / "tasa_cache.json")

    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_ENABLED = True

    TIMEZONE = "America/Caracas"
    TZ_OFFSET_HOURS = -4

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": ProductionConfig,
}
