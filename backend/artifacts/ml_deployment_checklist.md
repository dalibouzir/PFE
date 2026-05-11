# ML Deployment Checklist

1. Run tests:
`python3 -m pytest -q tests/test_feature_engineering.py tests/test_training_pipeline.py tests/test_ml_resilience.py tests/test_ml_pipeline_diagnostics.py tests/test_recommendation_mapping.py tests/test_ml_evaluation.py tests/test_ml_seed_training_data.py tests/test_ml_monitoring.py tests/test_ml_deployment_readiness.py`

2. Run diagnostics:
`python3 scripts/ml_diagnostics.py --output artifacts/ml_diagnostics_phase5.json`

3. Run evaluation:
`python3 scripts/evaluate_ml_models.py --output-json artifacts/ml_evaluation_phase5.json --output-md artifacts/ml_evaluation_phase5.md`

4. Run monitoring report:
`python3 scripts/ml_monitoring_report.py --output-json artifacts/ml_monitoring_report.json --output-md artifacts/ml_monitoring_report.md`

5. Run deployment readiness report:
`python3 scripts/ml_deployment_readiness.py --output-json artifacts/ml_deployment_readiness.json --output-md artifacts/ml_deployment_readiness.md`

6. Confirm active model:
- Check `artifacts/active_model.json`
- Confirm model status is `active` and validation gates pass for MVP/demo.

7. Build Docker image (do not push yet):
`docker build -t weefarm-backend:ml-phase5 .`

8. Push to DockerHub (only after approval):
`docker tag weefarm-backend:ml-phase5 <dockerhub-user>/weefarm-backend:ml-phase5`
`docker push <dockerhub-user>/weefarm-backend:ml-phase5`

9. Redeploy Azure Container App (only after approval):
- Update image tag
- Trigger rollout

10. Smoke test endpoints:
- `/health`
- `/ml/health`
- `/ml/predict`
- `/ml/assess`

11. Rollback plan:
- Use model rollback utility to switch active model
- Restore previous image tag in Azure
- Re-run smoke tests
