#!/usr/bin/env bash
# Classio, environnement de développement en une commande.
#   ./dev.sh          démarre tout (base, migrations, données de démo, API, application)
#   ./dev.sh reset    efface la base locale et recrée les données de démonstration
#   ./dev.sh test     lance les tests du backend
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
COMPOSE="docker compose -f $ROOT/infra/docker-compose.dev.yml"

say() { printf '\n\033[1;32m▸ %s\033[0m\n' "$1"; }

backend_env() {
  cd "$ROOT/backend"
  [ -d .venv ] || { python3 -m venv .venv; .venv/bin/pip install -q --require-hashes -r requirements/dev.txt; }
  [ -f .env ] || cp .env.example .env
  # shellcheck disable=SC1091
  source .venv/bin/activate
  OWNER_URL="$(grep ^MIGRATION_DATABASE_URL .env | cut -d= -f2-)"
}

services() {
  say "Base de données et Redis"
  $COMPOSE up -d --wait
}

migrate_seed() {
  say "Migrations et données de démonstration"
  DATABASE_URL="$OWNER_URL" python manage.py migrate --no-input -v 0
  DATABASE_URL="$OWNER_URL" python manage.py seed_demo
}

case "${1:-start}" in
  reset)
    services
    say "Remise à zéro de la base locale"
    $COMPOSE exec -T postgres psql -q -U postgres \
      -c "DROP DATABASE IF EXISTS classio WITH (FORCE)" \
      -c "CREATE DATABASE classio OWNER classio_owner" \
      -c "REVOKE ALL ON DATABASE classio FROM PUBLIC" \
      -c "GRANT CONNECT ON DATABASE classio TO classio_app"
    $COMPOSE exec -T redis redis-cli FLUSHALL >/dev/null
    backend_env; migrate_seed
    ;;
  test)
    services; backend_env
    DATABASE_URL="$OWNER_URL" pytest -q "${@:2}"
    ;;
  start)
    services; backend_env; migrate_seed
    cd "$ROOT/frontend"; [ -d node_modules ] || npm ci
    LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    cat <<INFO

  Classio tourne. Ctrl+C pour tout arrêter.

  Parents        http://localhost:5173
  Personnel      http://localhost:5173/ecole
  Sur téléphone  http://${LAN_IP:-<ip-du-pc>}:5173   (même Wi-Fi que ce PC)
  Admin Django   http://localhost:8000/admin/

  Comptes de démonstration (mot de passe : classio-demo-2026)
    Parent (2 écoles) 01 97 00 00 01
    Parent à activer  01 97 00 00 02  « Première connexion », code PARE-NT26
    Direction         01 97 00 00 10  code école : ceg-les-pylones
    Secrétariat       01 97 00 00 11
    Enseignant        01 97 00 00 12  maths, SVT
    Enseignante       01 97 00 00 13  français, anglais (une saisie en cours)
    Enseignant        01 97 00 00 14  histoire-géo, EPS
    Super-admin       01 97 00 00 99  (admin Django)

INFO
    trap 'kill 0' EXIT INT TERM
    (cd "$ROOT/backend" && python manage.py runserver 0.0.0.0:8000) &
    (cd "$ROOT/frontend" && npm run dev -- --host 0.0.0.0) &
    wait
    ;;
  *) echo "Usage : ./dev.sh [start|reset|test]"; exit 1 ;;
esac
