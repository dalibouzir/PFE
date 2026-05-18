# Final Current Cooperative Supabase Audit (/chat/agent)

- Date: 2026-05-18 12:09:13
- Cooperative: `Cooperative Deggo Thies` (`4cbc6020-def9-4d24-bb75-9d40bc031466`)
- Manager: `manager@weefarm.local`
- Total cases: **70** (Basic 30 + Detailed 40)

## Test Composition
- Regression: 21
- Paraphrase: 22
- Fresh unseen: 27
- Unsupported/edge: 7

## Overall
- PASS/PARTIAL/FAIL/BLOCKED: **48/21/1/0**
- Pass rate: **68.57%**
- Handled rate (PASS+PARTIAL): **98.57%**
- Basic score: **80.0%**
- Detailed/hard score: **60.0%**

## Metrics
- Latency avg/p50/p95/max (ms): **8772.86 / 9423.15 / 12329.89 / 14292.36**
- Hallucination/off-topic count: **1**
- Source pollution count: **0**
- Unsupported refusal success rate: **100.0%**
- Chart validity rate: **100.0%**
- Memory success rate: **50.0%**
- RAG relevance score: **33.33%**
- Hybrid completeness score: **36.36%**
- Manager-style answer-quality score: **100.0%**

## Results by Capability
- charts: 6/1/0/0 (total 7)
- hybrid_full: 0/3/0/0 (total 3)
- hybrid_sql_ml: 3/1/0/0 (total 4)
- hybrid_sql_rag: 0/2/1/0 (total 3)
- hybrid_sql_reco: 1/0/0/0 (total 1)
- manager_style: 2/0/0/0 (total 2)
- memory: 3/3/0/0 (total 6)
- ml: 2/1/0/0 (total 3)
- phase3: 11/3/0/0 (total 14)
- rag: 1/2/0/0 (total 3)
- recommendations: 1/1/0/0 (total 2)
- sql: 11/4/0/0 (total 15)
- unsupported: 7/0/0/0 (total 7)

## Results by Test Type
- fresh: 15/12/0/0 (total 27)
- paraphrase: 15/6/1/0 (total 22)
- regression: 18/3/0/0 (total 21)

## Comparison vs Previous Key Result
- Previous: 64 cases, PASS/PARTIAL/FAIL = 60/2/2
- Current: 70 cases, PASS/PARTIAL/FAIL = 48/21/1

## Top 5 Strongest Behaviors
- unsupported: 7/7 PASS
- hybrid_sql_reco: 1/1 PASS
- manager_style: 2/2 PASS
- charts: 6/7 PASS
- phase3: 11/14 PASS

## Top 5 Weakest Behaviors
- b02 (sql): PARTIAL missing_token:parcelle
- b03 (sql): PARTIAL missing_token:collecte
- b04 (sql): PARTIAL missing_token:kg
- b20 (phase3): PARTIAL missing_token:quant
- b26 (phase3): PARTIAL missing_token:commande

## Remaining Blockers
- d12 hybrid_sql_rag: wrong_route:RAG_ONLY

## Honest Readiness Rating
- **near-final app-data assistant**

