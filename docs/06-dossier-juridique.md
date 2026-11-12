# Classio : conformité au droit béninois des données personnelles

Avis au 12 novembre 2026. Texte de référence : loi n° 2017-20 du 20 avril 2018 portant Code du
numérique, **Livre V** (articles cités ci-dessous d'après la version publiée en 2018).

**Limites de cet avis :**
- Il a été établi à partir du texte de la loi, non par un avocat inscrit au barreau.
- La loi n° 2020-35 du 6 janvier 2021 a modifié le Code du numérique. Avant d'ouvrir le pilote,
  vérifiez dans la version consolidée que les articles cités n'ont pas changé.
- Les formalités auprès de l'APDP sont faites par l'école et par vous ; personne d'autre ne peut
  les faire à votre place.

Pièces jointes :
- [07-contrat-sous-traitance.md](07-contrat-sous-traitance.md) : contrat école ↔ Classio ;
- [08-conditions-utilisation.md](08-conditions-utilisation.md) : conditions d'utilisation de
  Classio ;
- la politique de confidentialité, dans l'application (`frontend/src/features/auth/Privacy.tsx`,
  version `2026-11-v1`).

## 1. Qui est responsable de quoi

| Acteur | Qualification | Fondement |
|---|---|---|
| L'école | **Responsable du traitement** : elle décide des finalités (gérer et communiquer les notes) | Livre V, définitions |
| Classio | **Sous-traitant** : traite pour le compte de l'école, sur ses instructions | art. 386 |
| Hébergeur du serveur, fournisseur des sauvegardes | Sous-traitants ultérieurs de Classio | art. 386, 426 |

Conséquence : c'est l'école qui répond devant les parents et l'APDP. Classio doit lui offrir des
« garanties suffisantes » de sécurité et signer avec elle un **contrat écrit** (art. 386 et 426).
C'est l'objet du document 07.

## 2. Base légale : pas de consentement

L'article 389 admet un traitement sans consentement lorsqu'il est nécessaire :
- à « l'exécution d'une mission d'intérêt public » (2°) : c'est le cas des **écoles publiques**,
  CEG et lycées ;
- à « l'exécution d'un contrat auquel la personne concernée est partie » (3°) : c'est le cas des
  **écoles privées**, par le contrat de scolarité.

Noter, calculer les moyennes et remettre les bulletins relève de l'une ou de l'autre.

De plus, l'article 390 précise qu'un consentement n'est pas libre si la fourniture d'un service y
est subordonnée. Exiger « j'accepte » pour accéder aux notes aurait donc fragilisé le traitement.

**Ce qui a été changé dans l'application :** la case de première connexion devient « J'ai lu la
politique de confidentialité ». C'est une preuve d'information (art. 384, transparence), avec sa
date et sa version, et non plus un consentement.

**Mineurs (art. 446) :** l'article 446 exige le consentement parental pour les moins de 16 ans,
mais il vise « l'offre directe de services de la société de l'information aux mineurs ». Classio
ne s'adresse pas aux élèves : seuls leurs parents et le personnel de l'école y ont un compte.
L'article ne s'applique donc pas. Le niveau de protection doit cependant rester élevé, car il
s'agit d'enfants : information rédigée simplement (art. 418) et aucun profilage.

## 3. Formalités auprès de l'APDP

| Qui | Quoi | Fondement |
|---|---|---|
| **Chaque école** | **Déclaration préalable** du traitement « gestion et communication des notes » à l'APDP, **ou** inscription dans un registre tenu par une personne désignée par l'école. Classio fournit le contenu tout prêt (§ 9). | art. 405, 409, 435 |
| Chaque école | **Autorisation préalable** (et non simple déclaration) si les données sortent de la CEDEAO | art. 391, 407 6° |
| École publique | **Délégué à la protection des données obligatoire** (organisme public) | art. 430 1° |
| École privée | Délégué non obligatoire, mais recommandé : une personne de la direction | art. 430 |
| Classio | Registre de ses activités de sous-traitant ; délégué non obligatoire au stade du pilote | art. 430, 435 |

**Analyse d'impact (art. 428) :** elle n'est pas obligatoire au sens strict. Classio ne prend
aucune décision automatisée produisant des effets juridiques, et ne traite aucune donnée sensible
de l'article 394.

