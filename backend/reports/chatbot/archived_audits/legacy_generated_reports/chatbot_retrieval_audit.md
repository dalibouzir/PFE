# Audit diagnostic - retrieval chatbot

## 1. Executive summary
- Total cas: 20 (pass=9, partial=11, fail=0).
- Les résultats confirment les routes SQL/RAG/ML existantes, mais la récupération RAG reste faible dans l’environnement de test.
- Plusieurs questions pré-récolte et parcelles ne disposent pas d’accès SQL dédié dans l’agent actuel.

## 2. Current chatbot architecture found
- Endpoint principal: /chat/agent (AgentOrchestrator).
- Routage via IntentRouter + EntityExtractor + MemoryAgent.
- Agents spécialisés: SQLAnalyticsAgent, RAGKnowledgeAgent, MLLossAgent, RecommendationAgent.
- Vérification via ResponseVerifier + AuditLogger.

## 3. Current retrieval pipeline found
- Rewrite: enrichissement des requêtes (pertes/séchage/tri/emballage/bilan matière).
- HybridRetriever: vecteur pgvector + recherche keyword, fusion 70/30.
- Rerank: boost produit/étape/thème + fraîcheur + type de source.

## 4. Current SQL/app-data usage found
- SQLTools couvre stocks, inputs, batches, process_steps, material_balance, stage_efficiency, top_farmers.
- Pré-récolte, parcelles, members étendus ne sont pas intégrés dans SQLAnalyticsAgent.

## 5. Current ML/recommendation usage found
- MLTools lit ml_prediction_logs; renvoie avertissement si non disponible.
- RecommendationAgent produit des recommandations heuristiques basées sur SQL/RAG/ML.

## 6. Current frontend source display found
- UI assistant-ia affiche sources et avertissements via citations et métriques.
- Les sources sont des labels SQL/RAG/ML simplifiés.

