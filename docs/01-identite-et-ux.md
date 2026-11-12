# Classio : identité visuelle et principes d'ergonomie

## 1. Logo : « Le C et le soleil »

![Planche du logo](brand/classio-planche.png)

Un C ouvert, et dans son ouverture un point jaune.

| Lecture | Sens |
|---|---|
| Le **C** | L'initiale de Classio, et un cercle de classe qui s'ouvre vers les familles. |
| L'**arc** | Une jauge de progression : l'élève avance. |
| Le **point** | Le soleil levant, et surtout la pastille de notification : la note qui arrive sur le téléphone du parent. C'est la promesse du produit. |

Le même soleil devient le point du « i » dans le mot-symbole, ce qui relie la marque au nom.

### Couleurs

| Nom | Code | Rôle |
|---|---|---|
| Forêt | `#0E5A43` | Couleur principale. Le vert évoque la croissance et rappelle le drapeau béninois. |
| Soleil | `#F4B740` | Accent, pastilles. Aussi présent dans le drapeau. |
| Latérite | `#B4472A` | Erreurs et alertes. Inspirée de la terre de barre du sud du Bénin. |
| Ivoire | `#FBF7EC` | Fond de page : plus doux que le blanc, évoque le papier du cahier. |
| Encre | `#14231E` | Texte. |

Contrastes mesurés (WCAG AA exige 4,5:1 pour du texte) :

| Texte sur fond | Ratio | Usage |
|---|---|---|
| Encre sur Ivoire | 15,2:1 | Texte courant |
| Forêt sur blanc | 8,2:1 | Liens, boutons secondaires |
| Ivoire sur Forêt | 7,7:1 | Boutons principaux |
| Encre sur Soleil | 9,1:1 | Texte sur une pastille jaune |
| Latérite sur blanc | 5,4:1 | Messages d'erreur |
| Soleil sur blanc | **1,8:1** | **Interdit pour du texte** : accent uniquement |

Le vert s'éloigne volontairement de celui de la v1 (`#075E54`), qui est presque celui de WhatsApp.
Les parents recevront nos messages dans WhatsApp : le logo ne doit pas passer pour celui de WhatsApp.

### Fichiers

Dans [brand/](brand/) : `classio-logo.svg` (fond clair), `classio-logo-on-dark.svg` (fond sombre),
`classio-icon.svg` (application), `classio-icon-maskable.svg` (Android), `classio-mark.svg`,
`classio-mark-mono.svg` (tampon, impression sur bulletin en noir et blanc).

Le mot-symbole est vectorisé depuis Poppins SemiBold (licence SIL OFL, usage commercial permis).
L'interface, elle, n'emploie aucune police web : la pile système évite un téléchargement sur forfait.

**À faire avant dépôt de marque :** une recherche d'antériorité sur le nom et le logo.

## 2. Principes communs

1. **Une action par écran** sur téléphone. Le parent vient chercher une information, pas naviguer.
2. **Budget de poids :** JavaScript initial sous 150 Ko compressés, écran de consultation sous 50 Ko
   de données API. Ces budgets servent l'objectif du cahier des charges : une note en moins de 2 s en 3G.
3. **Cibles tactiles de 48 px minimum**, texte de 16 px minimum (en dessous, iOS zoome sur les champs).
4. **Le contenu se voit avant le chargement :** on affiche la dernière version connue, avec sa date.
5. **Des mots simples :** « Envoyer à la direction », pas « Soumettre ». Pas de jargon, pas d'anglais.
6. **La couleur ne porte jamais seule l'information :** une note sous la moyenne a aussi une icône.

## 3. Espace parent : connexion par mot de passe

Décision du 12 novembre 2026 : pas de SMS pour l'instant (coût). Le parent se connecte avec son
numéro et un mot de passe, et reste connecté 30 jours sur son téléphone.

