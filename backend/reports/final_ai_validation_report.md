# Final AI Validation Report

Generated: 2026-05-08T22:44:20.100567+00:00

## 1. Executive Summary
- Positioning: An AI-first operational decision-support prototype validated on a synthetic full-platform cooperative dataset using hybrid SQL/RAG orchestration and reproducible evaluation pipelines.
- Full-platform chatbot pass rate: 0.9911
- High-risk hallucination count: 0
- Data integrity score: 100.0/100

## 2. Chatbot/RAG Validation
| Metric | Value |
|---|---:|
| Baseline pass rate | 1.0000 |
| Unseen pass rate | 1.0000 |
| Full-platform pass rate | 0.9911 |
| SQL_ONLY pass rate | 1.0000 |
| RAG_ONLY pass rate | 1.0000 |
| HYBRID pass rate | 0.9677 |
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
| UI/debug leakage count | 0 |
| Retrieval relevance score | 0.2206 |
| Grounding score | 0.5520 |
| Citation relevance score | 0.2600 |
| Expected chunk coverage | 0.1333 |
| Scope purity score | 0.9000 |
| Contamination rate | 0.1000 |
| Operational priority score | 0.3000 |

## 5. ML Validation
| Metric | Value |
|---|---:|
| Dataset size | 1517 |
| Classification accuracy | 0.8295 |
| Classification macro-F1 | 0.4435 |
| Classification precision (macro) | 0.4356 |
| Classification recall (macro) | 0.4517 |
| Regression MAE | 4.0150 |
| Regression RMSE | 7.2806 |
| Regression R² | 0.0651 |

## 6. Latency & Performance
| Metric | Value |
|---|---:|
| Avg SQL_ONLY latency (ms) | 1313.81 |
| Avg HYBRID latency (ms) | 6150.13 |
| Avg RAG_ONLY latency (ms) | 5479.52 |

## 7. RAG Index Coverage
- Total indexed documents: 577
- Total indexed chunks: 577

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