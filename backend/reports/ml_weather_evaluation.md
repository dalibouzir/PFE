# WeeFarm ML Weather Evaluation

## Dataset
- Rows: 45

## Weather Coverage
- Coverage rate: 0.7556
- Rows with weather: 34
- Rows without weather: 11

## Leakage Check
- Status: PASS
- Violations: 0

## Regression (Time Split Primary)
- Baseline (stage_season_mean_loss) MAE: 4.2478
- Internal model MAE: 3.7136
- Weather model MAE: 3.8807
- Selected decision: internal_model

## Regression (Random Split Secondary)
- Internal model MAE: 2.2065
- Weather model MAE: 2.3872

## Classification (Time Split)
- Internal model macro-F1: 0.3125
- Weather model macro-F1: 0.3125

## Gate Results
- Internal regression gate: PASS
- Weather regression gate: FAIL
- Internal classification gate: FAIL
- Weather classification gate: FAIL