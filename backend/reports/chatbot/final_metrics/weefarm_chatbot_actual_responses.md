# WeeFarm Chatbot - Actual Responses (latest 30 sanity questions)

## 1. Question
Donne une mini check-list tri + stockage pour éviter la casse.

### Réponse chatbot (exacte)
```text
1. Résultat principal
Les stocks actuels (4 produits) sont:
- Arachide: 1140.0 kg disponibles
- Bissap: 0.0 kg disponibles
- Mangue: 2750.0 kg disponibles
- Mil: 1620.0 kg disponibles

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: process_steps
- SQL: stocks

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 2. Question
Si l’humidité monte pendant stockage, quel ajustement process immédiat recommandes-tu ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Les stocks actuels (4 produits) sont:
- Arachide: 1140.0 kg disponibles
- Bissap: 0.0 kg disponibles
- Mangue: 2750.0 kg disponibles
- Mil: 1620.0 kg disponibles

2. Explication courte
Explication RAG: Agronomic knowledge reference for Multi-produit in Thies, Senegal. Topic: Humidité. Source: DEMOFP-SRC-KNOW-007. [DEMOFP] Mettre en place check-list humidité avant stockage.

3. Recommandations si pertinentes
1. [HIGH] Isoler le lot LOT-BISS-002, renforcer le contrôle au séchage, puis reclasser les intrants dégradés. - Perte élevée (69.3%) et efficacité faible (30.7%) sur le lot ciblé. | Cible: LOT-BISS-002 / Bissap / séchage
2. [HIGH] Mettre en place un contrôle d’entrée/sortie au niveau du lot LOT-BISS-002 et ajuster le temps de traitement de l’étape critique. - Efficacité en dessous de la cible (30.7%). | Cible: LOT-BISS-002 / Bissap / séchage
3. [HIGH] Standardiser les contrôles de séchage avec seuils humidité/tri et feuille de suivi par lot. - L’étape séchage concentre les pertes (36.5% en moyenne). | Cible: LOT-BISS-002 / Bissap / Sechage

4. Sources utilisées
- SQL: commercial_orders
- SQL: stocks
- RAG: Knowledge Multi-produit - Humidité
- RAG: Knowledge Arachide - Stockage
- RAG: Stock Mangue
- RAG: Stock Arachide
- RAG: Stock Mil
- ML: ml_signal

5. Avertissements si nécessaires
- Des informations contradictoires peuvent exister dans les sources.
- Le contexte documentaire RAG est faible.
```

## 3. Question
Montant moyen des factures payées ce trimestre ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Perte observée sur séchage du lot LOT-BISS-002: 68.0% (150.0 kg -> 48.0 kg).

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: commercial_invoices
- SQL: process_steps

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 4. Question
Quel client a le plus gros cumul de commandes ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Commandes commerciales disponibles: 14.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: commercial_orders
- SQL: inputs
- SQL: members

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 5. Question
Charges globales du mois en cours vs mois dernier ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Synthèse charges/dépenses: 7 transaction(s) trésorerie pour 5557000 FCFA, 24 charge(s) globales pour 797700 FCFA.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: global_charges
- SQL: treasury_transactions

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 6. Question
Si on exclut ceux à zéro, quel membre est le plus petit contributeur en kg cumulés ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
La coopérative compte 17 membre(s) inscrit(s).

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: members
- SQL: process_steps

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 7. Question
Pour Arachide, quelle parcelle est la plus grande et chez qui ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Je n’ai pas trouvé de preuve opérationnelle exploitable pour répondre précisément à cette demande.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: parcels
- SQL: pre_harvest_steps

5. Avertissements si nécessaires
- Aucune donnée disponible pour cette recherche.
```

## 8. Question
Combien de membres n'ont rien livré sur les 30 derniers jours ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Je n’ai pas trouvé de preuve opérationnelle exploitable pour répondre précisément à cette demande.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: members

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 9. Question
Aujourd’hui vs hier pour Arachide, on a collecté combien en kg ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Aucune collecte n’est disponible dans les données actuelles.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: inputs

5. Avertissements si nécessaires
- Des lignes attendues sont manquantes dans les données SQL.
- Aucune donnée SQL exploitable n’a été trouvée.
```

