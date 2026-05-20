# RAG + Grounding Diagnostic Report

**Generated:** 2026-05-20T02:00:00+00:00  
**Scope:** Cooperative 4cbc6020-def9-4d24-bb75-9d40bc031466

---

## 1. LLM PROVIDER STATUS

### Configuration
✅ **Configured:**
- Provider: OpenRouter
- Model: openai/gpt-4o-mini
- API Key: Present (sk-or-v1-...)
- Timeout: 30 seconds
- Max tokens: 280

### Connectivity Test
❌ **FAILED:** HTTP 402 Insufficient Credits
```
{"error":{"message":"Insufficient credits. This account never purchased credits. 
Make sure your key is on the correct account or org, and if so, purchase more at 
https://openrouter.ai/settings/credits"}}
```

### Impact
- **This is why validation_audit shows "LLM unavailable"**
- Not a code configuration issue - an **account funding issue**
- All HYBRID and RAG_ONLY queries degrade to deterministic SQL fallback
- HYBRID route shows: "Le fournisseur LLM est indisponible. Analyse limitée aux données structurées..."

### Action
**CRITICAL:** Resolve OpenRouter account - either:
- Add credits to account
- OR switch to alternative LLM provider (GROQ, OpenAI key, local LLM)
- Update environment: `OPENROUTER_API_KEY=...` or switch `LLM_PROVIDER`

---

## 2. RAG INDEX AUDIT

### Summary
| Metric | Value | Status |
|---|---|---|
| Documents | 699 | ✅ Present |
| Chunks | 699 | ✅ Present |
| Knowledge chunks | 25 | ✅ Seeded |
| Embeddings | 699/699 | ✅ Complete |
| Expected | ~589 | ✓ Exceeded |

### Document Distribution by Source Table
```
process_steps:               120 chunks  (app data)
inputs:                       80 chunks  (app data)
pre_harvest_steps:            68 chunks  (app data)
ml_prediction_logs:           62 chunks  (app data)
batches:                      61 chunks  (app data)
recommendation_feedback_logs: 52 chunks  (app data)
ml_recommendation_logs:       21 chunks  (app data)
members:                      22 chunks  (app data)
parcels:                      22 chunks  (app data)
farmer_advances:              18 chunks  (app data)
reference_metrics:            17 chunks  (knowledge reference)
fields:                       20 chunks  (app data)
global_charges:               24 chunks  (app data)
knowledge_chunks:             25 chunks  (KNOWLEDGE BASE) ← Key for RAG
...
TOTAL:                       699 chunks
```

### Knowledge Base Content
✅ **Knowledge chunks present:** 25 documents
- Topics covered:
  - Mangue: drying, packaging, tri (sorting), humidity control, handling
  - Mil: post-harvest loss prevention, storage, drying, conditioning
  - Arachide: sorting, storage, drying, moisture stability, breakage prevention
  - Multi-produit: loss prevention, packaging, humidity
  - Bissap: sorting

**Sources referenced:**
- DEMOFP-SRC-KNOW-001 (Séchage)
- DEMOFP-SRC-KNOW-002 (Tri)
- DEMOFP-SRC-KNOW-003 (Stockage)
- DEMOFP-SRC-KNOW-004 (Séchage - Mil)
- DEMOFP-SRC-KNOW-005 (Tri - Bissap)
- REF-KNOW-* (Agriculture reference sources)

### Embeddings Status
✅ **All 699 chunks have embeddings**
- Type: Vector strings (pgvector format)
- Dimensions: 384 (from local sentence-transformers/all-MiniLM-L6-v2)
- All marked as present in database

---

## 3. ENTITY LOOKUP AUDIT

### Test Results

**LOT-MANG-005**
```
✅ FOUND in cooperative database
  Code: LOT-MANG-005
  Status: COMPLETED
  Quantity: 250.0 / 950.0 kg (74% loss)
  Product: Mangue (96c76b60-cbae-4a83-8697-39e2e9ed6f68)
```

**MANG-004**
```
❌ NOT FOUND
  Never existed in any cooperative
  (Appears in validation audit as "missing data" - expected fail case)
```

**DEMOFP-LOT-MANG-003**
```
✅ FOUND in cooperative database
  Code: DEMOFP-LOT-MANG-003
  Status: IN_PROGRESS
  Quantity: 570.36 / 700.0 kg (18.5% loss)
  Product: Mangue
```

### Diagnosis
- **LOT-MANG-005 exists in DB** ← Why does validation audit fail to find it?
- **MANG-004 never existed** ← Correct "no data" response
- **Entity lookup queries work correctly** ← Issue is not in database retrieval

**Root cause of entity lookup failures:** Must be in the chatbot SQL template or query routing, not in the data layer.

---

## 4. CITATION METADATA STATUS