Une analyse d'impact courte reste toutefois recommandée avant d'ouvrir le service à plus d'écoles :
il s'agit de données de mineurs, et le classement par rang influence leur parcours. Elle tient en
quelques pages et s'appuiera sur le § 6 ci-dessous.

## 4. Hébergement : rester dans la CEDEAO

Le Code définit l'**« État tiers »** comme « tout État non membre de la CEDEAO ». Les règles sont
les suivantes :
- **Hébergement au Bénin ou dans un pays membre de la CEDEAO :** ce n'est pas un transfert vers un
  État tiers. Aucune autorisation particulière n'est requise, au-delà de la déclaration.
- **Hébergement hors CEDEAO (Europe, États-Unis, Afrique du Sud) :** il faut l'**autorisation
  préalable de l'APDP**, qui doit constater un niveau de protection équivalent (art. 391 et
  407 6°). Les exceptions de l'article 392 ne conviennent pas ici : un consentement exprès de
  chaque parent ne peut pas servir de base à un service quotidien.

**Décision recommandée :** héberger le serveur **et la copie des sauvegardes** dans un pays membre
de la CEDEAO (Bénin, Côte d'Ivoire, Sénégal, Ghana, Nigeria, par exemple). La politique de
confidentialité l'annonce déjà : choisissez le fournisseur en conséquence.

Vérifiez l'appartenance à la CEDEAO au moment du choix. Le Burkina Faso, le Mali et le Niger en
sont sortis en 2025.

**Supervision des erreurs (Sentry) :**
- l'application l'a configurée pour n'envoyer aucune donnée personnelle (`send_default_pii=False`),
  mais un message d'erreur peut en contenir par accident ;
- sans autorisation de l'APDP, deux solutions sûres :
  - ne pas activer Sentry et surveiller par les journaux du serveur, qui sont déjà sans numéro
    ni note ;
  - ou héberger un outil équivalent sur votre serveur.

**Adresse de contact sur Gmail (`classiobenin@gmail.com`) :**
- les messages reçus sont stockés par Google, hors CEDEAO. Les demandes de parents qui y
  arrivent sortent donc de la CEDEAO ;
- le risque est faible : c'est le parent qui choisit d'écrire, et le volume est minime ;
- règles à tenir : n'envoyer **depuis** cette adresse ni notes, ni bulletins, ni listes
  d'élèves ; transmettre la demande à l'école et y répondre sans recopier de données
  scolaires ; activer la validation en deux étapes du compte ;
- dès que Classio a un nom de domaine, passer à une adresse sur ce domaine, chez un fournisseur
  de messagerie de la CEDEAO si possible.

## 5. Durées de conservation

Le principe : pas plus longtemps que nécessaire (art. 383 6°). Durées retenues, reprises dans la
politique de confidentialité :

| Donnée | Durée | État dans le code |
|---|---|---|
| Notes, bulletins, journal des modifications de notes | Scolarité dans l'école + **1 an** après le départ de l'élève | ⬜ **À développer avant septembre 2027** : export de l'archive à l'école, puis effacement. Aucun élève n'est concerné pendant la première année du pilote. |
| Compte parent | Tant qu'un enfant est inscrit | ⬜ Même chantier |
| Notifications | 400 jours | ✅ purge quotidienne |
| Codes d'accès | 30 jours + 30 jours | ✅ |
| Imports non validés | 7 jours | ✅ |
| Sauvegardes | 30 jours | ✅ |
| Session parent / personnel | 30 jours / 12 heures | ✅ |

Le journal des modifications de notes suit la durée des notes : il sert de preuve en cas de
contestation d'une note, et ne se justifie plus une fois la note effacée.

**L'archivage des bulletins incombe à l'école**, selon ses propres obligations administratives :
Classio lui remet l'archive et ne la conserve pas indéfiniment.

## 6. Sécurité (art. 426) : ce qui est en place

L'article 426 cite expressément :
- **le chiffrement** : HTTPS obligatoire avec HSTS ; sauvegardes chiffrées en AES-256 ; mots de
  passe hachés avec Argon2 ; codes d'accès conservés sous forme d'empreinte ;
- **la confidentialité et l'intégrité** :
  - isolation des écoles dans la base de données (Row Level Security), testée automatiquement ;
  - droits par rôle ;
  - journal inaltérable de toute modification de note (auteur, date, ancienne et nouvelle valeur,
    motif) ;
- **la disponibilité et la restauration** : sauvegarde chaque nuit, copie hors du serveur, test de
  restauration chaque mois ;
- **les tests réguliers** : 103 tests automatiques et un parcours complet dans le navigateur à
  chaque modification ; audit des dépendances dans l'intégration continue.

Autres mesures :
- limitation des tentatives de connexion ;
- aucun numéro de téléphone ni contenu de notification dans les journaux ;
- accès de l'équipe Classio aux données d'une école : **interdit** tant que l'outil d'accès tracé
  avec accord de l'école n'est pas développé.

## 7. Violation de données (art. 427)

- Classio prévient l'école **sans délai** ; le contrat fixe un maximum de **48 heures** après la
  découverte.
- L'école notifie **sans délai** l'APDP et les personnes concernées. Le contenu minimal est fixé
  par l'article 427 : nature, nombre de personnes concernées, contact, conséquences, mesures
  prises.
- Exception : les personnes n'ont pas à être prévenues individuellement si les données touchées
  étaient chiffrées (cas d'une sauvegarde volée, par exemple).

## 8. Droits des personnes

Le parent peut demander l'accès, la rectification ou l'effacement, en écrivant au secrétariat de
l'école ou à l'adresse de Classio. La réponse est due dans les 30 jours (art. 418). Cette demande
s'exerce pour ses propres données et pour celles de son enfant mineur.

Dans l'application :
- la rectification passe par le secrétariat (ce qui existe) ;
- ⬜ **l'export des données d'un élève**, utile pour le droit d'accès, reste à développer. En
  attendant, le secrétariat peut remettre le bulletin.

**Sanctions encourues en cas de manquement :** jusqu'à **50 millions de FCFA**, et 100 millions en
cas de récidive (art. 455), sans compter les sanctions pénales (art. 460 et suivants).

## 9. Déclaration à l'APDP : contenu à reprendre par l'école (art. 409)

| Rubrique | Contenu |
|---|---|
| Responsable du traitement | L'école (nom, adresse, représentant légal) |
| Délégué ou contact | La personne désignée par l'école |
| Finalité | Gestion des évaluations, calcul des moyennes et des rangs, établissement des bulletins, communication des notes et bulletins aux parents |
| Base légale | Mission d'intérêt public (école publique) ou contrat de scolarité (école privée), art. 389 |
| Personnes concernées | Élèves, parents ou tuteurs, personnel enseignant et administratif |
| Données | Voir la politique de confidentialité, « Quelles données ? ». Aucune donnée sensible au sens de l'art. 394. |
| Destinataires | Parents (pour leurs enfants), enseignants (pour leurs classes), direction et secrétariat |
| Sous-traitant | Classio, contrat écrit (art. 386) ; hébergeur : [nom, pays de la CEDEAO] |
| Transfert hors CEDEAO | Aucun |
| Durées | § 5 |
| Sécurité | § 6 |
| Droits | Auprès du secrétariat de l'école, ou de Classio : classiobenin@gmail.com |

## 10. Avant le lancement

1. Choisir un hébergeur et un second fournisseur pour les sauvegardes **dans la CEDEAO**.
2. ✅ Adresse de contact « données personnelles » : `classiobenin@gmail.com` (reportée dans
   `Privacy.tsx` et dans le document 08). Voir la réserve du § 4 sur Gmail.
3. Vérifier la version consolidée du Code du numérique (loi n° 2020-35 de 2021) sur les articles
   cités.
4. Faire signer le contrat de sous-traitance par chaque école pilote.
5. Faire déposer par chaque école sa déclaration auprès de l'APDP (§ 9). Pour une école publique,
   faire désigner son délégué.
6. Tenir le registre de Classio (art. 435) : ce document et le contrat en constituent la base.
7. Avant septembre 2027 : développer l'export de l'archive à l'école puis l'effacement un an après
   le départ (§ 5), et l'export des données d'un élève (§ 8).
