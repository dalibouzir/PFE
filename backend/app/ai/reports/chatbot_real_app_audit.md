# Real App Chatbot Audit Report

**Date:** 2026-05-12T22:18:38.118648+00:00
**Audit Mode:** supabase_readonly
**Database Provider:** Supabase PostgreSQL
**Dialect:** postgresql
**pgvector Enabled:** True

## Summary

- **Total Cases:** 11
- **Passed:** 0 ✓
- **Failed:** 0 ✗
- **Errors:** 0 ⚠️

## Database Tables

- **members:** 17 rows
- **stocks:** 7 rows
- **batches:** 387 rows
- **rag_chunks:** 589 rows
- **rag_documents:** 583 rows
- **process_steps:** 1517 rows
- **inputs:** 76 rows

## Audit Results

### SQL-MBR-01 ⚠️
**Status:** SKIP
**Error:** (psycopg.errors.ForeignKeyViolation) insert or update on table "chat_messages" violates foreign key constraint "fk_chat_messages_session_id_chat_sessions"
DETAIL:  Key (session_id)=(36b3a84c-c1f9-47cc-9030-356aedb5e604) is not present in table "chat_sessions".
[SQL: INSERT INTO chat_messages (id, session_id, role, content, mode, llm_provider, llm_model, citations_json, context_metrics_json, ui_blocks_json, created_at, updated_at) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s::VARCHAR, %(content)s::VARCHAR, %(mode)s::VARCHAR, %(llm_provider)s::VARCHAR, %(llm_model)s::VARCHAR, %(citations_json)s::JSON, %(context_metrics_json)s::JSON, %(ui_blocks_json)s::JSON, %(created_at)s::TIMESTAMP WITH TIME ZONE, %(updated_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': UUID('abba5758-2a97-4908-a518-934cb91ee2bb'), 'session_id': UUID('36b3a84c-c1f9-47cc-9030-356aedb5e604'), 'role': 'assistant', 'content': '1. Résultat principal\nLes données disponibles ne permettent pas de confirmer ce point.\n\n2. Explication courte\nAucune explication détaillée dispon ... (61 characters truncated) ... tion prioritaire confirmée.\n\n4. Sources utilisées\n- SQL: inputs\n- SQL: members\n\n5. Avertissements si nécessaires\nAucun avertissement critique.', 'mode': 'agentic:SQL_ONLY', 'llm_provider': None, 'llm_model': None, 'citations_json': Json([{'source_id': 'members', 'source_u ... (273 chars)), 'context_metrics_json': Json([{'source_id': 'agent', 'region': ' ... (295 chars)), 'ui_blocks_json': Json([{'type': 'executive_summary', 'tit ... (363 chars)), 'created_at': datetime.datetime(2026, 5, 12, 22, 18, 7, 989930, tzinfo=datetime.timezone.utc), 'updated_at': datetime.datetime(2026, 5, 12, 22, 18, 7, 990015, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)

### SQL-STK-01 ⚠️
**Status:** SKIP
**Error:** (psycopg.errors.ForeignKeyViolation) insert or update on table "chat_messages" violates foreign key constraint "fk_chat_messages_session_id_chat_sessions"
DETAIL:  Key (session_id)=(528b682e-84be-4da2-984e-a10d0ffc0c06) is not present in table "chat_sessions".
[SQL: INSERT INTO chat_messages (id, session_id, role, content, mode, llm_provider, llm_model, citations_json, context_metrics_json, ui_blocks_json, created_at, updated_at) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s::VARCHAR, %(content)s::VARCHAR, %(mode)s::VARCHAR, %(llm_provider)s::VARCHAR, %(llm_model)s::VARCHAR, %(citations_json)s::JSON, %(context_metrics_json)s::JSON, %(ui_blocks_json)s::JSON, %(created_at)s::TIMESTAMP WITH TIME ZONE, %(updated_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': UUID('56ab5de6-0225-4a46-b350-4989d4c82f96'), 'session_id': UUID('528b682e-84be-4da2-984e-a10d0ffc0c06'), 'role': 'assistant', 'content': '1. Résultat principal\nLes stocks actuels (4 produits) sont:\n- Arachide: 1140.0 kg disponibles\n- Bissap: 0.0 kg disponibles\n- Mangue: 2750.0 kg di ... (146 characters truncated) ... ucune recommandation prioritaire confirmée.\n\n4. Sources utilisées\n- SQL: stocks\n\n5. Avertissements si nécessaires\nAucun avertissement critique.', 'mode': 'agentic:SQL_ONLY', 'llm_provider': None, 'llm_model': None, 'citations_json': Json([{'source_id': 'stocks', 'source_ur ... (143 chars)), 'context_metrics_json': Json([{'source_id': 'agent', 'region': ' ... (295 chars)), 'ui_blocks_json': Json([{'type': 'executive_summary', 'tit ... (633 chars)), 'created_at': datetime.datetime(2026, 5, 12, 22, 18, 9, 720575, tzinfo=datetime.timezone.utc), 'updated_at': datetime.datetime(2026, 5, 12, 22, 18, 9, 720587, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)

### SQL-LOT-02 ⚠️
**Status:** SKIP
**Error:** (psycopg.errors.ForeignKeyViolation) insert or update on table "chat_messages" violates foreign key constraint "fk_chat_messages_session_id_chat_sessions"
DETAIL:  Key (session_id)=(2813e65c-3beb-4a91-836d-80d7ed32aceb) is not present in table "chat_sessions".
[SQL: INSERT INTO chat_messages (id, session_id, role, content, mode, llm_provider, llm_model, citations_json, context_metrics_json, ui_blocks_json, created_at, updated_at) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s::VARCHAR, %(content)s::VARCHAR, %(mode)s::VARCHAR, %(llm_provider)s::VARCHAR, %(llm_model)s::VARCHAR, %(citations_json)s::JSON, %(context_metrics_json)s::JSON, %(ui_blocks_json)s::JSON, %(created_at)s::TIMESTAMP WITH TIME ZONE, %(updated_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': UUID('59e7c33a-e958-4ef3-a198-252f4edbf5fb'), 'session_id': UUID('2813e65c-3beb-4a91-836d-80d7ed32aceb'), 'role': 'assistant', 'content': '1. Résultat principal\nLots en cours (8):\n- LOT-MANG-001: perte 6.0 % | efficacité 94.0 %\n- LOT-BISS-002: perte 69.3 % | efficacité 30.7 %\n- DEMOF ... (438 characters truncated) ... cune recommandation prioritaire confirmée.\n\n4. Sources utilisées\n- SQL: batches\n\n5. Avertissements si nécessaires\nAucun avertissement critique.', 'mode': 'agentic:SQL_ONLY', 'llm_provider': None, 'llm_model': None, 'citations_json': Json([{'source_id': 'batches', 'source_u ... (132 chars)), 'context_metrics_json': Json([{'source_id': 'agent', 'region': ' ... (295 chars)), 'ui_blocks_json': Json([{'type': 'executive_summary', 'tit ... (718 chars)), 'created_at': datetime.datetime(2026, 5, 12, 22, 18, 11, 357454, tzinfo=datetime.timezone.utc), 'updated_at': datetime.datetime(2026, 5, 12, 22, 18, 11, 357475, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)

### SQL-EFF-01 ⚠️
**Status:** SKIP
**Error:** (psycopg.errors.ForeignKeyViolation) insert or update on table "chat_messages" violates foreign key constraint "fk_chat_messages_session_id_chat_sessions"
DETAIL:  Key (session_id)=(78828825-4101-4d00-8ad6-5e2442f0ee80) is not present in table "chat_sessions".
[SQL: INSERT INTO chat_messages (id, session_id, role, content, mode, llm_provider, llm_model, citations_json, context_metrics_json, ui_blocks_json, created_at, updated_at) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s::VARCHAR, %(content)s::VARCHAR, %(mode)s::VARCHAR, %(llm_provider)s::VARCHAR, %(llm_model)s::VARCHAR, %(citations_json)s::JSON, %(context_metrics_json)s::JSON, %(ui_blocks_json)s::JSON, %(created_at)s::TIMESTAMP WITH TIME ZONE, %(updated_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': UUID('7e0f542b-ff90-458c-8a3f-10bef25d4741'), 'session_id': UUID('78828825-4101-4d00-8ad6-5e2442f0ee80'), 'role': 'assistant', 'content': '1. Résultat principal\nLots à efficacité faible (4):\n- LOT-BISS-002: efficacité 30.7 % | perte 69.3 %\n- DEMOFP-LOT-MANG-013: efficacité 76.4 % | pe ... (253 characters truncated) ... ioritaire confirmée.\n\n4. Sources utilisées\n- SQL: batches\n- SQL: process_steps\n\n5. Avertissements si nécessaires\nAucun avertissement critique.', 'mode': 'agentic:SQL_ONLY', 'llm_provider': None, 'llm_model': None, 'citations_json': Json([{'source_id': 'batches', 'source_u ... (271 chars)), 'context_metrics_json': Json([{'source_id': 'agent', 'region': ' ... (295 chars)), 'ui_blocks_json': Json([{'type': 'executive_summary', 'tit ... (849 chars)), 'created_at': datetime.datetime(2026, 5, 12, 22, 18, 13, 238232, tzinfo=datetime.timezone.utc), 'updated_at': datetime.datetime(2026, 5, 12, 22, 18, 13, 238239, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)

### SQL-MB-01 ⚠️
**Status:** SKIP
**Error:** (psycopg.errors.ForeignKeyViolation) insert or update on table "chat_messages" violates foreign key constraint "fk_chat_messages_session_id_chat_sessions"
DETAIL:  Key (session_id)=(922c65dc-20c8-463c-b6cf-8317ccdb0add) is not present in table "chat_sessions".
[SQL: INSERT INTO chat_messages (id, session_id, role, content, mode, llm_provider, llm_model, citations_json, context_metrics_json, ui_blocks_json, created_at, updated_at) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s::VARCHAR, %(content)s::VARCHAR, %(mode)s::VARCHAR, %(llm_provider)s::VARCHAR, %(llm_model)s::VARCHAR, %(citations_json)s::JSON, %(context_metrics_json)s::JSON, %(ui_blocks_json)s::JSON, %(created_at)s::TIMESTAMP WITH TIME ZONE, %(updated_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': UUID('09a92987-9b05-4d6f-b323-52e0c37a7b80'), 'session_id': UUID('922c65dc-20c8-463c-b6cf-8317ccdb0add'), 'role': 'assistant', 'content': '1. Résultat principal\nLe bilan matière du lot LOT-MANG-001 montre une perte de 6.0 % et une efficacité de 94.0 %.\n\n2. Explication courte\nAucune e ... (95 characters truncated) ... ioritaire confirmée.\n\n4. Sources utilisées\n- SQL: batches\n- SQL: process_steps\n\n5. Avertissements si nécessaires\nAucun avertissement critique.', 'mode': 'agentic:SQL_ONLY', 'llm_provider': None, 'llm_model': None, 'citations_json': Json([{'source_id': 'batches', 'source_u ... (276 chars)), 'context_metrics_json': Json([{'source_id': 'agent', 'region': ' ... (295 chars)), 'ui_blocks_json': Json([{'type': 'executive_summary', 'tit ... (397 chars)), 'created_at': datetime.datetime(2026, 5, 12, 22, 18, 16, 597700, tzinfo=datetime.timezone.utc), 'updated_at': datetime.datetime(2026, 5, 12, 22, 18, 16, 597710, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)

### SQL-PSL-01 ⚠️
**Status:** SKIP
**Error:** (psycopg.errors.ForeignKeyViolation) insert or update on table "chat_messages" violates foreign key constraint "fk_chat_messages_session_id_chat_sessions"
DETAIL:  Key (session_id)=(84d3d6d3-08d2-4cf5-a78a-bcb01c5ed03e) is not present in table "chat_sessions".
[SQL: INSERT INTO chat_messages (id, session_id, role, content, mode, llm_provider, llm_model, citations_json, context_metrics_json, ui_blocks_json, created_at, updated_at) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s::VARCHAR, %(content)s::VARCHAR, %(mode)s::VARCHAR, %(llm_provider)s::VARCHAR, %(llm_model)s::VARCHAR, %(citations_json)s::JSON, %(context_metrics_json)s::JSON, %(ui_blocks_json)s::JSON, %(created_at)s::TIMESTAMP WITH TIME ZONE, %(updated_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': UUID('ce8baabd-f268-4743-a695-5cf2494973bb'), 'session_id': UUID('84d3d6d3-08d2-4cf5-a78a-bcb01c5ed03e'), 'role': 'assistant', 'content': '1. Résultat principal\nLes données disponibles ne permettent pas de confirmer ce point.\n\n2. Explication courte\nAucune explication détaillée dispon ... (52 characters truncated) ... ecommandation prioritaire confirmée.\n\n4. Sources utilisées\n- SQL: process_steps\n\n5. Avertissements si nécessaires\nAucun avertissement critique.', 'mode': 'agentic:SQL_ONLY', 'llm_provider': None, 'llm_model': None, 'citations_json': Json([{'source_id': 'process_steps', 'so ... (139 chars)), 'context_metrics_json': Json([{'source_id': 'agent', 'region': ' ... (295 chars)), 'ui_blocks_json': Json([{'type': 'executive_summary', 'tit ... (332 chars)), 'created_at': datetime.datetime(2026, 5, 12, 22, 18, 18, 226726, tzinfo=datetime.timezone.utc), 'updated_at': datetime.datetime(2026, 5, 12, 22, 18, 18, 226735, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)

### RAG-DRY-01 ⚠️
**Status:** SKIP
**Error:** (psycopg.errors.ForeignKeyViolation) insert or update on table "chat_messages" violates foreign key constraint "fk_chat_messages_session_id_chat_sessions"
DETAIL:  Key (session_id)=(8859b8a3-6ab9-453f-8288-ef4f64f55e78) is not present in table "chat_sessions".
[SQL: INSERT INTO chat_messages (id, session_id, role, content, mode, llm_provider, llm_model, citations_json, context_metrics_json, ui_blocks_json, created_at, updated_at) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s::VARCHAR, %(content)s::VARCHAR, %(mode)s::VARCHAR, %(llm_provider)s::VARCHAR, %(llm_model)s::VARCHAR, %(citations_json)s::JSON, %(context_metrics_json)s::JSON, %(ui_blocks_json)s::JSON, %(created_at)s::TIMESTAMP WITH TIME ZONE, %(updated_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': UUID('2d181e72-bf1c-40fd-b514-9fea006ef7f3'), 'session_id': UUID('8859b8a3-6ab9-453f-8288-ef4f64f55e78'), 'role': 'assistant', 'content': '1. Résultat principal\nClassement des membres par quantité collectée (10):\n- Awa Ndiaye (DEMOFP-M-002): 1715.0 kg\n- Mamadou Ba (DEMOFP-M-001): 1565 ... (497 characters truncated) ...  utilisées\n- SQL: inputs\n- SQL: members\n- SQL: process_steps\n\n5. Avertissements si nécessaires\n- Aucune donnée SQL exploitable n’a été trouvée.', 'mode': 'agentic:SQL_ONLY', 'llm_provider': None, 'llm_model': None, 'citations_json': Json([{'source_id': 'process_steps', 'so ... (278 chars)), 'context_metrics_json': Json([{'source_id': 'agent', 'region': ' ... (310 chars)), 'ui_blocks_json': Json([{'type': 'executive_summary', 'tit ... (1471 chars)), 'created_at': datetime.datetime(2026, 5, 12, 22, 18, 19, 874934, tzinfo=datetime.timezone.utc), 'updated_at': datetime.datetime(2026, 5, 12, 22, 18, 19, 875531, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)

### RAG-SRT-01 ⚠️
**Status:** SKIP
**Error:** (psycopg.errors.ForeignKeyViolation) insert or update on table "chat_messages" violates foreign key constraint "fk_chat_messages_session_id_chat_sessions"
DETAIL:  Key (session_id)=(1fb1762f-ac46-4ce7-b19e-0593909ebcb8) is not present in table "chat_sessions".
[SQL: INSERT INTO chat_messages (id, session_id, role, content, mode, llm_provider, llm_model, citations_json, context_metrics_json, ui_blocks_json, created_at, updated_at) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s::VARCHAR, %(content)s::VARCHAR, %(mode)s::VARCHAR, %(llm_provider)s::VARCHAR, %(llm_model)s::VARCHAR, %(citations_json)s::JSON, %(context_metrics_json)s::JSON, %(ui_blocks_json)s::JSON, %(created_at)s::TIMESTAMP WITH TIME ZONE, %(updated_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': UUID('7c905df6-7270-47ba-9ac3-deaa16ba1b53'), 'session_id': UUID('1fb1762f-ac46-4ce7-b19e-0593909ebcb8'), 'role': 'assistant', 'content': "1. Résultat principal\nCommandes commerciales disponibles: 14.\n\n2. Explication courte\nExplication RAG: Le tri est essentiel pour garantir la quali ... (628 characters truncated) ... 91fd8dd6881b\n- ML: ml_signal\n\n5. Avertissements si nécessaires\n- CONTRADICTORY_CONTEXT_POSSIBLE\n- Aucune donnée SQL exploitable n’a été trouvée.", 'mode': 'agentic:HYBRID_FULL', 'llm_provider': None, 'llm_model': None, 'citations_json': Json([{'source_id': 'commercial_orders', ... (1899 chars)), 'context_metrics_json': Json([{'source_id': 'agent', 'region': ' ... (313 chars)), 'ui_blocks_json': Json([{'type': 'executive_summary', 'tit ... (1846 chars)), 'created_at': datetime.datetime(2026, 5, 12, 22, 18, 25, 37676, tzinfo=datetime.timezone.utc), 'updated_at': datetime.datetime(2026, 5, 12, 22, 18, 25, 37688, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)

### ML-RISK-01 ⚠️
**Status:** SKIP
**Error:** (psycopg.errors.ForeignKeyViolation) insert or update on table "chat_messages" violates foreign key constraint "fk_chat_messages_session_id_chat_sessions"
DETAIL:  Key (session_id)=(9040ca6b-d91e-436f-8b10-16fae6b6bc6f) is not present in table "chat_sessions".
[SQL: INSERT INTO chat_messages (id, session_id, role, content, mode, llm_provider, llm_model, citations_json, context_metrics_json, ui_blocks_json, created_at, updated_at) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s::VARCHAR, %(content)s::VARCHAR, %(mode)s::VARCHAR, %(llm_provider)s::VARCHAR, %(llm_model)s::VARCHAR, %(citations_json)s::JSON, %(context_metrics_json)s::JSON, %(ui_blocks_json)s::JSON, %(created_at)s::TIMESTAMP WITH TIME ZONE, %(updated_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': UUID('c298e7cb-ae77-4951-a0de-1e1d5ce73032'), 'session_id': UUID('9040ca6b-d91e-436f-8b10-16fae6b6bc6f'), 'role': 'assistant', 'content': '1. Résultat principal\nLots à risque élevé (5):\n- LOT-BISS-002: perte 69.3 % | efficacité 30.7 %\n- DEMOFP-LOT-MANG-013: perte 23.6 % | efficacité 7 ... (356 characters truncated) ... on prioritaire confirmée.\n\n4. Sources utilisées\n- SQL: batches\n- ML: ml_signal\n\n5. Avertissements si nécessaires\nAucun avertissement critique.', 'mode': 'agentic:HYBRID_SQL_ML', 'llm_provider': None, 'llm_model': None, 'citations_json': Json([{'source_id': 'batches', 'source_u ... (283 chars)), 'context_metrics_json': Json([{'source_id': 'agent', 'region': ' ... (314 chars)), 'ui_blocks_json': Json([{'type': 'executive_summary', 'tit ... (936 chars)), 'created_at': datetime.datetime(2026, 5, 12, 22, 18, 27, 729217, tzinfo=datetime.timezone.utc), 'updated_at': datetime.datetime(2026, 5, 12, 22, 18, 27, 729225, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)

### REC-01 ⚠️
**Status:** SKIP
**Error:** (psycopg.errors.ForeignKeyViolation) insert or update on table "chat_messages" violates foreign key constraint "fk_chat_messages_session_id_chat_sessions"
DETAIL:  Key (session_id)=(60ae3068-c147-45da-aaec-78919c2952c3) is not present in table "chat_sessions".
[SQL: INSERT INTO chat_messages (id, session_id, role, content, mode, llm_provider, llm_model, citations_json, context_metrics_json, ui_blocks_json, created_at, updated_at) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s::VARCHAR, %(content)s::VARCHAR, %(mode)s::VARCHAR, %(llm_provider)s::VARCHAR, %(llm_model)s::VARCHAR, %(citations_json)s::JSON, %(context_metrics_json)s::JSON, %(ui_blocks_json)s::JSON, %(created_at)s::TIMESTAMP WITH TIME ZONE, %(updated_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': UUID('a68115b2-0dfb-4e2d-9d07-d4de4f165efb'), 'session_id': UUID('60ae3068-c147-45da-aaec-78919c2952c3'), 'role': 'assistant', 'content': '1. Résultat principal\nLes données disponibles ne permettent pas de confirmer ce point.\n\n2. Explication courte\nAucune explication détaillée dispon ... (30 characters truncated) ...  pertinentes\nAucune recommandation prioritaire confirmée.\n\n4. Sources utilisées\n\n5. Avertissements si nécessaires\nAucun avertissement critique.', 'mode': 'agentic:RECOMMENDATION_ONLY', 'llm_provider': None, 'llm_model': None, 'citations_json': Json([{'source_id': 'Recommendation evid ... (167 chars)), 'context_metrics_json': Json([{'source_id': 'agent', 'region': ' ... (306 chars)), 'ui_blocks_json': Json([{'type': 'executive_summary', 'tit ... (290 chars)), 'created_at': datetime.datetime(2026, 5, 12, 22, 18, 29, 366396, tzinfo=datetime.timezone.utc), 'updated_at': datetime.datetime(2026, 5, 12, 22, 18, 29, 366444, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)

### COM-INV-01 ⚠️
**Status:** SKIP
**Error:** (psycopg.errors.ForeignKeyViolation) insert or update on table "chat_messages" violates foreign key constraint "fk_chat_messages_session_id_chat_sessions"
DETAIL:  Key (session_id)=(d41f3cf5-6fb0-4448-9292-211f28de81de) is not present in table "chat_sessions".
[SQL: INSERT INTO chat_messages (id, session_id, role, content, mode, llm_provider, llm_model, citations_json, context_metrics_json, ui_blocks_json, created_at, updated_at) VALUES (%(id)s::UUID, %(session_id)s::UUID, %(role)s::VARCHAR, %(content)s::VARCHAR, %(mode)s::VARCHAR, %(llm_provider)s::VARCHAR, %(llm_model)s::VARCHAR, %(citations_json)s::JSON, %(context_metrics_json)s::JSON, %(ui_blocks_json)s::JSON, %(created_at)s::TIMESTAMP WITH TIME ZONE, %(updated_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': UUID('1119ef57-301e-46ba-a35a-d06fec96de53'), 'session_id': UUID('d41f3cf5-6fb0-4448-9292-211f28de81de'), 'role': 'assistant', 'content': '1. Résultat principal\nFactures disponibles: 8.\n\n2. Explication courte\nAucune explication détaillée disponible.\n\n3. Recommandations si pertinent ... (44 characters truncated) ... mée.\n\n4. Sources utilisées\n- SQL: commercial_invoices\n- SQL: commercial_orders\n\n5. Avertissements si nécessaires\nAucun avertissement critique.', 'mode': 'agentic:SQL_ONLY', 'llm_provider': None, 'llm_model': None, 'citations_json': Json([{'source_id': 'commercial_invoices ... (299 chars)), 'context_metrics_json': Json([{'source_id': 'agent', 'region': ' ... (295 chars)), 'ui_blocks_json': Json([{'type': 'executive_summary', 'tit ... (813 chars)), 'created_at': datetime.datetime(2026, 5, 12, 22, 18, 34, 20000, tzinfo=datetime.timezone.utc), 'updated_at': datetime.datetime(2026, 5, 12, 22, 18, 34, 20013, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/gkpj)
