#!/bin/sh
# Deux rôles distincts : c'est ce qui rend le RLS réellement contraignant.
#  - classio_owner : possède les tables, joue les migrations, jamais utilisé par l'application.
#  - classio_app   : rôle d'exécution, sans BYPASSRLS, soumis à toutes les politiques.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" \
  -v owner_pw="$CLASSIO_OWNER_PASSWORD" -v app_pw="$CLASSIO_APP_PASSWORD" <<'SQL'
CREATE ROLE classio_app LOGIN PASSWORD :'app_pw'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE classio_owner LOGIN PASSWORD :'owner_pw'
  NOSUPERUSER CREATEDB NOCREATEROLE BYPASSRLS;
GRANT classio_app TO classio_owner;
CREATE DATABASE classio OWNER classio_owner;
REVOKE ALL ON DATABASE classio FROM PUBLIC;
GRANT CONNECT ON DATABASE classio TO classio_app;
SQL
