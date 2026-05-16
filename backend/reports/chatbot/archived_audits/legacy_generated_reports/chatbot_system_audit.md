# Chatbot System Audit

## Executive summary
- Total cas: 34 | PASS=18 | PARTIAL=16 | FAIL=0
- Taux route correcte: 100.0% | outils corrects: 100.0% | sources correctes: 100.0%
- Routes: exactes=97.06% | compatibles acceptées=2.94% | échecs route=0.0%
- Français conforme: 100.0% | fuites contexte: 0 | grounding reco: 100.0%
- Audit only: aucun correctif produit dans cette exécution.

## Architecture map found in code
- Backend endpoints:
  - /chat: @router.post('')
  - /chat/agent: @router.post('/agent')
- Frontend usage:
  - Endpoint constant: agentAsk: '/chat/agent'
  - Request call: apiFetch(endpoints.chat.agentAsk)
  - conversation_id forwarded: yes
- Orchestrator components:
  - AgentOrchestrator: found
  - IntentRouter: found
  - EntityExtractor: found
  - AgentRegistry: found
  - SQLAnalyticsAgent: found
  - RAGKnowledgeAgent: found
  - MLLossAgent: found
  - RecommendationAgent: found
  - ResponseVerifier: found
  - SourceFormatter: found
  - MemoryContext: found

## Endpoint usage
- Test target: /chat/agent
- Chat endpoint present: @router.post('')
- Frontend route used: agentAsk: '/chat/agent'
- Debug mode: AI_AUDIT_DEBUG=1

## Tested modules
- ML risk/anomaly
- RAG knowledge
- collections/inputs
- lots/batches
- material balance
- members
- memory/context
- parcels
- pre-harvest
- process steps / flux matière
- recommendations
- stocks

## Pass / partial / fail counts
- PASS: 18
- PARTIAL: 16
- FAIL: 0

## Module-by-module results
| Module | PASS | PARTIAL | FAIL |
| --- | ---: | ---: | ---: |
| ML risk/anomaly | 0 | 3 | 0 |
| RAG knowledge | 3 | 0 | 0 |
| collections/inputs | 3 | 0 | 0 |
| lots/batches | 0 | 3 | 0 |
| material balance | 1 | 2 | 0 |
| members | 2 | 1 | 0 |
| memory/context | 2 | 2 | 0 |
| parcels | 0 | 1 | 0 |
| pre-harvest | 2 | 1 | 0 |
| process steps / flux matière | 2 | 0 | 0 |
| recommendations | 0 | 3 | 0 |
| stocks | 3 | 0 | 0 |

## Quality rates
- Route correctness rate: 100.0%
- Route exact match rate: 97.06%
- Route compatible accepted rate: 2.94%
- Route failure rate: 0.0%
- Tool correctness rate: 100.0%
- Source correctness rate: 100.0%
- French compliance rate: 100.0%
- Context leakage count: 0
- Recommendation grounding rate: 100.0%

## SQL/ML contradiction warnings
- Total warnings détectés: 8
- Explained warnings: 0
- Unresolved warnings: 8
  - preharvest-02: explained=no | status=PARTIAL
  - ml-01: explained=no | status=PARTIAL
  - ml-02: explained=no | status=PARTIAL
  - ml-03: explained=no | status=PARTIAL
  - reco-01: explained=no | status=PARTIAL
  - reco-02: explained=no | status=PARTIAL
  - memory-a2: explained=no | status=PARTIAL
  - memory-b1: explained=no | status=PARTIAL

## Top 10 failures
- FRONTEND_DISPLAY_RISK: 15
- ML_SQL_CONTRADICTION: 8
- CONTENT_SEMANTIC_ERROR: 1
- ENTITY_EXTRACTION_ERROR: 1

## Exact suspected root causes
- Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. (cas=14)
- La réponse ne reflète pas correctement le contenu opérationnel attendu (liste/détail/pluriel). (cas=1)
- EntityExtractor ne capture pas correctement les entités (scope, lot, membre) pour cette formulation. (cas=1)

## Worst failing modules
- ML risk/anomaly: FAIL=0 PARTIAL=3
- lots/batches: FAIL=0 PARTIAL=3
- recommendations: FAIL=0 PARTIAL=3
- material balance: FAIL=0 PARTIAL=2
- memory/context: FAIL=0 PARTIAL=2

## Priority fix list
1. Corriger les erreurs de routage (IntentRouter) pour les cas où le mode attendu n’est pas sélectionné.
2. Fiabiliser extraction d’entités (scope, membre, lot) pour éviter erreurs de contexte et de tool selection.
3. Forcer le grounding de recommandations avec preuves SQL/RAG/ML explicites.
4. Renforcer émission de sources attendues par mode (SQL/RAG/ML) et signaler manque de preuve en metadata.
5. Limiter fuite de contexte via règles de reset/filtrage d’entités mémoire pour questions non liées.