```
┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
│       ◖ classio       │   │  ‹ Retour             │   │  Bonjour              │
│                       │   │  Première connexion   │   │ ┌───────────────────┐ │
│  Numéro de téléphone  │   │                       │   │ │ Koffi · 6e A      │ │
│ [+229 01 97 00 00 01] │   │  Numéro               │   │ │ Moyenne 16,09     │ │
│  Mot de passe         │   │  Code de l'école      │   │ └───────────────────┘ │
│ [••••••••] Afficher   │   │  [ K7QM-3XPA ]        │   │ ┌───────────────────┐ │
│                       │   │  Mot de passe ×2      │   │ │ Sèna · 3e A       │ │
│ [ Me connecter ]      │   │  ☑ J'accepte la       │   │ │ Moyenne 7,81      │ │
│ [ Première connexion ]│   │    confidentialité    │   │ └───────────────────┘ │
│  Mot de passe oublié ?│   │ [ Enregistrer ]       │   │                       │
└───────────────────────┘   └───────────────────────┘   └───────────────────────┘
```

- **L'accès vient de l'école, sur papier.** Le secrétariat imprime une lettre par parent (code à
  usage unique, valable 30 jours) et la remet par l'enfant ou en réunion de parents.
- **Première connexion :** numéro + code + mot de passe choisi + consentement. Le code ne sert
  qu'une fois et n'est valable qu'avec le bon numéro.
- **Mot de passe oublié :** le secrétariat génère un nouveau code en un clic ; l'ancien est annulé.
- **Mot de passe :** 8 caractères au moins, les mots de passe trop courants sont refusés.
  Des chiffres seuls sont acceptés : plus simple à taper sur un téléphone d'entrée de gamme.
- **Même message d'erreur** pour un numéro inconnu et un mauvais mot de passe.
- **Un parent, plusieurs écoles :** un seul compte ; les enfants s'affichent ensemble.

## 4. Espace enseignant : grille de notes

```
┌───────────────────────────────────────────┐
│ ‹ 6e A · Maths · T1 · Composition    /20  │
│ ● Enregistré sur ce téléphone   ↻ 3 à envoyer
├───────────────────────────────────────────┤
│  Élève                  Note              │
│  ADJOVI Koffi          [ 14   ]           │
│  AGBO Awa              [ 9,5  ]           │
│  AHOUNOU Marc          [ 23   ] ⚠ > 20    │
│  AKPLOGAN Sena         [ Abs. ]           │
│  ALLADE Rita           [      ] vide      │
├───────────────────────────────────────────┤
│ Moy. 11,75 · 38/42 saisies                │
│ [ Envoyer à la direction ]                │
└───────────────────────────────────────────┘
```

- **Une seule colonne par évaluation sur téléphone.** Le classeur complet, avec une colonne par
  évaluation, n'apparaît que sur grand écran.
- **Clavier :** Entrée ou Suivant descend à l'élève suivant ; flèches et Tab sur ordinateur. On saisit
  sans quitter la feuille des yeux.
- **Le clavier décimal accepte la virgule et le point** (`inputmode="decimal"`) : « 9,5 » et « 9.5 »
  donnent la même note.
- **« a » ou « abs » vaut absent.** Une case vide n'est jamais un zéro.
- **Une alerte n'empêche pas de saisir :** note supérieure au barème signalée sur la ligne ; c'est
  l'envoi à la direction qui est bloqué tant qu'une erreur subsiste, avec un lien vers la ligne.
- **La sauvegarde est invisible et permanente :** chaque cellule s'enregistre sur le téléphone à la
  sortie du champ, le bandeau dit l'état en clair. Rien à cliquer, rien à perdre en cas de coupure.
- **Un conflit est montré, jamais écrasé :** si la direction a modifié la note entre-temps, les deux
  valeurs s'affichent et l'enseignant choisit.
- **Grille écrite à la main, avec de vrais `<input>` :** une bibliothèque de tableur pèserait
  plusieurs fois le budget de toute l'application, et une classe tient en une centaine de lignes.
