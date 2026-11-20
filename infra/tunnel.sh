#!/usr/bin/env bash
# Classio en ligne depuis cet ordinateur, gratuitement, pour les tests (données fictives) :
#   infra/tunnel.sh          lance Classio et affiche son adresse https://….trycloudflare.com
#   infra/tunnel.sh seed     charge les écoles fictives (une fois) et affiche leur mot de passe
#   infra/tunnel.sh stop     arrête tout (les données sont gardées)
# L'adresse change à chaque lancement. Les données restent sur cet ordinateur ; le tunnel
# Cloudflare les fait transiter : jamais de vraies données d'élèves.
set -euo pipefail
cd "$(dirname "$0")"
ENV_FILE=.env.tunnel
C=(docker compose -p classio-test -f docker-compose.prod.yml -f docker-compose.tunnel.yml --env-file "$ENV_FILE")

if [ ! -e "$ENV_FILE" ]; then
  ENV_OUT="$ENV_FILE" ./make-env.sh en-attente.trycloudflare.com >/dev/null
  printf '\n# Mode tunnel (infra/tunnel.sh)\nCADDY_SITE_ADDRESS=:80\nCADDY_TRUSTED_PROXIES=private_ranges\n' >> "$ENV_FILE"
fi
url() { "${C[@]}" logs tunnel 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | grep -v '//api\.' | tail -1 || true; }

case "${1:-start}" in
  stop)
    "${C[@]}" stop
    ;;
  seed)
    owner=$(grep '^CLASSIO_OWNER_PASSWORD=' "$ENV_FILE" | cut -d= -f2)
    password=$(openssl rand -hex 8)  # 16 caractères faciles à taper sur un téléphone
    "${C[@]}" run --rm -e DATABASE_URL="postgres://classio_owner:$owner@postgres:5432/classio" \
      backend python manage.py seed_demo --password "$password"
    echo "Mot de passe de tous les comptes de démonstration : $password  (notez-le)"
    ;;
  start)
    echo "▸ Ouverture du tunnel…"
    # Connexion lente : la demande d'adresse à Cloudflare échoue parfois, on réessaie.
    address=""
    for attempt in 1 2 3; do
      "${C[@]}" up -d --force-recreate tunnel
      for _ in $(seq 60); do address=$(url); [ -n "$address" ] && break 2; sleep 1; done
      echo "  pas de réponse de Cloudflare (essai $attempt sur 3)…"
    done
    [ -n "$address" ] || { echo "Le tunnel ne répond pas : ${C[*]} logs tunnel" >&2; exit 1; }
    host=${address#https://}
    sed -i "s/^DOMAIN=.*/DOMAIN=$host/; s/^BASE_DOMAIN=.*/BASE_DOMAIN=$host/" "$ENV_FILE"
    echo "▸ Démarrage de Classio (la première fois : 10 minutes environ)…"
    # Docker Hub coupe parfois la connexion pendant la construction : trois essais.
    for attempt in 1 2 3; do
      "${C[@]}" up -d --build && break
      [ "$attempt" -lt 3 ] || { echo "Construction impossible : vérifiez la connexion, puis relancez." >&2; exit 1; }
      echo "  connexion coupée, nouvel essai dans 10 secondes…"; sleep 10
    done
    for _ in $(seq 90); do curl -sf -o /dev/null "$address" && break; sleep 2; done
    cat <<INFO

  Classio est en ligne : $address

  À ouvrir sur un téléphone (Chrome), puis « Installer Classio ».
  Cet ordinateur doit rester allumé et connecté. L'adresse change à chaque lancement.
  Écoles fictives : infra/tunnel.sh seed   ·   Arrêter : infra/tunnel.sh stop
INFO
    ;;
  *) echo "Usage : infra/tunnel.sh [start|seed|stop]" >&2; exit 1 ;;
esac
