# Chat SQL/RAG Diagnostic (2026-05-11)

- Manager account tested: `manager@weefarm.local`

## Ground Truth
- Members in cooperative: **17**
- Active lots: **0**
- Sample product: **Arachide**
- Members table first row matches DB: **True**

## Key Case Results
- `members_list` mode=`fallback` table_count=`1` citations=`2`
  - Prompt: lister les membres dans notre cooperative
  - Message preview: Je n'ai pas pu joindre le fournisseur LLM. Contexte actuel: pertes 9.2%, efficacite 90.8%, production 11022.5 kg. Requete: lister les membres dans notre cooperative. Reference disponible: sql:ops-member-efficiency:top_collected_kg (top_collected_kg). Prochaine action: confirmer l
- `active_lots` mode=`sql_only` table_count=`0` citations=`0`
  - Prompt: combien de lots actifs avons-nous ?
  - Message preview: Lots actifs en cours: 0.
- `lots_table` mode=`sql_only` table_count=`0` citations=`0`
  - Prompt: affiche-moi un tableau des 10 derniers lots avec code lot, produit, quantité entrée, quantité sortie, taux de perte, statut
  - Message preview: Pertes moyennes par étape : Sechage=36.53%; Séchage=11.14%; Tri=3.17%; Conditionnement=2.0%; Nettoyage=1.86%; Emballage=1.0%.
- `member_vs_lot_confusion` mode=`sql_only` table_count=`0` citations=`0`
  - Prompt: liste les membres actifs avec code et statut
  - Message preview: Membres (extrait) : DEMOFP-M-009 (Abdoulaye Sy), DEMOFP-M-013 (Alioune Cisse), DEMOFP-M-002 (Awa Ndiaye), DEMOFP-M-003 (Cheikh Diop), FB-0 (Fatou Fall), DEMOFP-M-004 (Fatou Sarr), DEMOFP-M-005 (Ibrahima Fall), DEMOFP-M-008 (Khady Kane).
- `rag_reference` mode=`fallback` table_count=`0` citations=`3`
  - Prompt: donne des références agronomiques sur le séchage du mil avec sources
  - Message preview: Je n'ai pas pu joindre le fournisseur LLM. Contexte actuel: pertes 9.2%, efficacite 90.8%, production 11022.5 kg. Requete: donne des références agronomiques sur le séchage du mil avec sources. Reference disponible: DEMOFP-SRC-KNOW-001 (Séchage). Prochaine action: confirmer les do

## Main Findings
- Member list can include a correct table, but routing still marks it HYBRID and fallback text can include irrelevant lot/loss context when LLM provider is unavailable.
- "Tableau des lots" request is routed to SQL-only text answer without UI table (table_count=0), creating UX mismatch.
- RAG reference requests can degrade to generic fallback text if LLM provider call fails, despite citations being available.

## Root Cause (Code Path)
- In `generate_chat_reply`, SQL_ONLY has an early return that persists `ui_blocks_json=[]`; this bypasses table blocks for deterministic SQL requests.