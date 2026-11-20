#!/bin/sh
# Démarrage sur Render. DATABASE_ADMIN_URL est l'utilisateur fourni par l'hébergeur : il joue
# les migrations et possède les tables. L'application, elle, se connecte avec classio_app,
# soumis au RLS : comme en production, une école ne voit jamais les données d'une autre.
set -eu
: "${DATABASE_ADMIN_URL:?}" "${CLASSIO_APP_PASSWORD:?}" "${PORT:=10000}"
host="${RENDER_EXTERNAL_HOSTNAME:-${DOMAIN:?RENDER_EXTERNAL_HOSTNAME ou DOMAIN}}"
export ALLOWED_HOSTS="$host" CSRF_TRUSTED_ORIGINS="https://$host" PUBLIC_URL="https://$host"
export BASE_DOMAIN="${BASE_DOMAIN:-$host}" DJANGO_DEBUG=False TRUSTED_PROXY_COUNT=1
# Pas de worker séparé dans l'offre gratuite : les tâches s'exécutent dans la requête.
export CELERY_TASK_ALWAYS_EAGER=True WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"

echo "▸ Rôles de la base"
DATABASE_URL="$DATABASE_ADMIN_URL" python - <<'PY'
import os, sys
import psycopg
from psycopg import sql

with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as db:
    me, bypass = db.execute(
        "SELECT current_user, rolbypassrls FROM pg_roles WHERE rolname = current_user").fetchone()
    if not bypass:
        sys.exit(f"L'utilisateur {me} n'a pas l'attribut BYPASSRLS : les commandes d'administration "
                 "(création d'école, données fictives) ne pourraient pas fonctionner. Utilisez une "
                 "base où l'utilisateur principal l'a (docs/10-deploiement-gratuit.md).")
    password = os.environ["CLASSIO_APP_PASSWORD"]
    exists = db.execute("SELECT 1 FROM pg_roles WHERE rolname = 'classio_app'").fetchone()
    verb = "ALTER" if exists else "CREATE"
    db.execute(sql.SQL(verb + " ROLE classio_app LOGIN PASSWORD {} "
                       "NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS").format(sql.Literal(password)))
    db.execute(sql.SQL("GRANT classio_app TO {}").format(sql.Identifier(me)))
    dbname = db.info.dbname
    db.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(dbname)))
    db.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO classio_app").format(sql.Identifier(dbname)))
    print(f"  propriétaire : {me} (BYPASSRLS) ; application : classio_app")
PY

app_url=$(python -c "
import os, urllib.parse as u
p = u.urlsplit(os.environ['DATABASE_ADMIN_URL'])
host = p.hostname + (f':{p.port}' if p.port else '')
pw = u.quote(os.environ['CLASSIO_APP_PASSWORD'], safe='')
print(u.urlunsplit((p.scheme, f'classio_app:{pw}@{host}', p.path, p.query, '')))")

echo "▸ Migrations"
DATABASE_URL="$DATABASE_ADMIN_URL" python manage.py migrate --noinput
if [ -n "${DEMO_PASSWORD:-}" ]; then
  echo "▸ Écoles fictives (si absentes)"
  DATABASE_URL="$DATABASE_ADMIN_URL" python manage.py seed_demo --password "$DEMO_PASSWORD"
fi
export DATABASE_URL="$app_url"
python manage.py collectstatic --noinput -v 0

echo "▸ Démarrage"
gunicorn config.wsgi -c gunicorn.conf.py --bind 127.0.0.1:8000 &
export SITE_ADDRESS=":$PORT" BACKEND_UPSTREAM=127.0.0.1:8000 DJANGO_STATIC_ROOT=/app/staticfiles
export TRUSTED_PROXIES="${TRUSTED_PROXIES:-private_ranges}"
export CLIENT_IP_HEADERS="${CLIENT_IP_HEADERS:-Cf-Connecting-IP X-Forwarded-For}"
export ACME_EMAIL="${ACME_EMAIL:-classiobenin@gmail.com}"
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
