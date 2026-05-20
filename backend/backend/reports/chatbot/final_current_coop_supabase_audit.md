# Final Current Cooperative Supabase Audit (/chat/agent)

- Date: 2026-05-19 01:42:31
- Cooperative: `Cooperative Deggo Thies` (`4cbc6020-def9-4d24-bb75-9d40bc031466`)
- Manager: `manager@weefarm.local`
- Total cases: **70** (Basic 30 + Detailed 40)

## Test Composition
- Regression: 21
- Paraphrase: 22
- Fresh unseen: 27
- Unsupported/edge: 7

## Overall
- PASS/PARTIAL/FAIL/BLOCKED: **28/41/1/0**
- Pass rate: **40.0%**
- Handled rate (PASS+PARTIAL): **98.57%**
- Basic score: **80.0%**
- Detailed/hard score: **10.0%**

## Metrics
- Latency avg/p50/p95/max (ms): **11414.47 / 10594.88 / 18505.66 / 34627.6**
- Hallucination/off-topic count: **1**
- Source pollution count: **0**
- Unsupported refusal success rate: **100.0%**
- Chart validity rate: **100.0%**
- Memory success rate: **0.0%**
- RAG relevance score: **0.0%**
- Hybrid completeness score: **0.0%**
- Manager-style answer-quality score: **0.0%**

## Results by Capability
- charts: 0/7/0/0 (total 7)
- hybrid_full: 0/3/0/0 (total 3)
- hybrid_sql_ml: 0/4/0/0 (total 4)
- hybrid_sql_rag: 0/3/0/0 (total 3)
- hybrid_sql_reco: 0/0/1/0 (total 1)
- manager_style: 0/2/0/0 (total 2)
- memory: 0/6/0/0 (total 6)
- ml: 2/1/0/0 (total 3)
- phase3: 7/7/0/0 (total 14)
- rag: 0/3/0/0 (total 3)
- recommendations: 0/2/0/0 (total 2)
- sql: 12/3/0/0 (total 15)
- unsupported: 7/0/0/0 (total 7)

## Results by Test Type
- fresh: 14/13/0/0 (total 27)
- paraphrase: 6/15/1/0 (total 22)
- regression: 8/13/0/0 (total 21)

## Comparison vs Previous Key Result
- Previous: 64 cases, PASS/PARTIAL/FAIL = 60/2/2
- Current: 70 cases, PASS/PARTIAL/FAIL = 28/41/1

## Top 5 Strongest Behaviors
- unsupported: 7/7 PASS
- sql: 12/15 PASS
- ml: 2/3 PASS
- phase3: 7/14 PASS
- recommendations: 0/2 PASS

## Top 5 Weakest Behaviors
- b07 (sql): PARTIAL missing_token:perte,missing_token:étape
- b11 (sql): PARTIAL missing_token:transaction
- b17 (recommendations): PARTIAL missing_token:recommand
- b18 (rag): PARTIAL missing_token:pratique
- b19 (charts): PARTIAL missing_token:graphique

## Remaining Blockers
- d11 hybrid_sql_reco: wrong_route:SQL_ONLY

## Honest Readiness Rating
- **near-final app-data assistant**

