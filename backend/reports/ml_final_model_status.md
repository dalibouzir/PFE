# ML Final Model Status and Integration-Readiness Audit

Date: 2026-05-17

## A. Executive Verdict
- WeeFarm ML pipeline and offline evaluation loop are implemented and reproducible.
- Real production readiness remains constrained by low real operational sample size (`~45-49` process-step rows).
- Runtime ML remains non-promoted and recommendation mode remains rule-based.
- Synthetic benchmark supports controlled model development claims only.

## B. Real App Readiness Status
- Source of truth: real Supabase snapshot and readiness audit.
- `dataset_n`: ~`45-49`
- `ml_readiness_state`: `INSUFFICIENT_DATA`
- `dataset_readiness_level`: `VERY_LOW_DATA`
- `model_gate_status`: `FAIL`
- `promoted`: `false`
- `recommendation_mode`: `RULE_BASED`
- Real-data interpretation: no production ML promotion claim is justified.

## C. Synthetic/Offline Benchmark Boundary
- Synthetic source: `backend/artifacts/synthetic_postharvest_benchmark.csv` (`2000` rows).
- Label boundary: **SYNTHETIC OFFLINE BENCHMARK — NOT REAL APP PERFORMANCE**.
- Synthetic metrics are not production metrics and must not be reported as cooperative deployment accuracy.
- Synthetic/offline benchmark metrics are controlled development evidence and must not be interpreted as real cooperative deployment accuracy.
- Synthetic data is not mixed with Supabase runtime data and does not override runtime readiness governance.

## D. Model-by-Model Final Status
| Component | Final status | Best candidate/baseline | Key result | Runtime promotion |
|---|---|---|---|---|
| Regression | baseline_fallback_not_ml_promoted | `stage_season_mean_loss` baseline | MAE `2.5622`; best ML did not beat baseline | No |
| Classification | PARTIAL_improved_but_non_promoted | `Phase1C_LogRegBalanced_plus_HighOverride_balanced` | macro-F1 `0.4679`; high-risk recall `0.4783`; precision `0.0688` | No |
| Anomaly | PASS_assessment_mode_offline_only | `AssessmentRulesPlusStatistical` | precision `0.8788`; recall `1.0000`; F1 `0.9355`; precision@10% `0.7250` | No ML promotion |
| Recommendation ranking | PARTIAL_proxy_useful_not_fully_met | `ConservativeRanking` | assessment-mode P@3 `0.6734`; NDCG@5 `0.9172`; top coverage `1.0000` | No learned recommender |

## E. Regression Result and Decision
- Decision: keep baseline fallback.
- Best baseline: `stage_season_mean_loss` (MAE `2.5622`).
- Best ML candidate did not exceed baseline gate requirements.
- Integration implication: baseline-driven regression remains safest behavior.

## F. Classification Result and Decision
- Decision: `PARTIAL` and frozen as non-promoted.
- Best prediction-mode candidate: `Phase1C_LogRegBalanced_plus_HighOverride_balanced`.
- Metrics: macro-F1 `0.4679`, high-risk recall `0.4783`, high-risk precision `0.0688`, false-low-high-risk rate `0.4348`, false alarms `149`.
- Interpretation: recall improved materially from early reference (`0.0000`) but full quality gate was not met.

## G. Anomaly Result and Decision
- IsolationForest baseline remained weak on synthetic labels: precision `0.0222`, recall `0.0345`, F1 `0.0270`, precision@10% `0.0000`.
- Best assessment-mode candidate: `AssessmentRulesPlusStatistical`.
- Metrics: precision `0.8788`, recall `1.0000`, F1 `0.9355`, precision@10% `0.7250`, gate `PASS`.
- Prediction-mode anomaly/risk remains weak (`PredictionRulesPlusStatistical`: precision `0.0442`, recall `0.2759`, F1 `0.0762`).
- Decision: assessment-mode anomaly diagnostics are useful offline; runtime remains non-promoted.

## H. Recommendation Ranking Result and Decision
- Decision: `PARTIAL` (`proxy_ranking_is_useful_but_gate_not_fully_met`).
- Recommendation actions remain rule-generated (not learned policy).
- Best prediction-mode ranking: `FinalConservativeEvidenceRanking` (P@3 `0.7096`, P@5 `0.4758`, NDCG@5 `0.9380`, top coverage `1.0000`).
- Best assessment-mode ranking: `ConservativeRanking` (P@3 `0.6734`, P@5 `0.4621`, NDCG@5 `0.9172`, top coverage `1.0000`).
- Gate outcome: assessment-mode P@3 below `0.70`, so no full pass.
- Boundary: synthetic proxy relevance is not real recommendation outcome evidence.

## I. Integration-Readiness Table
| Component | Can integrate into app code? | Runtime promoted? | Conditions | Notes |
|---|---|---|---|---|
| Regression | Yes, baseline fallback only | No | Keep baseline as primary numeric decision path | ML regression did not beat baseline |
| Classification | Maybe, advisory candidate only | No | Keep advisory-only and gated; no promotion under low data | Recall improved but macro-F1/precision remain weak |
| Anomaly | Yes, rule/statistical assessment diagnostics as advisory | Not as ML promotion | Use as post-step diagnostic signals with explicit boundary | Assessment-mode synthetic gate passed |
| Recommendation ranking | Yes, rule-first ranking as advisory later | No learned recommender promotion | Keep rule actions primary; use ranking as prioritization aid only | Proxy benchmark remains partial |
| Readiness layer | Already integrated | Governs promotion | Keep unchanged | Prevents overclaiming under low-data conditions |

## J. What Can Be Integrated Safely Later
- Rule/statistical assessment anomaly diagnostics as advisory post-step checks.
- Rule-first recommendation prioritization logic with transparent scoring.
- Continued baseline-first regression behavior with explicit fallback logging.
- Classification advisory outputs only behind readiness and non-promotion gates.

## K. What Must Remain Report-Only
- Synthetic benchmark leaderboard comparisons.
- Assessment-mode metrics derived from post-event fields when used for offline analysis.
- Proxy relevance recommendation ranking outcomes.
- Any synthetic metric interpreted as deployment accuracy.

## L. What Must Not Be Claimed in PFE
- Production-ready ML.
- Real cooperative model accuracy from synthetic data.
- Learned recommendation effectiveness validated in production.
- Validated production anomaly detection from synthetic-only evidence.
- Runtime `ML_PROMOTED` under the current low-data readiness state.

## M. PFE-Safe Final Wording
- The WeeFarm ML pipeline and governance gates were implemented end-to-end, with strict source-aware reporting.
- On real operational data (`~45-49` rows), readiness remains insufficient; therefore runtime stays non-promoted and rule-based.
- Controlled synthetic benchmarking enabled model diagnostics at larger scale, showing baseline dominance for regression, partial improvement for critical-risk classification, strong assessment-mode anomaly diagnostics, and partial recommendation ranking utility under proxy relevance.
- These synthetic findings are development evidence only and are not deployment-accuracy claims.
