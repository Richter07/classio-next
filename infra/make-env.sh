#!/usr/bin/env bash
# Crée infra/.env.prod avec des secrets tirés au hasard (une seule fois) :
#   infra/make-env.sh classio-test.duckdns.org
# Le fichier reste sur le serveur : jamais dans git, jamais envoyé par courriel ou WhatsApp.
set -euo pipefail
cd "$(dirname "$0")"
domain="${1:?Usage : infra/make-env.sh <domaine>, par exemple classio-test.duckdns.org}"
out="${ENV_OUT:-.env.prod}"
[ ! -e "$out" ] || { echo "infra/$out existe déjà : rien n'est modifié." >&2; exit 1; }
secret() { openssl rand -hex 32; }
umask 077
cat > "$out" <<ENV
DOMAIN=$domain
BASE_DOMAIN=$domain
ACME_EMAIL=classiobenin@gmail.com

DJANGO_SECRET_KEY=$(secret)
ACCESS_CODE_KEY=$(secret)
POSTGRES_PASSWORD=$(secret)
CLASSIO_OWNER_PASSWORD=$(secret)
CLASSIO_APP_PASSWORD=$(secret)

SENTRY_DSN=
ENV
echo "infra/$out créé pour https://$domain (lisible par vous seul)."