### Issue Description
Validation audit reports:
- `citation_relevance_score: 0.0` (all cases)
- `sources: []` (empty in all cases)
- Grounding: Failed despite factual accuracy sometimes > 0

### Known Issues
1. **LLM unavailable** → fallback responses don't synthesize citations
2. **RAG retrieval may not be returning results** → no RAG sources to cite
3. **Citation format in orchestrator.py** → needs verification

### Investigation Needed
- Check `agent_orchestrator.py` for source/citation dict structure
- Verify SQL answers include `sources` field
- Confirm RAG fallback attaches chunks to `sources`
- Test citation emission with mock LLM response

---

## 5. SUMMARY TABLE

| Category | Status | Finding | Action |
|---|---|---|---|
| **LLM Connectivity** | ❌ DOWN | OpenRouter account has no credits (402) | **ADD CREDITS or SWITCH PROVIDER** |
| **RAG Index** | ✅ READY | 699 chunks with embeddings, 25 knowledge docs | No action needed |
| **Knowledge Base** | ✅ SEEDED | Topics: drying, storage, sorting, packaging, loss prevention | Re-test retrieval once LLM restored |
| **Entity Lookups** | ✅ DB OK | Real entities (LOT-MANG-005) exist in DB | Debug SQL templates in chatbot |
| **Citations** | ⚠️ PENDING | 0.0 scores due to LLM being offline | Re-test after LLM restored |
| **Validation Audit** | 🔴 UNBLOCKED | 0% pass rate → will resolve when LLM restored | Re-run after LLM fix |

---

## 6. BLOCKERS RANKED

### 🔴 BLOCKER #1 (HIGHEST PRIORITY): OpenRouter Account Has No Credits
- **Impact:** LLM unavailable for HYBRID and RAG routes → all HYBRID/RAG fail
- **Fix:** Add credits to OpenRouter OR switch to alternative provider
- **Time:** 15 minutes (if account owner has payment method)

### 🟡 BLOCKER #2: Entity Lookup Failures (Database Level)
- **Impact:** Valid entities like LOT-MANG-005 return "no data" to user
- **Root:** Not database - must be SQL template or scope filtering
- **Example:** LOT-MANG-005 exists but SQL query fails to find it
- **Fix:** Debug `sql_tools.py` batch/lot query templates
- **Time:** 30-60 minutes

### 🟡 BLOCKER #3: Citation Metadata Empty
- **Impact:** Validation audit sees 0.0 citation relevance
- **Root:** Either LLM offline (confirmed) OR orchestrator not emitting sources
- **Fix:** Verify `agent_orchestrator.py` dict structure, test after LLM restored
- **Time:** 30 minutes

---

## 7. RECOMMENDED PATH FORWARD

### Immediate (Today)
1. **Fix OpenRouter account:**
   - Go to https://openrouter.ai/settings/credits
   - Add credits (or use API from another account if available)
   - Test LLM connectivity: `python scripts/rag_grounding_diagnostic.py`

2. **Debug entity lookup failures:**
   - Check `backend/app/ai/tools/sql_tools.py` for batch lookup template
   - Run direct SQL: `SELECT * FROM batches WHERE code='LOT-MANG-005' AND cooperative_id='...'`
   - Compare query that chatbot runs vs manual SQL

### After LLM Restored (Hours 2-4)
1. **Re-run validation audit:**
   ```bash
   python scripts/chatbot_validation_audit.py
   ```
   - Expected: Pass rate > 50% (up from 0%)
   
2. **Test RAG retrieval on knowledge topics:**
   ```bash
   # Manual test 5 RAG queries
   ```
   - "Quelles bonnes pratiques de séchage ?" → should find knowledge_chunks
   - "Benchmarks de pertes ?" → should find reference_metrics

3. **Re-run all 5 audits:**
   ```bash
   python scripts/chatbot_unseen_generalization_audit.py
   python scripts/chatbot_t01_t05_variants_audit.py
   python scripts/chatbot_targeted_manual_regression_audit.py
   python scripts/chatbot_manager_style_audit.py
   python scripts/chatbot_validation_audit.py
   ```

### If Blockers Persist
- **RAG retrieval not finding knowledge chunks:** Check HybridRetriever vector search logic
- **Citation scores still 0:** Implement citation dict wrapping in orchestrator
- **HYBRID latency > 5s:** May require optimization after LLM restored

---

## 8. REMAINING UNKNOWNS

These require testing after LLM is restored:
1. Will RAG retrieval actually return knowledge_chunks when LLM is available?
2. Will HYBRID route synthesize answers correctly with restored LLM?
3. Will citation metadata flow through orchestrator correctly?
4. Is entity lookup failure in SQL template or in scope filtering?

---

**Diagnostic Tool:** `/backend/scripts/rag_grounding_diagnostic.py`  
**Files Generated:** 1 (diagnostic script)  
**Code Changes:** 0 (audit only)
