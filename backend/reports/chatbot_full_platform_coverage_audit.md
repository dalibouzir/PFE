# Chatbot Full Platform Coverage Audit

## Overview
- Generated at: 2026-05-08T22:35:17.351645+00:00
- Total questions: 112
- Overall pass rate: 0.9911

## Pass Rate by Intent
- HYBRID: 30/31 (0.9677)
- RAG_ONLY: 9/9 (1.0)
- SMALL_TALK: 4/4 (1.0)
- SQL_ONLY: 64/64 (1.0)
- UNSUPPORTED: 4/4 (1.0)

## Pass Rate by Module
- collections: 7/7 (1.0)
- finance: 7/7 (1.0)
- hybrid: 14/14 (1.0)
- invoices: 8/8 (1.0)
- lots: 7/7 (1.0)
- members: 11/11 (1.0)
- ml: 5/6 (0.8333)
- orders: 9/9 (1.0)
- parcels: 8/8 (1.0)
- process: 3/3 (1.0)
- recommendations: 7/7 (1.0)
- reference: 9/9 (1.0)
- small_talk: 4/4 (1.0)
- stocks: 8/8 (1.0)
- unsupported: 4/4 (1.0)

## Coverage & Risk
- Seeded modules: ['members', 'parcels', 'collections', 'stocks', 'lots', 'process', 'recommendations', 'orders', 'invoices', 'finance', 'ml', 'reference']
- Tested modules: ['collections', 'finance', 'invoices', 'lots', 'members', 'ml', 'orders', 'parcels', 'process', 'recommendations', 'reference', 'stocks']
- Module coverage rate: 1.0
- Fake-entity high-risk hallucinations: 0
- Stale response issues: 0
- UI/debug leakage issues: 0

## Acceptance Targets
- overall >= 85%: True
- SQL_ONLY >= 90%: True
- RAG_ONLY >= 85%: True
- HYBRID >= 80%: True
- SMALL_TALK = 100%: True
- UNSUPPORTED = 100%: True
- fake entity high-risk hallucination = 0: True
- stale response issues = 0: True
- UI/debug leakage = 0: True
- module coverage >= 80%: True
- major seeded modules all tested: True
- at least 100 questions: True

## Top Failures
- `ml-05` [HYBRID/ml] Explique les signaux ML à haut risque et leurs implications opérationnelles.
  - expected/actual: ['HYBRID'] -> HYBRID | pass=False
  - snippet: Aucune preuve de référence n'a été récupérée pour étayer cette analyse opérationnelle. Je ne peux pas fournir une synthèse HYBRID fiable pour le moment.
  - citations=0 sql=['ml_metrics'] tables=['ml', 'ml_model_registry', 'ml_prediction_logs', 'ml_training_runs']
  - hallucination=low stale=low debug=low
  - notes: Unexpected missing-data response for non-fake case.