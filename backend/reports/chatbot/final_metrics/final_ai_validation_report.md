# Final AI Validation Report

Generated: 2026-05-13T10:44:35.191347+00:00

## 1. Executive Summary
- Positioning: An AI-first operational decision-support prototype validated on a synthetic full-platform cooperative dataset using hybrid SQL/RAG orchestration and reproducible evaluation pipelines.
- Full-platform chatbot pass rate: 0.7500
- High-risk hallucination count: 0
- Data integrity score: 100.0/100

## 2. Chatbot/RAG Validation
| Metric | Value |
|---|---:|
| Baseline pass rate | 0.8600 |
| Unseen pass rate | 0.8833 |
| Full-platform pass rate | 0.7500 |
| SQL_ONLY pass rate | 0.9531 |
| RAG_ONLY pass rate | 0.2222 |
| HYBRID pass rate | 0.4194 |
| SMALL_TALK pass rate | 1.0000 |
| UNSUPPORTED pass rate | 1.0000 |
| Routing accuracy | 1.0000 |
| SQL factual accuracy | 0.9050 |
| Module coverage rate | 1.0000 |

## 3. NLP Similarity Metrics
| Metric | Value |
|---|---:|
| BLEU_1 | 0.0000 |
| BLEU_2 | 0.0000 |
| BLEU_4 | 0.0000 |
| ROUGE_1 | 0.0000 |
| ROUGE_2 | 0.0000 |
| ROUGE_L | 0.0000 |
| SEMANTIC_COSINE_SIMILARITY | 0.0000 |

## 4. Grounding & Hallucination Control
| Metric | Value |
|---|---:|
| Hallucination high-risk count | 0 |
| Stale response count | 0 |
| UI/debug leakage count | 7 |
| Retrieval relevance score | 0.0000 |
| Grounding score | 0.5100 |
| Citation relevance score | 0.2600 |
| Expected chunk coverage | 0.1000 |
| Scope purity score | 1.0000 |
| Contamination rate | 0.0000 |
| Operational priority score | 0.0000 |

## 5. ML Validation
| Metric | Value |
|---|---:|
| Dataset size | 52 |
| Classification accuracy | 0.9167 |
| Classification macro-F1 | 0.4783 |
| Classification precision (macro) | 0.3056 |
| Classification recall (macro) | 0.3333 |
| Regression MAE | 2.3662 |
| Regression RMSE | 3.6404 |
| Regression R² | -0.4634 |

## 6. Latency & Performance
| Metric | Value |
|---|---:|
| Avg SQL_ONLY latency (ms) | 1313.81 |
| Avg HYBRID latency (ms) | 6150.13 |
| Avg RAG_ONLY latency (ms) | 5479.52 |

## 7. RAG Index Coverage
- Total indexed documents: 4
- Total indexed chunks: 4

## 8. Data Integrity & Reproducibility
- Integrity score: 100.0/100
- Inconsistencies: 0
- Seeded module coverage rate: 1.0000

## 9. Key Limitations
- Validation is performed on a synthetic full-platform dataset; external validity on real cooperative operations remains limited.
- Hybrid/RAG latency remains above strict 5s target in current environment.
- RAG metadata completeness is uneven for some fields (e.g., source_id, severity).
- ML regression fit is weak (low R²), and anomaly validation lacks supervised labels.

## 10. Final Positioning Statement
An AI-first operational decision-support prototype validated on a synthetic full-platform cooperative dataset using hybrid SQL/RAG orchestration and reproducible evaluation pipelines.

### Methodological Notes
- Operational validation metrics and NLP lexical similarity metrics are complementary but not equivalent.
- BLEU/ROUGE are reported as lightweight indicators only and should not be interpreted as standalone quality truth for LLM systems.
- Real-world production validation remains distinct from this controlled synthetic-dataset evaluation.