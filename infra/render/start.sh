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
    password = os.environ["CLASSIO_APP_PASSWORD"]
    exists = db.execute("SELECT 1 FROM pg_roles WHERE rolname = 'classio_app'").fetchone()
    # Sans SUPERUSER, PostgreSQL 16+ interdit de nommer SUPERUSER ou BYPASSRLS, même pour les
    # refuser : on crée le rôle avec les valeurs par défaut (toutes à NO), puis on les vérifie.
    verb = "ALTER" if exists else "CREATE"
    db.execute(sql.SQL(verb + " ROLE classio_app LOGIN PASSWORD {}").format(sql.Literal(password)))
    unsafe = db.execute(
        "SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles "
        "WHERE rolname = 'classio_app'").fetchone()[0]
    if unsafe:
        sys.exit("Le rôle classio_app a des droits qui contournent le RLS : arrêt.")
    if not db.execute("SELECT pg_has_role(current_user, 'classio_app', 'MEMBER')").fetchone()[0]:
        db.execute(sql.SQL("GRANT classio_app TO {}").format(sql.Identifier(me)))
    dbname = db.info.dbname
    db.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(dbname)))
    db.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO classio_app").format(sql.Identifier(dbname)))
    mode = "BYPASSRLS" if bypass else "propriétaire des tables, RLS non forcé pour lui"
    print(f"  propriétaire : {me} ({mode}) ; application : classio_app, soumis au RLS")
PY

app_url=$(python -c "
import os, urllib.parse as u
p = u.urlsplit(os.environ['DATABASE_ADMIN_URL'])
host = p.hostname + (f':{p.port}' if p.port else '')
pw = u.quote(os.environ['CLASSIO_APP_PASSWORD'], safe='')
print(u.urlunsplit((p.scheme, f'classio_app:{pw}@{host}', p.path, p.query, '')))")

echo "▸ Migrations"
DATABASE_URL="$DATABASE_ADMIN_URL" python manage.py migrate --noinput

# Les hébergeurs gérés (Render, Neon…) ne donnent jamais BYPASSRLS. Avec FORCE, le propriétaire
# des tables serait bloqué par des politiques qui ne visent que classio_app. Sans FORCE, il en est
# exempté comme tout propriétaire, alors que classio_app, qui n'est pas propriétaire, reste soumis
# à toutes les politiques. Refait à chaque démarrage : une nouvelle migration remet FORCE.
DATABASE_URL="$DATABASE_ADMIN_URL" python - <<'PY'
import os
import psycopg
from psycopg import sql

with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as db:
    if db.execute("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user").fetchone()[0]:
        raise SystemExit
    tables = db.execute(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relforcerowsecurity "
        "AND pg_get_userbyid(c.relowner) = current_user").fetchall()
    for (table,) in tables:
        db.execute(sql.SQL("ALTER TABLE {} NO FORCE ROW LEVEL SECURITY").format(sql.Identifier(table)))
    print(f"  RLS non forcé pour le propriétaire sur {len(tables)} table(s)")
PY
export DATABASE_URL="$app_url"
python manage.py collectstatic --noinput -v 0

echo "▸ Démarrage"
gunicorn config.wsgi -c gunicorn.conf.py --bind 127.0.0.1:8000 &

# Après le démarrage, en arrière-plan : sur l'offre gratuite, le chargement dure plusieurs
# minutes, et Render arrête le service si aucun port n'est ouvert à temps. Le chargement est
# tout ou rien : interrompu, il recommence au démarrage suivant.
if [ -n "${DEMO_PASSWORD:-}" ]; then
  (
    echo "▸ Écoles fictives (si absentes), en arrière-plan"
    DATABASE_URL="$DATABASE_ADMIN_URL" nice python manage.py seed_demo --password "$DEMO_PASSWORD" \
      || echo "▸ Échec du chargement des écoles fictives (voir ci-dessus)"
  ) &
fi
export SITE_ADDRESS=":$PORT" BACKEND_UPSTREAM=127.0.0.1:8000 DJANGO_STATIC_ROOT=/app/staticfiles
export TRUSTED_PROXIES="${TRUSTED_PROXIES:-private_ranges}"
export CLIENT_IP_HEADERS="${CLIENT_IP_HEADERS:-Cf-Connecting-IP X-Forwarded-For}"
export ACME_EMAIL="${ACME_EMAIL:-classiobenin@gmail.com}"
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