## 10. Question
Sur 90 jours, quel grade pèse le plus en volume collecté ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Quantité collectée observée: 21000.0 kg.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: inputs

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 11. Question
Quels sont les 3 jours les plus forts en collecte sur 6 mois ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Quantité collectée observée: 21000.0 kg.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: inputs

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 12. Question
Quel produit est le plus proche de rupture si on regarde le ratio disponible/seuil ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Je n’ai pas trouvé de preuve opérationnelle exploitable pour répondre précisément à cette demande.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: stocks

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 13. Question
Pour Arachide, combien de disponible net et quel écart au seuil ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Je n’ai pas trouvé de preuve opérationnelle exploitable pour répondre précisément à cette demande.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: stocks

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 14. Question
Quels produits ont plus de 30% du stock total déjà réservé ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Les stocks actuels (4 produits) sont:
- Arachide: 1140.0 kg disponibles
- Bissap: 0.0 kg disponibles
- Mangue: 2750.0 kg disponibles
- Mil: 1620.0 kg disponibles

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: stocks

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 15. Question
Parmi les lots encore ouverts, lequel est le plus ancien ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Le lot LOT-MANG-001 présente une perte de 6.0% et une efficacité de 94.0%.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: batches

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 16. Question
Sur les lots clôturés, quels sont les 2 pires en % de perte ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Perte observée sur séchage du lot LOT-BISS-002: 68.0% (150.0 kg -> 48.0 kg).

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: batches
- SQL: process_steps

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 17. Question
Ce trimestre, quel produit a généré le plus de nouveaux lots ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Perte observée sur séchage du lot LOT-BISS-002: 68.0% (150.0 kg -> 48.0 kg).

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: batches
- SQL: process_steps

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 18. Question
Sur 30 jours, quelle étape a généré le plus de pertes en kg ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Perte observée sur séchage du lot LOT-BISS-002: 68.0% (150.0 kg -> 48.0 kg).

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: process_steps

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 19. Question
Quelle étape unique a eu la plus grosse chute matière (qty_in - qty_out) ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Je n’ai pas trouvé de preuve opérationnelle exploitable pour répondre précisément à cette demande.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 20. Question
Quelle étape est la moins performante en rendement moyen sortie/entrée ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Je n’ai pas trouvé de preuve opérationnelle exploitable pour répondre précisément à cette demande.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 21. Question
Quel produit a le pire rendement moyen sur les lots avec quantité initiale non nulle ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Le lot LOT-MANG-001 présente une perte de 6.0% et une efficacité de 94.0%.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: batches

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 22. Question
Ce mois-ci, quel est le bilan matière global (entrée/sortie/perte%) ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Bilan matière global: entrée 12140.0 kg, sortie 11022.5 kg, perte 9.2%.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: batches
- SQL: process_steps

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 23. Question
Combien de lots clôturés dépassent 12% de pertes ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Perte observée sur séchage du lot LOT-BISS-002: 68.0% (150.0 kg -> 48.0 kg).

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: batches
- SQL: process_steps

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 24. Question
Sur 60 jours, combien de signaux ML sont classés HIGH ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Je n’ai pas trouvé de preuve opérationnelle exploitable pour répondre précisément à cette demande.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 25. Question
Quel lot porte le plus grand anomaly_score dans les logs ML ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Le lot LOT-MANG-001 présente une perte de 6.0% et une efficacité de 94.0%.

2. Explication courte
Signal ML: risque LOW | anomalie non; les mesures SQL restent la vérité opérationnelle.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: batches
- ML: ml_signal

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 26. Question
Combien de lots sont HIGH côté ML mais sous 6% de perte SQL ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Perte observée sur séchage du lot LOT-BISS-002: 68.0% (150.0 kg -> 48.0 kg).

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: batches
- SQL: process_steps

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 27. Question
Dernière recommandation générée: pour quel lot et quel niveau de risque ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Lots à risque élevé (5):
- LOT-BISS-002: perte 69.3 % | efficacité 30.7 %
- DEMOFP-LOT-MANG-013: perte 23.6 % | efficacité 76.4 %
- DEMOFP-LOT-MIL-009: perte 23.2 % | efficacité 76.8 %
- DEMOFP-LOT-MANG-003: perte 18.5 % | efficacité 81.5 %
- DEMOFP-LOT-MANG-001: perte 14.4 % | efficacité 85.6 %

2. Explication courte
Explication RAG: A recommendation was generated for lot DEMOFP-LOT-MANG-001 (Mangue) after losses reached 14.39% and efficiency dropped to 85.61%. Risk level is MEDIUM. Suggested action: Renforcer le contrôle humidité et le tri sur lots en cours.. Rationale: DEMOFP recommandat...

3. Recommandations si pertinentes
1. [HIGH] Isoler le lot LOT-BISS-002, renforcer le contrôle au séchage, puis reclasser les intrants dégradés. - Perte élevée (69.3%) et efficacité faible (30.7%) sur le lot ciblé. | Cible: LOT-BISS-002 / Bissap / séchage
2. [HIGH] Mettre en place un contrôle d’entrée/sortie au niveau du lot LOT-BISS-002 et ajuster le temps de traitement de l’étape critique. - Efficacité en dessous de la cible (30.7%). | Cible: LOT-BISS-002 / Bissap / séchage
3. [HIGH] Standardiser les contrôles de séchage avec seuils humidité/tri et feuille de suivi par lot. - L’étape séchage concentre les pertes (36.5% en moyenne). | Cible: LOT-BISS-002 / Bissap / Sechage

