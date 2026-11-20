# Classio : serveur de test gratuit

Pour mettre Classio en ligne et le faire essayer (démonstrations aux écoles, tests sur de vrais
téléphones), sans rien payer.

Trois solutions, **données fictives uniquement** dans tous les cas :

| | C. Render (recommandé) | A. Sur votre ordinateur | B. Serveur Oracle Cloud |
|---|---|---|---|
| Coût | 0 F | 0 F, ni carte ni compte | 0 F, carte bancaire exigée |
| Disponible | jour et nuit, ordinateur éteint | tant que l'ordinateur est allumé | jour et nuit |
| Adresse | fixe : `https://classio-test.onrender.com` | nouvelle à chaque lancement | fixe : `classio-test.duckdns.org` |
| Limites | s'endort après 15 min sans visite (réveil en ~1 min) ; base gratuite supprimée après 30 jours | | machine reprise si inutilisée 7 jours |

> Les données de test ne doivent jamais être de vraies données d'élèves ou de parents : Render,
> le tunnel Cloudflare et les serveurs Oracle sont hors CEDEAO. Les vraies écoles attendront
> l'autorisation de l'APDP ([09-courriel-apdp.md](09-courriel-apdp.md)) et le serveur choisi
> ([05-deploiement.md](05-deploiement.md)).

## C. Render : en ligne jour et nuit, comme en production

Ce qui est créé, à partir de [render.yaml](../render.yaml) : le site (Caddy et Django dans un
seul conteneur, [infra/render/](../infra/render/)), une base PostgreSQL 17 et un Redis, tous
gratuits, à Francfort (la région Render la plus proche du Bénin). Comme en production, la base
a deux rôles : l'API se connecte avec `classio_app`, soumis à l'isolation entre écoles (RLS).

### C1. Mettre en ligne (une fois, 20 minutes)

1. Le code doit être sur GitHub, branche `feat/refonte-django-react` (commit et push).
2. Créer un compte sur [render.com](https://render.com) avec « Sign in with GitHub », et
   autoriser Render à lire le dépôt `classio-next`.
3. **New → Blueprint**, choisir le dépôt et la branche `feat/refonte-django-react`. Render lit
   `render.yaml` et affiche les trois éléments à créer.
4. Il demande `DEMO_PASSWORD` : un mot de passe d'au moins 16 caractères pour les comptes de
   démonstration (par exemple le résultat de `openssl rand -hex 8`). **Notez-le.**
5. **Apply.** La première construction prend 10 à 15 minutes. Le site est ensuite à l'adresse
   affichée par Render (`https://classio-test.onrender.com` si le nom est libre).

Les écoles fictives sont chargées au premier démarrage. Le code du parent à activer
(01 97 00 00 02) est tiré au hasard : il est dans les journaux du service (**Logs**, ligne
« Code d'accès du parent à activer »).

### C2. Mettre à jour

Chaque `git push` sur la branche redéploie le site tout seul. Les téléphones qui ont installé
Classio affichent « Une nouvelle version est disponible ».

### C3. Limites de l'offre gratuite

- **Mise en veille** : sans visite pendant 15 minutes, le site s'endort ; la visite suivante
  attend environ une minute. Avant une démonstration, ouvrez le site une minute plus tôt.
- **Base supprimée après 30 jours** (14 jours de grâce ensuite). Pour repartir : dans Render,
  supprimer la base `classio-test-db`, puis **Blueprint → Sync** la recrée ; le premier
  démarrage recharge les écoles fictives.
- **Pas de worker Celery** : les bulletins PDF sont produits dans la requête (environ
  4 secondes pour un bulletin ; une classe entière peut prendre plus longtemps). La purge
  quotidienne des documents expirés ne tourne pas.
- Redis gratuit sans sauvegarde : un redémarrage déconnecte les utilisateurs.
- 512 Mo de mémoire : Classio en utilise environ 200.

### C4. Si le démarrage s'arrête sur « n'a pas l'attribut BYPASSRLS »

Le rôle propriétaire doit pouvoir contourner l'isolation pour créer les écoles. Si l'utilisateur
de la base Render ne l'a pas, prenez une base gratuite chez [Neon](https://neon.com), qui
n'expire pas : créez un projet (région Francfort), copiez sa chaîne de connexion, puis dans
Render, **classio-test → Environment**, remplacez `DATABASE_ADMIN_URL` par cette chaîne.
Si Neon refuse aussi, dites-le-moi : il faudra adapter les migrations.

## A. Sur votre ordinateur, par un tunnel Cloudflare

Il faut Docker sur l'ordinateur (déjà installé sur le poste de développement). Depuis le dossier
du projet :

```bash
infra/tunnel.sh          # lance Classio et affiche son adresse https://….trycloudflare.com
infra/tunnel.sh seed     # une seule fois : écoles fictives, affiche le mot de passe des comptes
infra/tunnel.sh stop     # arrête tout ; les données sont gardées pour le prochain lancement
```

- La première fois, la construction prend une dizaine de minutes. Si la connexion coupe, le
  script réessaie tout seul.
- **L'adresse change à chaque `infra/tunnel.sh`.** Une application installée sur un téléphone
  reste liée à l'ancienne adresse : il faut rouvrir la nouvelle et réinstaller. Pour une
  démonstration, lancez une fois le matin et n'y touchez plus.
- Les comptes de démonstration ont les mêmes numéros que sur le poste de développement (voir
  `./dev.sh`), avec le mot de passe affiché par `seed`. Le parent à activer reçoit un code tiré
  au hasard, affiché lui aussi.
- Rien n'est ouvert sur l'ordinateur : tout passe par le tunnel, qui chiffre en HTTPS. Le tunnel
  sans compte n'a aucune garantie de disponibilité : c'est pour des tests, pas pour une école.
- Cloudflare transmet l'adresse réelle de chaque visiteur : la limite d'essais de connexion
  s'applique à chacun, pas à tous les testeurs ensemble.

## B. Serveur Oracle Cloud « Always Free » et adresse DuckDNS

| Besoin | Solution gratuite |
|---|---|
| Serveur | Oracle Cloud « Always Free » : une machine ARM gratuite sans limite de durée |
| Adresse web | DuckDNS : `classio-test.duckdns.org` |
| HTTPS | Let's Encrypt, obtenu automatiquement par Caddy |

Limites à connaître :
- Oracle demande une **carte bancaire** à l'inscription et bloque une petite somme (environ
  1 €) pour la vérifier ; elle est ensuite libérée. Certaines cartes prépayées sont refusées.
- En 2026, Oracle a réduit l'offre gratuite (environ 2 processeurs et 12 Go de mémoire au lieu
  de 4 et 24). C'est largement suffisant pour Classio.
