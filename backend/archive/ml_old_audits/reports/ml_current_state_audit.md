# WeeFarm ML Current State Audit (Post Phase 1-3)

Date: 2026-05-17
Scope: Audit only (no behavior/schema/runtime changes).

## A. Executive verdict
The current AI/ML stack is **mixed-readiness**:
- **Reliable enough today**: threshold-gated risk classification signal in offline evaluation; deterministic rule-based recommendations; weather feature coverage and leakage guard logic.
- **Not reliable yet**: regression superiority over strong baselines; supervised anomaly validation; ML-learned recommendation policy effectiveness.
- **Runtime reality**: chatbot mostly consumes **persisted SQL/ML logs + SQL analytics + RAG**, not direct online model inference for each question.

## B. Current ML architecture map

### Runtime-active ML files (called by API/services/agents)
- `backend/app/api/routes/ml.py`: ML API routes (`/train`, `/predict`, `/assess`, `/recommendation/{batch_id}`, `/feedback`, `/health`, `/reliability`).
- `backend/app/services/ml.py`: orchestrates training, prediction/assessment, rule recommendation, confidence/impact decision, feedback logging.
- `backend/app/ml/features/engineer.py`: feature extraction from `process_steps`, `batches`, `products`, `stocks`; optional weather enrichment.
- `backend/app/ml/inference/predictor.py`: predictive inference (`predict_from_features`) and assessment inference (`assess_from_features`, anomaly score).
- `backend/app/ml/training/trainer.py`: model training, metrics, artifact writing, validation gates, registry integration.
- `backend/app/ml/utils/feature_prep.py`: feature contract, forbidden predictive leakage fields, risk thresholds, final prepared frame.
- `backend/app/ml/utils/model_store.py`: active artifact loading and compatibility checks.
- `backend/app/ml/utils/model_registry.py`: model version registry + active model materialization.
- `backend/app/ml/utils/model_validation.py`: activation/demo/production gate computation.
- `backend/app/ml/utils/prediction_logging.py`: prediction warning flags + JSONL append/read.
- `backend/app/ml/recommendations/rule_engine.py`: deterministic template recommendation policy.
- `backend/app/ml/recommendations/impact_engine.py`: feedback-based action ranking + reliability status (used by `services/ml.py`).
- `backend/app/ml/weather_features.py`: weather cache loading, leakage-aware weather window features.
- `backend/app/ml/llm/provider.py`, `backend/app/ml/llm/prompt.py`: optional natural-language explanation generation.
- `backend/app/ai/tools/ml_tools.py`: chatbot ML tooling over `ml_prediction_logs`/registry tables.
- `backend/app/ai/tools/recommendation_tools.py`: chatbot recommendation composition from SQL/ML/RAG evidence.
- `backend/app/services/chat_orchestrator.py`, `backend/app/ai/orchestrator/*`: compose AI answer blocks, include SQL/ML/RAG/recommendation evidence.

### Evaluation/audit-only files
- `backend/scripts/evaluate_ml_models.py`: offline benchmark harness (time split + random split + strong baselines).
- `backend/scripts/evaluate_ml_reliability.py`: strict reliability gates + claim audit.
- `backend/scripts/evaluate_ml_weather.py`: internal-vs-weather model comparison + leakage check summary.
- `backend/scripts/backfill_weather_features.py`: offline weather cache backfill from Open-Meteo archive API.
- `backend/tests/test_ml_reliability_audit.py`, `backend/tests/test_ml_weather_evaluation.py`, `backend/tests/test_backfill_weather_features.py`: audit/weather tests.
- `backend/reports/ml_*.md`, `backend/reports/ml_*.json`: generated offline reports, not runtime logic.

### Likely legacy/low-use items
- `backend/app/ml/training/runner.py`: standalone startup trainer script; referenced minimally.
- `backend/backend/reports/ml_reliability_audit.*`: duplicated nested report path suggests stale/legacy artifact location.

## C. Current data flow

### 1) Training/evaluation data flow
1. Source data (DB tables):
   - `process_steps` + `batches` + `products` + `stocks` (via `fetch_process_records`).
2. Feature engineering (`build_features`):
   - Loss/efficiency, season/stage normalization, historical aggregates, batch rolling stats.
   - Optional weather joins from cache (`weather_cache.jsonl`) with past-window enforcement.
3. Feature preparation (`prepare_feature_frame`):
   - Enforce predictive feature contract; map final model feature sets.
4. Training (`train_models`):
   - Regressor: `RandomForestRegressor`.
   - Classifier: `RandomForestClassifier`.
   - Anomaly: `IsolationForest`.
   - Baseline comparisons, model validation gates, artifact writes, registry updates.
5. Evaluation scripts:
   - `evaluate_ml_models.py` → raw benchmarking.
   - `evaluate_ml_reliability.py` → claim-safe gate decisions.
   - `evaluate_ml_weather.py` → weather-vs-internal path assessment.

