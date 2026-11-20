#!/usr/bin/env bash
# Sauvegarde chiffrée de la base. À lancer chaque nuit par cron sur le serveur :
#   15 2 * * * /opt/classio/infra/backup.sh >> /var/log/classio-backup.log 2>&1
# La phrase de passe vit dans un fichier lisible par root seul, jamais à côté des sauvegardes.
# Copiez ensuite BACKUP_DIR hors du serveur (rclone, autre fournisseur) : une sauvegarde sur la
# même machine ne protège pas d'une panne de disque ou d'un piratage du serveur.
set -euo pipefail
cd "$(dirname "$0")"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
# Sans ce fichier, docker compose refuse de lire la configuration (variables obligatoires) et la
# sauvegarde échoue chaque nuit.
ENV_FILE="${ENV_FILE:-.env.prod}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/classio}"
PASSPHRASE_FILE="${PASSPHRASE_FILE:-/etc/classio/backup.pass}"
KEEP_DAYS="${KEEP_DAYS:-30}"

mkdir -p "$BACKUP_DIR"
target="$BACKUP_DIR/classio-$(date +%Y%m%d-%H%M%S).dump.gpg"
# Une sauvegarde interrompue ne doit pas rester : le test de restauration la prendrait pour la
# dernière.
trap 'rm -f "$target"; echo "$(date -Is) ÉCHEC de la sauvegarde" >&2' ERR
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres pg_dump -U postgres -Fc classio \
  | gpg --batch --yes --quiet --symmetric --cipher-algo AES256 \
        --passphrase-file "$PASSPHRASE_FILE" -o "$target"
[ -s "$target" ] || { echo "Sauvegarde vide : échec" >&2; exit 1; }
# Copie hors du serveur (ex. RCLONE_REMOTE=sauvegardes:classio, configuré avec `rclone config`).
# Le fichier est déjà chiffré : le second fournisseur ne voit jamais les données.
if [ -n "${RCLONE_REMOTE:-}" ]; then
  rclone copy --no-traverse "$target" "$RCLONE_REMOTE"
  rclone delete --min-age "${KEEP_DAYS}d" "$RCLONE_REMOTE"
fi
find "$BACKUP_DIR" -name 'classio-*.dump.gpg' -mtime +"$KEEP_DAYS" -delete
echo "$(date -Is) sauvegarde OK : $target ($(du -h "$target" | cut -f1))"