4. Sources utilisées
- SQL: batches
- RAG: Recommendation DEMOFP-LOT-MANG-001
- RAG: Lot recommendation DEMOFP-LOT-MANG-001
- RAG: Recommendation DEMOFP-LOT-MANG-002
- RAG: Lot recommendation DEMOFP-LOT-MANG-002
- RAG: Recommendation DEMOFP-LOT-MANG-003
- ML: ml_signal

5. Avertissements si nécessaires
- Le contexte documentaire RAG est faible.
```

## 28. Question
Combien de recommandations sont marquées HIGH ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
5 action(s) priorisée(s) générée(s), dont 3 priorité haute. Action principale: Isoler le lot LOT-BISS-002, renforcer le contrôle au séchage, puis reclasser les intrants dégradés. (cible: LOT-BISS-002 / Bissap / séchage).

2. Explication courte
Priorisation: Perte élevée (69.3%) et efficacité faible (30.7%) sur le lot ciblé. Efficacité en dessous de la cible (30.7%).

3. Recommandations si pertinentes
1. [HIGH] Isoler le lot LOT-BISS-002, renforcer le contrôle au séchage, puis reclasser les intrants dégradés. - Perte élevée (69.3%) et efficacité faible (30.7%) sur le lot ciblé. | Cible: LOT-BISS-002 / Bissap / séchage
2. [HIGH] Mettre en place un contrôle d’entrée/sortie au niveau du lot LOT-BISS-002 et ajuster le temps de traitement de l’étape critique. - Efficacité en dessous de la cible (30.7%). | Cible: LOT-BISS-002 / Bissap / séchage
3. [HIGH] Standardiser les contrôles de séchage avec seuils humidité/tri et feuille de suivi par lot. - L’étape séchage concentre les pertes (36.5% en moyenne). | Cible: LOT-BISS-002 / Bissap / Sechage

4. Sources utilisées

5. Avertissements si nécessaires
Aucun avertissement critique.
```

## 29. Question
Pour le lot au pire taux de perte, quelle recommandation est stockée ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Les stocks actuels (4 produits) sont:
- Arachide: 1140.0 kg disponibles
- Bissap: 0.0 kg disponibles
- Mangue: 2750.0 kg disponibles
- Mil: 1620.0 kg disponibles

2. Explication courte
Mesures SQL: étape critique Sechage (68.0%). Explication RAG: A recommendation was generated for lot DEMOFP-LOT-MANG-001 (Mangue) after losses reached 14.39% and efficiency dropped to 85.61%. Risk level is MEDIUM. Suggested action: Renforcer le contrôle humidité et le tri sur lots en cours.. Rationale: DEMOFP recommandat...

3. Recommandations si pertinentes
1. [HIGH] Isoler le lot LOT-BISS-002, renforcer le contrôle au séchage, puis reclasser les intrants dégradés. - Perte élevée (69.3%) et efficacité faible (30.7%) sur le lot ciblé. | Cible: LOT-BISS-002 / Bissap / séchage
2. [HIGH] Mettre en place un contrôle d’entrée/sortie au niveau du lot LOT-BISS-002 et ajuster le temps de traitement de l’étape critique. - Efficacité en dessous de la cible (30.7%). | Cible: LOT-BISS-002 / Bissap / séchage
3. [HIGH] Standardiser les contrôles de séchage avec seuils humidité/tri et feuille de suivi par lot. - L’étape séchage concentre les pertes (36.5% en moyenne). | Cible: LOT-BISS-002 / Bissap / Sechage

4. Sources utilisées
- SQL: batches
- SQL: process_steps
- SQL: stocks
- RAG: Recommendation DEMOFP-LOT-MANG-001
- RAG: Lot recommendation DEMOFP-LOT-MANG-001
- RAG: Recommendation DEMOFP-LOT-MANG-002
- RAG: Lot recommendation DEMOFP-LOT-MANG-002
- RAG: Recommendation DEMOFP-LOT-MANG-003

5. Avertissements si nécessaires
- Le contexte documentaire RAG est faible.
```

## 30. Question
Pour limiter la reprise d’humidité après séchage de Arachide, que recommandes-tu en priorité ?

### Réponse chatbot (exacte)
```text
1. Résultat principal
Commandes commerciales disponibles: 14.

2. Explication courte
Aucune explication détaillée disponible.

3. Recommandations si pertinentes
Aucune recommandation prioritaire confirmée.

4. Sources utilisées
- SQL: commercial_orders
- SQL: process_steps

5. Avertissements si nécessaires
- Aucune donnée SQL exploitable n’a été trouvée.
```
