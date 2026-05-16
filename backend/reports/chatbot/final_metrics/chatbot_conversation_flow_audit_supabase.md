# Chatbot Conversation Flow Audit (Supabase Readonly)

- Timestamp UTC: 2026-05-13T19:13:26.931444+00:00
- Conversation ID: 3479fd20-f3e0-4d26-a513-bf6a6d21a143
- Total cases: 48
- PASS: 36
- PARTIAL: 12
- FAIL: 0
- PASS rate: 75.0%
- Overall verdict: PASS
- Chatbot rating: 90.0/100

## Metrics by module
| Module | Total | PASS | PARTIAL | FAIL |
|---|---:|---:|---:|---:|
| lots | 4 | 4 | 0 | 0 |
| members | 4 | 2 | 2 | 0 |
| rag_best_practices | 4 | 4 | 0 | 0 |
| stocks | 4 | 1 | 3 | 0 |
| parcels | 4 | 2 | 2 | 0 |
| inputs | 4 | 3 | 1 | 0 |
| process_steps | 4 | 2 | 2 | 0 |
| material_balance | 4 | 3 | 1 | 0 |
| loss_efficiency | 4 | 4 | 0 | 0 |
| ml_risk | 4 | 3 | 1 | 0 |
| recommendations | 4 | 4 | 0 | 0 |
| business_ops | 4 | 4 | 0 | 0 |

## Memory/context metrics
- Follow-up reuse: 4 / 4
- Context reset: 3 / 3
- Context leak count: 0
- False fallback count: 0

## Member ranking diagnosis
- Verdict: no_mismatch_detected
- SQL truth top member: Awa Ndiaye (1715.0 kg)
- Legacy expectation: Awa Ndiaye (1715.0 kg)
- Detail: chatbot and legacy expectation align

## Worst failures
- ml-04 [PARTIAL] ml_risk -> route_mismatch:SQL_ONLY not in ['HYBRID_FULL', 'HYBRID_SQL_ML', 'HYBRID_SQL_RAG', 'ML_ONLY'], missing_sources:['ml'], fact_mismatch:expected risk semantics; sql_risk_count=4
- members-03 [PARTIAL] members -> fact_mismatch:expected top_member=Awa Ndiaye (1715.0 kg)
- members-04 [PARTIAL] members -> fact_mismatch:expected top_member=Awa Ndiaye (1715.0 kg)
- parcels-03 [PARTIAL] parcels -> fact_mismatch:expected semantic signal for parcel_semantic
- process-01 [PARTIAL] process_steps -> fact_mismatch:expected top_stage=séchage
- process-04 [PARTIAL] process_steps -> fact_mismatch:expected semantic signal for process_semantic
- mb-01 [PARTIAL] material_balance -> fact_mismatch:expected material in=12140.0 out=11022.5 loss=9.2%
- stocks-01 [PARTIAL] stocks -> fact_mismatch:expected stock_total=5510.0 kg
- stocks-02 [PARTIAL] stocks -> fact_mismatch:expected semantic signal for stock_product
- stocks-04 [PARTIAL] stocks -> memory_product_missing:banane

## Suspected root causes
- fact_mismatch
- memory_product_missing
- route_mismatch
- missing_sources

## Top 5 recommended fixes
1. Ajouter des vérifications de vérité SQL avant formulation finale (post-aggregation check).
2. Traiter les occurrences de memory_product_missing.
3. Renforcer les règles sémantiques de routage multi-intent et follow-up.
4. Garantir la collecte de sources attendues par route (SQL/RAG/ML/reco).

## Case log
- lots-01 [PASS] module=lots route=SQL_ONLY sources=sql
- lots-02 [PASS] module=lots route=SQL_ONLY sources=sql
- lots-03 [PASS] module=lots route=SQL_ONLY sources=sql
- lots-04 [PASS] module=lots route=SQL_ONLY sources=sql
- members-01 [PASS] module=members route=SQL_ONLY sources=sql
- members-02 [PASS] module=members route=SQL_ONLY sources=sql
- members-03 [PARTIAL] module=members route=SQL_ONLY sources=sql
  - issues: fact_mismatch:expected top_member=Awa Ndiaye (1715.0 kg)
- members-04 [PARTIAL] module=members route=SQL_ONLY sources=sql
  - issues: fact_mismatch:expected top_member=Awa Ndiaye (1715.0 kg)
