# Literature-Informed Benchmark Methodology

## Purpose
This dataset is a literature-informed benchmark to test ML architecture behavior under source-backed distributions.
It is not cooperative operational data and must not be used to claim production accuracy.

## Data generation approach
- Rows generated as process-step records with BENCH-ML-* batch IDs and [ML_LITERATURE_BENCHMARK] markers.
- Products: Mangue, Arachide, Mil.
- Stages: Nettoyage, Séchage, Tri, Emballage.
- Loss ranges start from source-informed priors and are perturbed with seasonality, scenario noise, stock-pressure effects, and small-batch volatility.
- Contradictory cases are injected (e.g., low drying loss during risky season, medium packaging loss, high sorting loss in otherwise normal periods).

## Source mapping policy
- APHLIS and AKP are used as primary cereal post-harvest references.
- Mango and groundnut stage tails are partially assumption-derived where direct Senegal stage percentages are unavailable.
- Each source entry is tracked in benchmark_sources.json/md with reliability notes.

## Important limits
- This is synthetic benchmark data informed by literature, not real cooperative trace data.
- It can test potential and architecture sensitivity, but cannot validate production accuracy.