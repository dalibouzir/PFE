# Hardships & Learnings: WeeFarm PFE Project

**Purpose:** Document technical and project challenges encountered during development, with resolutions and key lessons learned.

**Period:** April 17-25, 2026  
**Severity Levels:** 🔴 Critical | 🟠 Major | 🟡 Medium | 🟢 Minor

---

## Challenge #1: ML Reliability and Production-Readiness Gates

**Date:** April 17, 2026  
**Severity:** 🔴 Critical  
**Area:** ML System & Production Readiness

### The Problem

The impact recommendation model is operationally deployed, but reliability targets are not fully met in the runtime status. Specifically:

```
❌ Precision@1:            0.0 vs target 0.7 (target gap: -0.7)
❌ Harmful rate:           1.0 vs target 0.02 (target gap: +0.98)
❌ Calibration error:      1.0 vs target 0.05 (target gap: +0.95)
❌ Mean loss reduction:    0.0 vs target > 0.0 (not improving)
❌ Feedback rows:          16 vs target 200 (only 8% of needed data)
```

**Impact:** We cannot claim "production-ready" confidence despite strong baseline metrics. System remains in **advisory mode**.

### Root Cause Analysis

1. **Insufficient Real Feedback:** Most data is auto-backfilled proxy labels, not actual operator feedback
2. **Low Coverage:** Recommendations don't reach enough batches for statistical reliability
3. **Calibration Issues:** Model confidence scores not well-calibrated to actual performance
4. **Limited Evaluation Data:** Only 16 feedback rows insufficient for reliable performance estimates

### What We Tried

✓ Rebuilt and retrained through Docker startup pipeline  
✓ Validated `/ml/health` and `/ml/reliability` endpoints  
✓ Verified manager authentication and API access  
✓ Inspected artifact files for training completion  
✓ Ran live API snapshots with explicit token auth

### Current Workaround

```python
# System enforces guardrails in recommendation logic
if confidence < 0.6 or harmful_probability > 0.1 or drift_detected:
    return {
        "mode": "abstain",
        "recommendation": None,
        "reason": "manual_review_required",
        "context": full_context_for_manager
    }
```

**Result:** MVP/preproduction mode is stable. Autonomous recommendations blocked; managers get assistive context instead.

### Final Resolution Status

✅ **Partial Resolution** - MVP/preprod readiness achieved  
❌ **Production Gate Remains Open** - Reliability targets still unmet

### Lessons Learned

1. **"Model available" ≠ "Model production-ready"**
   - Just because a model runs doesn't mean it's safe to automate decisions with it
   - Need explicit, quantified reliability gates

2. **Reliability targets must be enforced as hard gates**
   - Don't imply production-readiness based on artifact metrics alone
   - Separate offline evaluation from runtime readiness checks

3. **Feedback volume is critical**
   - 16 proxy rows vs 200 real rows = not enough signal
   - Need operational feedback loop to close the confidence gap

4. **Calibration is as important as accuracy**
   - Model can be "right" but poorly calibrated
   - Confidence scores must correlate with actual correctness

### Recommendations for Next Phase

```
Priority 1: Collect Real Feedback
├─ Implement UI for manager feedback on recommendations
├─ Track: accepted? executed? outcome? loss_before/after?
├─ Target: 50+ real feedback rows in 1 week
└─ Expected impact: Recalibrate model, improve precision@1

Priority 2: Improve Recommendation Coverage
├─ Analyze why coverage = 0%
├─ Check if recommendations reach batches with feedback
├─ Tune coverage threshold if too high
└─ Target: 60%+ coverage on active batches

Priority 3: Retrain with Real Data
├─ Once we have 50+ real feedback rows
├─ Retrain impact recommender with real labels
├─ Expected: precision@1 → 0.6-0.7+
└─ Timeline: 2 weeks after feedback collection
```

---

## Challenge #2: Feedback Loop Quality (Real-World Learning)

**Date:** April 17, 2026  
**Severity:** 🔴 Critical  
**Area:** ML & Operations Integration

### The Problem

