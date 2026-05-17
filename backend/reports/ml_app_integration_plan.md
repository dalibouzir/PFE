# ML App Integration Plan (Safe, Non-Promoting)

## Scope
This document is a planning artifact only. No backend runtime implementation, DB migration, workflow change, or model promotion is performed in this task.

## Integration Principles
- Keep real-data readiness as the only production-readiness source of truth.
- Keep `promoted = false` behavior unchanged under current low-data conditions.
- Keep recommendation mode rule-first.
- Integrate only advisory logic that does not weaken readiness gates.

## Component-by-Component Plan
### Regression
- Integration posture: baseline fallback only.
- Runtime promotion: no.
- Intended behavior: keep `stage_season_mean_loss`/baseline-driven decision path as numeric fallback.

### Classification
- Integration posture: advisory candidate only.
- Runtime promotion: no.
- Intended behavior: expose critical-risk signals as advisory metadata only, behind existing readiness constraints.

### Anomaly
- Integration posture: advisory post-step diagnostics candidate.
- Runtime promotion: not as promoted ML.
- Intended behavior: use rule/statistical assessment-mode diagnostics as operational checks after step completion.

### Recommendation Ranking
- Integration posture: rule-first advisory prioritization only.
- Runtime promotion: no learned recommender promotion.
- Intended behavior: rank rule-generated actions for operator assistance, with transparent evidence scoring.

### Readiness Layer
- Integration posture: keep unchanged.
- Runtime promotion: gate controller remains source of truth.
- Intended behavior: no gate threshold weakening, no bypass logic.

## Likely Files to Touch Later (Implementation Phase, Not Now)
- `backend/app/services/ml.py`
- `backend/app/ml/readiness.py`
- `backend/app/ml/features/engineer.py`
- `backend/app/schemas/ml.py`
- `backend/app/ml/training/trainer.py`
- `backend/app/ml/cold_start_priors.py`

## Files That Must Not Be Touched
- `backend/alembic/*`
- `backend/app/models/*` (schema changes)
- workflow/operational modules for pre-récolte/post-récolte/Collecte/stock behavior
- production model artifact files under active runtime registry
- any Supabase data operations outside current normal app flows

## Required Tests Before Any Future Integration
1. `backend/tests/test_ml_readiness_truthfulness.py`
2. `backend/tests/test_synthetic_model_improvement.py`
3. `backend/tests/test_synthetic_ml_benchmark.py`
4. Regression/unit tests for any touched service/schema files.
5. Endpoint-level `/ml` response compatibility checks.

## Risk Register
- Advisory signals may be over-interpreted as promoted ML decisions.
- Synthetic/offline calibration may not transfer to real cooperative operations.
- Classification false alarms can reduce operator trust if surfaced without guardrails.
- Recommendation ranking proxy metrics do not prove real-world uplift.

## Rollback Plan
- Keep integration changes feature-flagged/advisory-only.
- If regressions appear, disable advisory layer and keep existing rule-only output.
- Preserve previous artifacts and report snapshots for rollback traceability.
- Re-run readiness truthfulness tests before and after rollback.

## Explicit Non-Implementation Note
No runtime code path, DB schema, workflow policy, or production model promotion behavior has been changed in this task. This file is planning-only.
