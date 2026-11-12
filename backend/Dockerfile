# Image unique du backend : API (gunicorn), worker et planificateur Celery.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Bibliothèques de WeasyPrint. HarfBuzz-subset rend le découpage des polices bien plus rapide.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fontconfig fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements/base.txt requirements/base.txt
# Hachages vérifiés : un paquet modifié sur PyPI ferait échouer la construction.
RUN pip install --require-hashes -r requirements/base.txt

COPY . .
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin classio \
    && mkdir -p /app/staticfiles && chown classio /app/staticfiles
USER classio

EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "-c", "gunicorn.conf.py"]
