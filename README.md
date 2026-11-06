# Classio

Application Next.js 15 App Router pour la gestion scolaire.

## Démarrage

1. Copier `.env.example` vers `.env.local`.
2. Renseigner les variables Supabase et la clé de session.
3. Installer les dépendances avec `npm install`.
4. Lancer le serveur avec `npm run dev`.
5. Ouvrir `http://localhost:3000`.

## Production

```sh
npm run build
npm start
```

## Variables requises

- `SUPABASE_URL` : URL du projet Supabase.
- `SUPABASE_SERVICE_ROLE_KEY` : clé serveur de rôle de service.
- `SESSION_SECRET` : secret aléatoire d'au moins 32 caractères.
- `SUPERADMIN_EMAIL` : compte administrateur initial.
- `SUPERADMIN_PASSWORD` : mot de passe administrateur initial.
- `SITE_URL` : URL publique canonique.

Les intégrations FedaPay et SMS sont optionnelles.

## Structure

- `app/` : pages App Router et routes API.
- `components/` : composants d'interface réutilisables.
- `lib/` : sessions, accès Supabase et utilitaires serveur.
- `app/dashboard/` : espaces école et super-administrateur.
- `app/api/` : API serveur.
