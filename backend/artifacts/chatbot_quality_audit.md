# Chatbot Quality Audit Report

## Overview
- Generated at: 2026-05-13T10:44:06.240393+00:00
- Total test questions: 50
- Overall pass rate: 0.86

## Pass Rate by Intent
- HYBRID: 14/14 (1.0)
- RAG_ONLY: 2/9 (0.2222)
- SMALL_TALK: 7/7 (1.0)
- SQL_ONLY: 14/14 (1.0)
- UNSUPPORTED: 6/6 (1.0)

## Worst Failed Questions
- `rag-05` [RAG_ONLY] Donne des références agronomiques utiles pour la transformation de Arachide.
  - expected/actual intent: ['RAG_ONLY'] -> RAG_ONLY
  - pass: False | hallucination_risk: low | citations: 3
  - notes: Raw JSON-like content detected in manager-facing answer payload.
- `rag-07` [RAG_ONLY] Quelles sources conseillent des pratiques de tri pour limiter les pertes ?
  - expected/actual intent: ['RAG_ONLY'] -> RAG_ONLY
  - pass: False | hallucination_risk: low | citations: 3
  - notes: Raw JSON-like content detected in manager-facing answer payload.
- `rag-08` [RAG_ONLY] Que disent les références sur la prévention des moisissures en stockage ?
  - expected/actual intent: ['RAG_ONLY'] -> RAG_ONLY
  - pass: False | hallucination_risk: low | citations: 3
  - notes: Raw JSON-like content detected in manager-facing answer payload.
- `rag-01` [RAG_ONLY] Quelles sont les meilleures pratiques pour le séchage de la mangue ?
  - expected/actual intent: ['RAG_ONLY'] -> RAG_ONLY
  - pass: False | hallucination_risk: low | citations: 4
  - notes: Raw JSON-like content detected in manager-facing answer payload.
- `rag-02` [RAG_ONLY] Quels benchmarks de pertes existent pour le mil ?
  - expected/actual intent: ['RAG_ONLY'] -> RAG_ONLY
  - pass: False | hallucination_risk: low | citations: 4
  - notes: Raw JSON-like content detected in manager-facing answer payload.
- `rag-03` [RAG_ONLY] Quels conseils post-récolte pour le stockage afin de réduire les pertes ?
  - expected/actual intent: ['RAG_ONLY'] -> RAG_ONLY
  - pass: False | hallucination_risk: low | citations: 4
  - notes: Raw JSON-like content detected in manager-facing answer payload.
- `rag-06` [RAG_ONLY] Quels seuils d'humidité sont recommandés en séchage post-récolte ?
  - expected/actual intent: ['RAG_ONLY'] -> RAG_ONLY
  - pass: False | hallucination_risk: low | citations: 4
  - notes: Raw JSON-like content detected in manager-facing answer payload.

## Hallucination Cases
- No high-risk hallucination case detected.

## Routing Errors
- None

## Citation Issues
- None

## Stale Response Issues
- None

## UI/Debug Leakage Issues
- `rag-01` raw_json=True technical=False labels=[]
- `rag-02` raw_json=True technical=False labels=[]
- `rag-03` raw_json=True technical=False labels=[]
- `rag-05` raw_json=True technical=False labels=[]
- `rag-06` raw_json=True technical=False labels=[]
- `rag-07` raw_json=True technical=False labels=[]
- `rag-08` raw_json=True technical=False labels=[]

## Recommended Fixes (Priority)
- P1 — UI/debug leakage: Keep technical labels/codes out of manager-facing text and isolate them in technical drawer only.

## Minimal Acceptance Check
- At least 40 questions: True
- All required intents covered: True
- Uses real DB values: True
- Uses fake/non-existing values: True
- Clear pass/fail + priority fixes: True