# Post-Deploy Chatbot Audit

- Generated at: `2026-05-21T12:15:15.403271+00:00`
- Question count: `50`
- Execution mode: `local_fastapi_supabase_runtime`

## Latency
- p50: `9887.28 ms`
- p90: `15197.55 ms`
- p95: `21471.53 ms`
- timeout/error rate: `0.0`

## Routing
- route accuracy: `0.86`
- intent family accuracy: `0.76`
- sql operation correctness: `0.0`

## Reliability
- overall score: `0.36`
- critical failures: `32`

## Critical Failure Counts
- SQL_OPERATION_ERROR: `22`
- NO_FAILURE: `18`
- ROUTING_ERROR: `7`
- WARNING_NOISE: `3`

## Not Computed Metrics
- frontend_perceived_delay: Not computed because browser UX telemetry was not captured in this backend runtime audit.
- stock_match_with_dashboard: Not computed because dashboard-side reference export was not available in this run.
- ROUGE-1: Not computed because no gold reference answer set was provided for overlap scoring.
- ROUGE-L: Not computed because no gold reference answer set was provided for overlap scoring.
- BLEU: Not computed because no gold reference answer set was provided for overlap scoring.
- METEOR: Not computed because metric package/reference set was not configured.
- BERTScore: Not computed because model package/reference set was not configured.
- Perplexity: Not computed because no local perplexity evaluation model/pipeline was configured.
