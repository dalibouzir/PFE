# Chatbot Data Coverage Map

Generated: 2026-05-08  
Scope: backend schema (`backend/app/models`) + chatbot runtime (`assistant.py`, `chat_retrieval_router.py`, `rag_indexer.py`)

## Coverage Legend
- `SQL_ONLY`: deterministic factual answers from relational queries.
- `RAG`: semantic chunk indexing/retrieval through `rag_documents` + `rag_chunks`.
- `HYBRID`: combined SQL + RAG reasoning path.

## Module Coverage Matrix
| Table / Model | Business meaning | Current chatbot access status | SQL_ONLY | RAG | HYBRID | Current gaps | Required action |
|---|---|---|---|---|---|---|---|
| `members` | Farmer/member registry | Covered | Yes | Yes | Yes | Member-name disambiguation can still be ambiguous in free text | Add stricter member entity resolver (name/code + confidence) |
| `fields` | Farmer fields (legacy parcel granularity) | Partially covered | No (direct) | Yes | Partial | No dedicated SQL factual answer route | Add SQL extractor for field-level questions |
| `parcels` | Parcels/cultures/surface | Covered | Yes | Yes | Yes | None critical | Keep parcel-specific test coverage in full-platform audit |
| `pre_harvest_steps` | Pre-harvest operations/status | Covered | Yes (through parcel/pre-harvest summaries) | Yes | Yes | Dedicated step-level SQL intents could be richer | Add direct SQL pre-harvest step-status extractor by parcel/step key |
| `inputs` | Collections/inputs by member/product/date/grade | Covered | Yes | Yes | Yes | Trend by period currently aggregate-only | Add explicit period slicing (week/month) in SQL extractor |
| `products` | Product master | Covered (supporting table) | Indirect | Indirect | Indirect | Not directly surfaced as catalog listing | Add optional SQL product-list fact |
| `stocks` | Stock totals/reserved/available/threshold | Covered | Yes | Yes | Yes | None critical | Keep stock alert deterministic checks |
| `batches` | Lots/batches lifecycle | Covered | Yes | Yes | Yes | None critical | Keep multi-lot comparative HYBRID checks |
| `process_steps` | Transformation stages/losses | Covered | Yes | Yes | Yes | Stage filtering can be improved for typo-heavy queries | Add canonical stage typo map in SQL extractor |
| `recommendations` | Operational recommendations by lot/risk | Covered | Yes (summary facts) | Yes | Yes | SQL_ONLY detail filters (stage/product) can be deeper | Add optional recommendation filters by product/stage/lot |
| `recommendation_feedback_logs` | Recommendation acceptance/execution outcome | Partially covered | No (direct) | Yes | Partial | Missing deterministic SQL status summary | Add SQL extractor for accepted/rejected/executed counts |
| `ml_prediction_logs` | ML prediction outputs/risk/anomaly | Covered | Yes (latest prediction) | Yes | Yes | Missing deterministic high-risk/top-N SQL view | Add SQL extractor for top high-risk predictions |
| `ml_recommendation_logs` | ML recommendation generation logs | Partially covered | No (direct) | Yes | Partial | No SQL_ONLY surface | Add SQL extractor for recent ML recommendations |
| `ml_training_runs` | ML training metadata | Partially covered | No (direct) | Yes | Partial | No deterministic SQL route | Add SQL extractor for latest training metrics |
| `ml_model_registry` | Model versions/active artifacts | Partially covered | No (direct) | Yes | Partial | No deterministic SQL route | Add SQL extractor for active model/version |
| `commercial_catalog_products` | Commercial product catalog & sale stock | Covered | Yes (via order/facture/commercial stock) | Yes | Yes | None critical | Expand SQL_ONLY catalog listing question set |
| `commercial_orders` | Orders/workflow status | Covered | Yes | Yes | Yes | At-risk order logic can be richer (stock constraint scoring) | Add deterministic “orders at risk due to stock” score rule |
| `commercial_order_lines` | Ordered quantities by product | Covered | Yes (order detail aggregation) | Indirect | Yes | None critical | Add explicit SQL “quantities by product” endpoint style fact |
| `commercial_invoices` | Invoice lifecycle | Covered | Yes | Yes | Yes | Overdue requires due-date-now branch for explicit wording | Add overdue-only SQL filter fact |
| `commercial_invoice_lines` | Invoice line-level amounts | Covered | Yes (invoice detail line totals) | Indirect | Yes | None critical | Add customer-level amount aggregation |
| `treasury_transactions` | Income/expense ledger | Covered | Yes | Yes | Yes | Transaction-level listing not yet explicit | Add optional SQL latest transactions fact |
| `global_charges` | Charges by category/scope | Covered | Yes | Yes | Yes | Cost-per-stage not fully explicit in SQL_ONLY | Add stage/category charge rollups |
| `farmer_advances` | Farmer advances | Covered | Yes | Yes | Yes | None critical | Keep active/cancelled split checks |
| `knowledge_chunks` | Agronomic knowledge references | Covered | No (factual) | Yes | Yes | None critical | Keep evidence/citation requirements |
| `reference_metrics` | Benchmarks/reference metrics | Covered | No (factual) | Yes | Yes | None critical | Keep benchmark freshness checks |
| `rag_documents` / `rag_chunks` | Indexed semantic layer | Covered (internal) | N/A | Yes | Yes | Metadata completeness varies by source | Add metadata coverage report + enforcement |
| `chat_sessions` / `chat_messages` | Chat memory/history | Covered (conversation infrastructure) | N/A | N/A | N/A | Not a business analytics domain | Keep stale-response regression tests |
| `users`, `cooperatives` | Identity/tenant scope | Covered (scope enforcement) | Indirect | Indirect | Indirect | No direct manager-facing QA intent | Keep excluded from business factual response layer |

## Full-Platform Coverage Check Against Requested Domains
- Members/farmers: `members`, `farmer_advances` => covered.
- Parcels/cultures: `parcels`, `fields`, `pre_harvest_steps` => covered (fields SQL pending).
- Collections/inputs: `inputs` => covered.
- Stocks: `stocks` => covered.
- Lots/process/losses/material balance: `batches`, `process_steps` => covered.
- Recommendations + feedback: `recommendations`, `recommendation_feedback_logs` => recommendation covered; feedback SQL pending.
- ML predictions/logs: `ml_prediction_logs`, `ml_recommendation_logs`, `ml_training_runs`, `ml_model_registry` => partial SQL, strong RAG/HYBRID.
- Commercial/orders: `commercial_catalog_products`, `commercial_orders`, `commercial_order_lines` => covered.
- Invoices/factures: `commercial_invoices`, `commercial_invoice_lines` => covered.
- Finance/charges/advances: `treasury_transactions`, `global_charges`, `farmer_advances` => covered.
- Reference knowledge: `knowledge_chunks`, `reference_metrics` => covered.

## Exclusions (Intentional)
- `users`, `chat_sessions`, `chat_messages` are excluded from manager operational QA content.
- Technical RAG storage tables (`rag_documents`, `rag_chunks`) are internal and should not be surfaced directly as manager-facing domain answers.

## Priority Gaps To Close
1. Add direct SQL_ONLY extractors for: `fields`, `recommendation_feedback_logs`, `ml_recommendation_logs`, `ml_training_runs`, `ml_model_registry`.
2. Strengthen deterministic SQL for overdue invoices and order-at-risk-by-stock scoring.
3. Enforce metadata completeness thresholds per chunk type in reindex coverage report.
