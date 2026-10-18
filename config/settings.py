"""Settings 100% desde variables de entorno (ver .env.example). Sin secretos en el repo."""
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

# ponytail: mini-cargador de .env en vez de python-dotenv (0 dependencias). Solo KEY=VALOR simple.
_env = BASE_DIR / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.split(" #")[0].strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"  # apagado por defecto (prod)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG or "pytest" in sys.modules:
        SECRET_KEY = "solo-para-desarrollo-y-tests"
    else:
        raise ImproperlyConfigured("Falta DJANGO_SECRET_KEY (ver .env.example)")

ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "radar",
    "decision",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

WSGI_APPLICATION = "config.wsgi.application"

# ponytail: SQLite basta para el demo; para piloto real cambiar a Postgres via DATABASE_URL.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ponytail: en PythonAnywhere free (100 s de CPU/día) no se comprime ni se copia nada: whitenoise sirve desde las apps.
WHITENOISE_USE_FINDERS = os.environ.get("STATIC_SIN_COLLECT") == "1"
if not DEBUG and "pytest" not in sys.modules and not WHITENOISE_USE_FINDERS:
    STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}

if not DEBUG:
    SESSION_COOKIE_HTTPONLY = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# --- Motor de decision (ver decision/decide.py) ---
DECISION_MODE = os.environ.get("DECISION_MODE", "live")
AUTO_THRESHOLD = float(os.environ.get("AUTO_THRESHOLD", "0.80"))
REVIEW_THRESHOLD = float(os.environ.get("REVIEW_THRESHOLD", "0.50"))
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:20128/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("9ROUTER_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "5"))
LLM_PRICE_IN_PER_1M = float(os.environ.get("LLM_PRICE_IN_PER_1M", "0"))
LLM_PRICE_OUT_PER_1M = float(os.environ.get("LLM_PRICE_OUT_PER_1M", "0"))
SYSTEMONE_URL = os.environ.get("SYSTEMONE_URL", "")
SYSTEMONE_API_KEY = os.environ.get("SYSTEMONE_API_KEY", "")  # vacío con Von local; clave de TypeSafe con Jev real
SYSTEMONE_TIMEOUT = float(os.environ.get("SYSTEMONE_TIMEOUT", "30"))  # Von en CPU tarda ~7 s por pieza
DECISION_RECORDINGS_DIR = BASE_DIR / "decision" / "recordings"

