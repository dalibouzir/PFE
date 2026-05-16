# Final Supabase Quality Audit - /chat/agent

## 1. Executive summary
- Total cases: **64**
- PASS / PARTIAL / FAIL / BLOCKED: **60 / 2 / 2 / 0**
- Overall pass rate: **93.8%**
- Handled rate: **93.8%**
- Overfitting risk: **LOW**
- Honest readiness rating: **PFE-defense-ready**

## 2. Supabase runtime verification
- audit_mode: `None`
- db_dialect: `postgresql`
- masked_url: `aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require`
- provider: `Supabase PostgreSQL`
- pgvector: `True`
- authenticated_user_email: `manager@weefarm.local`
- cooperative_id: `356f4e38-f4f8-4559-a005-0a9c10366d37`

## 3. Dataset row counts
- members: `17`
- parcels: `18`
- inputs: `76`
- stocks: `7`
- batches: `387`
- process_steps: `1517`
- commercial_orders: `14`
- commercial_invoices: `8`
- global_charges: `24`
- recommendations: `14`
- ml_prediction_logs: `1530`
- rag_documents: `583`
- rag_chunks: `589`

## 4. Test set composition
- regression: 16
- paraphrase: 22
- fresh unseen: 20
- unsupported/edge: 6

## 5. Overall metrics
- factual accuracy rate (proxy): 100.0%
- route/tool correctness rate: 96.9%
- source relevance rate (proxy): 100.0%
- evidence-layer completeness rate (proxy): 96.9%
- hallucination/off-topic count: 2
- generic fallback misuse count: 0
- clean unsupported refusal rate: 80.0%
- memory reuse success rate: 100.0%
- memory reset success rate: 100.0%
- chart validity rate: 100.0%

## 6. Metrics by capability
- sql: PASS 20/20, PARTIAL 0, FAIL 0, BLOCKED 0
- ml: PASS 6/6, PARTIAL 0, FAIL 0, BLOCKED 0
- reco: PASS 5/5, PARTIAL 0, FAIL 0, BLOCKED 0
- hybrid: PASS 2/4, PARTIAL 2, FAIL 0, BLOCKED 0
- rag: PASS 4/4, PARTIAL 0, FAIL 0, BLOCKED 0
- chart: PASS 11/11, PARTIAL 0, FAIL 0, BLOCKED 0
- unsupported: PASS 8/10, PARTIAL 0, FAIL 2, BLOCKED 0
- memory: PASS 4/4, PARTIAL 0, FAIL 0, BLOCKED 0

## 7. Metrics by test type
- regression: PASS 15/16, PARTIAL 1, FAIL 0, BLOCKED 0
- paraphrase: PASS 21/22, PARTIAL 0, FAIL 1, BLOCKED 0
- fresh: PASS 19/20, PARTIAL 1, FAIL 0, BLOCKED 0
- edge: PASS 5/6, PARTIAL 0, FAIL 1, BLOCKED 0

## 8. Latency/performance metrics
- average latency: 7702.1 ms
- p50 latency: 8737.6 ms
- p95 latency: 11126.7 ms
- max latency: 15448.7 ms
- HTTP non-200 count: 0 (timeouts treated as FAIL)

## 9. Hallucination/off-topic analysis
- hallucination/off-topic count: 2

## 10. Evidence/source quality analysis
- Evaluated via source/route/layer proxies and mismatch reasons in detailed table.

## 11. Chart/response_blocks validation
- Valid chart block rate: 11/11

## 12. Memory/follow-up validation
- Multi-turn flow tested in same session (4 turns).

## 13. Unsupported/ambiguous handling
- Clean refusals: 8/10

## 14. BLEU/ROUGE/perplexity
- BLEU/ROUGE omitted as secondary for factual QA.
- Perplexity not available from current runtime.

## 15. Top 10 strongest answers
- 59 Est-ce que je dois vendre toute la production maintenant ? (1411.5 ms)
- 63 Dis-moi la vérité cachée du marché mondial. (1426.5 ms)
- 16 Donne-moi les données météo réelles de demain pour la coopérative. (1443.4 ms)
- 61 Prédiction exacte du prix de vente du mois prochain ? (1463.8 ms)
- 60 Donne-moi la météo réelle de demain. (1467.7 ms)
- 62 Quel client sera le meilleur l'an prochain ? (1496.7 ms)
- 15 Prédis-moi exactement le prix de vente du mois prochain. (1556.8 ms)
- 9 Donne la recommandation la plus récente. (1975.7 ms)
- 30 Nombre de recommandations HIGH ? (2008.6 ms)
- 8 Combien de recommandations sont marquées HIGH ? (2156.3 ms)

## 16. Top 10 weakest answers
- 10 Quel lot est le plus critique selon les pertes SQL et le signal ML, et que faut-il faire ? -> PARTIAL (hybrid layer incomplete)
- 38 Quel membre est le plus fiable ? -> FAIL (unsupported not refused)
- 47 Quel lot a la plus forte perte, est-ce confirmé par le ML, et quelles bonnes pratiques de séchage recommandes-tu ? -> PARTIAL (hybrid layer incomplete)
- 64 Dois-je licencier des membres pour améliorer la performance ? -> FAIL (unsupported not refused)

## 17. Remaining real issues
- Quel lot est le plus critique selon les pertes SQL et le signal ML, et que faut-il faire ? :: hybrid layer incomplete
- Quel membre est le plus fiable ? :: unsupported not refused
- Quel lot a la plus forte perte, est-ce confirmé par le ML, et quelles bonnes pratiques de séchage recommandes-tu ? :: hybrid layer incomplete
- Dois-je licencier des membres pour améliorer la performance ? :: unsupported not refused

## 18. True Supabase data gaps, if any
- None flagged as BLOCKED in this run.

