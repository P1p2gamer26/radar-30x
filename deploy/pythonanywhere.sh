#!/usr/bin/env bash
# Uso en una consola Bash de PythonAnywhere:
#   git clone https://github.com/P1p2gamer26/radar-30x.git ~/radar-30x  (solo la primera vez)
#   bash ~/radar-30x/deploy/pythonanywhere.sh
set -e
cd ~/radar-30x && git fetch -q origin && git checkout -q -f -B main origin/main  # el servidor solo refleja GitHub
[ -f ~/.radar_secret ] || python3 -c "import secrets;print(secrets.token_urlsafe(50))" > ~/.radar_secret
[ -d .venv ] || python3.13 -m venv --system-site-packages .venv
.venv/bin/pip install -q --no-cache-dir -r requirements.txt
export DJANGO_SECRET_KEY="$(cat ~/.radar_secret)" DJANGO_ALLOWED_HOSTS="${USER,,}.pythonanywhere.com"
.venv/bin/python manage.py migrate -v0
# sin collectstatic: STATIC_SIN_COLLECT=1 (ver config/settings.py)
touch /var/www/${USER,,}_pythonanywhere_com_wsgi.py 2>/dev/null || true
echo "OK: recarga la web app en la pestaña Web"
