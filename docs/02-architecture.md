# Classio : architecture et environnement

## 1. Organisation du dépôt

```
classio-next/                    Branche feat/refonte-django-react
├── backend/                     API Django, indépendante du frontend
│   ├── manage.py
│   ├── pyproject.toml           Configuration pytest et ruff
│   ├── .env.example
│   ├── requirements/
│   │   ├── base.in              Dépendances directes de production
│   │   ├── base.txt             Verrou avec hachages (généré)
│   │   ├── dev.in
│   │   └── dev.txt              Verrou avec hachages (généré)
│   ├── config/                  settings, urls, wsgi, celery
│   ├── apps/
│   │   ├── tenancy/             École, contexte RLS, middleware, abonnement, accès support
│   │   │   ├── context.py       tenant_context() : point d'entrée unique vers les données
│   │   │   ├── middleware.py    Sous-domaine vers école, contrôle d'appartenance
│   │   │   └── rls.py           SQL : politiques, FK composites, journal d'audit
│   │   ├── accounts/            User global, Membership, codes d'accès, comptes du personnel
│   │   ├── academics/           Années, périodes, niveaux, classes, matières, coefficients
│   │   ├── students/            Élèves, inscriptions, parents, imports
│   │   ├── grades/              Évaluations, notes, journal, bulletins
│   │   ├── notifications/       Nouveautés des parents (dans l'application, push à venir)
│   │   └── documents/           PDF longs en tâche de fond (Celery), purges
│   └── tests/                   Isolation prouvée sur un vrai PostgreSQL
├── frontend/                    PWA React, indépendante du backend
│   ├── package.json
│   ├── vite.config.ts           PWA, proxy /api en développement
│   ├── public/icons/
│   └── src/
│       ├── main.tsx
│       ├── app/                 Routes et fournisseurs globaux
│       ├── features/            Un dossier par espace, chargé à la demande
│       │   ├── auth/            Connexion, première connexion, confidentialité
│       │   ├── parent/          Enfants, notes, bulletins
│       │   ├── teacher/         Grille de saisie
│       │   ├── school-admin/    Direction et secrétariat
│       │   └── platform/        Super-admin
│       └── shared/
│           ├── api/             Client HTTP
│           ├── offline/         IndexedDB (Dexie) et file de synchronisation
│           ├── styles/          tokens.css
│           └── ui/              Composants communs
├── infra/
│   ├── docker-compose.dev.yml   PostgreSQL 17 et Redis 7, sur la boucle locale
│   ├── docker-compose.prod.yml  Production : Caddy, API, worker, planificateur, base, Redis
│   ├── caddy/                   Image web (application construite + HTTPS)
│   ├── backup.sh                Sauvegarde chiffrée quotidienne
│   └── restore-test.sh          Test de restauration
│   └── postgres/init/           Création des deux rôles PostgreSQL
└── docs/
```

La seule frontière entre `backend/` et `frontend/` est l'API HTTP `/api/v1/`. Aucun import ne la
traverse, chacun a ses dépendances, son `.env` et se déploie seul.

La v1 Next.js reste à la racine pour l'instant, le temps de décider de son sort (voir section 7).

## 2. Installation

Raccourci : `./dev.sh` fait tout ce qui suit et lance les deux serveurs (voir
[03-guide-de-test.md](03-guide-de-test.md)). Le détail, pour comprendre ou dépanner :

Prérequis : Python 3.12, Node 22, Docker. WeasyPrint s'appuie sur Pango : si `import weasyprint`
échoue sur votre poste, `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0`.
Ces bibliothèques devront figurer dans l'image Docker de production.

```bash
# Services : PostgreSQL et Redis, dans des conteneurs propres au projet
docker compose -f infra/docker-compose.dev.yml up -d --wait

# Backend : tout reste dans backend/.venv
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements/dev.txt
cp .env.example .env

# Migrations avec le rôle propriétaire, jamais avec le rôle applicatif
DATABASE_URL=$(grep ^MIGRATION_DATABASE_URL .env | cut -d= -f2-) python manage.py migrate

# Tests : également avec le rôle propriétaire, qui peut créer la base de test
DATABASE_URL=$(grep ^MIGRATION_DATABASE_URL .env | cut -d= -f2-) pytest

python manage.py runserver

# Frontend : tout reste dans frontend/node_modules
cd ../frontend
npm ci
npm run dev
```

En local, ouvrir `http://ecole-x.classio.localhost:5173` : les navigateurs résolvent `*.localhost`
d'eux-mêmes, ce qui permet de tester les sous-domaines sans toucher au système.

Ajouter une dépendance Python : l'écrire dans `requirements/base.in`, puis
`pip-compile --generate-hashes --strip-extras -o requirements/base.txt requirements/base.in`,
et de même pour `dev`.

## 3. Modèle de données

| Portée | Tables | Isolation |
|---|---|---|
| Globale | `School`, `User`, `AccessCode`, `PushSubscription` | Pas de RLS : aucune donnée pédagogique, aucun nom de personne |
| Par école | Tout le reste | `school_id` + RLS + FK composites |

Tous les identifiants sont des UUID : ils ne s'énumèrent pas, et le téléphone peut en générer hors ligne.

**Pourquoi `User` est global et sans nom.** Parents et enseignants vacataires travaillent avec
plusieurs écoles sous un seul numéro. Le nom affiché vit dans `Guardian` et `Membership`, propres à
chaque école, qui ne voient donc jamais ce qu'une autre école a saisi.

