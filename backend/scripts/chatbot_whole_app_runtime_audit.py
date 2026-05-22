from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app

FAILURE_CATEGORIES = {
    "ROUTING_ERROR",
    "INTENT_MISMATCH",
    "SQL_OPERATION_MISSING",
    "DATA_SOURCE_NOT_COVERED",
    "EVIDENCE_INSUFFICIENT",
    "WRONG_RESPONSE_SHAPE",
    "SUMMARY_SELECTION_ERROR",
    "RECOMMENDATION_NOT_GROUNDED",
    "MEMORY_CONTEXT_ERROR",
    "WARNING_NOISE",
    "MODULE_NOT_SUPPORTED",
    "RAG_WEAK_OR_MISSING",
    "ML_SIGNAL_UNAVAILABLE",
    "LATENCY_OR_PROVIDER_ERROR",
    "LATENCY_SLOW_PATH",
    "CANONICAL_METRIC_INCONSISTENCY",
    "NO_FAILURE",
}


@dataclass
class AuditCase:
    qid: str
    module_group: str
    question: str
    expected_module: str
    expected_route: str
    expected_intent_family: str
    expected_tool_agent: str
    expected_evidence_source: str
    expected_response_shape: str


def build_cases() -> list[AuditCase]:
    cases: list[AuditCase] = []

    # Dashboard/global KPIs: 6
    cases.extend([
        AuditCase("D01", "dashboard", "Donne un résumé KPI global de la coopérative.", "cooperative_summary", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_cooperative_overview", "sql:members,parcels,stocks,batches,process_steps", "summary+kpi"),
        AuditCase("D02", "dashboard", "Combien de membres, parcelles et lots ouverts actuellement ?", "cooperative_summary", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_cooperative_overview", "sql:members,parcels,batches", "summary+table"),
        AuditCase("D03", "dashboard", "Quel est le stock disponible total de la coopérative ?", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_current_stock", "sql:stocks,products", "summary+kpi"),
        AuditCase("D04", "dashboard", "Perte moyenne observée sur les étapes de process ?", "cooperative_summary", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_cooperative_overview", "sql:process_steps", "summary"),
        AuditCase("D05", "dashboard", "Charges globales ce mois vs mois dernier ?", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:month_vs_month_charges", "sql:global_charges,treasury_transactions", "summary+comparison"),
        AuditCase("D06", "dashboard", "Top lots critiques actuellement ?", "material_balance", "SQL_ONLY", "LOSS_RANKING", "SQLAnalyticsAgent:get_canonical_material_balance", "sql:process_steps,batches", "ranking_table"),
    ])

    # Stocks/stock movements: 8
    cases.extend([
        AuditCase("S01", "stocks", "Stock disponible par produit ?", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks,products", "table"),
        AuditCase("S02", "stocks", "Produit avec le plus de stock disponible ?", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks,products", "ranking"),
        AuditCase("S03", "stocks", "Montre total/réservé/disponible pour chaque produit.", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks", "comparison_table"),
        AuditCase("S04", "stocks", "Quels produits sont sous seuil ?", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_low_stock_alerts", "sql:stocks", "alerts_table"),
        AuditCase("S05", "stock_movements", "Journal des mouvements de stock les plus récents.", "stock_movements", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_stock_movements_journal", "sql:stock_movements", "table"),
        AuditCase("S06", "stock_movements", "Mouvements de stock pour LOT-MILX-001.", "stock_movements", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_stock_movements_journal", "sql:stock_movements,batches", "table"),
        AuditCase("S07", "stocks", "Disponible net vs seuil pour la mangue.", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:available_stock_gap", "sql:stocks", "summary"),
        AuditCase("S08", "stocks", "Le stock restant et le stock total sont-ils cohérents pour chaque produit ?", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_current_stock", "sql:stocks", "consistency_table"),
    ])

    # Collectes/inputs: 6
    cases.extend([
        AuditCase("C01", "collectes", "Résumé des collectes par produit.", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_collections_summary", "sql:inputs,products", "table"),
        AuditCase("C02", "collectes", "Top 3 jours de collecte (6 mois).", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:top_collection_days", "sql:inputs", "ranking"),
        AuditCase("C03", "collectes", "Grade dominant en volume collecté ?", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:top_grade_by_volume", "sql:inputs", "summary"),
        AuditCase("C04", "collectes", "Traçabilité collectes: BL, justificatifs, liaison lot.", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_collecte_traceability", "sql:inputs,uploaded_files,batches", "summary+table"),
        AuditCase("C05", "collectes", "Collectes liées à des lots: combien ?", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_collecte_traceability", "sql:inputs,batches", "summary"),
        AuditCase("C06", "collectes", "Preuves documentaires upload associées aux collectes ?", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_uploaded_files_evidence", "sql:uploaded_files,inputs", "summary+table"),
    ])

    # Members/farmers: 6
    cases.extend([
        AuditCase("M01", "members", "Liste des membres producteurs (collecteurs).", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_members_list", "sql:members", "table"),
        AuditCase("M02", "members", "Top producteurs collecteurs par quantité livrée.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_top_farmers", "sql:members,inputs", "ranking"),
        AuditCase("M03", "members", "Plus petit contributeur non zéro ?", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:lowest_nonzero_member_contributor", "sql:members,inputs", "summary"),
        AuditCase("M04", "members", "Valeur cumulée par membre ?", "member_value", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_top_members_by_cost", "sql:members,global_charges", "ranking"),
        AuditCase("M05", "members", "Plus grande parcelle pour la mangue ?", "parcels", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:largest_parcel_by_product", "sql:parcels,members", "summary"),
        AuditCase("M06", "members", "Parcelles enregistrées par membre.", "parcels", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_parcels_list", "sql:parcels,members", "table"),
    ])

    # Lots/material balance/process steps: 10
    cases.extend([
        AuditCase("L01", "lots", "Lots post-récolte disponibles.", "lots", "SQL_ONLY", "POSTHARVEST_AVAILABLE_LOTS", "SQLAnalyticsAgent:get_available_postharvest_lots", "sql:batches", "table"),
        AuditCase("L02", "lots", "Résumé du lot LOT-MILX-001.", "lots", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_batch_summary", "sql:batches", "summary"),
        AuditCase("L03", "lots", "Lot ouvert le plus ancien ?", "lots", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:oldest_open_lot", "sql:batches", "summary"),
        AuditCase("L04", "material_balance", "Top lots par perte %.", "material_balance", "SQL_ONLY", "LOSS_RANKING", "SQLAnalyticsAgent:get_canonical_material_balance", "sql:process_steps,batches", "ranking"),
        AuditCase("L05", "material_balance", "Top lots par écart kg entrée-sortie.", "material_balance", "SQL_ONLY", "INPUT_OUTPUT_GAP", "SQLAnalyticsAgent:get_canonical_material_balance", "sql:process_steps,batches", "ranking"),
        AuditCase("L06", "material_balance", "Comparer LOT-MILX-001 et LOT-MANG-001 en perte/efficacité.", "material_balance", "SQL_ONLY", "LOT_COMPARISON", "SQLAnalyticsAgent:get_canonical_material_balance_for_lots", "sql:process_steps,batches", "comparison_table"),
        AuditCase("L07", "process_steps", "Étape la plus pénalisante (30j).", "process_steps", "SQL_ONLY", "STAGE_LOSS_ANALYSIS", "SQLAnalyticsAgent:get_stage_loss_analysis", "sql:process_steps", "summary"),
        AuditCase("L08", "process_steps", "Pertes par étape pour LOT-MILX-001.", "process_steps", "SQL_ONLY", "STAGE_LOSS_ANALYSIS", "SQLAnalyticsAgent:get_stage_loss_analysis", "sql:process_steps,batches", "table"),
        AuditCase("L09", "process_steps", "Comparaison séchage vs tri (perte moyenne).", "process_steps", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_stage_efficiency_summary", "sql:process_steps", "comparison_table"),
        AuditCase("L10", "material_balance", "Lots incohérents output>input ?", "material_balance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_postharvest_material_balance", "sql:process_steps,batches", "warnings+table"),
    ])

    # Recommendations: 4
    cases.extend([
        AuditCase("R01", "recommendations", "Donne 3 actions pour réduire les pertes de LOT-MILX-001 avec preuves.", "recommendations", "HYBRID_FULL", "LOT_SPECIFIC_RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "recommendation_cards"),
        AuditCase("R02", "recommendations", "Actions prioritaires cette semaine pour améliorer le rendement global.", "recommendations", "HYBRID_FULL", "RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "recommendation_cards"),
        AuditCase("R03", "recommendations", "Plan d’action manager basé SQL+ML+RAG avec evidence_refs.", "recommendations", "HYBRID_FULL", "action_recommendation", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "recommendation_cards+summary"),
        AuditCase("R04", "recommendations", "Pour le lot le plus critique, quelles actions immédiates ?", "recommendations", "HYBRID_FULL", "RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "recommendation_cards"),
    ])

    # RAG best practices: 3
    cases.extend([
        AuditCase("G01", "rag", "Bonnes pratiques de séchage pour limiter les pertes.", "rag", "RAG_ONLY", "BEST_PRACTICES", "RAGKnowledgeAgent:search", "rag", "best_practices"),
        AuditCase("G02", "rag", "Checklist avant emballage pour éviter casse et humidité.", "rag", "RAG_ONLY", "BEST_PRACTICES", "RAGKnowledgeAgent:search", "rag", "best_practices"),
        AuditCase("G03", "rag", "Précautions de stockage post-conditionnement.", "rag", "RAG_ONLY", "BEST_PRACTICES", "RAGKnowledgeAgent:search", "rag", "best_practices"),
    ])

    # Commercialisation/orders/sales: 6
    cases.extend([
        AuditCase("O01", "commercial", "Top client par cumul de commandes.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:top_customer_by_orders", "sql:commercial_orders", "summary"),
        AuditCase("O02", "commercial", "Résumé des commandes commerciales par statut.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_orders_summary", "sql:commercial_orders", "table"),
        AuditCase("O03", "commercial", "Totaux commerciaux (ventes).", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_totals", "sql:commercial_orders", "kpi"),
        AuditCase("O04", "commercial", "Lien commandes-factures-trésorerie.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_invoice_linkage", "sql:commercial_orders,commercial_invoices,treasury_transactions", "summary+table"),
        AuditCase("O05", "commercial", "Commandes payées avec facture générée ?", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_invoice_linkage", "sql:commercial_orders,commercial_invoices", "summary"),
        AuditCase("O06", "commercial", "Revenus trésorerie liés aux factures commerciales ?", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_invoice_linkage", "sql:treasury_transactions,commercial_invoices", "summary"),
    ])

    # Factures/invoices: 4
    cases.extend([
        AuditCase("F01", "invoices", "Montant moyen des factures payées ce trimestre.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:avg_paid_invoices_current_quarter", "sql:commercial_invoices", "summary"),
        AuditCase("F02", "invoices", "Résumé factures par statut payé/non payé.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_invoices_summary", "sql:commercial_invoices", "table"),
        AuditCase("F03", "invoices", "Factures payées ce mois ?", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_invoices_summary", "sql:commercial_invoices", "summary"),
        AuditCase("F04", "invoices", "Factures sans données: signaler proprement si vide.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_invoices_summary", "sql:commercial_invoices", "summary+warning"),
    ])

    # Trésorerie: 4
    cases.extend([
        AuditCase("T01", "treasury", "Dépenses finance/trésorerie récentes.", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_finance_expenses", "sql:treasury_transactions,global_charges", "table"),
        AuditCase("T02", "treasury", "Statuts trésorerie et justificatifs.", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_treasury_traceability", "sql:treasury_transactions", "summary+table"),
        AuditCase("T03", "treasury", "Coverage receipt_reference en trésorerie.", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_treasury_traceability", "sql:treasury_transactions", "summary"),
        AuditCase("T04", "treasury", "Transactions sans justificatif: combien ?", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_treasury_traceability", "sql:treasury_transactions", "summary"),
    ])

    # ML: 2
    cases.extend([
        AuditCase("ML1", "ml", "Combien de signaux ML HIGH sur 30 jours ?", "ml_logs", "ML_ONLY", "risk_ml", "MLLossAgent:ml_high_signal_count", "ml:ml_prediction_logs", "summary"),
        AuditCase("ML2", "ml", "Lot avec anomaly_score maximal ?", "ml_logs", "ML_ONLY", "risk_ml", "MLLossAgent:max_anomaly_score_lot", "ml:ml_prediction_logs", "summary"),
    ])

    # Memory/follow-up/reset: 1 (3-turn sequence evaluated as one scored case)
    cases.append(
        AuditCase("MEM1", "memory", "[SEQUENCE] Q1: lot le plus critique ? Q2: actions pour ce lot ? Q3: oublie ce lot et donne stock mangue.", "memory", "SQL_ONLY", "STOCK_CURRENT", "MemoryAgent+SQLAnalyticsAgent", "memory+sql:stocks", "sequence_reset")
    )

    assert len(cases) == 60, f"Expected 60 cases, got {len(cases)}"
    return cases


def build_fresh_cases() -> list[AuditCase]:
    cases: list[AuditCase] = []

    cases.extend([
        AuditCase("FD01", "dashboard", "Vue macro de la coop: KPI principaux du moment.", "cooperative_summary", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_cooperative_overview", "sql:members,parcels,stocks,batches,process_steps", "summary+kpi"),
        AuditCase("FD02", "dashboard", "Synthèse membres/parcelles/lots actifs aujourd’hui.", "cooperative_summary", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_cooperative_overview", "sql:members,parcels,batches", "summary+table"),
        AuditCase("FD03", "dashboard", "Volume stockable total actuellement disponible ?", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks,products", "summary+kpi"),
        AuditCase("FD04", "dashboard", "Quelles étapes ont la perte moyenne la plus élevée globalement ?", "cooperative_summary", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_process_step_losses", "sql:process_steps", "summary"),
        AuditCase("FD05", "dashboard", "Classe les lots les plus critiques en ce moment.", "material_balance", "SQL_ONLY", "LOSS_RANKING", "SQLAnalyticsAgent:get_canonical_material_balance", "sql:process_steps,batches", "ranking_table"),
    ])

    cases.extend([
        AuditCase("FS01", "stocks", "Inventaire par produit avec quantités disponibles.", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks,products", "table"),
        AuditCase("FS02", "stocks", "Produit le plus fourni en stock net ?", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks,products", "ranking"),
        AuditCase("FS03", "stocks", "Par produit: total, réservé et disponible.", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks", "comparison_table"),
        AuditCase("FS04", "stocks", "Références stock sous seuil d’alerte.", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_low_stock_alerts", "sql:stocks", "alerts_table"),
        AuditCase("FS05", "stock_movements", "Historique récent des mouvements de stock.", "stock_movements", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_stock_movements_journal", "sql:stock_movements", "table"),
        AuditCase("FS06", "stock_movements", "Trace des mouvements sur LOT-MILX-001.", "stock_movements", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_stock_movements_journal", "sql:stock_movements,batches", "table"),
    ])

    cases.extend([
        AuditCase("FC01", "collectes", "Bilan des volumes collectés par produit.", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_collections_summary", "sql:inputs,products", "table"),
        AuditCase("FC02", "collectes", "Quels jours ont concentré le plus de collecte récemment ?", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:top_collection_days", "sql:inputs", "ranking"),
        AuditCase("FC03", "collectes", "Le grade dominant en tonnage collecté ?", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:top_grade_by_volume", "sql:inputs", "summary"),
        AuditCase("FC04", "collectes", "Qualité traçabilité des collectes (BL/justificatifs/lots).", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_collecte_traceability", "sql:inputs,uploaded_files,batches", "summary+table"),
    ])

    cases.extend([
        AuditCase("FM01", "members", "Répertoire des membres producteurs enregistrés.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_members_list", "sql:members", "table"),
        AuditCase("FM02", "members", "Top producteurs collecteurs en kg livrés.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_top_farmers", "sql:members,inputs", "ranking"),
        AuditCase("FM03", "members", "Qui est le plus petit contributeur non nul ?", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:lowest_nonzero_member_contributor", "sql:members,inputs", "summary"),
        AuditCase("FM04", "members", "Parcelles recensées par membre.", "parcels", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_parcels_list", "sql:parcels,members", "table"),
    ])

    cases.extend([
        AuditCase("FL01", "lots", "Lots post-récolte encore exploitables.", "lots", "SQL_ONLY", "POSTHARVEST_AVAILABLE_LOTS", "SQLAnalyticsAgent:get_available_postharvest_lots", "sql:batches", "table"),
        AuditCase("FL02", "lots", "Donne le résumé du lot LOT-MILX-001.", "lots", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_batch_summary", "sql:batches", "summary"),
        AuditCase("FL03", "lots", "Quel lot ouvert est le plus ancien ?", "lots", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:oldest_open_lot", "sql:batches", "summary"),
        AuditCase("FL04", "material_balance", "Classement des lots par taux de perte.", "material_balance", "SQL_ONLY", "LOSS_RANKING", "SQLAnalyticsAgent:get_canonical_material_balance", "sql:process_steps,batches", "ranking"),
        AuditCase("FL05", "material_balance", "Lots triés par écart matière en kg.", "material_balance", "SQL_ONLY", "INPUT_OUTPUT_GAP", "SQLAnalyticsAgent:get_canonical_material_balance", "sql:process_steps,batches", "ranking"),
        AuditCase("FL06", "material_balance", "Comparatif LOT-MILX-001 vs LOT-MANG-001 sur perte/efficacité.", "material_balance", "SQL_ONLY", "LOT_COMPARISON", "SQLAnalyticsAgent:get_canonical_material_balance_for_lots", "sql:process_steps,batches", "comparison_table"),
        AuditCase("FL07", "process_steps", "Sur 30 jours, quelle étape pénalise le plus ?", "process_steps", "SQL_ONLY", "STAGE_LOSS_ANALYSIS", "SQLAnalyticsAgent:get_stage_loss_analysis", "sql:process_steps", "summary"),
        AuditCase("FL08", "process_steps", "Détail des pertes par étape pour LOT-MILX-001.", "process_steps", "SQL_ONLY", "STAGE_LOSS_ANALYSIS", "SQLAnalyticsAgent:get_stage_loss_analysis", "sql:process_steps,batches", "table"),
    ])

    cases.extend([
        AuditCase("FR01", "recommendations", "Trois actions immédiates pour réduire les pertes de LOT-MILX-001, avec preuves.", "recommendations", "HYBRID_FULL", "LOT_SPECIFIC_RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "recommendation_cards"),
        AuditCase("FR02", "recommendations", "Quelles actions prioriser cette semaine pour le rendement global ?", "recommendations", "HYBRID_FULL", "RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "recommendation_cards"),
        AuditCase("FR03", "recommendations", "Plan d’actions justifié par SQL+ML+RAG (evidence_refs requis).", "recommendations", "HYBRID_FULL", "action_recommendation", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "recommendation_cards+summary"),
        AuditCase("FR04", "recommendations", "Pour le lot le plus critique, quelles mesures lancer d’abord ?", "recommendations", "HYBRID_FULL", "RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "recommendation_cards"),
    ])

    cases.extend([
        AuditCase("FG01", "rag", "Bonnes pratiques de séchage pour diminuer les pertes (général).", "rag", "RAG_ONLY", "BEST_PRACTICES", "RAGKnowledgeAgent:search", "rag", "best_practices"),
        AuditCase("FG02", "rag", "Mini checklist avant conditionnement pour éviter humidité/casse.", "rag", "RAG_ONLY", "BEST_PRACTICES", "RAGKnowledgeAgent:search", "rag", "best_practices"),
        AuditCase("FG03", "rag", "Pratiques de stockage après emballage, sans données opérationnelles.", "rag", "RAG_ONLY", "BEST_PRACTICES", "RAGKnowledgeAgent:search", "rag", "best_practices"),
    ])

    cases.extend([
        AuditCase("FO01", "commercial", "Quel client cumule le plus de commandes ?", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:top_customer_by_orders", "sql:commercial_orders", "summary"),
        AuditCase("FO02", "commercial", "Distribution des commandes commerciales par statut.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_orders_summary", "sql:commercial_orders", "table"),
        AuditCase("FO03", "commercial", "Totaux commerciaux consolidés (nombre + montant).", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_totals", "sql:commercial_orders", "kpi"),
        AuditCase("FO04", "commercial", "Contrôle du chaînage commandes/factures/trésorerie.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_invoice_linkage", "sql:commercial_orders,commercial_invoices,treasury_transactions", "summary+table"),
    ])

    cases.extend([
        AuditCase("FF01", "invoices", "Montant moyen des factures réglées ce trimestre.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:avg_paid_invoices_current_quarter", "sql:commercial_invoices", "summary"),
        AuditCase("FF02", "invoices", "État des factures: payé vs non payé.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_invoices_summary", "sql:commercial_invoices", "table"),
        AuditCase("FF03", "invoices", "S’il n’y a pas de facture, réponds proprement sans halluciner.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_invoices_summary", "sql:commercial_invoices", "summary+warning"),
    ])

    cases.extend([
        AuditCase("FT01", "treasury", "Dépenses et sorties trésorerie récentes.", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_finance_expenses", "sql:treasury_transactions,global_charges", "table"),
        AuditCase("FT02", "treasury", "Combien de transactions sans justificatif ?", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_treasury_traceability", "sql:treasury_transactions", "summary"),
        AuditCase("FT03", "treasury", "Couverture des receipt_reference en trésorerie.", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_treasury_traceability", "sql:treasury_transactions", "summary"),
    ])

    cases.extend([
        AuditCase("FML1", "ml", "Nombre de signaux ML HIGH sur 30 jours.", "ml_logs", "ML_ONLY", "risk_ml", "MLLossAgent:ml_high_signal_count", "ml:ml_prediction_logs", "summary"),
        AuditCase("FML2", "ml", "Quel lot porte l’anomaly_score maximal ?", "ml_logs", "ML_ONLY", "risk_ml", "MLLossAgent:max_anomaly_score_lot", "ml:ml_prediction_logs", "summary"),
    ])

    # Added no-data/paraphrase stress cases (anti-overfit).
    cases.extend([
        AuditCase("FN01", "invoices", "Y a-t-il des factures payées ce trimestre ? Si aucune, confirme explicitement l’absence.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:avg_paid_invoices_current_quarter", "sql:commercial_invoices", "summary"),
        AuditCase("FN02", "invoices", "Moyenne des factures réglées ce trimestre fiscal, avec réponse claire si zéro facture payée.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:avg_paid_invoices_current_quarter", "sql:commercial_invoices", "summary"),
        AuditCase("FN03", "ml", "Combien d’alertes ML HIGH sont journalisées sur 14 jours ?", "ml_logs", "ML_ONLY", "risk_ml", "MLLossAgent:ml_high_signal_count", "ml:ml_prediction_logs", "summary"),
        AuditCase("FN04", "ml", "Quel est le maximum d’anomaly_score ML enregistré dans les journaux ? Si vide, indique-le.", "ml_logs", "ML_ONLY", "risk_ml", "MLLossAgent:max_anomaly_score_lot", "ml:ml_prediction_logs", "summary"),
        AuditCase("FN05", "stocks", "Confirme s’il existe ou non des alertes de stock sous seuil actuellement.", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_low_stock_alerts", "sql:stocks", "summary"),
        AuditCase("FN06", "recommendations", "Donne uniquement les actions vraiment prouvées pour LOT-MILX-001; si une seule est solide, dis-le.", "recommendations", "HYBRID_FULL", "action_recommendation", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "recommendation_cards"),
        AuditCase("FN07", "recommendations", "Pour le lot critique actuel, propose des mesures prioritaires sans ajouter d’action sans evidence_refs valides.", "recommendations", "HYBRID_FULL", "RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "recommendation_cards"),
        AuditCase("FN08", "rag", "Bonnes pratiques pour une étape de fumage artisanal post-récolte (si non documenté, indique-le).", "rag", "RAG_ONLY", "BEST_PRACTICES", "RAGKnowledgeAgent:search", "rag", "best_practices"),
        AuditCase("FN09", "rag", "Checklist qualité pour un protocole exotique non standard, sans données SQL.", "rag", "RAG_ONLY", "BEST_PRACTICES", "RAGKnowledgeAgent:search", "rag", "best_practices"),
        AuditCase("FN10", "invoices", "Existe-t-il une moyenne trimestrielle de factures payées aujourd’hui ? Sinon, réponds en no-data explicite.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:avg_paid_invoices_current_quarter", "sql:commercial_invoices", "summary"),
    ])

    cases.append(
        AuditCase("FMEM1", "memory", "[SEQUENCE] Q1: lot critique actuel ? Q2: actions sur ce lot ? Q3: oublie ce contexte et donne seulement le stock mangue.", "memory", "SQL_ONLY", "STOCK_CURRENT", "MemoryAgent+SQLAnalyticsAgent", "memory+sql:stocks", "sequence_reset")
    )

    assert len(cases) >= 40, f"Expected at least 40 fresh cases, got {len(cases)}"
    return cases


def build_manual_regression_cases() -> list[AuditCase]:
    cases = [
        AuditCase("MR01", "stocks", "Présente l’inventaire disponible par article et qualité.", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks,products", "table:stock_by_grade"),
        AuditCase("MR02", "stock_movements", "Donne les derniers mouvements de stock avec nature, produit, quantité et origine.", "stock_movements", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_stock_movements_journal", "sql:stock_movements", "table:stock_movements"),
        AuditCase("MR03", "collectes", "Agrège les quantités collectées par produit.", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_collections_summary", "sql:inputs,products", "table:collected_by_product"),
        AuditCase("MR04", "collectes", "Montre la traçabilité des collectes: bon de livraison, preuve et lot associé.", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_collecte_traceability", "sql:inputs,uploaded_files,batches", "table:collecte_traceability"),
        AuditCase("MR05", "members", "Liste les producteurs actifs avec leurs parcelles ou produits liés.", "parcels", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_parcels_list", "sql:members,parcels,products", "table:active_producers"),
        AuditCase("MR06", "members", "Quel producteur a livré le plus grand volume ?", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_top_farmers", "sql:members,inputs", "ranking:delivered_quantity"),
        AuditCase("MR07", "lots", "Quels lots sont disponibles pour passer en post-récolte ?", "lots", "SQL_ONLY", "POSTHARVEST_AVAILABLE_LOTS", "SQLAnalyticsAgent:get_available_postharvest_lots", "sql:batches", "table:postharvest_lots"),
        AuditCase("MR08", "material_balance", "Classe les lots selon la perte matière en kilogrammes.", "material_balance", "SQL_ONLY", "INPUT_OUTPUT_GAP", "SQLAnalyticsAgent:get_canonical_material_balance", "sql:process_steps,batches", "ranking:kg_loss"),
        AuditCase("MR09", "process_steps", "Quelle étape génère la plus forte perte matière ?", "process_steps", "SQL_ONLY", "STAGE_LOSS_ANALYSIS", "SQLAnalyticsAgent:get_stage_loss_analysis", "sql:process_steps,batches", "summary:stage_loss"),
        AuditCase("MR10", "commercial", "Répartis les commandes commerciales par statut.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_orders_summary", "sql:commercial_orders", "table:orders_by_status"),
        AuditCase("MR11", "invoices", "Répartis les factures selon leur statut de paiement.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_invoices_summary", "sql:commercial_invoices", "table:invoices_by_payment_status"),
        AuditCase("MR12", "treasury", "Affiche les opérations de trésorerie qui n’ont pas de justificatif.", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_treasury_traceability", "sql:treasury_transactions", "table:treasury_without_proof"),
        AuditCase("MR13", "stocks", "Pour chaque produit, distingue total, disponible et réservé si l’information existe.", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks", "table:stock_total_available_reserved"),
        AuditCase("MR14", "collectes", "Quel produit domine les collectes et avec quelle quantité cumulée ?", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_collections_summary", "sql:inputs,products", "summary:top_collected_product"),
        AuditCase("MR15", "process_steps", "Quelle étape cause le plus de pertes en kg et sur quels lots ?", "process_steps", "SQL_ONLY", "STAGE_LOSS_ANALYSIS", "SQLAnalyticsAgent:get_stage_loss_analysis", "sql:process_steps,batches", "table:stage_loss_with_lots"),
        AuditCase("MR16", "commercial", "Existe-t-il des commandes payées sans facture rattachée ?", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_invoice_linkage", "sql:commercial_orders,commercial_invoices", "summary:paid_orders_without_invoice"),
        AuditCase("MR17", "treasury", "Quelles transactions manquent de justificatif ou de référence de reçu ?", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_treasury_traceability", "sql:treasury_transactions", "table:treasury_missing_proof_or_receipt"),
        AuditCase("MR18", "ml", "Combien de signaux ML élevés sont enregistrés dans les journaux ?", "ml_logs", "ML_ONLY", "risk_ml", "MLLossAgent:ml_high_signal_count", "ml:ml_prediction_logs", "summary:ml_signal_count"),
    ]
    return cases


def build_detail_members_memory_cases() -> list[AuditCase]:
    cases: list[AuditCase] = []

    # A. Detailed request handling
    cases.extend([
        AuditCase("DM01", "stocks", "Quels produits sont sous le seuil critique de stock ?", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_low_stock_alerts", "sql:stocks", "table:low_stock"),
        AuditCase("DM02", "stocks", "Produits proches du seuil de rupture ?", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_low_stock_alerts", "sql:stocks", "table:low_stock"),
        AuditCase("DM03", "stocks", "Risque de rupture stock par produit.", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_low_stock_alerts", "sql:stocks", "table:low_stock"),
        AuditCase("DM04", "stocks", "Stock total, disponible, réservé et restant pour chaque produit.", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks", "table:stock_full_breakdown"),
        AuditCase("DM05", "stocks", "Pour la mangue: total/disponible/réservé/restant.", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_current_stock", "sql:stocks", "summary:stock_product_breakdown"),
        AuditCase("DM06", "stock_movements", "Derniers mouvements de stock avec type, produit, quantité, source et date.", "stock_movements", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_stock_movements_journal", "sql:stock_movements", "table:stock_movements_detail"),
        AuditCase("DM07", "stock_movements", "Mouvements de stock récents pour MIL uniquement.", "stock_movements", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_stock_movements_journal", "sql:stock_movements", "table:stock_movements_detail"),
        AuditCase("DM08", "commercial", "Commandes regroupées par statut avec nombre et montant total.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_orders_summary", "sql:commercial_orders", "table:orders_status_grouped"),
        AuditCase("DM09", "commercial", "Donne uniquement la catégorie de commande la plus importante par montant.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_orders_summary", "sql:commercial_orders", "summary:single_top_status"),
        AuditCase("DM10", "invoices", "Factures par statut de paiement: statut, nombre, montant total.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_invoices_summary", "sql:commercial_invoices", "table:invoices_status_grouped"),
        AuditCase("DM11", "invoices", "Uniquement le statut de facture dominant par montant.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_invoices_summary", "sql:commercial_invoices", "summary:single_top_status"),
        AuditCase("DM12", "members", "Top 2 producteurs par quantité livrée.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_top_farmers", "sql:members,inputs", "table:top_n_2"),
        AuditCase("DM13", "members", "Top 1 producteur sur l’arachide.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_top_farmers", "sql:members,inputs", "table:top_n_1"),
    ])

    # B. Members/producers
    cases.extend([
        AuditCase("DM14", "members", "lister notre membres", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_members_list", "sql:members", "table:members_active"),
        AuditCase("DM15", "members", "Liste les producteurs avec leurs parcelles.", "parcels", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_parcels_list", "sql:members,parcels", "table:producer_parcels"),
        AuditCase("DM16", "members", "Montre les producteurs enregistrés.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_members_list", "sql:members", "table:producer_products"),
        AuditCase("DM17", "members", "Quel producteur collecteur a livré le plus grand volume ?", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_top_farmers", "sql:members,inputs", "summary:top_delivered_farmer"),
        AuditCase("DM18", "members", "Contribution des producteurs par produit.", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_collections_summary", "sql:members,inputs,products", "table:producer_contrib_product"),
        AuditCase("DM19", "members", "Quel producteur n’a pas livré récemment ?", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_members_list", "sql:members,inputs", "summary:producer_no_recent_delivery"),
        AuditCase("DM20", "members", "Efficacité producteur par membre.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_top_farmers", "sql:members,inputs", "summary:producer_efficiency_limit"),
        AuditCase("DM21", "members", "Montre uniquement un producteur actif.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_members_list", "sql:members", "table:single_item"),
    ])

    # C. Memory/follow-up
    cases.extend([
        AuditCase("DM22", "memory", "[SEQUENCE] Q1 lot critique; Q2 recommandations pour ce lot.", "memory", "HYBRID_FULL", "LOT_SPECIFIC_RECOMMENDATION", "MemoryAgent+RecommendationAgent", "memory+sql+recommendation", "sequence_followup_lot"),
        AuditCase("DM23", "memory", "[SEQUENCE] Q1 top producteur; Q2 détail pour ce producteur.", "memory", "SQL_ONLY", "factual_sql", "MemoryAgent+SQLAnalyticsAgent", "memory+sql:members", "sequence_followup_producer"),
        AuditCase("DM24", "memory", "[SEQUENCE] Q1 stock mangue; Q2 mouvements pour ce produit.", "memory", "SQL_ONLY", "factual_sql", "MemoryAgent+SQLAnalyticsAgent", "memory+sql:stocks,stock_movements", "sequence_followup_product"),
        AuditCase("DM25", "memory", "[SEQUENCE] Q1 classement lots; Q2 détail du premier.", "memory", "SQL_ONLY", "factual_sql", "MemoryAgent+SQLAnalyticsAgent", "memory+sql:lots", "sequence_first_item"),
        AuditCase("DM26", "memory", "[SEQUENCE] Q1 lot critique; Q2 oublie ce lot; Q3 recommandations pour ce lot.", "memory", "SQL_ONLY", "factual_sql", "MemoryAgent", "memory", "sequence_reset_clarification"),
        AuditCase("DM27", "memory", "[SEQUENCE] Q1 lot critique; Q2 change de sujet; Q3 stock mangue.", "memory", "SQL_ONLY", "STOCK_CURRENT", "MemoryAgent+SQLAnalyticsAgent", "memory+sql:stocks", "sequence_topic_switch"),
        AuditCase("DM28", "memory", "[SEQUENCE] Q1 lot critique; Q2 oublie ce lot + celui-ci (ambigu, même message).", "memory", "SQL_ONLY", "factual_sql", "MemoryAgent", "memory", "sequence_ambiguous_clarify"),
        AuditCase("DM29", "memory", "[SEQUENCE] Q1 lot critique; Q2 parlons du stock; Q3 ce lot ?", "memory", "SQL_ONLY", "factual_sql", "MemoryAgent+SQLAnalyticsAgent", "memory+sql:stocks", "sequence_no_stale_lot"),
        AuditCase("DM30", "memory", "[SEQUENCE] Q1 stock mangue; Q2 ce lot ?", "memory", "SQL_ONLY", "factual_sql", "MemoryAgent", "memory", "sequence_no_lot_inference"),
        AuditCase("DM31", "memory", "[SEQUENCE] Q1 top producteur; Q2 ce lot ?", "memory", "SQL_ONLY", "factual_sql", "MemoryAgent", "memory", "sequence_cross_entity_clarify"),
    ])

    assert len(cases) >= 30, f"Expected at least 30 detail-members-memory cases, got {len(cases)}"
    return cases


def build_response_quality_cases() -> list[AuditCase]:
    cases: list[AuditCase] = []
    cases.extend([
        AuditCase("RQ01", "stocks", "Quel est le stock disponible total actuel ?", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks", "rq_simple_sql"),
        AuditCase("RQ02", "stocks", "Détaille le stock par produit et grade.", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks,products", "rq_detailed_table"),
        AuditCase("RQ03", "commercial", "Commandes regroupées par statut avec nombre et montant total.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_orders_summary", "sql:commercial_orders", "rq_grouped_status"),
        AuditCase("RQ04", "invoices", "Factures regroupées par statut de paiement avec nombre et montant total.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_invoices_summary", "sql:commercial_invoices", "rq_grouped_status"),
        AuditCase("RQ05", "invoices", "Moyenne des factures payées ce trimestre, et si aucune donnée précise-le.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:avg_paid_invoices_current_quarter", "sql:commercial_invoices", "rq_no_data_or_fact"),
        AuditCase("RQ06", "recommendations", "Donne une action prioritaire pour LOT-MILX-001 avec preuve.", "recommendations", "HYBRID_FULL", "LOT_SPECIFIC_RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "rq_reco_single"),
        AuditCase("RQ07", "recommendations", "Top 3 actions fiables pour LOT-MILX-001 avec preuves.", "recommendations", "HYBRID_FULL", "LOT_SPECIFIC_RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "rq_reco_topn"),
        AuditCase("RQ08", "material_balance", "Compare LOT-MILX-001 et LOT-MANG-001.", "material_balance", "SQL_ONLY", "LOT_COMPARISON", "SQLAnalyticsAgent:get_canonical_material_balance_for_lots", "sql:process_steps,batches", "rq_lot_comparison"),
        AuditCase("RQ09", "process_steps", "Quelle étape perd le plus et pourquoi la valeur peut différer d’un bilan lot ?", "process_steps", "SQL_ONLY", "STAGE_LOSS_ANALYSIS", "SQLAnalyticsAgent:get_stage_loss_analysis", "sql:process_steps", "rq_stage_loss_diff"),
        AuditCase("RQ10", "members", "Affiche la liste des membres.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_members_list", "sql:members", "rq_members_table"),
        AuditCase("RQ11", "members", "Top producteurs collecteurs par quantité livrée.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_top_farmers", "sql:members,inputs", "rq_members_top"),
        AuditCase("RQ12", "stock_movements", "Derniers mouvements de stock: type, produit, quantité, source, date.", "stock_movements", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_stock_movements_journal", "sql:stock_movements", "rq_detailed_table"),
        AuditCase("RQ13", "stocks", "Quels produits sont sous le seuil critique ?", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_low_stock_alerts", "sql:stocks", "rq_simple_sql"),
        AuditCase("RQ14", "recommendations", "Que recommandes-tu pour le lot le plus critique sans inventer ?", "recommendations", "HYBRID_FULL", "RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "rq_reco_topn"),
        AuditCase("RQ15", "treasury", "Combien de transactions sans justificatif ?", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_treasury_traceability", "sql:treasury_transactions", "rq_simple_sql"),
        AuditCase("RQ16", "commercial", "Donne uniquement le statut de commande dominant par montant.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_orders_summary", "sql:commercial_orders", "rq_grouped_single"),
        AuditCase("RQ17", "invoices", "Donne uniquement le statut de facture dominant par montant.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_invoices_summary", "sql:commercial_invoices", "rq_grouped_single"),
        AuditCase("RQ18", "lots", "Quels lots sont disponibles pour la post-récolte ?", "lots", "SQL_ONLY", "POSTHARVEST_AVAILABLE_LOTS", "SQLAnalyticsAgent:get_available_postharvest_lots", "sql:batches", "rq_detailed_table"),
        AuditCase("RQ19", "material_balance", "Classe les lots par écart matière en kg.", "material_balance", "SQL_ONLY", "INPUT_OUTPUT_GAP", "SQLAnalyticsAgent:get_canonical_material_balance", "sql:process_steps,batches", "rq_gap_summary"),
        AuditCase("RQ20", "rag", "Checklist de bonnes pratiques avant emballage.", "rag", "RAG_ONLY", "BEST_PRACTICES", "RAGKnowledgeAgent:search", "rag", "rq_rag_practice"),
        AuditCase("RQ21", "ml", "Combien de signaux ML HIGH sur 30 jours ?", "ml_logs", "ML_ONLY", "risk_ml", "MLLossAgent:ml_high_signal_count", "ml:ml_prediction_logs", "rq_ml_fact"),
        AuditCase("RQ22", "memory", "[SEQUENCE] Q1 lot critique ; Q2 oublie ce lot + celui-ci (ambigu).", "memory", "SQL_ONLY", "factual_sql", "MemoryAgent", "memory", "sequence_rq_memory_clarify"),
        AuditCase("RQ23", "memory", "[SEQUENCE] Q1 lot critique ; Q2 oublie ce lot ; Q3 recommandations pour ce lot.", "memory", "SQL_ONLY", "factual_sql", "MemoryAgent", "memory", "sequence_rq_memory_reset"),
        AuditCase("RQ24", "members", "Producteurs et produits principaux.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_members_list", "sql:members", "rq_members_table"),
        AuditCase("RQ25", "process_steps", "Pertes par étape pour LOT-MILX-001.", "process_steps", "SQL_ONLY", "STAGE_LOSS_ANALYSIS", "SQLAnalyticsAgent:get_stage_loss_analysis", "sql:process_steps,batches", "rq_stage_loss_diff"),
    ])
    assert len(cases) >= 25, f"Expected at least 25 response-quality cases, got {len(cases)}"
    return cases


def build_latency_cases() -> list[AuditCase]:
    cases: list[AuditCase] = [
        AuditCase("LT01", "stocks", "Donne le stock disponible total de la coop.", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks", "latency_sql_fast"),
        AuditCase("LT02", "stocks", "Inventaire par produit avec total/disponible/réservé.", "stocks", "SQL_ONLY", "STOCK_CURRENT", "SQLAnalyticsAgent:get_current_stock", "sql:stocks", "latency_sql_fast"),
        AuditCase("LT03", "stock_movements", "Journal des mouvements de stock récents.", "stock_movements", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_stock_movements_journal", "sql:stock_movements", "latency_sql_fast"),
        AuditCase("LT04", "collectes", "Volumes collectés par produit.", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_collections_summary", "sql:inputs,products", "latency_sql_fast"),
        AuditCase("LT05", "members", "Liste des membres producteurs actifs.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_members_list", "sql:members", "latency_sql_fast"),
        AuditCase("LT06", "members", "Top producteurs par quantité livrée.", "members", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_top_farmers", "sql:members,inputs", "latency_sql_fast"),
        AuditCase("LT07", "commercial", "Commandes commerciales regroupées par statut.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_commercial_orders_summary", "sql:commercial_orders", "latency_sql_grouped"),
        AuditCase("LT08", "invoices", "Factures regroupées par statut de paiement.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_invoices_summary", "sql:commercial_invoices", "latency_sql_grouped"),
        AuditCase("LT09", "treasury", "Transactions sans justificatif.", "finance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_treasury_traceability", "sql:treasury_transactions", "latency_sql_fast"),
        AuditCase("LT10", "material_balance", "Classe les lots par perte (%).", "material_balance", "SQL_ONLY", "LOSS_RANKING", "SQLAnalyticsAgent:get_canonical_material_balance", "sql:process_steps,batches", "latency_sql_analytics"),
        AuditCase("LT11", "material_balance", "Classe les lots par écart matière en kg.", "material_balance", "SQL_ONLY", "INPUT_OUTPUT_GAP", "SQLAnalyticsAgent:get_canonical_material_balance", "sql:process_steps,batches", "latency_sql_analytics"),
        AuditCase("LT12", "process_steps", "Étape la plus pénalisante sur 30 jours.", "process_steps", "SQL_ONLY", "STAGE_LOSS_ANALYSIS", "SQLAnalyticsAgent:get_stage_loss_analysis", "sql:process_steps", "latency_sql_analytics"),
        AuditCase("LT13", "lots", "Lots post-récolte disponibles.", "lots", "SQL_ONLY", "POSTHARVEST_AVAILABLE_LOTS", "SQLAnalyticsAgent:get_available_postharvest_lots", "sql:batches", "latency_sql_fast"),
        AuditCase("LT14", "rag", "Bonnes pratiques de séchage pour limiter les pertes.", "rag", "RAG_ONLY", "BEST_PRACTICES", "RAGKnowledgeAgent:search", "rag", "latency_rag"),
        AuditCase("LT15", "rag", "Checklist avant emballage pour éviter humidité.", "rag", "RAG_ONLY", "BEST_PRACTICES", "RAGKnowledgeAgent:search", "rag", "latency_rag"),
        AuditCase("LT16", "ml", "Combien de signaux ML HIGH sur 30 jours ?", "ml_logs", "ML_ONLY", "risk_ml", "MLLossAgent:ml_high_signal_count", "ml:ml_prediction_logs", "latency_ml"),
        AuditCase("LT17", "recommendations", "Donne 2 actions fiables pour LOT-MILX-001 avec preuves.", "recommendations", "HYBRID_FULL", "LOT_SPECIFIC_RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "latency_hybrid_reco"),
        AuditCase("LT18", "recommendations", "Quelles actions recommandes-tu cette semaine pour réduire les pertes, avec preuves explicites ?", "recommendations", "HYBRID_FULL", "RECOMMENDATION", "RecommendationAgent:build_recommendations", "sql+rag+ml+recommendation", "latency_hybrid_reco"),
        AuditCase("LT19", "material_balance", "Donne le bilan matière de LOT-MILX-001 (entrée, sortie, perte, efficacité).", "material_balance", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_batch_summary", "sql:batches,process_steps", "latency_sql_analytics"),
        AuditCase("LT20", "stocks", "Produits sous seuil critique de stock.", "stocks", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_low_stock_alerts", "sql:stocks", "latency_sql_no_data_or_fact"),
        AuditCase("LT21", "invoices", "Moyenne des factures payées ce trimestre; si aucune, dis-le.", "invoices", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:avg_paid_invoices_current_quarter", "sql:commercial_invoices", "latency_sql_no_data_or_fact"),
        AuditCase("LT22", "memory", "[SEQUENCE] Q1 lot critique ; Q2 recommandations pour ce lot.", "memory", "HYBRID_FULL", "LOT_SPECIFIC_RECOMMENDATION", "MemoryAgent+RecommendationAgent", "memory+sql+recommendation", "sequence_latency_followup"),
        AuditCase("LT23", "memory", "[SEQUENCE] Q1 lot critique ; Q2 oublie ce lot ; Q3 recommandations pour ce lot.", "memory", "SQL_ONLY", "factual_sql", "MemoryAgent", "memory", "sequence_latency_reset"),
        AuditCase("LT24", "commercial", "Client avec le plus grand cumul de commandes.", "commercial", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:top_customer_by_orders", "sql:commercial_orders", "latency_sql_fast"),
        AuditCase("LT25", "members", "Contribution des producteurs par produit.", "inputs", "SQL_ONLY", "factual_sql", "SQLAnalyticsAgent:get_collections_summary", "sql:members,inputs,products", "latency_sql_grouped"),
    ]
    assert len(cases) >= 25, f"Expected at least 25 latency cases, got {len(cases)}"
    return cases


def _safe_num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _extract_sql_operation(metadata: dict[str, Any]) -> str | None:
    top_trace = metadata.get("sql_dispatch_trace") or {}
    if isinstance(top_trace, dict) and top_trace.get("sql_operation"):
        return str(top_trace.get("sql_operation"))
    debug = metadata.get("agent_debug") or {}
    sql_data = ((debug.get("SQLAnalyticsAgent") or {}).get("data") or {})
    trace = sql_data.get("sql_dispatch_trace") or {}
    op = trace.get("sql_operation")
    return str(op) if op else None


def _extract_intent_family(metadata: dict[str, Any]) -> str:
    ent = metadata.get("detected_entities") or {}
    return str(metadata.get("intent_family") or ent.get("intent_family") or "")


def _extract_evidence_row_count(payload: dict[str, Any], metadata: dict[str, Any]) -> int:
    top_trace = metadata.get("sql_dispatch_trace") or {}
    if isinstance(top_trace, dict) and isinstance(top_trace.get("row_count"), int):
        return int(top_trace.get("row_count") or 0)
    debug = metadata.get("agent_debug") or {}
    sql_data = ((debug.get("SQLAnalyticsAgent") or {}).get("data") or {})
    trace = sql_data.get("sql_dispatch_trace") or {}
    rc = trace.get("row_count")
    if isinstance(rc, int):
        return rc
    ml_data = ((debug.get("MLLossAgent") or {}).get("data") or {})
    for key in ("ml_high_signal_count", "max_anomaly_score_lot", "ml_insight_summary"):
        rows = ml_data.get(key)
        if isinstance(rows, list):
            return len(rows)
    if isinstance(ml_data, dict) and ml_data:
        return 1
    sources = payload.get("sources") or []
    total = 0
    for s in sources:
        try:
            total += int(s.get("record_count") or 0)
        except Exception:
            pass
    return total


def _extract_evidence_statuses(metadata: dict[str, Any]) -> dict[str, str]:
    top_status = metadata.get("evidence_status") or {}
    top_trace = metadata.get("sql_dispatch_trace") or {}
    debug = metadata.get("agent_debug") or {}
    sql_data = ((debug.get("SQLAnalyticsAgent") or {}).get("data") or {})
    ml_data = ((debug.get("MLLossAgent") or {}).get("data") or {})
    rag_data = ((debug.get("RAGKnowledgeAgent") or {}).get("data") or {})
    trace = sql_data.get("sql_dispatch_trace") or {}
    return {
        "sql": str((top_trace if isinstance(top_trace, dict) else {}).get("evidence_status") or (top_status if isinstance(top_status, dict) else {}).get("sql") or trace.get("evidence_status") or "").strip().upper(),
        "ml": str((top_status if isinstance(top_status, dict) else {}).get("ml") or ml_data.get("evidence_status") or "").strip().upper(),
        "rag": str((top_status if isinstance(top_status, dict) else {}).get("rag") or rag_data.get("evidence_status") or "").strip().upper(),
    }


def _evidence_types(payload: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for s in payload.get("sources") or []:
        out.add(_upper((s or {}).get("type")))
    return out


def _response_shape(blocks: list[dict[str, Any]], answer: str) -> str:
    types = {str((b or {}).get("type") or "").lower() for b in blocks if isinstance(b, dict)}
    if "recommendations" in types or "recommendation_cards" in types:
        return "recommendation_cards"
    if "table" in types or "comparison_table" in types:
        return "table"
    if "chart" in types:
        return "chart"
    if "best_practices" in types:
        return "best_practices"
    if "kpi_cards" in types:
        return "summary"
    txt = str(answer or "").lower()
    if "check-list" in txt or "bonnes pratiques" in txt:
        return "best_practices"
    return "summary"


def _contains_raw_rag_leak(answer: str) -> bool:
    txt = str(answer or "").lower()
    return any(token in txt for token in ("chunk_id", "document_id", "source:", "topic:"))


def _too_noisy_warnings(warnings: list[str]) -> bool:
    return len(warnings) >= 4


def _recommendation_grounded(payload: dict[str, Any], metadata: dict[str, Any]) -> bool:
    refs_count = int((metadata or {}).get("recommendation_refs_count") or 0)
    if refs_count > 0:
        return True
    blocks = payload.get("response_blocks") or []
    for b in blocks:
        if str((b or {}).get("type") or "").lower() in {"recommendations", "recommendation_cards"}:
            for it in (b.get("items") or []):
                refs = (it or {}).get("evidence_refs")
                if isinstance(refs, list) and refs:
                    return True
    return False


def _expected_sql_operation(case: AuditCase) -> str:
    if ":" not in case.expected_tool_agent:
        return ""
    return case.expected_tool_agent.split(":", 1)[1].strip()


def _block_text(payload: dict[str, Any]) -> str:
    parts = [str(payload.get("answer") or "")]
    for block in payload.get("response_blocks") or []:
        if not isinstance(block, dict):
            continue
        parts.append(str(block.get("title") or ""))
        parts.append(str(block.get("content") or ""))
        for column in block.get("columns") or []:
            parts.append(str(column))
        for row in block.get("rows") or []:
            if isinstance(row, list):
                parts.extend(str(cell) for cell in row)
        for item in block.get("items") or []:
            parts.append(json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item))
    return " ".join(parts).lower()


def _table_columns(payload: dict[str, Any]) -> list[str]:
    columns: list[str] = []
    for block in payload.get("response_blocks") or []:
        if isinstance(block, dict) and str(block.get("type") or "").lower() in {"table", "comparison_table"}:
            columns.extend(str(col).lower() for col in (block.get("columns") or []))
    return columns


def _has_columns(payload: dict[str, Any], *groups: tuple[str, ...]) -> bool:
    merged = " ".join(_table_columns(payload))
    return all(any(token in merged for token in group) for group in groups)


def _manual_semantic_failure(case: AuditCase, *, payload: dict[str, Any], metadata: dict[str, Any]) -> tuple[str, str] | None:
    expected_op = _expected_sql_operation(case)
    actual_op = _extract_sql_operation(metadata)
    if expected_op and "SQLAnalyticsAgent" in case.expected_tool_agent and expected_op != actual_op:
        return "WRONG_RESPONSE_SHAPE", f"expected sql_operation {expected_op}, got {actual_op or 'none'}"

    warnings = [str(item) for item in (payload.get("warnings") or [])]
    text = _block_text(payload)
    if "signal ml unknown" in text or "ml unknown" in text:
        return "WRONG_RESPONSE_SHAPE", "irrelevant ML UNKNOWN block/text present"
    if any("avertissement de fiabilité" in item.lower() or "informations partielles ou insuffisantes" in item.lower() for item in warnings):
        statuses = _extract_evidence_statuses(metadata)
        if "HAS_EVIDENCE" in set(statuses.values()) or "PROVEN_NO_DATA" in set(statuses.values()):
            return "WARNING_NOISE", "generic reliability warning despite valid/proven evidence"

    shape = str(case.expected_response_shape)
    if shape.endswith("stock_by_grade") and not _has_columns(payload, ("produit", "product"), ("grade", "qualité", "qualite"), ("disponible", "restant", "available")):
        return "WRONG_RESPONSE_SHAPE", "stock by product/grade table missing required columns"
    if shape.endswith("stock_movements") and not _has_columns(payload, ("type", "nature", "mouvement"), ("produit", "product"), ("quantité", "quantity", "kg"), ("source", "origine")):
        return "WRONG_RESPONSE_SHAPE", "stock movement table missing type/product/quantity/source"
    if shape.endswith("collected_by_product") and not _has_columns(payload, ("produit", "product"), ("total", "quantité", "quantity", "kg")):
        return "WRONG_RESPONSE_SHAPE", "collection summary missing product + total quantity"
    if shape.endswith("collecte_traceability") and not _has_columns(payload, ("bl", "livraison", "delivery"), ("justificatif", "preuve", "proof"), ("lot", "batch")):
        return "WRONG_RESPONSE_SHAPE", "collecte traceability missing BL/proof/lot columns"
    if shape.endswith("active_producers") and not _has_columns(payload, ("producteur", "membre", "farmer"), ("parcelle", "produit", "product")):
        return "WRONG_RESPONSE_SHAPE", "active producer table missing producer and parcel/product"
    if shape.endswith("delivered_quantity") and ("avance" in text or "amount_fcfa" in text) and "livr" not in text:
        return "SUMMARY_SELECTION_ERROR", "top delivered producer appears to use advances instead of deliveries"
    if shape.endswith("postharvest_lots") and "stock disponible de la coopérative" in text:
        return "SUMMARY_SELECTION_ERROR", "post-harvest lot summary drifted to stock summary"
    if shape.endswith("kg_loss") and not _has_columns(payload, ("lot", "batch"), ("perte", "écart", "gap", "kg")):
        return "WRONG_RESPONSE_SHAPE", "kg loss ranking missing lot + kg loss/gap"
    if shape.endswith("stage_loss") and not (_has_columns(payload, ("étape", "etape", "stage"), ("perte", "loss", "kg", "%")) or "étape" in text or "etape" in text):
        return "SUMMARY_SELECTION_ERROR", "stage-loss answer does not identify the stage"
    if shape.endswith("orders_by_status") and not _has_columns(payload, ("statut", "status"), ("commande", "order", "nombre", "total")):
        return "WRONG_RESPONSE_SHAPE", "commercial orders by status missing status breakdown"
    if shape.endswith("invoices_by_payment_status") and not _has_columns(payload, ("statut", "status", "paiement", "payment"), ("facture", "invoice", "nombre", "total")):
        return "WRONG_RESPONSE_SHAPE", "invoices by payment status missing status breakdown"
    if shape.endswith("treasury_without_proof") and "justificatif" not in text:
        return "WRONG_RESPONSE_SHAPE", "treasury proof answer missing justificatif dimension"
    if shape.endswith("stock_total_available_reserved") and not (
        _has_columns(payload, ("produit", "product"), ("total",), ("disponible", "available", "restant")) and ("réserv" in text or "reserv" in text or "non disponible" in text)
    ):
        return "WRONG_RESPONSE_SHAPE", "stock total/available/reserved distinction missing or unclear"
    if shape.endswith("top_collected_product") and not ("produit" in text and ("collect" in text and ("kg" in text or "quantité" in text))):
        return "SUMMARY_SELECTION_ERROR", "top collected product summary missing product or total quantity"
    if shape.endswith("stage_loss_with_lots") and not _has_columns(payload, ("étape", "etape", "stage"), ("lot", "batch"), ("perte", "loss", "kg")):
        return "WRONG_RESPONSE_SHAPE", "stage loss with lots missing stage/lot/kg columns"
    if shape.endswith("paid_orders_without_invoice") and not ("pay" in text and ("facture" in text or "invoice" in text)):
        return "SUMMARY_SELECTION_ERROR", "paid orders without invoice not answered directly"
    if shape.endswith("treasury_missing_proof_or_receipt") and not ("justificatif" in text and ("reçu" in text or "recu" in text or "receipt" in text or "référence" in text or "reference" in text)):
        return "WRONG_RESPONSE_SHAPE", "treasury proof/receipt distinction missing"
    if shape.endswith("ml_signal_count") and "bilan matière" in text:
        return "SUMMARY_SELECTION_ERROR", "pure ML signal count polluted by material-balance answer"

    return None


def _detail_members_memory_failure(case: AuditCase, *, payload: dict[str, Any], metadata: dict[str, Any]) -> tuple[str, str] | None:
    text = _block_text(payload)
    shape = str(case.expected_response_shape or "")

    if shape.endswith("low_stock"):
        sql_op = _extract_sql_operation(metadata) or ""
        if sql_op != "get_low_stock_alerts":
            return "SQL_OPERATION_MISSING", f"low-stock intent expected get_low_stock_alerts, got {sql_op or 'none'}"
    if shape.endswith("stock_movements_detail") and not _has_columns(payload, ("type", "nature", "mouvement"), ("produit", "product"), ("quantité", "quantity", "kg"), ("source", "origine"), ("date",)):
        return "WRONG_RESPONSE_SHAPE", "stock movement detail missing required grouped fields"
    if shape.endswith("orders_status_grouped") and not _has_columns(payload, ("statut", "status"), ("nombre", "count"), ("montant", "total")):
        return "WRONG_RESPONSE_SHAPE", "orders grouped-by-status table missing statut/nombre/montant total"
    if shape.endswith("invoices_status_grouped") and not _has_columns(payload, ("statut", "status", "paiement"), ("nombre", "count"), ("montant", "total")):
        return "WRONG_RESPONSE_SHAPE", "invoices grouped-by-status table missing statut/nombre/montant total"
    if shape.endswith("single_top_status"):
        answer_low = str(payload.get("answer") or "").lower()
        if "statut dominant" not in answer_low and "catégorie dominante" not in answer_low and "categorie dominante" not in answer_low:
            return "WRONG_RESPONSE_SHAPE", "single-item request did not return dominant status summary"
    if shape.endswith("top_n_1") and _extract_evidence_row_count(payload, metadata) > 1:
        return "WRONG_RESPONSE_SHAPE", "top 1 request returned more than one row"
    if shape.endswith("producer_efficiency_limit") and ("efficacit" in text and "n’est pas calculable de manière fiable" not in text and "pas calculable de maniere fiable" not in text):
        return "SUMMARY_SELECTION_ERROR", "producer efficiency was asserted without explicit reliability limitation"
    return None


def _response_quality_failure(case: AuditCase, *, payload: dict[str, Any], metadata: dict[str, Any]) -> tuple[str, str] | None:
    answer = str(payload.get("answer") or "")
    answer_low = answer.lower()
    route = _upper(payload.get("route"))
    warnings = [str(w) for w in (payload.get("warnings") or [])]
    statuses = _extract_evidence_statuses(metadata)

    if any(bad in answer_low for bad in ("l’l", "l'l", "l’ l", "l' l")):
        return "COMPOSITION_QUALITY", "awkward apostrophe wording detected"

    # Deterministic clarification must remain exact.
    if case.expected_response_shape == "rq_memory_clarify":
        if "de quel lot parlez-vous ? indiquez une référence comme lot-milx-001." not in answer_low:
            return "MEMORY_CONTEXT_ERROR", "clarification sentence is not deterministic/exact"

    # Direct answer should appear first.
    first_content_line = ""
    for ln in answer.splitlines():
        t = ln.strip()
        if not t:
            continue
        if t.lower().startswith(("1. réponse directe", "1. donnees mesurees", "1. données mesurées", "résumé")):
            continue
        first_content_line = t.lower()
        break
    if not first_content_line:
        return "COMPOSITION_QUALITY", "missing direct first answer sentence"

    if case.expected_response_shape in {"rq_simple_sql", "rq_no_data_or_fact", "rq_ml_fact"}:
        if not any(token in first_content_line for token in ("aucun", "aucune", "disponible", "kg", "fcfa", "stock", "facture", "signal", "transactions", "commande", "trésorerie", "tresorerie", "preuve opérationnelle")):
            return "COMPOSITION_QUALITY", "first sentence not directly answering factual question"

    if case.expected_response_shape in {"rq_grouped_status", "rq_grouped_single"}:
        table_titles = [str((b or {}).get("title") or "").lower() for b in (payload.get("response_blocks") or []) if isinstance(b, dict) and str((b or {}).get("type") or "").lower() in {"table", "comparison_table"}]
        if not any("statut" in title for title in table_titles):
            return "WRONG_RESPONSE_SHAPE", "grouped status table title missing statut"
        if case.expected_response_shape == "rq_grouped_single" and "statut dominant" not in answer_low:
            return "COMPOSITION_QUALITY", "grouped single request missing dominant-status summary"

    if case.expected_response_shape in {"rq_reco_single", "rq_reco_topn"}:
        reco_blocks = [b for b in (payload.get("response_blocks") or []) if isinstance(b, dict) and str((b or {}).get("type") or "").lower() in {"recommendations", "recommendation_cards"}]
        if not reco_blocks:
            return "RECOMMENDATION_NOT_GROUNDED", "missing recommendation block"
        items = reco_blocks[0].get("items") or []
        if case.expected_response_shape == "rq_reco_single" and len(items) != 1:
            return "WRONG_RESPONSE_SHAPE", "single-action request did not return exactly one action"
        if case.expected_response_shape == "rq_reco_topn" and len(items) > 3:
            return "WRONG_RESPONSE_SHAPE", "top-3 request returned more than three actions"
        for item in items:
            if not str(item.get("action") or "").strip() or not str(item.get("reason") or "").strip():
                return "COMPOSITION_QUALITY", "recommendation action/reason missing"
            refs = item.get("evidence_refs")
            if not isinstance(refs, list) or not refs:
                return "RECOMMENDATION_NOT_GROUNDED", "recommendation proof missing"

    if route == "SQL_ONLY" and "ml unknown" in answer_low:
        return "COMPOSITION_QUALITY", "irrelevant ML UNKNOWN text in SQL-only answer"

    generic_warning = "avertissement de fiabilité: informations partielles ou insuffisantes pour cette requête."
    if any(generic_warning in str(w).lower() for w in warnings):
        if str(_extract_sql_operation(metadata) or "") == "get_low_stock_alerts" and statuses.get("sql") == "PROVEN_NO_DATA":
            return None
        if "HAS_EVIDENCE" in set(statuses.values()) or "PROVEN_NO_DATA" in set(statuses.values()):
            return "WARNING_NOISE", "generic warning present despite clean evidence"

    if "LLM_CHANGED_NUMBERS" in warnings or "LLM_DROPPED_LIMITATION" in warnings:
        return "COMPOSITION_QUALITY", "unresolved llm validation warning in final payload"

    return None


def _latency_class(total_ms: float) -> str:
    if total_ms < 2000:
        return "FAST"
    if total_ms < 6000:
        return "ACCEPTABLE"
    if total_ms < 10000:
        return "SLOW"
    return "CRITICAL"


def _extract_timing_components(metadata: dict[str, Any], elapsed_ms: float) -> dict[str, float]:
    durations = metadata.get("durations_ms") or {}
    timing_ms = metadata.get("timing_ms") or {}
    sql_ms = _safe_num(durations.get("sql_duration_ms"))
    rag_ms = _safe_num(durations.get("rag_duration_ms"))
    ml_ms = _safe_num(durations.get("ml_duration_ms"))
    llm_ms = _safe_num(durations.get("llm_duration_ms"), _safe_num((metadata.get("llm_metadata") or {}).get("llm_duration_ms")))
    compose_ms = _safe_num(durations.get("composition_duration_ms"), _safe_num(timing_ms.get("compose_answer")))
    total_ms = _safe_num(durations.get("total_duration_ms"), _safe_num(metadata.get("total_duration_ms"), elapsed_ms))
    if total_ms <= 0:
        total_ms = elapsed_ms
    return {
        "total_ms": round(total_ms, 2),
        "sql_ms": round(sql_ms, 2),
        "rag_ms": round(rag_ms, 2),
        "ml_ms": round(ml_ms, 2),
        "llm_ms": round(llm_ms, 2),
        "composition_ms": round(compose_ms, 2),
    }


def _latency_failure(case: AuditCase, *, payload: dict[str, Any], metadata: dict[str, Any], elapsed_ms: float) -> tuple[str, str, str] | None:
    route = _upper(payload.get("route"))
    agents = {str(a) for a in (payload.get("agents_used") or [])}
    timings = _extract_timing_components(metadata, elapsed_ms)
    warnings = {str(w).upper() for w in (payload.get("warnings") or [])}
    if route == "SQL_ONLY":
        if "RAGKnowledgeAgent" in agents:
            return "FAIL", "LATENCY_SLOW_PATH", "SQL_ONLY invoked RAGKnowledgeAgent unnecessarily"
        if "MLLossAgent" in agents:
            return "FAIL", "LATENCY_SLOW_PATH", "SQL_ONLY invoked MLLossAgent unnecessarily"
        if case.expected_response_shape.startswith("latency_sql") and timings["llm_ms"] > 200:
            return "PARTIAL", "LATENCY_SLOW_PATH", f"LLM not skipped on SQL fast-path (llm_ms={timings['llm_ms']})"
    if "LLM_CHANGED_NUMBERS" in warnings or "LLM_DROPPED_LIMITATION" in warnings:
        return "FAIL", "LATENCY_SLOW_PATH", "unresolved llm validation warning in final payload"
    return None


def _classify(case: AuditCase, *, payload: dict[str, Any], status_code: int, latency_ms: float, metadata: dict[str, Any], memory_probe: bool = False) -> tuple[str, str, str]:
    """return status, failure_category, reason"""
    if status_code != 200 or latency_ms > 45000:
        return "FAIL", "LATENCY_OR_PROVIDER_ERROR", "Request timeout/error"

    route = _upper(payload.get("route"))
    intent = _upper(_extract_intent_family(metadata))
    expected_route = _upper(case.expected_route)
    expected_intent = _upper(case.expected_intent_family)

    if route != expected_route:
        return "FAIL", "ROUTING_ERROR", f"expected route {expected_route}, got {route}"

    if expected_intent and expected_intent not in {"FACTUAL_SQL", "ACTION_RECOMMENDATION"}:
        if intent and intent != expected_intent:
            return "FAIL", "INTENT_MISMATCH", f"expected intent {expected_intent}, got {intent}"

    if case.qid.startswith("MR"):
        semantic_failure = _manual_semantic_failure(case, payload=payload, metadata=metadata)
        if semantic_failure:
            failure, reason = semantic_failure
            return "FAIL", failure, reason

    sql_op = _extract_sql_operation(metadata)
    if "SQLAnalyticsAgent" in case.expected_tool_agent and sql_op is None and case.qid not in {"MEM1"}:
        # strict only for SQL/hybrid operational questions
        if expected_route in {"SQL_ONLY", "HYBRID_SQL_RAG", "HYBRID_SQL_ML", "HYBRID_FULL"}:
            return "FAIL", "SQL_OPERATION_MISSING", "no sql_dispatch_trace.sql_operation"

    evidence_types = _evidence_types(payload)
    evidence_rows = _extract_evidence_row_count(payload, metadata)
    evidence_status = _extract_evidence_statuses(metadata)
    proven_no_data = "PROVEN_NO_DATA" in {evidence_status.get("sql"), evidence_status.get("ml"), evidence_status.get("rag")}
    if route == "SQL_ONLY" and "ML" in evidence_types:
        return "FAIL", "SOURCE_POLLUTION", "SQL_ONLY answer contains ML source although ML was not materially used"

    if expected_route == "RAG_ONLY" and "RAG" not in evidence_types:
        return "FAIL", "RAG_WEAK_OR_MISSING", "RAG route without RAG evidence source"

    if expected_route in {"ML_ONLY", "HYBRID_SQL_ML", "HYBRID_FULL"} and case.module_group == "ml" and "ML" not in evidence_types:
        return "FAIL", "ML_SIGNAL_UNAVAILABLE", "ML expected but missing"

    if case.module_group == "recommendations":
        if not _recommendation_grounded(payload, metadata):
            return "FAIL", "RECOMMENDATION_NOT_GROUNDED", "recommendation missing evidence_refs"

    if _contains_raw_rag_leak(payload.get("answer") or ""):
        return "FAIL", "EVIDENCE_INSUFFICIENT", "raw RAG/source leakage in answer"

    if str(sql_op or "").startswith("producer_efficiency_unsupported"):
        return "PASS", "NO_FAILURE", "clean unsupported producer efficiency limitation"

    shape = _response_shape(payload.get("response_blocks") or [], payload.get("answer") or "")
    expected_shape = case.expected_response_shape

    # shape mismatch
    if expected_shape in {"ranking", "comparison_table", "recommendation_cards", "table", "best_practices", "sequence_reset"}:
        ok = True
        if expected_shape == "recommendation_cards":
            ok = shape == "recommendation_cards"
        elif expected_shape == "comparison_table":
            ok = shape in {"table", "chart"}
        elif expected_shape == "ranking":
            ok = shape in {"table", "summary"}
        elif expected_shape == "best_practices":
            ok = shape in {"best_practices", "summary"}
        elif expected_shape == "sequence_reset":
            ok = memory_probe
        elif expected_shape == "table":
            ok = shape in {"table", "summary"}
        if not ok:
            return "FAIL", "WRONG_RESPONSE_SHAPE", f"expected shape {expected_shape}, got {shape}"

    # canonical consistency heuristic for lot/material queries
    if case.module_group in {"lots", "dashboard"} and any(t in case.question.lower() for t in ("perte", "efficacité", "écart", "kg")):
        answer = str(payload.get("answer") or "").lower()
        if "bilan matière global" in answer and "compare" in case.question.lower():
            return "PARTIAL", "SUMMARY_SELECTION_ERROR", "generic summary instead of explicit comparison"

    # warning noise
    warnings = payload.get("warnings") or []
    if _too_noisy_warnings(warnings) and not proven_no_data:
        return "PARTIAL", "WARNING_NOISE", "too many warnings for valid answer"

    # weak evidence
    if evidence_rows == 0 and expected_route != "RAG_ONLY":
        if proven_no_data:
            answer_text = str(payload.get("answer") or "").lower()
            if case.module_group == "invoices" and not (
                "aucune facture pay" in answer_text
                or "aucune facture regl" in answer_text
                or "aucune facture régl" in answer_text
            ):
                return "PARTIAL", "SUMMARY_SELECTION_ERROR", "proven no-data but invoice no-data sentence is unclear"
            if case.module_group == "ml" and "aucun signal ml élevé" not in answer_text and "aucun signal ml eleve" not in answer_text:
                return "PARTIAL", "SUMMARY_SELECTION_ERROR", "proven no-data but ML no-data sentence is unclear"
            return "PASS", "NO_FAILURE", "proven no-data"
        return "PARTIAL", "EVIDENCE_INSUFFICIENT", "no evidence rows"

    return "PASS", "NO_FAILURE", "ok"


def _run_one(client: TestClient, headers: dict[str, str], question: str, conversation_id: str | None = None) -> tuple[int, dict[str, Any], float]:
    payload: dict[str, Any] = {"message": question, "language": "fr"}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    t0 = time.perf_counter()
    resp = client.post("/chat/agent", headers=headers, json=payload, timeout=60)
    elapsed = (time.perf_counter() - t0) * 1000.0
    try:
        body = resp.json() if resp.status_code == 200 else {"error": resp.text}
    except Exception:
        body = {"error": resp.text}
    return resp.status_code, body, elapsed


def run_audit(*, mode: str = "baseline") -> dict[str, Any]:
    os.environ["AI_AUDIT_DEBUG"] = "1"
    mode_normalized = str(mode or "baseline").strip().lower()
    if mode_normalized not in {"baseline", "fresh", "manual-regression", "detail-members-memory", "response-quality", "latency"}:
        raise ValueError(f"Unsupported audit mode: {mode}")
    if mode_normalized == "fresh":
        cases = build_fresh_cases()
    elif mode_normalized == "manual-regression":
        cases = build_manual_regression_cases()
    elif mode_normalized == "detail-members-memory":
        cases = build_detail_members_memory_cases()
    elif mode_normalized == "response-quality":
        cases = build_response_quality_cases()
    elif mode_normalized == "latency":
        cases = build_latency_cases()
    else:
        cases = build_cases()
    total_cases = len(cases)

    # Persist cases for reproducibility
    suffix = "_fresh" if mode_normalized == "fresh" else ("_manual_regression" if mode_normalized == "manual-regression" else ("_detail_members_memory" if mode_normalized == "detail-members-memory" else ("_response_quality" if mode_normalized == "response-quality" else ("_latency" if mode_normalized == "latency" else ""))))
    cases_path = ROOT / "reports" / "chatbot" / f"whole_app_runtime_audit_cases{suffix}.json"
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.write_text(json.dumps([asdict(c) for c in cases], ensure_ascii=False, indent=2), encoding="utf-8")

    results: list[dict[str, Any]] = []

    with TestClient(app) as client:
        login = client.post("/auth/login", json={"email": "manager@weefarm.local", "password": "Manager123!"})
        if login.status_code != 200:
            raise RuntimeError(f"Login failed: {login.status_code} {login.text}")
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        memory_conversation_id: str | None = None

        for idx, case in enumerate(cases, start=1):
            if not case.expected_response_shape.startswith("sequence_"):
                status_code, body, elapsed_ms = _run_one(client, headers, case.question)
                metadata = body.get("metadata") or {}
                status, failure, reason = _classify(case, payload=body, status_code=status_code, latency_ms=elapsed_ms, metadata=metadata)
                if status == "PASS" and case.qid.startswith("DM"):
                    semantic_failure = _detail_members_memory_failure(case, payload=body, metadata=metadata)
                    if semantic_failure:
                        failure, reason = semantic_failure
                        status = "FAIL"
                if status == "PASS" and case.qid.startswith("RQ"):
                    quality_failure = _response_quality_failure(case, payload=body, metadata=metadata)
                    if quality_failure:
                        failure, reason = quality_failure
                        status = "FAIL"
                if status == "PASS" and mode_normalized == "latency":
                    latency_failure = _latency_failure(case, payload=body, metadata=metadata, elapsed_ms=elapsed_ms)
                    if latency_failure:
                        status, failure, reason = latency_failure
                timings = _extract_timing_components(metadata, elapsed_ms)

                result = {
                    "qid": case.qid,
                    "module_group": case.module_group,
                    "question": case.question,
                    "expected_module": case.expected_module,
                    "expected_route": case.expected_route,
                    "expected_intent_family": case.expected_intent_family,
                    "expected_tool_agent": case.expected_tool_agent,
                    "expected_evidence_source": case.expected_evidence_source,
                    "expected_response_shape": case.expected_response_shape,
                    "actual_route": body.get("route"),
                    "actual_intent_family": _extract_intent_family(metadata),
                    "actual_sql_operation_tool": _extract_sql_operation(metadata),
                    "evidence_status_sql": _extract_evidence_statuses(metadata).get("sql"),
                    "evidence_status_ml": _extract_evidence_statuses(metadata).get("ml"),
                    "evidence_status_rag": _extract_evidence_statuses(metadata).get("rag"),
                    "agents_called": body.get("agents_used") or [],
                    "evidence_row_count": _extract_evidence_row_count(body, metadata),
                    "response_blocks": [str((b or {}).get("type") or "") for b in (body.get("response_blocks") or []) if isinstance(b, dict)],
                    "warnings": body.get("warnings") or [],
                    "confidence": _safe_num(body.get("confidence"), 0.0),
                    "final_answer_text": str(body.get("answer") or ""),
                    "latency_ms": round(elapsed_ms, 2),
                    "timings": timings,
                    "latency_classification": _latency_class(float(timings.get("total_ms") or elapsed_ms)),
                    "status": status,
                    "failure_category": failure,
                    "reason": reason,
                }
                results.append(result)
                print(f"[{idx:02d}/{total_cases}] {case.qid} {status} {failure} route={result['actual_route']} latency={result['latency_ms']}ms", flush=True)
                continue

            # Memory/reset sequence (scored as one row)
            if case.qid == "DM22":
                q1, q2, q3 = "Quel lot a la perte la plus élevée ?", "Donne les recommandations disponibles pour ce lot sans inventer.", ""
            elif case.qid == "DM23":
                q1, q2, q3 = "Quel producteur a livré le plus grand volume ?", "Donne le détail pour ce producteur.", ""
            elif case.qid == "DM24":
                q1, q2, q3 = "Montre le stock de mangue.", "Affiche les mouvements pour ce produit.", ""
            elif case.qid == "DM25":
                q1, q2, q3 = "Classe les lots par perte.", "Donne le détail du premier.", ""
            elif case.qid == "DM26":
                q1, q2, q3 = "Quel lot a la perte la plus élevée ?", "Oublie ce lot.", "Donne les recommandations disponibles pour ce lot sans inventer."
            elif case.qid == "DM27":
                q1, q2, q3 = "Quel lot a la perte la plus élevée ?", "Change de sujet.", "Montre le stock mangue."
            elif case.qid == "DM28":
                q1, q2, q3 = "Quel lot a la perte la plus élevée ?", "Oublie ce lot. Et celui-ci, quelle est sa perte ?", ""
            elif case.qid == "DM29":
                q1, q2, q3 = "Quel lot a la perte la plus élevée ?", "Parlons du stock.", "Ce lot ?"
            elif case.qid == "DM30":
                q1, q2, q3 = "Montre le stock mangue.", "Ce lot ?", ""
            elif case.qid == "DM31":
                q1, q2, q3 = "Quel producteur a livré le plus grand volume ?", "Ce lot ?", ""
            elif case.qid == "RQ22":
                q1, q2, q3 = "Quel lot a la perte la plus élevée ?", "Oublie ce lot. Et celui-ci, quelle est sa perte ?", ""
            elif case.qid == "RQ23":
                q1, q2, q3 = "Quel lot a la perte la plus élevée ?", "Oublie ce lot.", "Donne les recommandations disponibles pour ce lot sans inventer."
            elif case.qid == "LT22":
                q1, q2, q3 = "Quel lot a la perte la plus élevée ?", "Donne les recommandations disponibles pour ce lot sans inventer.", ""
            elif case.qid == "LT23":
                q1, q2, q3 = "Quel lot a la perte la plus élevée ?", "Oublie ce lot.", "Donne les recommandations disponibles pour ce lot sans inventer."
            elif case.qid.startswith("F"):
                q1 = "Quel est le lot le plus critique actuellement ?"
                q2 = "Quelles actions concrètes pour ce lot ?"
                q3 = "Oublie ce lot maintenant et affiche uniquement le stock mangue."
            else:
                q1 = "Quel lot a la perte la plus élevée ?"
                q2 = "Quelles actions pour ce lot ?"
                q3 = "Maintenant oublie ce lot et montre seulement le stock de mangue."
            st1, b1, t1 = _run_one(client, headers, q1)
            m1 = b1.get("metadata") or {}
            memory_conversation_id = (m1.get("conversation_id") or memory_conversation_id)
            st2, b2, t2 = _run_one(client, headers, q2, conversation_id=memory_conversation_id)
            m2 = b2.get("metadata") or {}
            memory_conversation_id = (m2.get("conversation_id") or memory_conversation_id)
            if q3:
                st3, b3, t3 = _run_one(client, headers, q3, conversation_id=memory_conversation_id)
                m3 = b3.get("metadata") or {}
            else:
                st3, b3, t3, m3 = st2, b2, 0.0, (b2.get("metadata") or {})

            route2 = _upper(b2.get("route"))
            intent2 = _upper(_extract_intent_family(m2))
            route3 = _upper(b3.get("route"))
            intent3 = _upper(_extract_intent_family(m3))
            if case.qid in {"DM22", "LT22"}:
                mem_ok = st2 == 200 and route2 == "HYBRID_FULL" and intent2 in {"LOT_SPECIFIC_RECOMMENDATION", "RECOMMENDATION", "FOLLOW_UP"}
            elif case.qid in {"DM23", "DM24", "DM25"}:
                mem_ok = st2 == 200 and route2 in {"SQL_ONLY", "HYBRID_FULL"}
            elif case.qid in {"DM26", "LT23"}:
                mem_ok = st3 == 200 and ("de quel lot" in str(b3.get("answer") or "").lower())
            elif case.qid == "DM27":
                mem_ok = st3 == 200 and route3 == "SQL_ONLY" and intent3 == "STOCK_CURRENT"
            elif case.qid in {"DM28", "DM29", "DM30", "DM31", "RQ22"}:
                answer_l = str(b3.get("answer") or "").lower()
                mem_ok = st3 == 200 and ("de quel lot" in answer_l or "précisez" in answer_l or "precisez" in answer_l or "préciser" in answer_l or "preciser" in answer_l)
            elif case.qid == "RQ23":
                mem_ok = st3 == 200 and ("de quel lot" in str(b3.get("answer") or "").lower())
            else:
                mem_ok = (st3 == 200 and route3 == "SQL_ONLY" and intent3 == "STOCK_CURRENT")

            status = "PASS" if mem_ok else "FAIL"
            failure = "NO_FAILURE" if mem_ok else "MEMORY_CONTEXT_ERROR"
            reason = "memory reset honored" if mem_ok else f"reset ignored: route={route3} intent={intent3}"

            result = {
                "qid": case.qid,
                "module_group": case.module_group,
                "question": case.question,
                "expected_module": case.expected_module,
                "expected_route": case.expected_route,
                "expected_intent_family": case.expected_intent_family,
                "expected_tool_agent": case.expected_tool_agent,
                "expected_evidence_source": case.expected_evidence_source,
                "expected_response_shape": case.expected_response_shape,
                "actual_route": b3.get("route"),
                "actual_intent_family": _extract_intent_family(m3),
                "actual_sql_operation_tool": _extract_sql_operation(m3),
                "evidence_status_sql": _extract_evidence_statuses(m3).get("sql"),
                "evidence_status_ml": _extract_evidence_statuses(m3).get("ml"),
                "evidence_status_rag": _extract_evidence_statuses(m3).get("rag"),
                "agents_called": b3.get("agents_used") or [],
                "evidence_row_count": _extract_evidence_row_count(b3, m3),
                "response_blocks": [str((b or {}).get("type") or "") for b in (b3.get("response_blocks") or []) if isinstance(b, dict)],
                "warnings": b3.get("warnings") or [],
                "confidence": _safe_num(b3.get("confidence"), 0.0),
                "final_answer_text": str(b3.get("answer") or ""),
                "latency_ms": round(t1 + t2 + t3, 2),
                "timings": {
                    "total_ms": round(t1 + t2 + t3, 2),
                    "sql_ms": 0.0,
                    "rag_ms": 0.0,
                    "ml_ms": 0.0,
                    "llm_ms": 0.0,
                    "composition_ms": 0.0,
                },
                "latency_classification": _latency_class(round(t1 + t2 + t3, 2)),
                "status": status,
                "failure_category": failure,
                "reason": reason,
                "sequence_details": {
                    "step1": {"status": st1, "route": b1.get("route"), "intent": _extract_intent_family(m1)},
                    "step2": {"status": st2, "route": b2.get("route"), "intent": _extract_intent_family(m2)},
                    "step3": {"status": st3, "route": b3.get("route"), "intent": _extract_intent_family(m3)},
                },
            }
            results.append(result)
            print(f"[{idx:02d}/{total_cases}] {case.qid} {status} {failure} route={result['actual_route']} latency={result['latency_ms']}ms", flush=True)

    pass_count = sum(1 for r in results if r["status"] == "PASS")
    partial_count = sum(1 for r in results if r["status"] == "PARTIAL")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")

    module_scores: dict[str, dict[str, int]] = defaultdict(lambda: {"PASS": 0, "PARTIAL": 0, "FAIL": 0})
    for r in results:
        module_scores[r["module_group"]][r["status"]] += 1

    failure_counts = Counter(r["failure_category"] for r in results)

    p0_failures = [
        r for r in results
        if r["status"] == "FAIL" and r["failure_category"] in {
            "ROUTING_ERROR", "INTENT_MISMATCH", "SQL_OPERATION_MISSING", "DATA_SOURCE_NOT_COVERED",
            "RECOMMENDATION_NOT_GROUNDED", "MEMORY_CONTEXT_ERROR", "RAG_WEAK_OR_MISSING",
            "ML_SIGNAL_UNAVAILABLE", "CANONICAL_METRIC_INCONSISTENCY", "LATENCY_OR_PROVIDER_ERROR",
        }
    ]
    p0_failures = sorted(p0_failures, key=lambda x: (-float(x.get("latency_ms") or 0.0), x["qid"]))[:10]

    latency_values = [float((r.get("timings") or {}).get("total_ms") or r.get("latency_ms") or 0.0) for r in results]
    latency_sorted = sorted(latency_values)
    p50 = latency_sorted[int(0.50 * (len(latency_sorted) - 1))] if latency_sorted else 0.0
    p90 = latency_sorted[int(0.90 * (len(latency_sorted) - 1))] if latency_sorted else 0.0
    p95 = latency_sorted[int(0.95 * (len(latency_sorted) - 1))] if latency_sorted else 0.0
    route_latency: dict[str, list[float]] = defaultdict(list)
    for r in results:
        route_latency[str(r.get("actual_route") or "")].append(float((r.get("timings") or {}).get("total_ms") or r.get("latency_ms") or 0.0))
    route_latency_avg = {k: round(sum(v) / max(len(v), 1), 2) for k, v in route_latency.items()}

    report = {
        "audit_name": "chatbot_whole_app_runtime_audit_fresh" if mode_normalized == "fresh" else ("chatbot_whole_app_runtime_audit_manual_regression" if mode_normalized == "manual-regression" else ("chatbot_whole_app_runtime_audit_detail_members_memory" if mode_normalized == "detail-members-memory" else ("chatbot_whole_app_runtime_audit_response_quality" if mode_normalized == "response-quality" else ("chatbot_whole_app_runtime_audit_latency" if mode_normalized == "latency" else "chatbot_whole_app_runtime_audit")))),
        "audit_mode": mode_normalized,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(results),
        "counts": {"PASS": pass_count, "PARTIAL": partial_count, "FAIL": fail_count},
        "score_by_module": module_scores,
        "score_by_failure_category": dict(failure_counts),
        "latency_summary": {
            "p50_total_ms": round(p50, 2),
            "p90_total_ms": round(p90, 2),
            "p95_total_ms": round(p95, 2),
            "min_total_ms": round(min(latency_values), 2) if latency_values else 0.0,
            "max_total_ms": round(max(latency_values), 2) if latency_values else 0.0,
            "route_avg_total_ms": route_latency_avg,
        },
        "top_10_p0_failures": p0_failures,
        "results": results,
        "files": {
            "cases": str(cases_path),
        },
    }

    out_dir = ROOT / "artifacts" / "evals"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_prefix = "chatbot_whole_app_runtime_audit_fresh" if mode_normalized == "fresh" else ("chatbot_whole_app_runtime_audit_manual_regression" if mode_normalized == "manual-regression" else ("chatbot_whole_app_runtime_audit_detail_members_memory" if mode_normalized == "detail-members-memory" else ("chatbot_whole_app_runtime_audit_response_quality" if mode_normalized == "response-quality" else ("chatbot_whole_app_runtime_audit_latency" if mode_normalized == "latency" else "chatbot_whole_app_runtime_audit"))))
    json_path = out_dir / f"{file_prefix}_{ts}.json"
    md_path = out_dir / f"{file_prefix}_{ts}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown report
    lines: list[str] = []
    title_suffix = " (Fresh Anti-Overfit)" if mode_normalized == "fresh" else (" (Manual Semantic Regression)" if mode_normalized == "manual-regression" else (" (Detail + Members + Memory)" if mode_normalized == "detail-members-memory" else (" (Response Quality)" if mode_normalized == "response-quality" else (" (Latency)" if mode_normalized == "latency" else ""))))
    lines.append(f"# Chatbot Whole-App Runtime Audit{title_suffix}")
    lines.append("")
    lines.append(f"- Generated at: `{report['generated_at']}`")
    lines.append(f"- Total cases: `{report['total_cases']}`")
    lines.append(f"- PASS/PARTIAL/FAIL: `{pass_count}/{partial_count}/{fail_count}`")
    lines.append("")
    lines.append("## Score by Module")
    lines.append("")
    lines.append("| Module | PASS | PARTIAL | FAIL |")
    lines.append("|---|---:|---:|---:|")
    for module in sorted(module_scores.keys()):
        s = module_scores[module]
        lines.append(f"| {module} | {s['PASS']} | {s['PARTIAL']} | {s['FAIL']} |")

    lines.append("")
    lines.append("## Score by Failure Category")
    lines.append("")
    lines.append("| Failure category | Count |")
    lines.append("|---|---:|")
    for k, v in sorted(failure_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {k} | {v} |")

    lines.append("")
    lines.append("## Top 10 P0 Failures")
    lines.append("")
    lines.append("| QID | Module | Category | Reason | Route | Intent |")
    lines.append("|---|---|---|---|---|---|")
    for r in p0_failures:
        reason = str(r.get("reason") or "").replace("|", "/")
        lines.append(
            f"| {r['qid']} | {r['module_group']} | {r['failure_category']} | {reason} | {r.get('actual_route') or ''} | {r.get('actual_intent_family') or ''} |"
        )

    lines.append("")
    lines.append("## Full Results")
    lines.append("")
    lines.append("| QID | Module | Status | Failure | Expected route | Actual route | Expected intent | Actual intent | SQL op | Evidence rows | Confidence |")
    lines.append("|---|---|---|---|---|---|---|---|---|---:|---:|")
    for r in results:
        lines.append(
            "| {qid} | {module} | {status} | {failure} | {er} | {ar} | {ei} | {ai} | {op} | {rows} | {conf:.2f} |".format(
                qid=r["qid"],
                module=r["module_group"],
                status=r["status"],
                failure=r["failure_category"],
                er=r["expected_route"],
                ar=r.get("actual_route") or "",
                ei=r["expected_intent_family"],
                ai=r.get("actual_intent_family") or "",
                op=r.get("actual_sql_operation_tool") or "",
                rows=int(r.get("evidence_row_count") or 0),
                conf=float(r.get("confidence") or 0.0),
            )
        )
    if mode_normalized == "latency":
        lines.append("")
        lines.append("## Latency Details")
        lines.append("")
        lines.append("| QID | Total ms | SQL ms | RAG ms | ML ms | LLM ms | Compose ms | Class |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
        for r in results:
            t = r.get("timings") or {}
            lines.append(
                f"| {r['qid']} | {float(t.get('total_ms') or 0.0):.2f} | {float(t.get('sql_ms') or 0.0):.2f} | {float(t.get('rag_ms') or 0.0):.2f} | {float(t.get('ml_ms') or 0.0):.2f} | {float(t.get('llm_ms') or 0.0):.2f} | {float(t.get('composition_ms') or 0.0):.2f} | {r.get('latency_classification') or ''} |"
            )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report["files"]["json_report"] = str(json_path)
    report["files"]["md_report"] = str(md_path)

    # persist updated file pointers
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run deterministic whole-app chatbot runtime audit.")
    parser.add_argument(
        "--mode",
        choices=["baseline", "fresh", "manual-regression", "detail-members-memory", "response-quality", "latency"],
        default="baseline",
        help="Audit set to execute: baseline (fixed 60), fresh (paraphrased anti-overfit set), manual-regression (strict semantic families), detail-members-memory, response-quality, or latency.",
    )
    args = parser.parse_args()
    r = run_audit(mode=args.mode)
    print(r["files"]["json_report"])
    print(r["files"]["md_report"])
    print(json.dumps(r["counts"], ensure_ascii=False))
