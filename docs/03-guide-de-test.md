# Classio : guide de test

## Lancer l'application

```bash
./dev.sh          # base, migrations, données de démo, API et application
./dev.sh reset    # repartir de données de démonstration neuves
./dev.sh test     # tests du backend
```

Docker doit être démarré. Les conteneurs PostgreSQL et Redis redémarrent désormais tout seuls
avec Docker (`restart: unless-stopped`).

| Où | Adresse |
|---|---|
| Parents | http://localhost:5173 |
| Personnel | http://localhost:5173/ecole/connexion |
| Téléphone (même Wi-Fi) | http://IP-DU-PC:5173 (affichée au lancement) |
| Admin Django | http://localhost:8000/admin/ |

Après une mise à jour du code, rechargez la page (Ctrl+Maj+R sur ordinateur) : un onglet resté
ouvert garde l'ancienne version. Une adresse inconnue affiche désormais « Page introuvable » avec
un bouton pour recharger.

Sur téléphone, en HTTP sur le réseau local, l'installation de l'application (PWA) n'est pas
proposée : les navigateurs l'exigent en HTTPS. Tout le reste fonctionne.

## Comptes de démonstration

Mot de passe de tous les comptes : `classio-demo-2026`. Code école : `ceg-les-pylones`.

| Rôle | Numéro | À tester |
|---|---|---|
| Parent, 2 enfants dans 2 écoles | 01 97 00 00 01 | Koffi : notes, bulletin pas encore publié. Sèna (Saint-Michel) : bulletin publié, rang, PDF |
| Parent sans compte | 01 97 00 00 02 | « Première connexion » avec le code `PARE-NT26` |
| Direction | 01 97 00 00 10 | Validation, publication, correction, résultats, personnel |
| Secrétariat | 01 97 00 00 11 | Import Excel, lettres d'accès, codes, inscription |
| Enseignant | 01 97 00 00 12 | Maths, SVT |
| Enseignante | 01 97 00 00 13 | Français, anglais : une saisie à moitié faite |
| Enseignant | 01 97 00 00 14 | Histoire-géo, EPS |
| Super-admin | 01 97 00 00 99 | Admin Django : écoles, suspension |

Aucun SMS n'est envoyé : l'accès passe par les codes et lettres que l'école remet aux familles.
En développement, chaque notification s'écrit aussi dans le terminal.

## Scénario complet en 10 minutes

1. **Parent sans compte** : « Première connexion » avec 01 97 00 00 02 et `PARE-NT26`, choisissez un
   mot de passe, acceptez la confidentialité : vous voyez l'enfant.
2. **Enseignante** (01 97 00 00 13) : ouvrez « Interrogation 2 » (Brouillon). Tapez une note puis
   « Suivant ». Essayez `25` (signalé), `9,5`, le bouton « Abs » (absent, compte 0). Coupez le
   Wi-Fi : les notes restent sur le téléphone ; rallumez : elles partent seules. « 0 aux vides »
   remplit le reste. Envoyez à la direction.
3. **Direction** (01 97 00 00 10) : Validation → corrigez une note (motif obligatoire) → rouvrez-la :
   l'historique apparaît → « Publier aux parents ». Personnel → ajoutez un enseignant : son code
   d'accès s'affiche avec la marche à suivre. Sur la page de connexion du personnel :
   « J'ai un code d'accès », choisissez « Personnel », puis le mot de passe.
4. **Direction** : Résultats → 6e A : la publication des bulletins est bloquée, la liste dit
   pourquoi. 5e A : « Publier les bulletins du Trimestre 1 ».
5. **Parent** (01 97 00 00 01) : la cloche affiche la nouvelle note. Sèna : bulletin PDF. Koffi :
   « bulletin pas encore publié », pas de téléchargement.
6. **Direction** : Configuration → Classes → ajoutez « 6e C » (elle reçoit les matières du niveau)
   → Enseignants → attribuez les matières → Calcul → essayez la formule béninoise.
7. **Secrétariat** (01 97 00 00 11) : Élèves → choisissez une classe → lettres d'accès (PDF).
   Import → modèle Excel → rapport ligne par ligne → import → lettres des nouveaux parents.

## Ce qui est vérifié automatiquement

- 103 tests backend sur un vrai PostgreSQL, sous le rôle de l'application : isolation entre
  écoles, droits par rôle, parent limité aux notes publiées de ses enfants, code de connexion
  (expiration, 5 essais, limitation des demandes), import, calculs, journal d'audit.
- Un parcours navigateur de 28 étapes, dans le dépôt : `cd frontend && npm run e2e` (après
  `./dev.sh reset` et avec `./dev.sh` lancé). Captures dans `frontend/e2e/captures/`.

## Pas encore construit

- Passage d'année (« promouvoir la classe »), changement de numéro d'un parent.
- Notifications push (les nouveautés sont visibles dans l'application ; pas de SMS par choix).
- Écran super-admin dédié : création d'école par `python manage.py create_school`, suspension par
  l'admin Django. Accès support tracé.
- Restrictions à l'intérieur d'une école vérifiées par la base (aujourd'hui : par l'API, testées).

## Documents PDF

Les bulletins d'une classe et les lettres d'accès sont préparés en tâche de fond : le bouton
affiche « Préparation… » puis le téléchargement démarre. Un bulletin seul est servi directement,
et mis en cache. En production, l'image Docker inclut `libharfbuzz-subset0`, qui accélère la
génération ; sur votre PC : `sudo apt install libharfbuzz-subset0`.
