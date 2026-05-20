# Chatbot Unseen Generalization Audit

- Date: 2026-05-20T02:14:15.273723+00:00
- Cooperative: 4cbc6020-def9-4d24-bb75-9d40bc031466
- Total unseen cases: 65
- PASS/PARTIAL/FAIL: 59/5/1

## Category Breakdown
- multi_request: PASS 20 | PARTIAL 0 | FAIL 0
- entity_anchor: PASS 10 | PARTIAL 5 | FAIL 0
- rag_hybrid: PASS 10 | PARTIAL 0 | FAIL 0
- ui_unsupported: PASS 10 | PARTIAL 0 | FAIL 0
- memory_flow: PASS 9 | PARTIAL 0 | FAIL 1

## Top 10 Failure Patterns
- anchor_not_mentioned: 5
- wrong_route:OUT_OF_SCOPE: 1

## Case Results
|id|category|route|score|reasons|
|---|---|---|---|---|
|m01|multi_request|SQL_ONLY|PASS||
|m02|multi_request|SQL_ONLY|PASS||
|m03|multi_request|SQL_ONLY|PASS||
|m04|multi_request|SQL_ONLY|PASS||
|m05|multi_request|SQL_ONLY|PASS||
|m06|multi_request|SQL_ONLY|PASS||
|m07|multi_request|SQL_ONLY|PASS||
|m08|multi_request|HYBRID_SQL_RAG|PASS||
|m09|multi_request|SQL_ONLY|PASS||
|m10|multi_request|HYBRID_FULL|PASS||
|m11|multi_request|SQL_ONLY|PASS||
|m12|multi_request|SQL_ONLY|PASS||
|m13|multi_request|SQL_ONLY|PASS||
|m14|multi_request|SQL_ONLY|PASS||
|m15|multi_request|SQL_ONLY|PASS||
|m16|multi_request|HYBRID_SQL_ML|PASS||
|m17|multi_request|HYBRID_SQL_RAG|PASS||
|m18|multi_request|SQL_ONLY|PASS||
|m19|multi_request|SQL_ONLY|PASS||
|m20|multi_request|HYBRID_FULL|PASS||
|e01|entity_anchor|HYBRID_SQL_ML|PASS||
|e02|entity_anchor|HYBRID_FULL|PASS||
|e03|entity_anchor|HYBRID_SQL_RAG|PARTIAL|anchor_not_mentioned|
|e04|entity_anchor|HYBRID_SQL_RAG|PARTIAL|anchor_not_mentioned|
|e05|entity_anchor|HYBRID_SQL_ML|PASS||
|e06|entity_anchor|HYBRID_FULL|PASS||
|e07|entity_anchor|HYBRID_FULL|PASS||
|e08|entity_anchor|HYBRID_SQL_ML|PASS||
|e09|entity_anchor|SQL_ONLY|PARTIAL|anchor_not_mentioned|
|e10|entity_anchor|HYBRID_FULL|PASS||
|e11|entity_anchor|SQL_ONLY|PASS||
|e12|entity_anchor|HYBRID_SQL_ML|PASS||
|e13|entity_anchor|HYBRID_FULL|PARTIAL|anchor_not_mentioned|
|e14|entity_anchor|SQL_ONLY|PARTIAL|anchor_not_mentioned|
|e15|entity_anchor|SQL_ONLY|PASS||
|r01|rag_hybrid|HYBRID_SQL_RAG|PASS||
|r02|rag_hybrid|HYBRID_SQL_RAG|PASS||
|r03|rag_hybrid|HYBRID_SQL_RAG|PASS||
|r04|rag_hybrid|RAG_ONLY|PASS||
|r05|rag_hybrid|HYBRID_SQL_RAG|PASS||
|r06|rag_hybrid|HYBRID_SQL_RAG|PASS||
|r07|rag_hybrid|HYBRID_SQL_RAG|PASS||
|r08|rag_hybrid|HYBRID_SQL_RAG|PASS||
|r09|rag_hybrid|HYBRID_SQL_RAG|PASS||
|r10|rag_hybrid|HYBRID_SQL_RAG|PASS||
|u01|ui_unsupported|OUT_OF_SCOPE|PASS||
|u02|ui_unsupported|OUT_OF_SCOPE|PASS||
|u03|ui_unsupported|OUT_OF_SCOPE|PASS||
|u04|ui_unsupported|OUT_OF_SCOPE|PASS||
|u05|ui_unsupported|OUT_OF_SCOPE|PASS||
|u06|ui_unsupported|OUT_OF_SCOPE|PASS||
|u07|ui_unsupported|OUT_OF_SCOPE|PASS||
|u08|ui_unsupported|OUT_OF_SCOPE|PASS||
|u09|ui_unsupported|OUT_OF_SCOPE|PASS||
|u10|ui_unsupported|OUT_OF_SCOPE|PASS||
|f1-1|memory_flow|SQL_ONLY|PASS||
|f1-2|memory_flow|RECOMMENDATION_ONLY|PASS||
|f2-1|memory_flow|OUT_OF_SCOPE|FAIL|wrong_route:OUT_OF_SCOPE|
|f2-2|memory_flow|HYBRID_SQL_ML|PASS||
|f3-1|memory_flow|SQL_ONLY|PASS||
|f3-2|memory_flow|HYBRID_SQL_ML|PASS||
|f4-1|memory_flow|SQL_ONLY|PASS||
|f4-2|memory_flow|SQL_ONLY|PASS||
|f5-1|memory_flow|SQL_ONLY|PASS||
|f5-2|memory_flow|HYBRID_SQL_RAG|PASS||