The feedback dataset is mostly auto-backfilled **proxy data**, with **zero real operator feedback rows**.

```
Current Feedback Breakdown:
├─ Proxy/Backfilled Rows:   16 (100%)
├─ Real Operator Feedback:   0 (0%)
└─ Total Feedback Rows:     16
```

**Impact:** 
- Offline metrics look strong in parts, but built on synthetic data
- Trust in real-world decision quality remains limited
- Difficult to prove model helps actual operations

### Root Cause Analysis

1. **Feedback Collection UI/Process Not Yet Active**
   - UI for "Did this recommendation help?" not fully wired
   - Operators don't see feedback form in manager interface
   - No routine for logging accepted/executed/outcome

2. **Lack of Operational Context**
   - Managers don't yet use recommendations as routine input
   - No formal process for tracking recommendation + outcome

3. **Data Labeling Complexity**
   - Feedback requires: recommendation ID, acceptance, execution, loss delta, timestamp
   - Needs to be easy for busy managers to provide

### What We Tried

✓ Confirmed schema supports full feedback fields (accepted, executed, loss_before, loss_after, delta_loss, reasons, confidence)  
✓ Validated `/ml/feedback` endpoint (POST to log feedback)  
✓ Verified reliability payloads include feedback row counts  
✓ Reviewed manager dashboard for feedback UI entry points  
✓ Checked database for real feedback rows (found zero)

### Current Workaround

```python
# Use proxy/backfilled data for initial model training
# Keep human-in-the-loop override always available
# Log every recommendation for later analysis

feedback = {
    "recommendation_id": uuid,
    "manager_id": uuid,
    "batch_id": uuid,
    "accepted": None,  # Waiting for real feedback
    "executed": None,  # Waiting for real feedback
    "outcome": "pending",
    "source": "proxy_backfill"  # Mark source
}
```

### Final Resolution Status

❌ **Not Fully Resolved** - Technical pipeline is ready, operational collection is the blocker

### Lessons Learned

1. **Real cooperative feedback volume is THE KEY METRIC**
   - Models are only as good as the data they learn from
   - Synthetic data can bootstrap, but real data is essential for trust

2. **Feedback must be part of operations, not added later**
   - Can't retrofit feedback collection; must be integrated in workflow
   - Manager needs to see: "Was this recommendation good?" as part of their process

3. **Closing the feedback loop takes operational discipline**
   - Requires manager buy-in and simple UX
   - Without routine feedback, models can't improve

4. **Proxy data has an expiration date**
   - Useful for MVP and initial training
   - But doesn't prove real-world value
   - Must transition to real feedback to justify production use

### Recommendations for Next Phase

```
Priority 1: Make Feedback Collection Mandatory but Easy
├─ Add feedback form right after manager makes decision
├─ Required fields: accepted (Y/N), executed (Y/N), outcome_observed (in 1 week)
├─ Optional: notes on why/why not
└─ Target: 10+ feedback entries per week from managers

Priority 2: Integrate Feedback into Dashboard
├─ Show: "This recommendation was accepted X% of the time"
├─ Show: "Average loss reduction when followed: X%"
├─ Make feedback impact visible to managers
└─ Expected: Increased adoption and engagement

Priority 3: Run Pilot Feedback Collection
├─ Target: 50 real feedback entries in 2 weeks
├─ Analyze patterns: which recommendations were helpful?
├─ Retrain with real data
└─ Expected: Precision@1 improves from 0.0 → 0.5+
```

---

## Challenge #3: Dashboard/Analytics Integration Correctness

**Date:** April 17, 2026  
**Severity:** 🟠 Major  
**Area:** Frontend & Analytics Integration

### The Problem

Dashboard and analytics pages consume real backend analytics data, but recommendations shown there are primarily derived from analytics rule logic. Some UI blocks use fallback placeholders when data is sparse.

```
Current Dashboard Data Sources:
├─ Operational Data:      ✅ Real-time, via APIs
├─ Analytics KPIs:        ✅ Computed server-side
├─ ML Recommendations:    ⚠️ Rules-based fallback
├─ Confidence/Provenance: ❌ Not always visible
└─ Visual Indicators:     🟡 Mixed real/fallback/synthetic
```