- Une machine gratuite **inutilisée pendant 7 jours** (processeur, réseau et mémoire sous 20 %)
  peut être reprise par Oracle. Pour l'éviter : passer le compte en « Pay As You Go » (on reste
  gratuit tant qu'on ne dépasse pas l'offre), ou s'en servir régulièrement.
- Si la machine est perdue, on la recrée en 20 minutes avec ce guide : rien n'y est précieux.

### B1. Créer la machine (console Oracle, 15 minutes)

1. Créer un compte sur [cloud.oracle.com](https://cloud.oracle.com). Comme région d'origine,
   choisir la plus proche disponible (elle ne peut plus être changée ensuite).
2. **Compute → Instances → Create instance** :
   - Image : **Ubuntu 24.04** (pas « Minimal »).
   - Shape : **Ampere, VM.Standard.A1.Flex**, 2 OCPU, 12 Go de mémoire.
   - SSH : « Generate a key pair », **télécharger la clé privée** et la garder précieusement.
   - Si Oracle répond « Out of capacity », réessayer plus tard ou dans un autre
     « availability domain ».
3. Noter l'**adresse IP publique** de la machine.
4. Ouvrir les ports web : sur la page de l'instance, **Subnet → Security List → Add Ingress
   Rules** : source `0.0.0.0/0`, TCP, ports `80` et `443` (une règle chacun).

### B2. Obtenir l'adresse web (DuckDNS, 2 minutes)

1. Se connecter sur [duckdns.org](https://www.duckdns.org) (compte Google ou GitHub).
2. Créer le sous-domaine `classio-test` (ou un autre nom libre).
3. Dans le champ « current ip », mettre l'**adresse IP publique d'Oracle**, puis « update ip ».

Vérifier depuis votre ordinateur : `ping classio-test.duckdns.org` doit afficher cette adresse.

### B3. Installer Classio sur la machine (15 minutes)

Depuis votre ordinateur :

```bash
chmod 600 ~/Téléchargements/ssh-key-*.key
ssh -i ~/Téléchargements/ssh-key-*.key ubuntu@<adresse IP>
```

Puis, sur la machine :

```bash
sudo git clone https://github.com/Richter07/classio-next /opt/classio
sudo chown -R ubuntu /opt/classio && cd /opt/classio
git switch feat/refonte-django-react
sudo infra/server-setup.sh          # Docker, pare-feu, sauvegardes planifiées
sudo usermod -aG docker ubuntu && exit
```

Le dépôt est privé ? Il faut d'abord un « deploy key » GitHub en lecture seule, ou un jeton.

Reconnectez-vous (pour que le groupe docker soit pris en compte), puis :

```bash
cd /opt/classio
infra/make-env.sh classio-test.duckdns.org
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d --build
```

La première construction prend 10 à 15 minutes. Ensuite, ouvrez
`https://classio-test.duckdns.org` : le cadenas doit apparaître.

### B4. Charger les écoles fictives

```bash
DEMO_PASSWORD="$(openssl rand -hex 8)"; echo "Mot de passe de démonstration : $DEMO_PASSWORD"
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod run --rm \
  -e DATABASE_URL="postgres://classio_owner:$(grep ^CLASSIO_OWNER_PASSWORD infra/.env.prod | cut -d= -f2)@postgres:5432/classio" \
  backend python manage.py seed_demo --password "$DEMO_PASSWORD"
```

**Notez le mot de passe affiché** : c'est celui de tous les comptes de démonstration (mêmes
numéros que sur le poste de développement, voir `./dev.sh`). Le code du parent à activer est
tiré au hasard et affiché à la fin. Sur un serveur public, le mot de passe `classio-demo-2026`
du dépôt est refusé : n'importe qui pourrait ouvrir le compte super-admin.

Pour une démonstration à une école, on peut aussi créer une école vierge
(`create_school`, voir [05-deploiement.md](05-deploiement.md) § 4) et la configurer devant elle.

### B5. Mettre à jour après une modification

```bash
cd /opt/classio && git pull
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d --build
```

Les téléphones qui ont installé Classio affichent « Une nouvelle version est disponible ».

### B6. Si quelque chose ne va pas

| Symptôme | Vérification |
|---|---|
| La page ne s'ouvre pas du tout | Ports 80 et 443 ouverts dans la Security List d'Oracle (B1, point 4) ; `ping` donne la bonne IP |
| Erreur de certificat | `docker compose … logs caddy` : DuckDNS doit pointer vers la machine **avant** le premier lancement |
| « 502 » | `docker compose … ps` puis `logs backend` |
| Machine disparue | Reprise par Oracle pour inactivité : recommencer en B1, ou passer en « Pay As You Go » |
