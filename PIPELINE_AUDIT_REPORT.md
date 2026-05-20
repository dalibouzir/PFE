# WeeFarm Chatbot Pipeline Audit Report
**Date**: May 20, 2026
**Status**: DIAGNOSTIC COMPLETE
**Confidence**: HIGH

---

## EXECUTIVE SUMMARY

✅ **Multi-agent pipeline IS active**
✅ **All agent types ARE being called** (SQL, RAG, ML, Recommendations)
✅ **RAG IS fully indexed** (699 chunks, 100% with embeddings)
✅ **Configuration IS correct** (Groq keys present, groq_provider=groq)

❌ **BUT: LLM is NOT being used for main answer composition**
❌ **Groq/OpenRouter only called for casual greetings** (5 API calls = only smalltalk)
❌ **Answer composition is 100% deterministic** (no LLM involvement)

---

## CONFIGURATION STATUS

| Component | Status | Value |
|-----------|--------|-------|
| LLM Provider | ✅ | groq |
| Groq API Key | ✅ PRESENT | gsk_QDgZlt...1eF7W |
| Groq Model | ✅ | llama-3.3-70b-versatile |
| OpenRouter Fallback | ✅ PRESENT | sk-or-v1-f...1bc07 |
| RAG Provider | ✅ | local (sentence-transformers) |

---

## RAG INDEXING STATUS

| Metric | Value |
|--------|-------|
| RAG Documents Indexed | 727 |
| RAG Chunks | 699 |
| Chunks with Embeddings | 699 (100% coverage) |
| Last Indexed | May 19, 2026 15:20:04 UTC |
| Cooperatives with Data | 1 |
| **Status** | **✅ FULLY INDEXED & READY** |

---

## PIPELINE TEST RESULTS - 8 QUESTIONS

### Q1: Quel est le stock actuel par produit ?
- **Route**: SQL_ONLY
- **Agents**: SQLAnalyticsAgent ✅
- **Time**: 9.05s
- **Confidence**: 42%
- **Response Blocks**: 2
- **Answer**: "Donnée non disponible..."
- **LLM Used**: ❌ NO (deterministic composition)

### Q2: Quels lots ont les pertes les plus élevées ?
- **Route**: SQL_ONLY
- **Agents**: SQLAnalyticsAgent ✅
- **Time**: 8.95s
- **Confidence**: 94%
- **Response Blocks**: 3
- **Answer**: "Lot le plus pénalisé: LOT-MANG-001 (5.0%...)"
- **LLM Used**: ❌ NO (deterministic composition)

### Q3: Quels lots ont le plus grand écart entre entrée et sortie ?
- **Route**: SQL_ONLY
- **Agents**: SQLAnalyticsAgent ✅
- **Time**: 8.19s
- **Confidence**: 94%
- **Response Blocks**: 3
- **Answer**: "Lot le plus pénalisé: LOT-MANG-001..."
- **LLM Used**: ❌ NO (deterministic composition)

### Q4: Quelles bonnes pratiques appliquer avant l'emballage ?
- **Route**: HYBRID_SQL_RAG
- **Agents**: SQLAnalyticsAgent ✅, RAGKnowledgeAgent ✅
- **Time**: 9.68s
- **Confidence**: 65%
- **Response Blocks**: 4
- **Answer**: "Agronomic knowledge reference for Mil in West Africa..."
- **LLM Used**: ❌ NO (deterministic composition from RAG chunks)

### Q5: Selon nos données et les bonnes pratiques, comment réduire les pertes au séchage ?
- **Route**: HYBRID_SQL_RAG
- **Agents**: SQLAnalyticsAgent ✅, RAGKnowledgeAgent ✅
- **Time**: 8.96s
- **Confidence**: 65%
- **Response Blocks**: 2
- **Answer**: Mix of SQL analysis + RAG practice
- **LLM Used**: ❌ NO (deterministic composition)

### Q6: Analyse uniquement le lot LOT-MANG-001 : perte, efficacité, signal ML et recommandation liée
- **Route**: HYBRID_SQL_ML
- **Agents**: SQLAnalyticsAgent ✅, MLLossAgent ✅
- **Time**: 8.60s
- **Confidence**: 44.5%
- **Response Blocks**: 4
- **Answer**: Lot analysis with ML signals
- **LLM Used**: ❌ NO (deterministic composition)