### 2) Runtime prediction/inference data flow
- API `/ml/predict`:
  - Input payload features -> `predict_from_features` -> model bundle inference -> write `MLPredictionLog` -> rule recommendation + confidence decision -> `MLRecommendationLog`.
- API `/ml/assess`:
  - Batch-derived or payload assessment features -> anomaly + observed loss assessment -> rule recommendation + confidence decision -> `MLRecommendationLog`.
- API `/ml/recommendation/{batch_id}`:
  - Runs assess + rule recommendation on demand.

### 3) Weather feature path
- `backfill_weather_features.py` pulls historical observed weather from Open-Meteo archive API and writes JSONL cache.
- `build_weather_feature_frame` reads cache, computes rolling window weather features constrained to `weather_timestamp <= event_time`, with leakage violation tracking.
- Weather currently appears in both training/eval feature set and runtime feature engineering capability.

### 4) Chatbot evidence path
- Chat route orchestrator runs SQL/RAG/ML/recommendation agents based on intent route.
- ML chatbot agent (`MLLossAgent`) calls `MLTools`, which queries `ml_prediction_logs`/registry tables.
- Recommendation chatbot agent builds grounded actions from SQL + optional ML log signals + RAG snippets.
- Evidence pack explicitly includes source blocks (SQL vs ML vs RAG vs recommendation).

### 5) Recommendation rule data path
- Core recommendation policy remains template/rule logic from `rule_engine.py`.
- `impact_engine.py` can rank candidate actions using feedback logs but does not replace base rule policy with a fully learned end-to-end recommender.

## D. Current model inventory

### Regression / loss prediction
- Type: `RandomForestRegressor` pipeline with preprocessing.
- Target: `loss_pct`.
- Inputs: predictive regression feature set in `feature_prep.py` (product/stage/season, qty_in, historical/rolling stats, weather features, etc.; excludes forbidden target-derived fields).
- Trained in: `backend/app/ml/training/trainer.py`.
- Saved/loaded: `backend/artifacts/loss_regressor.joblib` (+ versioned copy), loaded via `model_store.py`.
- Called in live app:
  - Yes for `/ml/predict` and for benchmark comparison in `/ml/assess` output.
  - Chatbot does not run direct live inference per question; it mostly reads logged outputs.

### Risk classification
- Type: `RandomForestClassifier`.
- Target: `risk_level` derived from `loss_pct` thresholds.
- Inputs: same predictive feature family as regression.
- Trained/saved/loaded: same pattern (`risk_classifier.joblib`).
- Live use:
  - In training/eval and predictive pipeline context.
  - Runtime `/ml/predict` response risk label uses thresholded predicted loss method (`assign_thresholded_risk_level`), not direct classifier output in that endpoint path.

### Anomaly detection
- Type: `IsolationForest`.
- Target: none (unsupervised exploratory).
- Inputs: assessment anomaly feature set includes post-stage fields (`qty_out`, `loss_pct`, `efficiency_pct`, deviation).
- Trained/saved/loaded: `anomaly_detector.joblib`.
- Live use:
  - Used in `/ml/assess` for anomaly score/flag.
  - Chatbot consumes persisted anomaly fields from logs.

### Recommendation policy
- Type: deterministic rule engine + optional confidence/ranking overlay.
- Base policy: `rule_engine.py` templates by stage/risk/signals.
- Overlay: `impact_engine.py` ranks/reorders candidate actions if feedback model available.
- Live use: yes in `/ml/predict`, `/ml/assess`, `/ml/recommendation/{batch_id}` and chatbot recommendation agent.
- Status: still fundamentally rule-based (not end-to-end learned policy).

### Weather-aware model path
- Type: same RF models with weather-enriched features from cache.
- Use status:
  - Explicitly evaluated in `evaluate_ml_weather.py`.
  - Feature code supports runtime inclusion; operational benchmark decision still fallback baseline for regression.

## E. Current evaluation results

### Command execution status (this audit run)
- Failed command:
  - `python3 backend/scripts/evaluate_ml_reliability.py ...`
  - Failure: `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` while importing models.
- Failed command:
  - `python3 backend/scripts/evaluate_ml_weather.py ...`
  - Same failure.
- Failed command:
  - `cd backend && python3 -m pytest -q tests/test_ml_reliability_audit.py tests/test_ml_weather_evaluation.py tests/test_backfill_weather_features.py`
  - Same failure during import.
- Root cause observed: local `python3` is `Python 3.9.6`, while code uses `X | None` type-union syntax requiring newer runtime behavior.