## 19. Before/after summary
- Recent fixes preserved stock/process/reco charts and improved broad chart intent coverage.

## 20. Honest readiness rating
- **PFE-defense-ready**

## 21. Recommended next fixes
1. Reduce fallback/partial on factual intents via stricter deterministic operation detection.
2. Improve hybrid layer completeness enforcement for SQL+ML+RAG+actions prompts.
3. Lower latency and timeout frequency on long hybrid queries.

## Detailed case table
|#|type|capability|route|status|latency_ms|reason|
|---:|---|---|---|---|---:|---|
|1|regression|sql|SQL_ONLY|PASS|9788.36||
|2|regression|sql|SQL_ONLY|PASS|10051.28||
|3|regression|sql|SQL_ONLY|PASS|9340.55||
|4|regression|sql|SQL_ONLY|PASS|9079.38||
|5|regression|sql|SQL_ONLY|PASS|8829.95||
|6|regression|ml|HYBRID_SQL_ML|PASS|9642.31||
|7|regression|ml|HYBRID_SQL_ML|PASS|9016.9||
|8|regression|reco|RECOMMENDATION_ONLY|PASS|2156.34||
|9|regression|reco|RECOMMENDATION_ONLY|PASS|1975.73||
|10|regression|hybrid|HYBRID_SQL_RAG|PARTIAL|10673.19|hybrid layer incomplete|
|11|regression|rag|RAG_ONLY|PASS|2610.35||
|12|regression|chart|SQL_ONLY|PASS|8862.87||
|13|regression|chart|SQL_ONLY|PASS|8862.15||
|14|regression|chart|SQL_ONLY|PASS|8697.47||
|15|regression|unsupported|OUT_OF_SCOPE|PASS|1556.83||
|16|regression|unsupported|OUT_OF_SCOPE|PASS|1443.44||
|17|paraphrase|sql|SQL_ONLY|PASS|8689.81||
|18|paraphrase|sql|SQL_ONLY|PASS|8275.47||
|19|paraphrase|sql|SQL_ONLY|PASS|8634.45||
|20|paraphrase|sql|SQL_ONLY|PASS|9732.65||
|21|paraphrase|sql|SQL_ONLY|PASS|11403.66||
|22|paraphrase|sql|SQL_ONLY|PASS|10934.45||
|23|paraphrase|sql|SQL_ONLY|PASS|15448.68||
|24|paraphrase|sql|SQL_ONLY|PASS|8352.41||
|25|paraphrase|sql|SQL_ONLY|PASS|8339.3||
|26|paraphrase|sql|SQL_ONLY|PASS|8553.7||
|27|paraphrase|sql|SQL_ONLY|PASS|8649.69||
|28|paraphrase|ml|HYBRID_SQL_ML|PASS|8650.25||
|29|paraphrase|ml|HYBRID_SQL_ML|PASS|8937.25||
|30|paraphrase|reco|RECOMMENDATION_ONLY|PASS|2008.57||
|31|paraphrase|hybrid|HYBRID_FULL|PASS|10309.18||
|32|paraphrase|rag|RAG_ONLY|PASS|2380.98||
|33|paraphrase|chart|SQL_ONLY|PASS|8421.63||
|34|paraphrase|chart|SQL_ONLY|PASS|9226.15||
|35|paraphrase|chart|HYBRID_SQL_RAG|PASS|9569.17||
|36|paraphrase|chart|HYBRID_SQL_ML|PASS|9721.32||
|37|paraphrase|unsupported|OUT_OF_SCOPE|PASS|3823.32||
|38|paraphrase|unsupported|SQL_ONLY|FAIL|8777.75|unsupported not refused|
|39|fresh|sql|SQL_ONLY|PASS|8789.27||
|40|fresh|sql|SQL_ONLY|PASS|8604.17||
|41|fresh|sql|SQL_ONLY|PASS|8345.0||
|42|fresh|sql|SQL_ONLY|PASS|9783.89||
|43|fresh|ml|HYBRID_SQL_ML|PASS|8553.62||
|44|fresh|ml|HYBRID_SQL_ML|PASS|9578.8||
|45|fresh|reco|HYBRID_FULL|PASS|10252.62||
|46|fresh|reco|HYBRID_FULL|PASS|11408.08||
|47|fresh|hybrid|HYBRID_SQL_RAG|PARTIAL|11126.7|hybrid layer incomplete|
|48|fresh|hybrid|HYBRID_FULL|PASS|10026.69||
|49|fresh|rag|RAG_ONLY|PASS|2401.87||
|50|fresh|rag|RAG_ONLY|PASS|2400.75||
|51|fresh|chart|SQL_ONLY|PASS|8392.02||
|52|fresh|chart|HYBRID_FULL|PASS|9748.71||
|53|fresh|chart|SQL_ONLY|PASS|8581.01||
|54|fresh|chart|SQL_ONLY|PASS|8570.98||
|55|fresh|memory|SQL_ONLY|PASS|9606.75||
|56|fresh|memory|HYBRID_SQL_RAG|PASS|9433.89||
|57|fresh|memory|HYBRID_FULL|PASS|10104.59||
|58|fresh|memory|SQL_ONLY|PASS|10415.65||
|59|edge|unsupported|OUT_OF_SCOPE|PASS|1411.54||
|60|edge|unsupported|OUT_OF_SCOPE|PASS|1467.72||
|61|edge|unsupported|OUT_OF_SCOPE|PASS|1463.81||
|62|edge|unsupported|OUT_OF_SCOPE|PASS|1496.68||
|63|edge|unsupported|OUT_OF_SCOPE|PASS|1426.48||
|64|edge|unsupported|SQL_ONLY|FAIL|8114.89|unsupported not refused|