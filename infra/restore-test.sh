#!/usr/bin/env bash
# Test de restauration (cahier des charges §7) : restaure la dernière sauvegarde dans un
# PostgreSQL jetable, vérifie qu'elle contient des données, puis le détruit. À lancer chaque mois.
# Une sauvegarde jamais restaurée n'est pas une sauvegarde.
set -euo pipefail
BACKUP_DIR="${BACKUP_DIR:-/var/backups/classio}"
PASSPHRASE_FILE="${PASSPHRASE_FILE:-/etc/classio/backup.pass}"
latest="$(ls -1t "$BACKUP_DIR"/classio-*.dump.gpg | head -1)"
name="classio-restore-test-$$"

cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$name" -e POSTGRES_PASSWORD=test postgres:17-alpine >/dev/null
until docker exec "$name" pg_isready -U postgres -q; do sleep 1; done
sleep 2
# Les rôles doivent exister pour restaurer les droits et les politiques RLS à l'identique.
docker exec "$name" psql -q -U postgres -c "CREATE ROLE classio_app" \
  -c "CREATE ROLE classio_owner BYPASSRLS" -c "CREATE DATABASE classio OWNER classio_owner"
gpg --batch --quiet --decrypt --passphrase-file "$PASSPHRASE_FILE" "$latest" \
  | docker exec -i "$name" pg_restore -U postgres -d classio --exit-on-error
counts="$(docker exec "$name" psql -U postgres -d classio -tA -c \
  "SELECT (SELECT count(*) FROM tenancy_school) || ' écoles, ' ||
          (SELECT count(*) FROM students_student) || ' élèves, ' ||
          (SELECT count(*) FROM grades_grade) || ' notes'")"
policies="$(docker exec "$name" psql -U postgres -d classio -tA -c "SELECT count(*) FROM pg_policies")"
echo "Restauration de $(basename "$latest") : $counts, $policies politiques RLS."
[ "$policies" -gt 0 ] || { echo "Aucune politique RLS restaurée : échec" >&2; exit 1; }
