# PFE Demo Script

Generated: 2026-05-08 (Africa/Tunis)

## Demo Objective
Show an AI-first decision-support prototype for cooperative managers with deterministic SQL facts, grounded references, and cross-module HYBRID reasoning.

## Recommended Demo Flow
1. Dashboard overview
- Action: open manager dashboard.
- Jury should notice: operational KPIs and alerts without technical/debug noise.

2. SQL_ONLY stock fact
- Ask: `Quel est le stock actuel de mangue ?`
- Expected: compact SQL factual response (total, réservé, disponible, statut), no executive risk deck.
- Jury should notice: deterministic, concise, no hallucination.

3. SQL_ONLY member + collections
- Ask: `Quel est le total de collecte du membre DEMOFP-M-014 ?`
- Expected: member-scoped factual answer.
- Jury should notice: cross-module access beyond stocks/lots.

4. SQL_ONLY parcels
- Ask: `Parcelles et cultures du membre DEMOFP-M-014`
- Expected: parcel list and cultures (factual).
- Jury should notice: member→parcel linkage works.

5. HYBRID lot anomaly/risk
- Ask: `Compare la performance des lots LOT-MANG-001 et LOT-BISS-001 et explique les écarts.`
- Expected: executive synthesis with risks/actions; evidence policy applied.
- Jury should notice: analytical reasoning, not just raw SQL.

6. HYBRID commercial risk
- Ask: `Risque stock+commande: Mangue face aux commandes ouvertes, que faire ?`
- Expected: operational risk framing + actions.
- Jury should notice: stock + commercial joint reasoning.

7. SQL_ONLY invoices/finance
- Ask: `Quelles sont les factures impayées ?`
- Ask: `Total des charges par catégorie.`
- Expected: deterministic finance/commercial facts.
- Jury should notice: full-platform coverage.

8. RAG_ONLY reference guidance
- Ask: `Conseils post-récolte pour la conservation avec sources`
- Expected: reference-oriented answer with sources (or explicit no-evidence message).
- Jury should notice: evidence gating and citation behavior.

9. Hallucination safety trap
- Ask: `Surface de la parcelle PARCELLE_FAKE_8301`
- Expected: safe missing-data answer, no invented values.
- Jury should notice: anti-hallucination control.

10. Small talk boundary
- Ask: `hello`
- Expected: short greeting only; no KPI cards, no old analysis reuse.
- Jury should notice: routing guard + no stale response leak.

## Fallback Plan (LLM Provider Unavailable)
- Use SQL_ONLY questions (steps 2, 3, 4, 7, 9, 10): deterministic outputs remain demonstrable.
- For HYBRID/RAG questions, show controlled fallback behavior (`missing evidence`) rather than fabricated claims.
- Present latest audit reports as objective validation evidence.

## Evidence Files to Show During Demo
- `backend/reports/chatbot_full_platform_coverage_audit.md`
- `backend/reports/chatbot_unseen_robustness_audit.md`
- `backend/artifacts/chatbot_quality_audit.md`
- `backend/reports/ml_model_validation_report.md`
- `backend/reports/full_rag_index_coverage_report.md`
