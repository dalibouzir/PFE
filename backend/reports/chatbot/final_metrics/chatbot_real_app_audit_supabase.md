# Supabase Real-App Chatbot Audit

- Timestamp UTC: 2026-05-13T19:16:48.862904+00:00
- Audit mode: supabase_readonly
- Database dialect: postgresql
- Database provider: Supabase PostgreSQL
- URL masked: aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require
- pgvector extension installed: True
- RAG tables accessible: rag_documents=True, rag_chunks=True

## Overall Result

- Total cases: 12
- PASS: 12
- PARTIAL: 0
- FAIL: 0
- Overall verdict: PASS

## Case Results

### SQL-MEMBERS-COUNT [PASS] score=1.0
- Domain: members
- HTTP status: 200
- Route: SQL_ONLY
- Source types: sql
- response_blocks: sources, summary, warnings
- Question: Combien de membres sont inscrits dans ma coopérative ?

### SQL-MEMBERS-TOP-KG [PASS] score=1.0
- Domain: members
- HTTP status: 200
- Route: SQL_ONLY
- Source types: sql
- response_blocks: sources, summary, table, warnings
- Question: Classe les membres par kg collectés, du plus élevé au plus faible.

### SQL-STOCKS [PASS] score=1.0
- Domain: stocks
- HTTP status: 200
- Route: SQL_ONLY
- Source types: sql
- response_blocks: sources, summary, table, warnings
- Question: Quel est le stock actuel par produit en kg ?

### SQL-COMMERCIAL [PASS] score=1.0
- Domain: commercial
- HTTP status: 200
- Route: SQL_ONLY
- Source types: sql
- response_blocks: sources, summary, warnings
- Question: Combien de commandes commerciales et combien de factures avons-nous ?

### SQL-BATCHES [PASS] score=1.0
- Domain: batches
- HTTP status: 200
- Route: SQL_ONLY
- Source types: sql
- response_blocks: sources, summary, warnings
- Question: Combien de lots au total et combien sont encore en cours ?

### SQL-PROCESS-STEPS [PASS] score=1.0
- Domain: process_steps
- HTTP status: 200
- Route: SQL_ONLY
- Source types: sql
- response_blocks: sources, summary, table, warnings
- Question: Quelles étapes du process génèrent les plus grandes pertes ?

### SQL-EFFICIENCY [PASS] score=1.0
- Domain: efficiency
- HTTP status: 200
- Route: SQL_ONLY
- Source types: sql
- response_blocks: sources, summary, table, warnings
- Question: Quels lots ont une faible efficacité de rendement ?

### SQL-MATERIAL-BALANCE [PASS] score=1.0
- Domain: material_balance
- HTTP status: 200
- Route: SQL_ONLY
- Source types: sql
- response_blocks: sources, summary, warnings
- Question: Donne le bilan matière global (entrée/sortie/perte) des lots.

### HYBRID-ML-RISK [PASS] score=1.0
- Domain: ml_risk
- HTTP status: 200
- Route: HYBRID_SQL_ML
- Source types: ml, sql
- response_blocks: sources, summary, table, warnings
- Question: Quels lots présentent un risque élevé selon le signal ML ?

### RAG-BEST-PRACTICES [PASS] score=1.0
- Domain: rag_best_practices
- HTTP status: 200
- Route: HYBRID_SQL_RAG
- Source types: rag, sql
- response_blocks: best_practices, sources, summary, table, warnings
- Question: Quelles sont les meilleures pratiques de séchage et de tri avec références ?

### RECOMMENDATIONS [PASS] score=1.0
- Domain: recommendations
- HTTP status: 200
- Route: HYBRID_FULL
- Source types: ml, rag, recommendation, sql
- response_blocks: best_practices, recommendations, sources, summary, warnings
- Question: Donne des recommandations prioritaires, concrètes et actionnables pour améliorer la production.

### MULTI-INTENT [PASS] score=1.0
- Domain: multi_intent
- HTTP status: 200
- Route: HYBRID_SQL_RAG
- Source types: rag, sql
- response_blocks: best_practices, sources, summary, warnings
- Question: Donne le stock actuel en kg et les meilleures pratiques de tri/séchage dans la même réponse.

## Persistence Diagnosis

- existing /chat/agent status: 200
- conversation_id preserved in metadata: 3479fd20-f3e0-4d26-a513-bf6a6d21a143
- message count for probed session: 120 -> 122
- marker hits after call: 1
- refresh API status: /chat/sessions=200, /chat/sessions/{id}/messages=200
- missing conversation FK signature seen: False
- ai_chat_audit_logs table exists: True
- persistence_ok_after_refresh: True

### Root Causes

- No persistence root cause detected from this run.

## Recommended Fixes (Not Applied In This Audit)

1. Add a final `db.commit()` in `generate_agent_chat_reply` after assistant message + updated_at update.
2. Decouple `AuditLogger` transaction from chat persistence transaction (separate session or savepoint).
3. Ensure `ai_chat_audit_logs` migration is applied in Supabase or make logger failure non-rolling-back for chat persistence path.
4. Preserve atomic order: session create/resolve -> user message -> assistant message -> commit, with one rollback scope.
5. Add integration test: existing conversation returns 200 AND message appears via `/chat/sessions/{id}/messages` after refresh.