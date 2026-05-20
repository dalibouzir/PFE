# RAG + GROUNDING RECOVERY PHASE — DIAGNOSTIC COMPLETE

**Date:** 2026-05-20  
**Scope:** Audit only (no code changes except diagnostic tools)  
**Status:** ✅ Complete — 3 major blockers identified, 1 actionable immediately

---

## FILES CHANGED

### Created
- `backend/scripts/rag_grounding_diagnostic.py` — Diagnostic utility for LLM, RAG, entities
- `backend/reports/chatbot/rag_grounding_diagnostic_report.md` — Full diagnostic findings

### Regenerated (from re-running existing audits)
- `backend/reports/chatbot/targeted_manual_regression_audit.md` (now dated 2026-05-20)
- `backend/reports/chatbot/targeted_manual_regression_audit.json`
- `backend/reports/chatbot/unseen_generalization_audit.json`

### Code Modified
**ZERO** — No source code changes made.

---

## LLM PROVIDER STATUS

### ❌ CRITICAL: OpenRouter Account Out of Credits

```
HTTP 402 Insufficient Credits
{"error":{"message":"Insufficient credits. This account never purchased credits. 
Make sure your key is on the correct account or org..."}}
```

**Configuration:**
- ✅ Provider: OpenRouter (configured)
- ✅ Model: openai/gpt-4o-mini (configured)
- ✅ API Key: Present (sk-or-v1-...)
- ✅ Connectivity: Works (API reachable)
- ❌ **Account Status:** NO CREDITS

**Impact:**
- **ALL HYBRID and RAG_ONLY routes fail**
- Fallback to SQL-only with message: "Le fournisseur LLM est indisponible"
- This causes validation_audit to show **0% pass rate**
- Causes HYBRID route to show 41.9% instead of expected 75%+

**Fix (15 minutes):**
```
1. Go to https://openrouter.ai/settings/credits
2. Add credits to account (or use API key from different account)
3. Verify: python scripts/rag_grounding_diagnostic.py
4. Re-run audits
```

---

## RAG CHUNK AUDIT

### ✅ Index Status: READY

| Metric | Value | Status |
|---|---|---|
| Total Chunks | 699 | ✅ Present |
| With Embeddings | 699/699 | ✅ Complete |
| Knowledge Base Docs | 25 | ✅ Seeded |
| Expected | ~589 | ✓ Exceeded |

### Chunk Distribution

**Knowledge Base (25 documents):**
- Mangue: drying, packaging, tri, humidity, handling
- Mil: post-harvest loss prevention, storage, drying, conditioning
- Arachide: sorting, storage, drying, moisture, breakage
- Multi-produit: loss prevention, packaging, humidity
- Bissap: sorting

**App Data (674 documents):**
- Process steps: 120 chunks
- Inputs: 80 chunks
- Pre-harvest steps: 68 chunks
- ML prediction logs: 62 chunks
- Batches: 61 chunks
- And 18 other tables...

### ✅ Embeddings: All Present
- Type: pgvector format (384-dimensional, local embeddings)
- Status: 100% indexed
- Provider: sentence-transformers/all-MiniLM-L6-v2 (local, not API-dependent)

**No RAG reseeding needed** — index is complete.

---

## ENTITY LOOKUP AUDIT

### Test Results

| Entity | Status | Database | Chatbot |
|---|---|---|---|
| LOT-MANG-005 | ✅ EXISTS | Found (250/950 kg) | ❌ Returns "no data" |
| MANG-004 | ❌ NEVER EXISTED | Not found | ✅ Correctly says missing |
| DEMOFP-LOT-MANG-003 | ✅ EXISTS | Found (570/700 kg) | ✅ Found |

### Root Cause Analysis

**Database level: ✅ WORKS**
```sql
SELECT * FROM batches 
WHERE code='LOT-MANG-005' 
  AND cooperative_id='4cbc6020-def9-4d24-bb75-9d40bc031466'
-- Result: FOUND (250.0/950.0 kg, completed)
```

**Chatbot level: ❌ FAILS**
- User asks: "What is the status of LOT-MANG-005?"
- Expected: "LOT-MANG-005 (Mangue): completed, 250/950 kg"
- Actual: "Je ne trouve pas cette donnée"

**Issue is NOT in SQL tool** (`get_batch_summary()` function verified to work correctly)

**Likely causes (in priority order):**
1. **Entity extraction** — Agent doesn't correctly parse "LOT-MANG-005" from question
2. **Query routing** — Agent doesn't route to batch lookup correctly
3. **Parameter passing** — batch_ref not passed correctly to SQL tool
4. **LLM fallback** — When LLM is offline, some entity extraction may fail