**Impact:** 
- Decision UI is functional but not purely ML-driven
- Users can't easily distinguish real recommendations from rules/fallback
- Trust in recommendations reduced if source is unclear

### Root Cause Analysis

1. **Frontend depends on `/analytics/dashboard` payload**
   - Local insight builders derive values, not pure ML output
   - Direct ML endpoint integration incomplete

2. **ML Endpoint Integration Incomplete**
   - Managers don't see `/ml/predict` or `/ml/recommend` output directly
   - Passes through analytics layer which may transform/filter

3. **Fallback Masking**
   - When data is sparse, system uses fallback logic
   - UI doesn't clearly mark these as fallback vs real recommendation

### What We Tried

✓ Audited manager dashboard end-to-end  
✓ Traced data source paths (API → service → frontend)  
✓ Verified analytics endpoint responses  
✓ Reviewed fallback behavior in UI blocks  
✓ Checked frontend component data dependencies

### Current Workaround

```typescript
// Manager dashboard continues using current hierarchy
// Documentation added for provenance
interface DashboardRecommendation {
  value: string
  source: "ml_model" | "analytics_rule" | "fallback"
  confidence: number | null
  explanation: string
}

// Every recommendation gets a source marker
recommendation = {
  value: "Reduce processing time by 2 hours",
  source: "fallback",  // Track source
  confidence: null,
  explanation: "Based on typical mango processing duration"
}
```

### Final Resolution Status

✅ **Partially Resolved** - Layout and hierarchy improved, but full ML-first rendering pending

### Lessons Learned

1. **Provenance is as important as the value**
   - "What's the recommendation?" is less important than "How did you get there?"
   - Users need to trust the source

2. **Three recommendation sources must be clearly distinguished**
   - ML Model (learned from data)
   - Analytics Rule (hard-coded business logic)
   - Fallback (no data available)

3. **Fallback isn't bad; obscured fallback is**
   - Okay to use sensible defaults when data sparse
   - NOT okay to present defaults as ML recommendations

4. **Frontend-backend integration requires explicit contracts**
   - Can't rely on implicit understanding
   - Need explicit "is this from ML or fallback?" field

### Recommendations for Next Phase

```
Priority 1: Add Source Labels to All Recommendations
├─ Badge/icon: "ML Model", "Rule", "Fallback"
├─ Color coding: Green (ML) | Yellow (Rule) | Gray (Fallback)
├─ Tooltip: Shows how value was calculated
└─ Timeline: 1-2 days

Priority 2: Direct ML Endpoint Integration
├─ Update dashboard to call `/ml/recommend` directly
├─ Show confidence scores
├─ Include reasoning/explanation
├─ Timeline: 3-4 days

Priority 3: Feedback Integration
├─ Add "Was this helpful?" button for each recommendation
├─ Log response to `/ml/feedback`
├─ Show: "Managers found this helpful X% of the time"
└─ Timeline: 2-3 days
```

---

## Challenge #4: Dockerized Deployment Readiness

**Date:** April 17, 2026  
**Severity:** 🟡 Medium  
**Area:** DevOps & Deployment

### The Problem

Need to ensure backend stack is reproducibly rebuildable and bootstraps ML artifacts automatically on startup.

```
Startup Sequence Requirements:
1. Load environment variables
2. Start PostgreSQL with pgvector
3. Run Alembic migrations
4. Seed initial data
5. Train ML models
6. Start FastAPI server
7. Verify health endpoints
```

**Impact:** 
- Without consistency, preprod demos and validation could drift from local
- Dependency on startup sequence fragility

### Root Cause Analysis

1. **Complex Startup Sequence**
   - Multiple stages must complete in order
   - Any failure blocks API startup

2. **Unclear Completion Signals**
   - How do we know migrations are done?
   - How do we know ML training succeeded?
   - Service "starts" before it's truly ready

3. **Limited Startup Logging**
   - Hard to diagnose where startup fails
   - No clear progress indicators

