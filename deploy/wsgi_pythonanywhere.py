# Pegar como contenido del archivo WSGI de PythonAnywhere (pestaña Web > WSGI configuration file).
import os
import sys

path = os.path.expanduser("~/radar-30x")
if path not in sys.path:
    sys.path.insert(0, path)
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_SECRET_KEY"] = open(os.path.expanduser("~/.radar_secret")).read().strip()
os.environ["DJANGO_ALLOWED_HOSTS"] = "p1p2gamer26.pythonanywhere.com"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