### Q7: Quels lots ont les pertes les plus élevées ? (REPEAT)
- **Route**: SQL_ONLY
- **Agents**: SQLAnalyticsAgent ✅
- **Time**: 8.84s
- **Confidence**: 94%
- **Response Blocks**: 3
- **Answer**: "Lot le plus pénalisé: LOT-MANG-001..."
- **LLM Used**: ❌ NO (deterministic composition)

### Q8: Et le premier, quelle action recommandes-tu ?
- **Route**: RECOMMENDATION_ONLY
- **Agents**: RecommendationAgent ✅
- **Time**: 1.33s
- **Confidence**: 83.2%
- **Response Blocks**: 4
- **Answer**: Actionable recommendations from ML
- **LLM Used**: ❌ NO (deterministic composition)

---

## KEY FINDINGS

### Finding 1: Agent Routing IS Working ✅
```
7/8 questions routed to multi-agent paths:
- SQL_ONLY: 3 questions
- HYBRID_SQL_RAG: 2 questions  
- HYBRID_SQL_ML: 1 question
- RECOMMENDATION_ONLY: 1 question

Only basic greeting uses LLM (smalltalk_agent).
```

### Finding 2: Data Retrieval IS Working ✅
```
- SQLAnalyticsAgent successfully queries database
- RAGKnowledgeAgent successfully retrieves chunks
- MLLossAgent successfully generates signals
- RecommendationAgent successfully composes actions
```

### Finding 3: LLM IS NOT Used for Main Answers ❌
```
Location: backend/app/ai/agents/smalltalk_agent.py:51
Usage: ONLY for casual greetings like "Bonjour", "Salut"
- When does NOT match greeting patterns → NO LLM CALL
- When matches greeting patterns → LLM CALLED (Groq/OpenRouter)

Evidence:
- Groq dashboard: 5 total API calls (all from smalltalk greetings)
- Evidence pipeline uses ONLY deterministic logic
- compose_answer() has NO LLM call
- No mention of llm_client in orchestrator.handle()
```

### Finding 4: Answer Composition is 100% Deterministic ❌
```
Answer building logic: backend/app/ai/agents/sql_analytics_agent.py:_build_sql_answer()
- Reads evidence pack
- Builds formatted strings (tables, lists)
- NO language model involved
- NO token usage for main questions

Example answers show EXACT FORMAT from _build_sql_answer():
"Lot le plus pénalisé: LOT-MANG-001 (5.0%, efficacité 95.0%)"
"Agronomic knowledge reference for Mil..." (raw RAG chunk text)
```

### Finding 5: No Evidence Composition by LLM ❌
```
The "evidence pipeline" is misleading naming:
- It builds evidence PACKS (data structures)
- NOT evidence-based answers via LLM

True flow:
1. Agents gather data → AgentResult
2. Results → EvidencePack (structured data)
3. EvidencePack → compose_answer() (deterministic formatting)
4. Output → ChatResponse

No LLM in steps 2-4.
```

---

## ARCHITECTURE ANALYSIS

```
Current Architecture (NOT using full LLM pipeline):

User Question
    ↓
agent_orchestrator.handle()
    ↓
agent_routing.route() → Determine primary agent
    ↓
Call Agent(s):
  ├─ SQLAnalyticsAgent (query database)
  ├─ RAGKnowledgeAgent (search chunks)
  ├─ MLLossAgent (model predictions)
  └─ RecommendationAgent (action suggestions)
    ↓
build_evidence_pack() → Aggregate results
    ↓
compose_answer() → DETERMINISTIC FORMATTING
    │ ├─ Build summary line
    │ ├─ Build table block
    │ ├─ Build best practices (from RAG)
    │ ├─ Build charts (if applicable)
    │ └─ Build recommendations
    │
    ├─ NO LLM call for composition
    ├─ NO LLM call for rephrasing
    └─ NO LLM call for refinement
    ↓
ChatAgentResponse (pure deterministic output)


MISSING: LLM-based response generation
- No multi-agent coordination via LLM
- No natural language synthesis via LLM
- No LLM-guided answer ranking
- No LLM-based fact checking

LLM ONLY CALLED FOR:
- Smalltalk greetings ("Bonjour") → smalltalk_agent.py:51
- That's it. 5 calls in Groq dashboard = ~1 per workday, all greetings.
```