- rag-01 [PASS] module=rag_best_practices route=HYBRID_SQL_RAG sources=rag,sql
- rag-02 [PASS] module=rag_best_practices route=HYBRID_SQL_RAG sources=rag,sql
- rag-03 [PASS] module=rag_best_practices route=HYBRID_SQL_RAG sources=rag,sql
- rag-04 [PASS] module=rag_best_practices route=HYBRID_SQL_RAG sources=rag,sql
- stocks-01 [PARTIAL] module=stocks route=SQL_ONLY sources=sql
  - issues: fact_mismatch:expected stock_total=5510.0 kg
- stocks-02 [PARTIAL] module=stocks route=SQL_ONLY sources=sql
  - issues: fact_mismatch:expected semantic signal for stock_product
- stocks-03 [PASS] module=stocks route=SQL_ONLY sources=sql
- stocks-04 [PARTIAL] module=stocks route=SQL_ONLY sources=sql
  - issues: memory_product_missing:banane
- parcels-01 [PASS] module=parcels route=SQL_ONLY sources=sql
- parcels-02 [PASS] module=parcels route=SQL_ONLY sources=sql
- parcels-03 [PARTIAL] module=parcels route=SQL_ONLY sources=sql
  - issues: fact_mismatch:expected semantic signal for parcel_semantic
- parcels-04 [PARTIAL] module=parcels route=SQL_ONLY sources=sql
  - issues: fact_mismatch:expected semantic signal for parcel_semantic
- inputs-01 [PASS] module=inputs route=SQL_ONLY sources=sql
- inputs-02 [PASS] module=inputs route=SQL_ONLY sources=sql
- inputs-03 [PASS] module=inputs route=SQL_ONLY sources=sql
- inputs-04 [PARTIAL] module=inputs route=SQL_ONLY sources=sql
  - issues: fact_mismatch:expected semantic signal for inputs_semantic
- process-01 [PARTIAL] module=process_steps route=SQL_ONLY sources=sql
  - issues: fact_mismatch:expected top_stage=séchage
- process-02 [PASS] module=process_steps route=SQL_ONLY sources=sql
- process-03 [PASS] module=process_steps route=SQL_ONLY sources=sql
- process-04 [PARTIAL] module=process_steps route=SQL_ONLY sources=sql
  - issues: fact_mismatch:expected semantic signal for process_semantic
- mb-01 [PARTIAL] module=material_balance route=SQL_ONLY sources=sql
  - issues: fact_mismatch:expected material in=12140.0 out=11022.5 loss=9.2%
- mb-02 [PASS] module=material_balance route=SQL_ONLY sources=sql
- mb-03 [PASS] module=material_balance route=SQL_ONLY sources=sql
- mb-04 [PASS] module=material_balance route=SQL_ONLY sources=sql
- loss-01 [PASS] module=loss_efficiency route=SQL_ONLY sources=sql
- loss-02 [PASS] module=loss_efficiency route=SQL_ONLY sources=sql
- loss-03 [PASS] module=loss_efficiency route=HYBRID_SQL_RAG sources=rag,sql
- loss-04 [PASS] module=loss_efficiency route=HYBRID_SQL_RAG sources=rag,sql
- ml-01 [PASS] module=ml_risk route=HYBRID_SQL_ML sources=ml,sql
- ml-02 [PASS] module=ml_risk route=HYBRID_SQL_ML sources=ml,sql
- ml-03 [PASS] module=ml_risk route=HYBRID_SQL_ML sources=ml,sql
- ml-04 [PARTIAL] module=ml_risk route=SQL_ONLY sources=sql
  - issues: route_mismatch:SQL_ONLY not in ['HYBRID_FULL', 'HYBRID_SQL_ML', 'HYBRID_SQL_RAG', 'ML_ONLY'], missing_sources:['ml'], fact_mismatch:expected risk semantics; sql_risk_count=4
- reco-01 [PASS] module=recommendations route=HYBRID_FULL sources=ml,rag,recommendation,sql
- reco-02 [PASS] module=recommendations route=HYBRID_FULL sources=ml,rag,recommendation,sql
- reco-03 [PASS] module=recommendations route=HYBRID_FULL sources=ml,rag,recommendation,sql
- reco-04 [PASS] module=recommendations route=RECOMMENDATION_ONLY sources=ml,recommendation,sql
- biz-01 [PASS] module=business_ops route=SQL_ONLY sources=sql
- biz-02 [PASS] module=business_ops route=SQL_ONLY sources=sql
- biz-03 [PASS] module=business_ops route=SQL_ONLY sources=sql
- biz-04 [PASS] module=business_ops route=SQL_ONLY sources=sql