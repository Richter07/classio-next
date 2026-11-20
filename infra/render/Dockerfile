# Serveur de test sur Render (offre gratuite) : tout dans un seul conteneur, car l'offre gratuite
# n'a qu'un service web. Caddy sert l'application React et relaie l'API vers Gunicorn.
# Contexte de construction : la racine du dépôt (voir render.yaml).
FROM node:22-alpine AS front
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine AS caddy

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    XDG_CACHE_HOME=/tmp/cache XDG_DATA_HOME=/tmp/caddy XDG_CONFIG_HOME=/tmp/caddy
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fontconfig fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements/base.txt requirements/base.txt
RUN pip install --require-hashes -r requirements/base.txt
COPY backend/ ./
COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy
COPY infra/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=front /app/dist /srv
COPY infra/render/start.sh /start.sh
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin classio \
    && mkdir -p /app/staticfiles && chown classio /app/staticfiles
USER classio
CMD ["/start.sh"]