## 7. Test results
| Question | Expected | Actual | Status | Failure reason |
| --- | --- | --- | --- | --- |
| Quel est le stock actuel de mangue ? | Utiliser les stocks/app-data (SQL) et retourner une source SQL. | route=SQL_ONLY / sources=sql / answer_preview=1. Résultat principal Les stocks actuels (1 produits) sont: - Mangue: 500.0 kg disponibles 2. Explication courte Aucune explication détaillée disponible. 3. Recommandations si pertinentes Aucune recommandation prioritair | pass | - |
| Quels lots sont en cours ? | Utiliser les lots/app-data (SQL) et retourner une source batches. | route=SQL_ONLY / sources=sql / answer_preview=1. Résultat principal Aucun lot en cours n’a été trouvé. 2. Explication courte Aucune explication détaillée disponible. 3. Recommandations si pertinentes Aucune recommandation prioritaire confirmée. 4. Sources utilisées  | partial | reponse_non_francaise |
| Quel lot a le plus de pertes ? | Comparer les pertes via process_steps/material balance (SQL), pas uniquement RAG. | route=SQL_ONLY / sources=sql / answer_preview=1. Résultat principal Lots à risque élevé (3): - BATCH-0003: perte 20.3 % / efficacité 79.7 % - BATCH-0002: perte 20.3 % / efficacité 79.7 % - BATCH-0001: perte 20.3 % / efficacité 79.7 % 2. Explication courte Aucune exp | partial | reponse_non_francaise |
| Quelle étape cause le plus de pertes ? | Comparer les pertes par étape via process_steps (SQL). | route=HYBRID_SQL_RAG / sources=rag,sql / answer_preview=1. Résultat principal Perte observée sur emballage du lot BATCH-0003: 7.0% (514.4 kg -> 478.4 kg). 2. Explication courte Mesures SQL: étape critique packaging (7.0%). 3. Recommandations si pertinentes Aucune recommandati | partial | reponse_non_francaise |
| Quels producteurs ont livré le plus cette semaine ? | Utiliser inputs/members et retourner une source SQL (collectes). | route=SQL_ONLY / sources=sql / answer_preview=1. Résultat principal La coopérative compte 0 membre(s) inscrit(s). 2. Explication courte Aucune explication détaillée disponible. 3. Recommandations si pertinentes Aucune recommandation prioritaire confirmée. 4. Sources | pass | - |
| Avons-nous des lots à risque ? | Question générale : ne pas extraire AVONS-NOUS comme lot, route SQL/ML. | route=HYBRID_SQL_ML / sources=ml,sql / answer_preview=1. Résultat principal Lots à risque élevé (3): - BATCH-0003: perte 20.3 % / efficacité 79.7 % - BATCH-0002: perte 20.3 % / efficacité 79.7 % - BATCH-0001: perte 20.3 % / efficacité 79.7 % 2. Explication courte Signal ML: | partial | reponse_non_francaise |
| Analyse le lot MANG-004 | Doit extraire batch_ref=MANG-004 si pattern valide; si absent en DB, indiquer lot introuvable. | route=SQL_ONLY / sources=sql / answer_preview=1. Résultat principal Les données disponibles ne permettent pas de confirmer ce point. 2. Explication courte Aucune explication détaillée disponible. 3. Recommandations si pertinentes Aucune recommandation prioritaire co | partial | reponse_non_francaise |
| Analyse le lot MANG-999 | Si MANG-999 est valide mais absent, retourner un message lot introuvable. | route=SQL_ONLY / sources=sql / answer_preview=1. Résultat principal Les données disponibles ne permettent pas de confirmer ce point. 2. Explication courte Aucune explication détaillée disponible. 3. Recommandations si pertinentes Aucune recommandation prioritaire co | partial | reponse_non_francaise, message_lot_introuvable_absent |
| Pourquoi les pertes sont élevées ? | Question causale : expliquer via RAG, idéalement avec métriques SQL. | route=HYBRID_SQL_RAG / sources=rag,sql / answer_preview=1. Résultat principal Perte observée sur emballage du lot BATCH-0003: 7.0% (514.4 kg -> 478.4 kg). 2. Explication courte Mesures SQL: étape critique packaging (7.0%). 3. Recommandations si pertinentes Aucune recommandati | partial | reponse_non_francaise |
| Comment réduire les pertes pendant le séchage ? | RAG sur séchage/pertes avec sources de connaissance. | route=RAG_ONLY / sources=rag / answer_preview=1. Résultat principal Les données disponibles ne permettent pas de confirmer ce point. 2. Explication courte Aucune explication détaillée n’a pu être extraite des sources RAG disponibles. 3. Recommandations si pertinente | pass | - |
| Explique le bilan matière. | RAG sur bilan matière avec sources. | route=HYBRID_SQL_RAG / sources=rag,sql / answer_preview=1. Résultat principal Bilan matière global: entrée 1800.0 kg, sortie 1435.1 kg, perte 20.3%. 2. Explication courte Mesures SQL: perte 20.3% et efficacité 79.7% 3. Recommandations si pertinentes Aucune recommandation prio | partial | reponse_non_francaise |
| Quelles sont les bonnes pratiques pour le tri des mangues ? | RAG sur tri + mangue avec sources. | route=RAG_ONLY / sources=rag / answer_preview=1. Résultat principal Les données disponibles ne permettent pas de confirmer ce point. 2. Explication courte Aucune explication détaillée n’a pu être extraite des sources RAG disponibles. 3. Recommandations si pertinente | pass | - |
| Comment améliorer l’emballage ? | RAG sur emballage avec sources. | route=RAG_ONLY / sources=rag / answer_preview=1. Résultat principal Les données disponibles ne permettent pas de confirmer ce point. 2. Explication courte Aucune explication détaillée n’a pu être extraite des sources RAG disponibles. 3. Recommandations si pertinente | pass | - |
| Quels lots sont à risque aujourd’hui ? | Utiliser ML si disponible, sinon expliquer indisponibilité. | route=HYBRID_SQL_ML / sources=ml,sql / answer_preview=1. Résultat principal Lots à risque élevé (3): - BATCH-0003: perte 20.3 % / efficacité 79.7 % - BATCH-0002: perte 20.3 % / efficacité 79.7 % - BATCH-0001: perte 20.3 % / efficacité 79.7 % 2. Explication courte Signal ML: | partial | reponse_non_francaise |
| Donne-moi les recommandations IA pour le lot MANG-004. | Utiliser recommandations + contexte SQL/ML/RAG si disponible. | route=HYBRID_FULL / sources=ml,rag,recommendation,sql / answer_preview=1. Résultat principal Les données disponibles ne permettent pas de confirmer ce point. 2. Explication courte Aucune explication détaillée disponible. 3. Recommandations si pertinentes 1. [HIGH] Isoler le lot BATCH-0003,  | partial | reponse_non_francaise |
| Quels sont les risques en pré-récolte ? | Utiliser données pré-récolte si disponibles, sinon signaler limite. | route=HYBRID_SQL_ML / sources=ml,sql / answer_preview=1. Résultat principal Signal ML: risque MEDIUM / anomalie non. 2. Explication courte Signal ML: risque MEDIUM / anomalie non; les mesures SQL restent la vérité opérationnelle. 3. Recommandations si pertinentes Aucune rec | partial | route_inattendue |
| Quelles parcelles nécessitent une action ? | Utiliser parcelles/pré-récolte si disponibles. | route=SQL_ONLY / sources=sql / answer_preview=1. Résultat principal Les données disponibles ne permettent pas de confirmer ce point. 2. Explication courte Aucune explication détaillée disponible. 3. Recommandations si pertinentes Aucune recommandation prioritaire co | pass | - |
| Quelle étape post-récolte pose le plus de problème ? | Utiliser process_steps/losses (SQL). | route=SQL_ONLY / sources=sql / answer_preview=1. Résultat principal Les données disponibles ne permettent pas de confirmer ce point. 2. Explication courte Aucune explication détaillée disponible. 3. Recommandations si pertinentes Aucune recommandation prioritaire co | pass | - |
| Bonjour | Réponse courte en français, sans SQL/RAG/ML. | route=SMALL_TALK / sources=none / answer_preview=Bonjour. Je peux vous aider à analyser les stocks, les lots, les pertes, l’efficacité des étapes de transformation et les recommandations de la coopérative. | pass | - |
| Who won the Champions League? | Réponse hors-scope en français. | route=OUT_OF_SCOPE / sources=none / answer_preview=Je suis conçu pour analyser les données de la coopérative : stocks, lots, pertes, transformation, recommandations et connaissances post-récolte. Je ne dispose pas de contexte fiable pour répondre à cette question. | pass | - |