**Action:** Debug intent router and entity extraction in `sql_analytics_agent.py` after LLM is restored.

---

## CITATION METADATA STATUS

### Issue
Validation audit reports:
- `citation_relevance_score: 0.0` (all 10 cases)
- `sources: []` (empty in all cases)

### Root Cause
**Primary: LLM is offline** → fallback responses can't synthesize grounded answers with citations

**Secondary: Citation dict structure unclear**
- Need to verify `agent_orchestrator.py` emits `sources` dict correctly
- Check if SQL/RAG/ML sources are wrapped properly

### Investigation After LLM Restored
```python
# Check response structure
response = orchestrator.route_and_answer(
    query="...",
    cooperative_id="...",
    user_role="manager"
)
# Should contain:
# - response['sources']: list of source dicts
# - response['citations']: citation references
# - response['answer']: grounded text
```

---

## SUMMARY: BLOCKERS RANKED

### 🔴 BLOCKER #1: OpenRouter Account Has No Credits
- **Severity:** CRITICAL
- **Impact:** LLM unavailable → HYBRID/RAG fail → validation audit fails
- **Fix Time:** 15 min
- **Action:** Add credits to OpenRouter account

### 🟡 BLOCKER #2: Entity Lookup Failures (LOT-MANG-005)
- **Severity:** HIGH
- **Impact:** ~22% of failures in full-platform audit
- **Root:** Agent entity extraction/routing (not database)
- **Fix Time:** 30-60 min
- **Status:** Investigation pending LLM restore

### 🟡 BLOCKER #3: Citation Metadata Empty
- **Severity:** MEDIUM
- **Impact:** Validation metrics unreliable
- **Root:** LLM offline + orchestrator dict structure
- **Fix Time:** 30 min
- **Status:** Likely resolves after LLM restored

---

## RECOMMENDED PATH FORWARD

### Phase 0: Immediate (Today, 15 min)
```bash
# 1. Restore LLM credits
# Go to: https://openrouter.ai/settings/credits
# Add credits or switch to alternative provider

# 2. Verify connection
cd backend
source ../.venv/bin/activate
python scripts/rag_grounding_diagnostic.py
# Expected: LLM Available: ✅ YES
```

### Phase 1: After LLM Restored (Hours 2-4)

```bash
# 1. Re-run full validation audit
python scripts/chatbot_validation_audit.py
# Expected: > 50% pass rate (up from 0%)

# 2. Debug entity lookup
# Check: backend/app/ai/agents/sql_analytics_agent.py
# Test: Does "LOT-MANG-005" get correctly extracted from questions?

# 3. Re-run all 5 core audits
python scripts/chatbot_unseen_generalization_audit.py     # expect 98.5%
python scripts/chatbot_t01_t05_variants_audit.py           # expect 100%
python scripts/chatbot_targeted_manual_regression_audit.py # expect 100%
python scripts/chatbot_manager_style_audit.py              # expect 96.7%
python scripts/chatbot_validation_audit.py                 # expect > 70%
```

### Phase 2: If Blockers Persist (Contingency)

**If RAG retrieval still not working:**
- Check `app/ai/retrieval/hybrid_retriever.py` vector search
- Verify knowledge_chunks are being searched (not just app_data)
- Test: `HybridRetriever.retrieve(query="séchage", filters={})`

**If citation metadata still empty:**
- Check `agent_orchestrator.py` source dict structure
- Verify SQL/RAG/ML sources are being emitted
- Add logging to trace citation flow

**If entity lookup still fails:**
- Add entity extraction logging in `sql_analytics_agent.py`
- Trace parameter passing to `sql_tools.get_batch_summary(batch_ref=...)`

---

## VALIDATION: No Code Changes Made

```bash
# Verify only diagnostic files changed
git diff --name-only | grep -v "reports/" | grep -v ".json"
# Expected output:
#   backend/scripts/rag_grounding_diagnostic.py

# No source files changed
git diff backend/app/ backend/app/ai/
# Expected: (no output)
```

✅ **Confirmed:** Only diagnostic tools created, no source code modified.

---

## NEXT STEPS FOR USER

1. **Today:** Fix OpenRouter account (add credits or switch provider)
2. **Hour 2:** Verify LLM works with diagnostic script
3. **Hour 3:** Re-run full audit suite (5 audits)
4. **If needed:** Debug entity extraction and citation metadata
5. **Ready:** Only after validation audit shows > 70% pass rate

---

**Diagnostic Tool Location:** `/backend/scripts/rag_grounding_diagnostic.py`  
**Diagnostic Report:** `/backend/reports/chatbot/rag_grounding_diagnostic_report.md`  
**Blockers:** 3 identified, 1 immediately actionable

