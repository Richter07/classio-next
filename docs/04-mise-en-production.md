# Classio : ce qui manque avant la mise en production

État au 12 novembre 2026 (fin de journée), branche `feat/refonte-django-react`. « Production » désigne le pilote avec
2 ou 3 écoles réelles (phase 2 du cahier des charges).

Légende : **B** bloquant, **I** important (avant d'élargir le pilote), **V2** peut attendre.
✅ fait et testé · ◐ préparé, une action de votre part reste · ⬜ reste à faire.

## 1. Fonctionnel

| | | Sujet | État |
|---|---|---|---|
| B | ✅ | Connexion des parents sans SMS | Mot de passe + session de 30 jours ; codes d'accès et lettres imprimées par l'école ; consentement à la première connexion. |
| B | ✅ | Création d'une école et de son directeur | `python manage.py create_school` (super-admin), qui affiche le code d'accès du directeur. |
| B | ✅ | Comptes du personnel | Écran « Personnel » : ajout, code d'accès, mot de passe oublié, désactivation. |
| B | ✅ | Configuration par la direction | Écran « Configuration » : périodes (trimestres ou semestres en un clic, clôture), niveaux, classes, matières, coefficients par niveau, attribution des enseignants, règles de calcul. Alerte sur l'accueil tant que l'école n'est pas prête. |
| B | ◐ | **Formule de calcul** | Par défaut, la formule béninoise : (moyenne des interrogations + devoir 1 + devoir 2) / 3 ; l'absence compte 0. Moyenne pondérée au choix. **À confirmer sur 2 ou 3 vrais bulletins.** |
| B | ✅ | Bulletins publiés par la direction | Les parents ne voient moyenne générale, rang et bulletin qu'après publication par la direction, classe par classe ; publication impossible tant qu'une évaluation n'est pas publiée ; bulletin figé ; retrait possible. |
| B | ✅ | Bulletin au format béninois | Moy. interro, devoir 1, devoir 2 (compositions s'il y en a), moyenne, coefficient, moyenne coefficientée, rang et appréciation par matière ; « Abs » affiché. |
| B | ✅ | Saisie sur téléphone | Bouton « Abs » (le clavier numérique n'a pas de lettres), « 0 aux vides », envoi impossible tant qu'un élève n'a pas de note. Périodes closes absentes de la création d'évaluation. |
| I | ✅ | Période close | Plus de saisie ni d'envoi sur une période close. |
| I | ⬜ | Changement de numéro d'un parent | |
| I | ⬜ | Accès support tracé, écran super-admin | Suspension via l'admin Django en attendant. |
| V2 | ⬜ | Passage d'année, notifications push, SMS/WhatsApp, absences, paiement | |

## 2. Technique et sécurité

| | | Sujet | État |
|---|---|---|---|
| B | ✅ | Adresse IP réelle derrière le proxy | Caddy fixe `X-Forwarded-For`, Django lit la valeur via `TRUSTED_PROXY_COUNT=1`. Testé. |
| B | ✅ | PDF longs en tâche de fond | Bulletins d'une classe et lettres d'accès : Celery, gardés une heure, réservés à leur auteur. |
| B | ✅ | Journaux sans données personnelles | Plus aucun numéro ni contenu de notification dans les journaux hors développement. |
| B | ✅ | Déploiement | `infra/docker-compose.prod.yml` : Caddy (HTTPS automatique), API, worker, planificateur, PostgreSQL, Redis persistant. Voir [05-deploiement.md](05-deploiement.md). |
| B | ✅ | Sauvegardes | `infra/backup.sh` (chiffrée AES-256) et `infra/restore-test.sh`, testés sur une vraie restauration. |
| B | ⬜ | **Serveur et domaine** | À louer et réserver par vous. `infra/server-setup.sh` prépare ensuite le serveur en une commande. |
| B | ◐ | **Copie des sauvegardes hors du serveur** | Prête dans `backup.sh` (rclone) ; il reste à ouvrir un espace chez un second fournisseur et à lancer `rclone config`. |
| I | ✅ | Intégration continue | `.github/workflows/ci.yml` : lint, migrations, tests, audit des dépendances, build ; actions épinglées par empreinte. Pas encore exécutée sur GitHub. |
| I | ✅ | Validation rapide en milieu d'année | États des évaluations calculés en une requête SQL. |
| I | ✅ | Page d'erreur | En français, avec rechargement. Indicateur de chargement entre les pages. |
| I | ✅ | `ALLOWED_HOSTS=*` refusé en production | Testé. |
| I | ✅ | Purges | Tâche quotidienne : codes expirés, notifications de plus de 400 jours, imports non appliqués. |
| I | ✅ | Parcours de bout en bout dans le dépôt | `npm run e2e`, 28 étapes. |
| I | ✅ | Démarrage à froid des PDF | Préchauffage de WeasyPrint au lancement de gunicorn, HarfBuzz-subset dans l'image. |
| I | ✅ | En-têtes de sécurité | HSTS, CSP stricte pour l'application, `nosniff`, `frame-ancestors 'none'`. |
| I | ⬜ | Supervision | Compte Sentry (`SENTRY_DSN`) et alerte de disponibilité externe. |
| I | ⬜ | Contrôles dans l'école par la base | « Parent : ses enfants » et « enseignant : ses classes » sont appliqués et testés dans l'API, pas encore par le RLS. |
| I | ⬜ | Audit des dépendances Python | `pip-audit` n'a pas pu joindre PyPI pendant les sessions ; la CI le fera. |

## 3. Conformité (données de mineurs)

| | | Sujet | État |
|---|---|---|---|
| B | ✅ | Information des parents | Base légale : mission de l'école ou contrat de scolarité (art. 389), pas le consentement. Case « J'ai lu la politique de confidentialité », date et version enregistrées. |
| B | ◐ | **Conformité** | Avis établi d'après le Code du numérique ([06](06-dossier-juridique.md)), contrat de sous-traitance ([07](07-contrat-sous-traitance.md)), conditions d'utilisation ([08](08-conditions-utilisation.md)), politique de confidentialité définitive dans l'application. **Restent de votre côté** : hébergement dans la CEDEAO, adresse de contact, signature du contrat et déclaration APDP par chaque école. |
| I | ⬜ | Droit d'accès | Export des données d'un élève ou d'un parent sur demande. |
| I | ⬜ | Effacement un an après le départ d'un élève | Archive remise à l'école puis effacement. À livrer avant septembre 2027. |
| I | ⬜ | Journal des actions sensibles hors notes | Imports, émission de codes, connexions du personnel. Les codes gardent déjà leur émetteur. |

## 4. L'ancienne v1 (branche `main`)

Si elle est en ligne : la connexion parent accepte `%` comme code élève. À corriger ou à arrêter.

## Ce qu'il reste avant d'ouvrir le pilote (actions de votre côté)

1. **Bulletins réels** : obtenir 2 ou 3 bulletins d'écoles, saisir leurs notes dans Classio et
   comparer moyennes, rangs et appréciations. Choisir la formule qui correspond.
2. **Serveur et domaine** : louer un VPS (2 vCPU, 4 Go), réserver le domaine, pointer le DNS,
   puis suivre [05-deploiement.md](05-deploiement.md).
3. **Second fournisseur pour les sauvegardes**, et copie de la phrase de passe hors du serveur.
4. **Conformité** : suivre « Avant le lancement » de [06-dossier-juridique.md](06-dossier-juridique.md)
   (hébergeur dans la CEDEAO, adresse de contact, contrat signé, déclaration APDP de chaque école).
5. **Supervision** : Sentry seulement après autorisation de l'APDP (serveurs hors CEDEAO) ; sinon, les
   journaux du serveur.
