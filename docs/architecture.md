# Architecture

## Overview
- Web App (`Next.js + TypeScript + Tailwind`): admin and manager dashboards, analytics pages, and assistant IA demo UI.
- Data Layer (`lib/mock-data.ts`): local mock datasets shared across pages for demo consistency.
- Static Assets (`public/`): logos and visual assets used by the UI.

## Rendering Flow
1. Next.js App Router serves route groups from `app/`.
2. Route pages compose reusable UI from `components/`.
3. Pages read mock entities from `lib/mock-data.ts` and render role-based views.

## Scalability Notes
- Replace mock data with API or database adapters behind `lib/` helpers.
- Add API routes under `app/api` if server logic is needed in the same app.
- Keep route-level loading and splitting for dashboard performance on mobile.
