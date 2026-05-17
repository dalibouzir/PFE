# WeeFarm ML Weather Evaluation

## Data Source
- Label: supabase
- Identifier: aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require
- Fallback used: False
- Generated at: 2026-05-17T01:28:25.651981+00:00
- Python runtime: 3.11.12

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
- Baseline (product_stage_mean_loss) MAE: 3.8362
- Internal model MAE: 3.7136
- Weather model MAE: 3.8807
- Internal relative improvement vs best baseline: 3.20%
- Weather relative improvement vs best baseline: -1.16%
- Best numeric candidate (model-only): internal_model
- Best numeric candidate (across all): internal_model
- Gate-promoted candidate: baseline:product_stage_mean_loss
- Production decision: baseline:product_stage_mean_loss
- Selected decision: baseline:product_stage_mean_loss

## Regression (Random Split Secondary)
- Internal model MAE: 2.2065
- Weather model MAE: 2.3872

## Classification (Time Split)
- Internal model macro-F1: 0.3125
- Internal best threshold baseline macro-F1: 0.5556
- Weather model macro-F1: 0.3125
- Weather best threshold baseline macro-F1: 0.5556

## Gate Results
- Internal regression gate: FAIL
- Weather regression gate: FAIL
- Internal classification gate: FAIL
- Weather classification gate: FAIL