### Verified metrics from existing report artifacts
(**HISTORICAL ARTIFACT — NOT CURRENT SUPABASE SNAPSHOT**)
(From `backend/reports/ml_reliability_audit.json` and `backend/reports/ml_weather_evaluation.json`)
- Dataset size: **1520 rows**.
- Regression model MAE: **4.3735**.
- Best baseline MAE: **3.7667** (`stage_season_mean_loss`).
- Selected regression decision: **`baseline:stage_season_mean_loss`**.
- Classification macro-F1: **0.4501**.
- Best classification baseline: **`thresholded_predicted_loss_baseline`**, macro-F1 **0.3554**.
- Classification gate status: **PASS** (historical artifact context only).
- Anomaly status: **EXPLORATORY**.
- Recommendation policy status: **RULE_BASED**.
- Weather coverage: **100%** (`1520/1520`, coverage rate `1.0`).
- Leakage check status: **PASS** (`0` violations).

## F. Weather pipeline status
- Data mode: **real observed historical weather cached locally** (`source_kind=observed_historical` in `weather_cache.jsonl`), not synthetic mock rows in the inspected cache.
- Cache status: `backend/artifacts/weather_cache.jsonl` present (~9.6 MB).
- Coordinate strategy: demo-coordinate fallback + geocoding (`resolve_cooperative_coordinates`), recorded via `coordinate_source`.
- Coverage: current report says 100% rows with weather.
- Leakage prevention: implemented in `build_weather_feature_frame` via `weather_timestamp <= event_ts` window checks; raises if only future rows when enforcement enabled.
- Forecast vs historical separation:
  - Distinction fields exist (`weather_is_forecast`, `weather_is_observed`, `weather_source_kind`).
  - Backfill currently writes `observed_historical`.
- Runtime vs evaluation use:
  - Weather included in feature engineering path and evaluators.
  - Regression decision still baseline fallback despite weather improvement over internal-only model.

## G. Recommendation layer status
- Current mode: **rule-based core** (stage/risk templates).
- Not fully ML-learned policy.
- Action/outcome feedback exists in DB schema and is consumed by impact engine (`recommendation_feedback_logs`), with holdout logic and reliability metrics.
- Recommendation outputs include evidence list in chatbot recommendation tool responses.
- Overclaim risk: because title/text can say “piloté par signal ML”, users may infer fully learned policy unless clearly caveated.

## H. Chatbot ML integration status
- Direct online ML model scoring per chat request: **generally no**.
- Primary chatbot ML path: reads **persisted ML logs** (`ml_prediction_logs`, `ml_recommendation_logs`) via `MLTools` and orchestrator context builders.
- Chatbot uses recommendation outputs: **yes** (Recommendation agent/tool integrated).
- SQL vs ML vs RAG distinction: present in source contracts/evidence pack formatting, with route-aware composition.
- Overstatement risk: some answer templates present ML as “signal” but confidence can still be overstated if not accompanied by gate context.

## I. What is actually reliable today
- Structured operational SQL analytics and deterministic KPI calculations.
- Rule-engine recommendation generation consistency.
- Classification signal improvement vs threshold baselines (per stored reliability report).
- Weather feature ingestion coverage and leakage guard checks.

## J. What is not reliable yet
- Regression superiority over strong stage-season baseline.
- Supervised anomaly detection accuracy claims (no labels).
- Fully ML-ranked recommendation effectiveness claims tied to real-world outcomes.
- Reproducible local audit execution in this environment (Python runtime mismatch).

## K. What can be claimed in the PFE report
- The platform has an operational ML pipeline with strict reliability gating and explicit fallback decisions.
- Classification performs above threshold baselines on macro-F1 in audited reports.
- Regression currently falls back to a stronger statistical baseline for reliability.
- Weather enrichment improves internal model MAE but does not yet beat the strongest baseline.
- Anomaly is exploratory and recommendations are rule-based with evidence-grounded outputs.

## L. What must not be claimed
- “Regression model is production-superior to strong baselines.”
- “Anomaly detection accuracy is validated.”
- “Recommendations are fully ML-learned/optimized end-to-end.”
- “Chatbot always performs fresh online ML inference for each answer.”

## M. Recommended next implementation step (do not implement now)
Stabilize the **evaluation execution environment** first (Python compatibility/runtime pinning) and rerun reliability/weather/test audits on the current code/data snapshot to make claim evidence reproducible; then prioritize regression feature/target redesign against stage-season baseline as the next ML improvement track.

---

## Additional risk findings from code inspection
- `backend/app/ml/utils/feature_prep.py` contains unreachable code after `return` in `prepare_feature_frame`; weather timestamp ordinal derivation block is dead code.
- Duplicate/stale artifact path appears (`backend/backend/reports/ml_reliability_audit.*`).
- Runtime mismatch risk: chatbot can present ML signals from logs that may be stale relative to latest operational data.
- Recommendation truthfulness risk: wording can imply ML-driven policy even when core action mapping is rule templates.
