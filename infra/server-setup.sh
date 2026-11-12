#!/usr/bin/env bash
# Préparation d'un VPS neuf sous Ubuntu 24.04, à lancer une fois en root :
#   curl -fsSL <dépôt>/infra/server-setup.sh | sudo bash      (ou après un git clone)
# Installe Docker, rclone, le pare-feu, les mises à jour de sécurité automatiques et les tâches
# planifiées de sauvegarde. Ne touche pas à la configuration SSH : faites-le en connaissance de
# cause (clé SSH, puis PasswordAuthentication no).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "À lancer en root (sudo)." >&2; exit 1; }
. /etc/os-release
[ "$ID" = ubuntu ] || { echo "Prévu pour Ubuntu, trouvé : $ID" >&2; exit 1; }

say() { printf '\n\033[1;32m▸ %s\033[0m\n' "$1"; }

say "Paquets de base et mises à jour de sécurité automatiques"
apt-get update -q
apt-get install -y -q ca-certificates curl gnupg git ufw unattended-upgrades rclone
dpkg-reconfigure -f noninteractive unattended-upgrades

say "Docker (dépôt officiel)"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
apt-get update -q
apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin

say "Pare-feu : SSH, HTTP, HTTPS seulement"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

say "Dossiers et phrase de passe des sauvegardes"
mkdir -p /opt/classio /var/backups/classio /etc/classio
chmod 700 /var/backups/classio /etc/classio
if [ ! -f /etc/classio/backup.pass ]; then
  openssl rand -hex 32 > /etc/classio/backup.pass
  chmod 600 /etc/classio/backup.pass
  echo "Phrase de passe créée dans /etc/classio/backup.pass : COPIEZ-LA HORS DU SERVEUR."
fi

say "Tâches planifiées (sauvegarde chaque nuit, test de restauration chaque mois)"
cat > /etc/cron.d/classio <<CRON
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# RCLONE_REMOTE=sauvegardes:classio  (décommentez après `rclone config`)
15 2 * * * root COMPOSE_FILE=/opt/classio/infra/docker-compose.prod.yml /opt/classio/infra/backup.sh >> /var/log/classio-backup.log 2>&1
0 4 1 * * root /opt/classio/infra/restore-test.sh >> /var/log/classio-backup.log 2>&1
CRON
chmod 644 /etc/cron.d/classio

say "Terminé"
cat <<NEXT
Étapes suivantes (docs/05-deploiement.md) :
  1. git clone <dépôt> /opt/classio && cd /opt/classio && git switch feat/refonte-django-react
  2. cp infra/.env.prod.example infra/.env.prod && chmod 600 infra/.env.prod   (remplir)
  3. docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d --build
  4. rclone config, puis décommenter RCLONE_REMOTE dans /etc/cron.d/classio
NEXT
