# WeeFarm Frontend

Interface web de demonstration pour WeeFarm, une plateforme de gestion de cooperatives agricoles au Senegal.

Cette livraison est **frontend-only**: aucune logique backend, base de donnees, authentification reelle ou integration IA serveur.

## Etat actuel du repo

L'application Next.js est maintenant a la **racine du repository**.

- Oui: il faut pousser le contenu de `frontend/` vers la racine (ce qui est fait)
- Non: il ne faut pas deployer une app vide avec un dossier wrapper `frontend` comme point d'entree
- Pour Vercel: laisse `Root Directory` vide (ou `.`)

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

La page ` /manager/assistant-ia ` est une interface de chat de demonstration:
- zone conversation
- suggestions de prompts
- etat vide
- historique mock
- reponses mock coherentes avec les donnees operationnelles

Non inclus:
- appels LLM
- RAG
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
- `backend/`, `database/`, `ai/` non utilises par cette demo frontend

Routes principales:
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

## Si Vercel affiche "Not Found"

Verifier:
- le projet pointe bien sur la branche contenant la migration vers la racine
- `Root Directory` n'est plus `frontend`
- le framework detecte est `Next.js`
- un nouveau redeploy a ete lance apres la mise a jour

## Notes techniques

- UI en francais, concise, dashboard-first
- Design garde une direction agricole moderne et calme
- Responsive desktop + mobile
- Donnees locales realistes pour demo PFE

## License

Usage academique / demo PFE.