## Recommended next implementation step
- Démarrer par une instrumentation ciblée d’IntentRouter + EntityExtractor (debug only) puis corriger les règles de routing membres/parcelles/risque avant toute refonte plus large.

## Detailed case results
| Case | Module | Expected route | Actual route | Route status | Scope exp/act | Source ok | French | Leakage | Status | Root cause |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| members-01 | members | SQL_ONLY | SQL_ONLY | exact_match | global/global | yes | yes | no | PARTIAL | La réponse ne reflète pas correctement le contenu opérationnel attendu (liste/détail/pluriel). |
| members-02 | members | SQL_ONLY | SQL_ONLY | exact_match | global/global | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| members-03 | members | SQL_ONLY | SQL_ONLY | exact_match | global/global | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| parcels-01 | parcels | SQL_ONLY | SQL_ONLY | exact_match | pre_harvest/pre_harvest | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| preharvest-01 | pre-harvest | SQL_ONLY | SQL_ONLY | exact_match | pre_harvest/pre_harvest | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| preharvest-02 | pre-harvest | HYBRID_SQL_ML | HYBRID_SQL_ML | exact_match | pre_harvest/pre_harvest | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| preharvest-03 | pre-harvest | SQL_ONLY | SQL_ONLY | exact_match | pre_harvest/pre_harvest | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| collections-01 | collections/inputs | SQL_ONLY | SQL_ONLY | exact_match | global/global | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| collections-02 | collections/inputs | SQL_ONLY | SQL_ONLY | exact_match | global/global | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| collections-03 | collections/inputs | SQL_ONLY | SQL_ONLY | exact_match | global/global | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| stocks-01 | stocks | SQL_ONLY | SQL_ONLY | exact_match | global/global | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| stocks-02 | stocks | SQL_ONLY | SQL_ONLY | exact_match | global/global | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| stocks-03 | stocks | SQL_ONLY | SQL_ONLY | exact_match | global/global | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| lots-01 | lots/batches | SQL_ONLY | SQL_ONLY | exact_match | post_harvest/post_harvest | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| lots-02 | lots/batches | SQL_ONLY | SQL_ONLY | exact_match | batch/batch | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| lots-03 | lots/batches | SQL_ONLY | SQL_ONLY | exact_match | post_harvest/post_harvest | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| process-01 | process steps / flux matière | SQL_ONLY | SQL_ONLY | exact_match | post_harvest/post_harvest | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| process-02 | process steps / flux matière | SQL_ONLY | SQL_ONLY | exact_match | post_harvest/post_harvest | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| balance-01 | material balance | HYBRID_SQL_RAG | HYBRID_SQL_RAG | exact_match | global/global | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| balance-02 | material balance | HYBRID_SQL_RAG | HYBRID_SQL_RAG | exact_match | batch/batch | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| balance-03 | material balance | SQL_ONLY | SQL_ONLY | exact_match | post_harvest/post_harvest | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| rag-01 | RAG knowledge | RAG_ONLY | RAG_ONLY | exact_match | post_harvest/post_harvest | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| rag-02 | RAG knowledge | RAG_ONLY | RAG_ONLY | exact_match | post_harvest/post_harvest | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| rag-03 | RAG knowledge | RAG_ONLY | RAG_ONLY | exact_match | post_harvest/post_harvest | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| ml-01 | ML risk/anomaly | HYBRID_SQL_ML | HYBRID_SQL_ML | exact_match | global/post_harvest | yes | yes | no | PARTIAL | EntityExtractor ne capture pas correctement les entités (scope, lot, membre) pour cette formulation. |
| ml-02 | ML risk/anomaly | HYBRID_SQL_ML | HYBRID_SQL_ML | exact_match | post_harvest/post_harvest | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| ml-03 | ML risk/anomaly | HYBRID_SQL_ML | HYBRID_SQL_ML | exact_match | post_harvest/post_harvest | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| reco-01 | recommendations | HYBRID_FULL | HYBRID_FULL | exact_match | batch/batch | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| reco-02 | recommendations | HYBRID_RAG_RECOMMENDATION | HYBRID_FULL | compatible_route_accepted | post_harvest/post_harvest | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| reco-03 | recommendations | RECOMMENDATION_ONLY | RECOMMENDATION_ONLY | exact_match | global/global | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| memory-a1 | memory/context | SQL_ONLY | SQL_ONLY | exact_match | global/global | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |
| memory-a2 | memory/context | HYBRID_SQL_ML | HYBRID_SQL_ML | exact_match | post_harvest/post_harvest | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| memory-b1 | memory/context | HYBRID_SQL_ML | HYBRID_SQL_ML | exact_match | post_harvest/post_harvest | yes | yes | no | PARTIAL | Les métadonnées sources/réponse risquent un affichage ambigu côté frontend. |
| memory-b2 | memory/context | SQL_ONLY | SQL_ONLY | exact_match | global/global | yes | yes | no | PASS | Aucune anomalie détectée pour ce cas. |