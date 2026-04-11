# WeeFarm - Frontend Demo (Role-Based)

Plateforme de gestion cooperative agricole (Senegal) avec interface **Admin** et **Manager**.

Ce repository contient un monorepo, mais la livraison actuelle est **frontend-first** (Next.js), avec donnees mock locales, sans integration backend.

## Important: GitHub + Vercel
- **Oui**, c'est normal de pousser le dossier `frontend/` (et son contenu) dans le repo.
- Pour deployer sur Vercel, configure:
  - **Framework**: `Next.js`
  - **Root Directory**: `frontend`
  - **Build Command**: `npm run build`
  - **Install Command**: `npm install`
- Tu n'es pas oblige de remonter les fichiers du dossier `frontend/` a la racine du repo.

## Current Frontend Scope
Implementation UI complete pour:
- **Admin platform**
  - Tableau de bord
  - Cooperatives
  - Managers
  - Parametres
- **Manager cooperative**
  - Tableau de bord
  - Membres
  - Parcelles
  - Produits
  - Inputs
  - Stocks
  - Lots
  - Transformations
  - Analytique
  - Assistant IA (UI mock uniquement)
  - Parametres

Hors scope technique dans cette passe:
- backend API
- auth reelle
- base de donnees
- appels LLM reels
- RAG reel
- moteur de recommandation
- prediction

## UI and Data Principles
- Design coherent, calme, dashboard-first
- Labels et microcopy en francais
- Donnees mock realistes Senegal:
  - zones: Thies, Louga, Casamance, etc.
  - produits: mangue, arachide, mil
  - lots, stocks, transformations, membres coherents entre pages

## Project Structure
- `frontend/` - Next.js app (App Router, TypeScript, Tailwind)
- `backend/` - backend workspace (non utilise pour cette demo frontend)
- `ai/` - IA workspace (non branche a l'UI de demo)
- `database/` - schema/seed (non utilise par le frontend mock)
- `docs/`, `docker/`, `scripts/` - ressources projet

Frontend key paths:
- `frontend/app/(platform)/admin/*` - pages Admin
- `frontend/app/(platform)/manager/*` - pages Manager
- `frontend/components/*` - UI components
- `frontend/lib/mock-data.ts` - donnees mock centrales

## Routing Overview
Entree:
- `/` -> ecran login/demo
- `/login` -> alias du login

Admin:
- `/admin/dashboard`
- `/admin/cooperatives`
- `/admin/managers`
- `/admin/parametres`

Manager:
- `/manager/dashboard`
- `/manager/membres`
- `/manager/parcelles`
- `/manager/produits`
- `/manager/inputs`
- `/manager/stocks`
- `/manager/lots`
- `/manager/transformations`
- `/manager/analytique`
- `/manager/assistant-ia`
- `/manager/parametres`

Legacy routes (compat):
- `/dashboard`, `/membres`, `/inputs`, `/lots`, `/transformations`, `/analytique`
- redirigees vers l'espace manager

## Assistant IA (Frontend Only)
La page `/manager/assistant-ia` est volontairement UI-only:
- layout chat propre
- zone conversation
- suggestions de prompts
- etat vide
- panneau historique
- reponses mock coherentes avec les donnees operationnelles

Aucune logique IA serveur n'est executee.

## Local Development (Frontend)
Depuis la racine du repo:

```bash
cd frontend
npm install
npm run dev
```

App disponible sur:
- `http://localhost:3001`

Build production:

```bash
cd frontend
npm run build
npm run start
```

## Deploy to Vercel
1. Import le repo `dalibouzir/PFE` dans Vercel
2. Set **Root Directory** = `frontend`
3. Verifie les commandes:
   - Install: `npm install`
   - Build: `npm run build`
4. Deploy

## Notes for Team
- Les donnees sont centralisees dans `frontend/lib/mock-data.ts`
- Les pages sont organisees par role pour garder une navigation claire
- Les modales/formulaires actuels sont en mode demo local
- Pour brancher un vrai backend plus tard:
  - conserver les structures de page
  - remplacer les mocks par une couche service/API

## License
Usage academique / demo projet PFE.
