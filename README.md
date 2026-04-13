# WeeFarm Web App

Interface web de demonstration pour WeeFarm, une plateforme de gestion de cooperatives agricoles au Senegal.

Cette livraison est **frontend-only**: aucune logique backend, base de donnees, authentification reelle ou integration IA serveur.

## Etat actuel du repo

L'application Next.js tourne a la racine du repository.

- Point d'entree: `app/` (App Router)
- Root Directory Vercel: vide (ou `.`)
- Commandes: `npm run dev`, `npm run build`, `npm run start`

## Perimetre fonctionnel implemente

### Espace Admin (plateforme)
- Tableau de bord
- Cooperatives
- Managers
- Parametres

### Espace Manager (cooperative)
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

## Assistant IA (frontend-only)

La page `/manager/assistant-ia` est une interface de chat de demonstration:
- zone conversation
- suggestions de prompts
- etat vide
- historique mock
- reponses mock coherentes avec les donnees operationnelles

Non inclus:
- appels LLM
- RAG serveur
- recommandations/predictions reelles
- API backend

## Donnees mock

Les donnees sont locales et coherentes entre les ecrans:
- regions/zones: Thies, Louga, Casamance
- produits: mangue, arachide, mil
- lots, stocks, pertes, statuts, transformations

Fichier principal:
- `lib/mock-data.ts`

## Structure du projet

- `app/` routes Next.js (App Router)
- `components/` composants UI
- `lib/` helpers + mock data
- `public/` assets statiques
- `ai/`, `database/`, `docs/`, `docker/` ressources projet hors runtime frontend

## Routes principales

- `/admin/dashboard`
- `/admin/cooperatives`
- `/admin/managers`
- `/admin/parametres`
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

## Lancer en local

Depuis la racine du repo:

```bash
npm install
npm run dev
```

Application disponible sur:
- `http://localhost:3001`

Build production:

```bash
npm run build
npm run start
```

## Deploiement Vercel

1. Importer `dalibouzir/PFE`
2. Detecter automatiquement `Next.js`
3. Verifier les commandes:
   - Install: `npm install`
   - Build: `npm run build`
4. **Root Directory**: vide (ou `.`)
5. Deploy

## Notes techniques

- UI en francais, concise, dashboard-first
- Responsive desktop + mobile
- Donnees locales realistes pour demo PFE

## License

Usage academique / demo PFE.