### What We Tried

✓ Ran `docker compose up -d --build`  
✓ Checked container health status  
✓ Inspected logs for Alembic + seed + ML training  
✓ Verified API docs endpoint  
✓ Validated health check responses  
✓ Tested role-based access after startup

### Current Workaround

```bash
# Rebuild verification checklist
docker compose up -d --build

# Wait for startup (typically 30-45 seconds)
sleep 45

# Verify each stage
docker compose logs test-backend | grep "Alembic" | tail -5
docker compose logs test-backend | grep "Training" | tail -5
docker compose logs test-backend | grep "Started" | tail -2

# Test health
curl -s http://localhost:8000/health | jq .

# Test auth
TOKEN=$(curl -s http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"manager@weefarm.local","password":"Manager123!"}' | jq -r '.access_token')

# Verify ML endpoints
curl -s http://localhost:8000/ml/health \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### Final Resolution Status

✅ **Resolved** - Preproduction backend scope working reliably

### Lessons Learned

1. **Rebuild verification must check multiple layers**
   - Container status alone is insufficient
   - Must verify: migrations, models, API endpoints, health

2. **Startup sequence is critical**
   - Each stage must complete before next starts
   - Partial startup is dangerous (appears ready but isn't)

3. **Logging is essential for debugging**
   - Need clear markers: "Starting X", "Completed X", "Failed X"
   - Helps diagnose issues during deployment

4. **Health checks need to be deep**
   - Not just "is port 8000 open?"
   - Should verify: DB connection, models loaded, auth working

### Recommendations

```
Priority 1: Add Startup Progress Indicators
├─ Log: "Stage 1/7: Loading environment..."
├─ Log: "Stage 2/7: Connecting to database..."
├─ Log: "Stage 3/7: Running migrations..."
├─ Timeline: 2 hours
└─ Benefit: Easier debugging

Priority 2: Comprehensive Health Check
├─ /health endpoint checks:
│  ├─ Database connectivity
│  ├─ pgvector availability
│  ├─ ML models loaded
│  ├─ Authentication working
│  └─ RAG embeddings ready
├─ Return: { ready: true/false, checks: {...} }
└─ Timeline: 2-3 hours

