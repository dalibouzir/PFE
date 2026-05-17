# WeeFarm ML Enhancement Strategy (Safe Layer, No Workflow/DB Changes)

## A. Current ML State
- WeeFarm already exposes ML runtime endpoints under `/ml` and service orchestration in `app/services/ml.py`.
- Current feature engineering includes post-récolte operational signals (`process_steps`, `batches`, `products`, `stocks`), historical/rolling behavior, and optional weather augmentation.
- Current model families:
  - `RandomForestRegressor` for loss regression.
  - `RandomForestClassifier` for risk classes.
  - `IsolationForest` for anomaly exploration.
- Recommendation generation remains primarily rule-based, with optional ML confidence/ranking support.
- Chatbot mostly consumes persisted ML traces and logs, not guaranteed fresh per-question direct model inference.

## B. Why Current Performance Is Weak
- Dataset maturity is still limited for robust lot/stage generalization across products and seasons.
- Regression/classification can underperform strong baselines depending on snapshot and split strategy.
- Recommendation policy uplift needs true action/outcome feedback loops, not only synthetic or proxy evidence.
- Anomaly signals are not supervised-validated due to missing anomaly ground-truth labels.

## C. Why More Real Post-Récolte Data Is Needed
- Reliable ML requires sufficient, diverse, real in-app post-récolte observations across crop/stage/weather/time contexts.
- Each completed lot can generate up to 4 process-step observations (`nettoyage`, `séchage`, `tri`, `emballage`).
- True learning for recommendations depends on action + outcome feedback, not static snapshots.
- Without enough real rows, the platform must stay explicit that ML is advisory.

## D. Cold-Start Strategy
- Use explicit non-DB cold-start priors as expert/context rules for explanation and fallback only.
- Do not write priors into database tables.
- Do not train supervised models on priors as if they were observed app labels.
- Keep source provenance explicit (`expert_rule`, `external_context`, `app_history`) to avoid label contamination.

## E. Readiness States
- `INSUFFICIENT_DATA`: dataset too small for reliable claims.
- `BASELINE_ONLY`: baseline/rule behavior only; ML not promotable.
- `RULE_BASED`: recommendation came from rule engine without promotable ML evidence.
- `ML_ASSISTED`: ML supports ranking/scoring but policy remains advisory.
- `ML_PROMOTED`: allowed only when dataset sufficiency and model gates both pass.

## F. Dataset Thresholds
- `min_rows_for_demo_model = 100`
- `min_rows_for_reliable_model = 500`
- `min_rows_for_production_candidate = 1000`

Dataset readiness levels:
- `VERY_LOW_DATA` (<100)
- `DEMO_ONLY` (100-499)
- `RELIABLE_CANDIDATE` (500-999)
- `PRODUCTION_CANDIDATE` (>=1000)

Policy:
- Never expose `ML_PROMOTED` when `N < min_rows_for_production_candidate`.
- Never expose `ML_PROMOTED` when model gate fails.

## G. Duration/Weather Feature Plan
- Weather remains a feature input and context signal, never a label.
- Duration will be derived only from existing fields (`duration_minutes`, `created_at`, `updated_at`, `executed_at`, batch timestamps) in ML/reporting logic.
- Derived duration readiness fields:
  - `step_duration_minutes`
  - `delay_since_previous_step_minutes`
  - `total_postharvest_duration_minutes`
  - `cumulative_duration_before_stage`
  - `missing_duration_flag`
- If timestamps are missing, use safe null/0 fallback for reporting features only.
- Do not use future-only duration leakage in predictive mode.

## H. Recommendation Truthfulness Plan
- Keep current recommendation decision behavior unchanged.
- Add explicit transparency metadata to outputs:
  - readiness state
  - dataset sufficiency context
  - gate status
  - fallback reason
  - recommendation mode (`RULE_BASED` vs `ML_ASSISTED` vs `ML_PROMOTED`)
  - evidence source list
  - caveat text
- Default caveat (FR):
  - "Le signal ML est utilisé comme aide à la décision. Le modèle n’est pas promu comme prédicteur fiable tant que le volume de données et les seuils de validation ne sont pas suffisants."

## I. Future Model Upgrade Path
- Keep current advisory layer until sufficient real post-récolte + feedback evidence accumulates.
- Increase gate strictness with stable time-split validation and drift monitoring.
- Add action/outcome causal tracking quality checks before any production promotion.
- Consider stage-specific models/calibration only after reliable-candidate dataset levels and robust holdout evidence.

## J. What Will Not Be Changed
- No Alembic migration.
- No DB column addition/removal.
- No enum modification.
- No repurposing existing columns.
- No pré-récolte lifecycle change.
- No post-récolte lifecycle change.
- No Collecte stock-IN behavior change.
- No stock movement policy rewrite.
- No process-step completion/idempotency logic change.
- No `/manager/lots` workflow change.
- No chatbot rewrite.
