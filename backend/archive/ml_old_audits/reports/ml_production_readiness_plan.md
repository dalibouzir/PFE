# WeeFarm ML Production Readiness Plan (Advisory-First)

## Current Status
- Current ML should be treated as advisory decision support, not production-grade predictive authority.
- Regression/classification promotion must remain blocked until both dataset sufficiency and model gates pass.
- Anomaly remains exploratory because labeled anomaly ground truth is unavailable.
- Recommendation policy remains rule-based until action/outcome feedback demonstrates measurable uplift.

## Learning Dependency on Real App History
- Real performance improvement depends on accumulated post-récolte app history.
- Each completed lot can generate up to 4 process-step observations.
- Required operational fields for meaningful supervised learning loops:
  - product
  - stage
  - qty_in
  - qty_out
  - loss_pct
  - efficiency_pct
  - weather
  - duration
  - timestamps
  - recommendation outcome

## Data Semantics
- Weather and duration are features/context signals, not training labels.
- External Senegal context data can enrich priors and heuristics but is not lot-level supervised app label data.
- Cold-start priors must not be treated as observed label truth.

## Promotion Conditions
- `ML_PROMOTED` is allowed only if:
  - dataset size meets production-candidate threshold, and
  - model gate status passes promotion criteria.
- Otherwise output must clearly communicate fallback/readiness state (`INSUFFICIENT_DATA`, `BASELINE_ONLY`, `RULE_BASED`, or `ML_ASSISTED`).

## Safe Implementation Boundaries
- No database migration.
- No schema mutation.
- No workflow mutation (pré-récolte, post-récolte, Collecte, stock policy unchanged).
- Enhancement scope is metadata, readiness policy, feature-readiness reporting, and testable truthfulness.