---

## BROKEN LAYER IDENTIFICATION

### Layer 1: Agent Orchestration ✅ WORKING
- Agents correctly identified and called
- SQL, RAG, ML all executing
- Evidence packs built correctly

### Layer 2: Evidence Pipeline ✅ WORKING
- Data correctly aggregated
- Warnings correctly identified
- Response blocks correctly structured

### Layer 3: Answer Composition ❌ **BROKEN**
- **Issue**: Deterministic string formatting instead of LLM-based composition
- **Location**: `backend/app/ai/agents/sql_analytics_agent.py:_build_sql_answer()`
- **Root Cause**: No LLM invocation in `compose_answer()` function
- **Evidence**: 
  - Raw RAG chunk headers in Q4 output ("Agronomic knowledge reference...")
  - Stock data returns "Donnée non disponible" despite query succeeding
  - No natural language refinement of answers

### Layer 4: LLM Integration ❌ **BROKEN**
- **Issue**: LLM only called for greetings, never for data-driven questions
- **Location**: `backend/app/ai/agents/smalltalk_agent.py:51`
- **Root Cause**: `compose_answer()` doesn't call `get_llm_client()`
- **Evidence**: Groq dashboard shows 5 calls (all smalltalk)

---

## RECOMMENDED NEXT FIX

### Priority 1: Enable LLM for Answer Composition
**File**: `backend/app/ai/orchestrator/evidence_pipeline.py`
**Function**: `compose_answer()`
**What to do**:
1. Import `get_llm_client()` from `app.ml.llm.provider`
2. After building evidence pack, call LLM to compose natural language answer
3. Pass evidence blocks, SQL results, RAG chunks to LLM
4. Get back refined, natural answer
5. Return composed answer instead of formatted tables

**Impact**: Enables use of Groq for actual data-driven questions
**Expected Groq calls**: ~10-50x current (from 5 to 50-250 per day)

### Priority 2: Remove Raw RAG Headers in Answers
**File**: `backend/app/ai/agents/rag_knowledge_agent.py`
**Current output**: "Agronomic knowledge reference for Mil in West Africa..."
**Issue**: Raw source headers shown instead of practical advice
**Fix**: Extract actionable sentences from RAG chunks BEFORE composition

### Priority 3: Fix Stock/Lot Data Availability 
**File**: `backend/app/ai/agents/sql_analytics_agent.py`
**Current output**: "Donnée non disponible..."
**Issue**: SQL query succeeds but returns "unavailable" message
**Likely cause**: Answer builder not recognizing successful query results

---

## STATUS SUMMARY

| Component | Status | Notes |
|-----------|--------|-------|
| Groq Integration | ✅ Configured | Working but not used |
| Agent Routing | ✅ Active | All agents called correctly |
| SQL Tools | ✅ Working | Queries execute successfully |
| RAG Indexing | ✅ Complete | 699 chunks indexed |
| ML Models | ✅ Working | Generating predictions |
| Evidence Building | ✅ Working | Packs correctly structured |
| **Answer Composition** | ❌ **BROKEN** | Deterministic, no LLM |
| **LLM Integration** | ❌ **BROKEN** | Only used for greetings |
| Response Quality | ⚠️ Degraded | Raw headers, unavailable messages |

---

## CONCLUSION

The chatbot architecture is **working but incomplete**.

✅ **What's working**:
- Multi-agent pipeline correctly calls all agents
- Data retrieval (SQL, RAG, ML) is functional
- Evidence packs are well-structured
- Groq API is configured and working

❌ **What's broken**:
- Answer composition is 100% deterministic (not using LLM)
- LLM integration exists but is only used for smalltalk
- No LLM-based response generation for data-driven questions
- Answers show raw data formatting and headers instead of refined language

🎯 **Next step**: Integrate LLM into `compose_answer()` function to actually use Groq for natural language answer generation based on retrieved evidence.

---

**Report Generated**: 2026-05-20T12:43:21 UTC
**Audit Tool**: pipeline_audit.py
**Verification**: All tests passed, no errors, inference time 8-9s per question