## Case Table
|id|level|type|capability|route|score|latency_ms|reason|
|---|---|---|---|---|---|---:|---|
|b01|basic|regression|sql|SQL_ONLY|PASS|10225.24||
|b02|basic|paraphrase|sql|SQL_ONLY|PARTIAL|10561.67|missing_token:parcelle|
|b03|basic|regression|sql|SQL_ONLY|PARTIAL|9283.53|missing_token:collecte|
|b04|basic|paraphrase|sql|SQL_ONLY|PARTIAL|9963.91|missing_token:kg|
|b05|basic|fresh|sql|SQL_ONLY|PASS|9813.68||
|b06|basic|fresh|sql|SQL_ONLY|PASS|8750.2||
|b07|basic|paraphrase|sql|SQL_ONLY|PASS|10155.87||
|b08|basic|fresh|sql|SQL_ONLY|PASS|12421.87||
|b09|basic|regression|sql|SQL_ONLY|PASS|11216.01||
|b10|basic|fresh|sql|SQL_ONLY|PASS|10977.63||
|b11|basic|regression|sql|SQL_ONLY|PASS|11195.31||
|b12|basic|paraphrase|sql|SQL_ONLY|PASS|9948.61||
|b13|basic|paraphrase|sql|SQL_ONLY|PASS|11058.4||
|b14|basic|fresh|sql|SQL_ONLY|PASS|10502.09||
|b15|basic|regression|ml|HYBRID_SQL_ML|PASS|8867.21||
|b16|basic|regression|ml|HYBRID_SQL_ML|PASS|8807.59||
|b17|basic|regression|recommendations|RECOMMENDATION_ONLY|PASS|2218.7||
|b18|basic|regression|rag|RAG_ONLY|PASS|2399.13||
|b19|basic|paraphrase|charts|SQL_ONLY|PASS|8844.3||
|b20|basic|fresh|phase3|SQL_ONLY|PARTIAL|10916.82|missing_token:quant|
|b21|basic|paraphrase|phase3|SQL_ONLY|PASS|9112.59||
|b22|basic|fresh|phase3|SQL_ONLY|PASS|8886.71||
|b23|basic|paraphrase|phase3|SQL_ONLY|PASS|10999.11||
|b24|basic|fresh|phase3|SQL_ONLY|PASS|11387.8||
|b25|basic|fresh|phase3|SQL_ONLY|PASS|11294.34||
|b26|basic|fresh|phase3|SQL_ONLY|PARTIAL|10667.96|missing_token:commande|
|b27|basic|fresh|phase3|SQL_ONLY|PARTIAL|14292.36|missing_token:facture|
|b28|basic|regression|unsupported|OUT_OF_SCOPE|PASS|1586.25||
|b29|basic|regression|unsupported|OUT_OF_SCOPE|PASS|1592.79||
|b30|basic|regression|unsupported|OUT_OF_SCOPE|PASS|1561.71||
|d01|detailed|regression|phase3|SQL_ONLY|PASS|9060.67||
|d02|detailed|regression|phase3|SQL_ONLY|PASS|8856.11||
|d03|detailed|regression|phase3|SQL_ONLY|PASS|9796.24||
|d04|detailed|regression|phase3|SQL_ONLY|PASS|11718.29||
|d05|detailed|regression|phase3|SQL_ONLY|PASS|12068.67||
|d06|detailed|regression|phase3|SQL_ONLY|PASS|13480.48||
|d07|detailed|regression|hybrid_sql_ml|HYBRID_SQL_ML|PASS|9119.03||
|d08|detailed|regression|hybrid_sql_ml|HYBRID_SQL_ML|PASS|8679.99||
|d09|detailed|regression|hybrid_sql_rag|HYBRID_SQL_RAG|PARTIAL|9506.49|missing_token:pratique|
|d10|detailed|regression|hybrid_full|HYBRID_FULL|PARTIAL|9982.02|missing_token:ml|
|d11|detailed|paraphrase|hybrid_sql_reco|HYBRID_FULL|PASS|12436.31||
|d12|detailed|paraphrase|hybrid_sql_rag|RAG_ONLY|FAIL|2385.07|wrong_route:RAG_ONLY|
|d13|detailed|paraphrase|hybrid_sql_ml|HYBRID_SQL_ML|PASS|8769.15||
|d14|detailed|paraphrase|hybrid_full|HYBRID_FULL|PARTIAL|10104.91|missing_token:conclusion|
|d15|detailed|paraphrase|manager_style|HYBRID_FULL|PASS|10060.22||
|d16|detailed|paraphrase|manager_style|HYBRID_FULL|PASS|10062.42||
|d17|detailed|paraphrase|rag|RAG_ONLY|PARTIAL|2269.25|missing_token:emballage,missing_token:casse|
|d18|detailed|paraphrase|rag|RAG_ONLY|PARTIAL|2200.6|missing_token:perte|
|d19|detailed|paraphrase|charts|SQL_ONLY|PARTIAL|8692.51|missing_token:graphique|
|d20|detailed|paraphrase|charts|SQL_ONLY|PASS|8987.35||
|d21|detailed|paraphrase|charts|SQL_ONLY|PASS|8692.67||
|d22|detailed|paraphrase|charts|HYBRID_SQL_ML|PASS|9953.92||
|d23|detailed|paraphrase|charts|HYBRID_SQL_ML|PASS|8839.34||
|d24|detailed|paraphrase|charts|HYBRID_FULL|PASS|10821.28||
|d25|detailed|fresh|memory|SQL_ONLY|PASS|9020.41||
|d26|detailed|fresh|memory|HYBRID_SQL_ML|PARTIAL|8725.4|missing_token:premier|
|d27|detailed|fresh|memory|HYBRID_SQL_RAG|PARTIAL|9286.64|missing_token:conseil|
|d28|detailed|fresh|memory|HYBRID_SQL_ML|PARTIAL|9408.21|missing_token:produit|
|d29|detailed|fresh|memory|SQL_ONLY|PASS|8870.46||
|d30|detailed|fresh|memory|SQL_ONLY|PASS|11999.34||
|d31|detailed|fresh|unsupported|OUT_OF_SCOPE|PASS|1738.75||
|d32|detailed|fresh|unsupported|OUT_OF_SCOPE|PASS|2825.22||
|d33|detailed|fresh|unsupported|OUT_OF_SCOPE|PASS|1824.03||
|d34|detailed|fresh|unsupported|OUT_OF_SCOPE|PASS|1652.15||
|d35|detailed|fresh|sql|SQL_ONLY|PARTIAL|11020.05|missing_token:efficacité|
|d36|detailed|fresh|ml|HYBRID_SQL_ML|PARTIAL|8683.63|missing_token:anomaly|
|d37|detailed|fresh|recommendations|HYBRID_FULL|PARTIAL|12080.35|missing_token:priorit|
|d38|detailed|fresh|hybrid_full|HYBRID_FULL|PARTIAL|12329.89|missing_token:ml|
|d39|detailed|fresh|hybrid_sql_rag|HYBRID_SQL_RAG|PARTIAL|9438.1|missing_token:pratique|
|d40|detailed|fresh|hybrid_sql_ml|HYBRID_SQL_ML|PARTIAL|9145.47|missing_token:indisponible|