Priority 3: Startup Timeout Handling
├─ If startup > 60 seconds, log warning
├─ If startup > 120 seconds, fail with message
├─ Include: what's still running
└─ Timeline: 1 hour
```

---

## Challenge #5: Production Deployment Architecture

**Date:** April 25, 2026  
**Severity:** 🔴 Critical  
**Area:** DevOps & Multi-Cloud Deployment

### The Problem

Production deployment required stabilizing cross-platform connectivity between:
- Backend on Azure Container Apps
- Frontend on Vercel
- Database on Supabase PostgreSQL/pgvector

While also migrating persistence from initial setup to Supabase, this introduced friction:

```
Deployment Complexity:
├─ Environment Configuration
│  ├─ DATABASE_URL (local vs Azure vs Supabase)
│  ├─ API Base URL (localhost:8000 vs Azure endpoint)
│  └─ CORS Origins (local vs Vercel vs Azure)
│
├─ Data State Synchronization
│  ├─ Seed data (localhost has test data, production doesn't)
│  ├─ Database migration state (must be identical)
│  └─ ML artifacts (must be deployed with backend)
│
├─ Role Access Verification
│  ├─ JWT tokens work differently in different environments
│  ├─ Database user roles may differ
│  └─ Need consistent test credentials
│
└─ Service Readiness Verification
   ├─ Backend health endpoint
   ├─ Database connectivity
   ├─ Frontend UI accessibility
   └─ API route response times
```

**Impact:** 
- Deployment time increased 3x (1 week instead of 2-3 days)
- Validation cycles were longer
- Temporary authentication/data state inconsistencies

### Root Cause Analysis

1. **Multi-Platform Complexity**
   - 3 cloud services (Azure, Vercel, Supabase) with different configs
   - Each has different environment variable handling
   - No single source of truth for configuration

2. **Live Data Migration**
   - Migrating from initial setup to Supabase was risky
   - Had to handle: schema changes, data transfer, connection string updates
   - Window of potential data loss/inconsistency

3. **Configuration Drift Risk**
   - Local development uses different DATABASE_URL than production
   - Azure environment may have different settings than Vercel
   - No enforcement of parity

4. **Insufficient Pre-Deployment Validation**
   - Didn't have comprehensive checklist before deploying
   - Discovered issues after deployment

### What We Tried

✓ Rebuilt/restarted backend containers multiple times  
✓ Verified health and API routes  
✓ Validated role-based access with real tokens  
✓ Migrated to Supabase connection strings  
✓ Cleaned seed/mock records with controlled scripts  
✓ Tested authentication flows end-to-end  
✓ Verified database schema consistency  
✓ Confirmed pgvector availability on Supabase

### Current Workaround

```bash
# Pre-Deployment Verification Checklist

# 1. Environment Configuration
echo "Backend DATABASE_URL (should be Supabase):"
echo $DATABASE_URL | grep supabase

# 2. Test Database Connectivity
curl -X GET $BACKEND_URL/health \
  -H "Authorization: Bearer $TEST_TOKEN"

# 3. Verify Auth Flow
TOKEN=$(curl -X POST $BACKEND_URL/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"manager@weefarm.local","password":"Manager123!"}')

# 4. Test Key API Endpoints
curl -X GET $BACKEND_URL/members \
  -H "Authorization: Bearer $TOKEN"

# 5. Verify Frontend Connectivity
curl -X GET $FRONTEND_URL/api/health

# 6. ML Endpoint Check
curl -X GET $BACKEND_URL/ml/health \
  -H "Authorization: Bearer $TOKEN"
```

### Final Resolution Status

✅ **Resolved** - Backend and frontend live, connected to Supabase, verified through smoke tests

### Lessons Learned

1. **Lock one production database source of truth EARLY**
   - Migrate once, never again
   - Supabase is now single source of truth
   - No more dual-database confusion

2. **Disable non-essential seeding in production**
   - Test data belongs in development only
   - Production should start clean
   - Use migration scripts for real data

3. **Treat data cleanup as a controlled operation**
   - Not a quick script; requires explicit targeting
   - Must verify before/after
   - Dry-run first, then execute with approval

4. **Environment parity is critical**
   - Same DATABASE_URL format everywhere
   - Same API endpoint routes
   - Same CORS origins
   - Use configuration management tools

5. **Multi-cloud requires integration planning**
   - More moving parts = more potential failures
   - Need explicit handshake verification between services
   - Document the dependency graph

6. **Pre-deployment validation prevents 80% of issues**
   - Comprehensive checklist saves deployment cycles
   - Dry-run production deployment in staging first
   - Verify each layer independently, then integration

### Recommendations for Next Production Deployment

```
Pre-Deployment (1 week before):
├─ Environment variables: Audit all, document required values
├─ Database: Verify schema, backups, recovery plan
├─ Migrations: Test on copy of production data
├─ Secrets: Rotate API keys, verify in .env
├─ Configuration: Document all settings
└─ Testing: Run full smoke test suite

Deployment Day:
├─ Backup production database (automated, verify)
├─ Deploy backend (one instance, verify health)
├─ Deploy frontend (test key routes)
├─ Verify integration (frontend → backend → database)
├─ Run smoke tests (150+ API endpoints)
├─ Verify auth flows
├─ Check ML endpoints
└─ Monitor for 1 hour

Post-Deployment:
├─ Monitor error rates (should be <0.1%)
├─ Check response times (p95 <1s)
├─ Verify user adoption (should grow gradually)
├─ Monitor database connections (should stabilize)
└─ Alert on any anomalies
```

---

## Challenge #6: Alembic Revision Drift Between Supabase and Deployed Docker Image

**Date:** April 28, 2026  
**Severity:** 🔴 Critical  
**Area:** Backend Deployment (Docker + Alembic + Azure Container Apps)

### The Problem

Backend startup failed in Azure with:

```
FAILED: Can't locate revision identified by '7c9d2e4a1b3f'
```

At the same time:
- Supabase `alembic_version` already pointed to `7c9d2e4a1b3f`
- Local migration file existed: `backend/alembic/versions/7c9d2e4a1b3f_add_chat_ui_blocks.py`

**Important clarification:** this was **not** caused by pgvector changing IDs.  
It was a **code/database migration state mismatch**.

### Root Cause Analysis

1. **DB ahead of deployed image**
   - Migration was already applied to Supabase.
   - Running container image did not include that migration revision file.

2. **Alembic dual-state contract violated**
   - Alembic requires both:
     - revision file in code image
     - revision value in DB table
   - If either side is missing/outdated, startup migration fails.

3. **Platform packaging nuance**
   - First republished image was ARM-only from local machine.
   - Azure required `linux/amd64`, causing an additional deploy failure until rebuilt with amd64.

### What We Tried

✓ Verified migration file exists locally  
✓ Verified Supabase `alembic_version = 7c9d2e4a1b3f`  
✓ Rebuilt image from project root context  
✓ Added in-image verification for migration file before push  
✓ Rebuilt with `--platform linux/amd64` and redeployed to Azure

### Final Resolution Status

✅ **Resolved** - New immutable image includes migration file and runs successfully in Azure  
✅ `/health` endpoint returns `200 OK`

### Lessons Learned

1. **Never treat Alembic as DB-only state**
   - Migration files in image must always match DB revision chain.

2. **Deploy image + migration as one release unit**
   - If DB is migrated but image is old, startup can fail immediately.

3. **Add image-level migration verification gate**
   - Before push/deploy, validate critical revision files exist inside `/app/alembic/versions`.

4. **Pin target runtime architecture**
   - Azure Container Apps expects `linux/amd64` in this setup.
   - Building from ARM laptop requires explicit `--platform linux/amd64`.

### Prevention Actions

```
Deployment Guardrails:
├─ Build from project root context (for backend/Dockerfile COPY paths)
├─ Build immutable tag (never use latest)
├─ Build for linux/amd64
├─ Verify required migration file inside built image
├─ Push only if verification passes
└─ Then update Azure revision
```

---

## Summary: Challenges Overcome

| Challenge | Severity | Area | Status | Key Lesson |
|-----------|----------|------|--------|------------|
| ML Reliability Gates | 🔴 Critical | ML | Partial ✅ | Hard gates required |
| Real Feedback Loop | 🔴 Critical | Operations | Not Resolved ❌ | Volume is key metric |
| Analytics Integration | 🟠 Major | Frontend | Partial ✅ | Provenance matters |
| Docker Readiness | 🟡 Medium | DevOps | Resolved ✅ | Multiple layer verification |
| Production Deployment | 🔴 Critical | Infrastructure | Resolved ✅ | Configuration parity critical |
| Alembic Revision Drift | 🔴 Critical | Deployment | Resolved ✅ | Code+DB migration state must stay aligned |

---

## Recommendations for Next Phase

### Immediate (Next 1-2 weeks)

1. **Collect Real Feedback** - Implement feedback UI, target 50+ responses
2. **Improve Coverage** - Debug why recommendation coverage is 0%, fix
3. **Enhance Provenance** - Add source labels to all recommendations in UI

### Short-term (Next 1 month)

1. **Retrain with Real Data** - Use collected feedback to retrain impact recommender
2. **Improve Precision** - Target precision@1 > 0.6 (from current 0.0)
3. **Monitor Performance** - Set up dashboards to track real-world recommendation accuracy

### Medium-term (Next 1-3 months)

1. **Close ML Reliability Gate** - Hit all targets: precision@1=0.7+, harm rate=0.02-, calibration=0.05-
2. **Move to Production ML** - Transition from advisory to autonomous recommendations
3. **Continuous Learning** - Implement automated retraining with fresh feedback

---

**Document Prepared By:** WeeFarm Development Team  
**Last Updated:** April 28, 2026  
**Status:** Active - For Internal Reference & PFE Submission