## Case Table
|id|level|type|capability|route|score|latency_ms|reason|
|---|---|---|---|---|---|---:|---|
|b01|basic|regression|sql|SQL_ONLY|PASS|14189.68||
|b02|basic|paraphrase|sql|SQL_ONLY|PASS|10064.36||
|b03|basic|regression|sql|SQL_ONLY|PASS|8958.43||
|b04|basic|paraphrase|sql|SQL_ONLY|PASS|9075.95||
|b05|basic|fresh|sql|SQL_ONLY|PASS|10630.52||
|b06|basic|fresh|sql|SQL_ONLY|PASS|8706.02||
|b07|basic|paraphrase|sql|SQL_ONLY|PARTIAL|8351.47|missing_token:perte,missing_token:étape|
|b08|basic|fresh|sql|SQL_ONLY|PASS|7994.46||
|b09|basic|regression|sql|SQL_ONLY|PASS|8944.84||
|b10|basic|fresh|sql|SQL_ONLY|PASS|9485.18||
|b11|basic|regression|sql|SQL_ONLY|PARTIAL|17344.6|missing_token:transaction|
|b12|basic|paraphrase|sql|SQL_ONLY|PASS|11806.04||
|b13|basic|paraphrase|sql|SQL_ONLY|PASS|13640.62||
|b14|basic|fresh|sql|SQL_ONLY|PASS|14701.5||
|b15|basic|regression|ml|HYBRID_SQL_ML|PASS|9380.93||
|b16|basic|regression|ml|HYBRID_SQL_ML|PASS|8259.55||
|b17|basic|regression|recommendations|RECOMMENDATION_ONLY|PARTIAL|1991.63|missing_token:recommand|
|b18|basic|regression|rag|HYBRID_SQL_RAG|PARTIAL|14668.41|missing_token:pratique|
|b19|basic|paraphrase|charts|SQL_ONLY|PARTIAL|10075.78|missing_token:graphique|
|b20|basic|fresh|phase3|SQL_ONLY|PASS|8610.65||
|b21|basic|paraphrase|phase3|SQL_ONLY|PASS|8381.72||
|b22|basic|fresh|phase3|SQL_ONLY|PASS|10376.56||
|b23|basic|paraphrase|phase3|SQL_ONLY|PASS|12433.65||
|b24|basic|fresh|phase3|SQL_ONLY|PASS|16139.26||
|b25|basic|fresh|phase3|SQL_ONLY|PASS|10559.24||
|b26|basic|fresh|phase3|SQL_ONLY|PASS|13318.62||
|b27|basic|fresh|phase3|SQL_ONLY|PARTIAL|13386.99|missing_token:facture|
|b28|basic|regression|unsupported|OUT_OF_SCOPE|PASS|1566.57||
|b29|basic|regression|unsupported|OUT_OF_SCOPE|PASS|3531.94||
|b30|basic|regression|unsupported|OUT_OF_SCOPE|PASS|2756.31||
|d01|detailed|regression|phase3|SQL_ONLY|PARTIAL|9034.97|missing_token:mouvement,manager_structure_missing|
|d02|detailed|regression|phase3|SQL_ONLY|PARTIAL|9276.97|manager_structure_missing|
|d03|detailed|regression|phase3|SQL_ONLY|PARTIAL|9301.18|manager_structure_missing|
|d04|detailed|regression|phase3|SQL_ONLY|PARTIAL|13233.86|manager_structure_missing|
|d05|detailed|regression|phase3|SQL_ONLY|PARTIAL|10352.86|manager_structure_missing|
|d06|detailed|regression|phase3|SQL_ONLY|PARTIAL|12732.88|manager_structure_missing|
|d07|detailed|regression|hybrid_sql_ml|HYBRID_SQL_ML|PARTIAL|8436.44|missing_token:perte,missing_token:ml,manager_structure_missing|
|d08|detailed|regression|hybrid_sql_ml|HYBRID_SQL_ML|PARTIAL|8196.24|manager_structure_missing|
|d09|detailed|regression|hybrid_sql_rag|HYBRID_SQL_RAG|PARTIAL|34627.6|missing_token:perte,missing_token:pratique,manager_structure_missing|
|d10|detailed|regression|hybrid_full|HYBRID_FULL|PARTIAL|13288.03|missing_token:action,missing_token:sql,manager_structure_missing|
|d11|detailed|paraphrase|hybrid_sql_reco|SQL_ONLY|FAIL|14268.9|wrong_route:SQL_ONLY|
|d12|detailed|paraphrase|hybrid_sql_rag|HYBRID_SQL_RAG|PARTIAL|20849.44|missing_token:améliorer,manager_structure_missing|
|d13|detailed|paraphrase|hybrid_sql_ml|HYBRID_SQL_ML|PARTIAL|16889.66|manager_structure_missing|
|d14|detailed|paraphrase|hybrid_full|HYBRID_FULL|PARTIAL|13133.99|manager_structure_missing|
|d15|detailed|paraphrase|manager_style|HYBRID_FULL|PARTIAL|18349.84|missing_token:preuve,manager_structure_missing|
|d16|detailed|paraphrase|manager_style|HYBRID_FULL|PARTIAL|18505.66|manager_structure_missing|
|d17|detailed|paraphrase|rag|HYBRID_SQL_RAG|PARTIAL|23968.25|missing_token:emballage,missing_token:casse,manager_structure_missing|
|d18|detailed|paraphrase|rag|HYBRID_SQL_RAG|PARTIAL|18491.73|missing_token:conditionnement,missing_token:perte,manager_structure_missing|
|d19|detailed|paraphrase|charts|SQL_ONLY|PARTIAL|11905.7|missing_token:graphique,manager_structure_missing|
|d20|detailed|paraphrase|charts|SQL_ONLY|PARTIAL|9065.62|manager_structure_missing|
|d21|detailed|paraphrase|charts|SQL_ONLY|PARTIAL|11228.7|manager_structure_missing|
|d22|detailed|paraphrase|charts|HYBRID_SQL_ML|PARTIAL|11811.44|manager_structure_missing|
|d23|detailed|paraphrase|charts|HYBRID_SQL_ML|PARTIAL|12210.98|manager_structure_missing|
|d24|detailed|paraphrase|charts|HYBRID_FULL|PARTIAL|11050.14|manager_structure_missing|
|d25|detailed|fresh|memory|SQL_ONLY|PARTIAL|12526.93|manager_structure_missing|
|d26|detailed|fresh|memory|HYBRID_SQL_ML|PARTIAL|10085.87|manager_structure_missing|
|d27|detailed|fresh|memory|HYBRID_SQL_RAG|PARTIAL|18411.22|manager_structure_missing|
|d28|detailed|fresh|memory|HYBRID_SQL_ML|PARTIAL|16150.35|missing_token:produit,missing_token:stock,manager_structure_missing|
|d29|detailed|fresh|memory|SQL_ONLY|PARTIAL|8719.37|manager_structure_missing|
|d30|detailed|fresh|memory|SQL_ONLY|PARTIAL|12058.54|manager_structure_missing|
|d31|detailed|fresh|unsupported|OUT_OF_SCOPE|PASS|1536.92||
|d32|detailed|fresh|unsupported|OUT_OF_SCOPE|PASS|1567.56||
|d33|detailed|fresh|unsupported|OUT_OF_SCOPE|PASS|1696.27||
|d34|detailed|fresh|unsupported|OUT_OF_SCOPE|PASS|1621.74||
|d35|detailed|fresh|sql|SQL_ONLY|PARTIAL|8738.0|manager_structure_missing|
|d36|detailed|fresh|ml|HYBRID_SQL_ML|PARTIAL|8402.16|manager_structure_missing|
|d37|detailed|fresh|recommendations|HYBRID_FULL|PARTIAL|16273.7|manager_structure_missing|
|d38|detailed|fresh|hybrid_full|HYBRID_FULL|PARTIAL|13687.22|manager_structure_missing|
|d39|detailed|fresh|hybrid_sql_rag|HYBRID_SQL_RAG|PARTIAL|19253.2|manager_structure_missing|
|d40|detailed|fresh|hybrid_sql_ml|HYBRID_SQL_ML|PARTIAL|8741.57|missing_token:indisponible,manager_structure_missing|