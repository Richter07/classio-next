# Classio : déploiement sur un serveur

Pour un VPS sous Ubuntu, avec Docker. Un seul domaine pour le pilote (ex. `app.classio.bj`) :
le personnel saisit le code de son école à la connexion.

Serveur de test gratuit, données fictives seulement : voir [10-deploiement-gratuit.md](10-deploiement-gratuit.md).

## 1. Préparer le serveur

1. Un VPS d'au moins 2 vCPU et 4 Go de mémoire (la génération des PDF en consomme), Ubuntu 24.04,
   **situé dans un pays membre de la CEDEAO**. Hors CEDEAO, il faut l'autorisation préalable de
   l'APDP (Code du numérique, art. 391 et 407 ; voir [06-dossier-juridique.md](06-dossier-juridique.md)).
2. Un nom de domaine, et un enregistrement DNS `A` de `app.<domaine>` vers l'adresse IP du
   serveur. Le HTTPS est indispensable : sans lui, l'application ne s'installe pas sur les
   téléphones et la connexion est refusée (cookies sécurisés).
3. Connecté en SSH avec une clé, lancez le script de préparation :

```bash
git clone <dépôt> /opt/classio && cd /opt/classio && git switch feat/refonte-django-react
sudo infra/server-setup.sh
```

Il installe Docker, rclone, le pare-feu (SSH, 80, 443 seulement), les mises à jour de sécurité
automatiques, crée la phrase de passe des sauvegardes et planifie sauvegarde et test de
restauration. **Copiez `/etc/classio/backup.pass` hors du serveur** : sans elle, les
sauvegardes sont illisibles.

## 2. Configurer

```bash
cd /opt/classio
cp infra/.env.prod.example infra/.env.prod
chmod 600 infra/.env.prod
# Remplir infra/.env.prod : un secret différent par ligne, `openssl rand -hex 32`
```

`infra/.env.prod` ne doit jamais être versionné (il est ignoré par git).

## 3. Lancer

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d --build
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod ps
```

Caddy obtient le certificat HTTPS tout seul au premier accès. Les migrations s'exécutent à chaque
démarrage, avec le rôle propriétaire, avant que l'API ne démarre.

## 4. Créer la première école

```bash
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod exec backend \
  python manage.py create_school --name "CEG Les Pylônes" --slug ceg-les-pylones \
  --director-name "M. HOUNGBEDJI Pascal" --director-phone "01 97 00 00 10"
```

La commande affiche le code d'accès du directeur : à lui remettre en main propre. Il active son
compte sur `https://app.classio.bj/activation`, puis ajoute son personnel depuis l'écran
« Personnel ».

Compte super-admin (admin Django, `/admin/`) :

```bash
docker compose ... exec backend python manage.py createsuperuser
```

## 5. Sauvegardes

Planifiées par `server-setup.sh` : chaque nuit à 2 h 15, test de restauration le 1er du mois,
journal dans `/var/log/classio-backup.log`. Pour la copie hors du serveur :

```bash
sudo rclone config                     # second fournisseur, lui aussi dans la CEDEAO
sudo nano /etc/cron.d/classio          # décommenter RCLONE_REMOTE=<remote>:classio
```

Les fichiers copiés sont déjà chiffrés : le second fournisseur ne voit jamais les données.

## 6. Avant d'ouvrir une école

La direction termine la configuration dans l'écran « Configuration » (l'accueil le lui rappelle) :
découpage de l'année, niveaux, classes, matières et coefficients, attribution des enseignants,
formule de calcul. Le secrétariat importe ensuite les élèves et imprime les lettres d'accès.

## 7. Installer l'application sur les téléphones

Classio n'est pas sur le Play Store : c'est une application web installable. Au premier
passage, chaque parent ou enseignant voit une carte « Installer Classio sur ce téléphone »
adaptée à son appareil (aussi dans « Mon compte »). La lettre d'accès l'annonce, et met en garde
contre toute application « Classio » sur les stores.

Lors de la réunion de rentrée, montrez-le une fois sur un téléphone : c'est ce qui fait le plus
pour l'adoption.

## 8. Mettre à jour

```bash
cd /opt/classio && git pull
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod up -d --build
```

Faites une sauvegarde juste avant chaque mise à jour (`sudo /opt/classio/infra/backup.sh`).

Les utilisateurs voient alors « Une nouvelle version de Classio est disponible » et mettent à
jour d'un geste, quand ils le veulent : un enseignant en pleine saisie n'est jamais interrompu.
