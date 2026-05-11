# Performance Summary

Generated: 2026-05-08T22:35:26.494711+00:00

## Data Sources
- chatbot_full_platform_coverage_audit.json: 112 responses
- chatbot_unseen_robustness_audit.json: 60 responses
- chatbot_quality_audit.json: 50 responses

## Latency by Intent (ms)
- avg SQL_ONLY latency: 1313.81
- avg HYBRID latency: 6150.13
- avg RAG_ONLY latency: 5479.52

## Targets
- SQL_ONLY < 2s: OK
- HYBRID < 5s: NOT MET

## Before/After
- Before baseline is taken from pre-optimization audit reports available in this workspace.
- After values reflect latest regenerated audits after Phase 6.2 optimizations.
- If historical pre-optimization JSON snapshots are not present, only current measured values are reported.

Total evaluated responses: 222