## 8. Top retrieval weaknesses
- reponse_non_francaise: 10 cas
- message_lot_introuvable_absent: 1 cas
- route_inattendue: 1 cas

## 9. Entity extraction issues
- Vérifier les hyphens et stopwords pour éviter les faux lots (ex: AVONS-NOUS).
- Ajouter validation DB + regex stricte avant de conclure lot introuvable.

## 10. SQL/app-data access gaps
- Absence de route SQL dédiée pour parcelles/pré-récolte dans SQLAnalyticsAgent.
- Les questions pré-récolte retombent vers RAG/ML sans données structurées.

## 11. RAG chunking/metadata issues
- Peu/pas de chunks en environnement test; vérifier ingestion et metadata (product, stage, topic, language).
- RAG ne renvoie pas de sources pour les questions de bonnes pratiques.

## 12. French-language issues
- Les réponses devraient rester 100% françaises; vérifier les warnings et labels si mélange détecté.

## 13. Source-grounding issues
- Plusieurs réponses opérationnelles manquent de sources SQL/RAG/ML explicites.
- Ajouter un avertissement quand la route exige une source absente.

## 14. ML/recommendation integration gaps
- ML dépend de ml_prediction_logs; absence de logs = réponse faible.
- Recommendations doivent citer au moins une preuve SQL/RAG/ML.

## 15. Pre-harvest/post-harvest insight gaps
- Pré-récolte: pas d’accès direct aux steps/parcel status dans l’agent SQL.
- Post-récolte: données présentes via process_steps, mais pas de vue synthétique dédiée.

## 16. Recommended improvements (priority order)
1. Corriger extraction des lots (stopwords + validation DB + pattern strict).
2. Exposer pré-récolte/parcelles dans SQLAnalyticsAgent (routes dédiées).
3. Renforcer ingestion RAG + metadata (language/product/stage/topic).
4. Ajouter scoring/alertes de grounding et de manque de sources.
5. Structurer la réponse avec citations normalisées pour UI.

## 17. Proposed implementation phases
- Phase 1: Full-app data access + entity extraction fix
- Phase 2: RAG retrieval upgrade + lightweight orchestrator (inspiration: Ruflo, rag_api)
- Phase 3: ML loss/anomaly intelligence + shared recommendations
- Phase 4: UI integration + pre/post-harvest AI insights + docs/tests

## 18. Next recommended Codex prompt
Analyser le rapport backend/app/ai/reports/chatbot_retrieval_audit.md et proposer un plan d’implémentation Phase 1 pour:
- corriger l’extraction des lots (stopwords + regex stricte + validation DB),
- ajouter les outils SQL pré-récolte/parcelles,
- améliorer la remontée de sources SQL/RAG/ML dans les réponses.
Ne pas modifier l’architecture globale ni ajouter de dépendances.