**Statuts de note :** `DRAFT` → `SUBMITTED` → `VALIDATED` → `PUBLISHED`.

**Bulletin :** `ReportCard.snapshot` fige les chiffres publiés. Changer un coefficient plus tard ne
réécrit pas un bulletin déjà remis aux familles.

## 4. Isolation entre écoles

Trois couches, parce que chacune seule a un trou :

1. **RLS activé et forcé** sur chaque table d'école. Sans contexte, aucune ligne.
2. **Rôle d'exécution `classio_app` sans `BYPASSRLS`.** Un superutilisateur ou le propriétaire d'une
   table contournerait les politiques : un RLS mal branché ne protège rien, sans le moindre message
   d'erreur. Les migrations tournent sous `classio_owner`, l'application jamais.
3. **Clés étrangères composites `(school_id, x_id)`.** PostgreSQL vérifie les clés étrangères en
   contournant le RLS : sans elles, une note de l'école A pourrait référencer un élève de l'école B.

```python
with tenant_context(school_id, user_id):    # ouvre une transaction, pose le contexte
    Student.objects.all()                   # seulement les élèves de cette école
```

- **Requêtes HTTP :** `TenantMiddleware` déduit l'école du sous-domaine, vérifie que l'utilisateur en
  fait partie, puis enveloppe la requête. Une réponse 4xx ou 5xx annule la transaction.
- **Tâches Celery et commandes :** elles doivent ouvrir `tenant_context` elles-mêmes. Sinon elles
  voient une base vide : l'erreur est visible, jamais une fuite.
- **Parent multi-écoles :** sur `app.<domaine>`, seul `user_id` est posé. La politique `self_read`
  lui montre ses `Guardian`, puis la vue ouvre un contexte par école.
- **Super-admin :** le contexte plateforme donne accès aux abonnements et aux accès support, jamais
  aux notes. Pour intervenir, il lui faut un `SupportGrant` approuvé par l'école.
- **Pool de connexions :** `set_config(..., true)` est lié à la transaction, donc compatible avec le
  mode transaction de PgBouncer.

Toute nouvelle table d'école doit passer par `rls.harden_model` et `rls.add_composite_foreign_keys`
dans sa migration. `tests/test_isolation.py` interroge le catalogue PostgreSQL et échoue sinon.

**Limite assumée :** le RLS protège d'un filtre oublié, pas d'une injection SQL ni d'un serveur
compromis, car le rôle applicatif peut lui-même poser `app.school_id`. Les restrictions à l'intérieur
d'une école (enseignant limité à ses classes, parent à ses enfants, parent ne voyant que les notes
publiées) sont aujourd'hui du ressort de l'API et devront être testées avec elle.

## 5. Journal d'audit

Le trigger `grades_audit_change` écrit dans `GradeAudit` à chaque changement d'une note sortie du
brouillon : ancienne et nouvelle valeur, statut, auteur, motif. Il s'exécute dans la base : ni un
oubli dans une vue ni une requête SQL brute n'y échappent. Le rôle applicatif ne peut que lire le
journal, et un second trigger refuse modification et suppression, propriétaire compris.

Les modifications d'un brouillon ne sont pas journalisées (voir section 7).

## 6. Dépendances

**Backend**

| Paquet | Rôle |
|---|---|
| Django 5.2 LTS, Django REST Framework, drf-spectacular | API et documentation OpenAPI |
| psycopg 3 | Pilote PostgreSQL |
| django-environ | Configuration par variables d'environnement |
| argon2-cffi | Hachage des mots de passe du personnel |
| celery, redis, django-redis | Tâches asynchrones, cache, sessions |
| openpyxl | Lecture et écriture Excel |
| phonenumbers | Validation des numéros, ancien format béninois compris |
| weasyprint | Bulletins PDF |
| django-storages, boto3 | Stockage objet compatible S3 |
| sentry-sdk | Supervision des erreurs, sans données personnelles |
| gunicorn | Serveur de production |
| pytest, pytest-django, ruff, pip-tools, pip-audit | Développement et CI |

**Frontend**

| Paquet | Rôle |
|---|---|
| react, react-dom, react-router-dom | Interface et routes |
| @tanstack/react-query | Cache des données serveur |
| dexie | IndexedDB, pour la saisie hors ligne |
| vite, vite-plugin-pwa, typescript | Build, service worker, manifeste |

Aucune bibliothèque de composants ni de tableur : c'est le poids téléchargé qui est en jeu.

## 7. Décisions à prendre

| Sujet | État actuel | Question |
|---|---|---|
| Domaine | `DOMAIN` et `BASE_DOMAIN` configurables | Le cahier dit `notebenin.bj`, le produit s'appelle Classio. Lequel réserver ? Pilote sur un seul domaine (code école à la connexion) ; sous-domaines plus tard. |
| Calcul de la moyenne de matière | `Assessment.weight` | La formule exacte (interrogations, devoirs, composition) doit venir de bulletins réels. Non codée à ce stade. |
| Connexion des parents | Mot de passe, session de 30 jours, codes d'accès remis par l'école (décidé le 12/11/2026) | SMS ou WhatsApp quand le budget le permettra |
| Journal des brouillons | Non journalisés | Le §8 dit « toute modification » : à confirmer, sinon chaque frappe crée une ligne. |
| v1 Next.js | Conservée | Supprimer de la branche, ou migrer ses données s'il existe des écoles réelles ? |
| Changement de numéro | Non traité | Le numéro est partagé entre écoles : qui peut le changer, et avec quelle preuve ? |
