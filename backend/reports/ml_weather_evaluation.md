# WeeFarm ML Weather Evaluation

## Dataset
- Rows: 1520

## Weather Coverage
- Coverage rate: 1.0000
- Rows with weather: 1520
- Rows without weather: 0

## Leakage Check
- Status: PASS
- Violations: 0

## Regression (Time Split Primary)
- Baseline (stage_season_mean_loss) MAE: 3.7667
- Internal model MAE: 4.3735
- Weather model MAE: 4.1977
- Selected decision: baseline:stage_season_mean_loss

## Regression (Random Split Secondary)
- Internal model MAE: 2.7763
- Weather model MAE: 2.7938

## Classification (Time Split)
- Internal model macro-F1: 0.4501
- Weather model macro-F1: 0.4112

## Gate Results
- Internal regression gate: FAIL
- Weather regression gate: FAIL
- Internal classification gate: PASS
- Weather classification gate: PASS