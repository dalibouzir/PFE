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


@dataclass
class AuditRunOptions:
    warmup: bool = False
    max_cases: int | None = None
    case_timeout: float = 60.0
    retry_transient: int = 0
    resume_from: str | None = None


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


def _pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def _round4(value: float) -> float:
    return round(float(value), 4)


def _intent_matches(expected_intent: str, actual_intent: str) -> bool:
    exp = _upper(expected_intent)
    act = _upper(actual_intent)
    if not exp:
        return True
    if exp == act:
        return True
    if exp in {"FACTUAL_SQL", "ACTION_RECOMMENDATION"}:
        return bool(act) and act not in {"OUT_OF_SCOPE", "UNSUPPORTED", "SMALL_TALK"}
    if exp == "RECOMMENDATION" and act in {"RECOMMENDATION", "LOT_SPECIFIC_RECOMMENDATION", "ACTION_RECOMMENDATION", "FOLLOW_UP"}:
        return True
    return False


def _is_sql_expected_case(row: dict[str, Any]) -> bool:
    expected_route = _upper(row.get("expected_route"))
    expected_tool = str(row.get("expected_tool_agent") or "")
    return (
        ("SQLANALYTICSAGENT" in expected_tool.upper())
        or expected_route in {"SQL_ONLY", "HYBRID_SQL_RAG", "HYBRID_SQL_ML", "HYBRID_FULL"}
    )


def _reliability_warning_present(row: dict[str, Any]) -> bool:
    warning_items = [str(x) for x in (row.get("warnings") or [])]
    text = " ".join(warning_items).lower()
    return "informations partielles ou insuffisantes" in text


def _llm_flag_count(rows: list[dict[str, Any]], code: str) -> int:
    code_u = _upper(code)
    c = 0
    for row in rows:
        for w in (row.get("warning_codes_upper") or []):
            if _upper(w) == code_u:
                c += 1
                break
    return c


def _status_is_no_data(row: dict[str, Any]) -> bool:
    return "PROVEN_NO_DATA" in {
        _upper(row.get("evidence_status_sql")),
        _upper(row.get("evidence_status_rag")),
        _upper(row.get("evidence_status_ml")),
    }


def _status_is_unsupported(row: dict[str, Any]) -> bool:
    if "UNSUPPORTED" in {
        _upper(row.get("evidence_status_sql")),
        _upper(row.get("evidence_status_rag")),
        _upper(row.get("evidence_status_ml")),
    }:
        return True
    op = str(row.get("actual_sql_operation_tool") or "")
    shape = str(row.get("expected_response_shape") or "")
    return op.startswith("UNSUPPORTED_") or op.startswith("producer_efficiency_unsupported") or "unsupported" in shape


def _source_pollution_case(row: dict[str, Any]) -> bool:
    route = _upper(row.get("actual_route"))
    sources = {_upper(s) for s in (row.get("source_types") or [])}
    if route == "SQL_ONLY" and "ML" in sources:
        return True
    if row.get("failure_category") == "SOURCE_POLLUTION":
        return True
    return False


def _status_expected_for_rows(row: dict[str, Any]) -> bool:
    route = _upper(row.get("actual_route"))
    sql_status = _upper(row.get("evidence_status_sql"))
    rag_status = _upper(row.get("evidence_status_rag"))
    ml_status = _upper(row.get("evidence_status_ml"))
    rows = int(row.get("evidence_row_count") or 0)

    if route == "SQL_ONLY":
        if rows > 0:
            return sql_status in {"HAS_EVIDENCE", "PARTIAL_EVIDENCE"}
        return sql_status in {"PROVEN_NO_DATA", "UNSUPPORTED", "TOOL_ERROR", "PARTIAL_EVIDENCE"}
    if route == "RAG_ONLY":
        return rag_status in {"HAS_EVIDENCE", "PARTIAL_EVIDENCE", "PROVEN_NO_DATA", "UNSUPPORTED", "TOOL_ERROR"}
    if route == "ML_ONLY":
        if rows > 0:
            return ml_status in {"HAS_EVIDENCE", "PARTIAL_EVIDENCE"}
        return ml_status in {"PROVEN_NO_DATA", "UNSUPPORTED", "TOOL_ERROR", "PARTIAL_EVIDENCE"}
    # Hybrid: at least one usable status among expected layers.
    statuses = {sql_status, rag_status, ml_status}
    return bool(statuses.intersection({"HAS_EVIDENCE", "PROVEN_NO_DATA", "PARTIAL_EVIDENCE", "UNSUPPORTED", "TOOL_ERROR"}))


def _value_from_timing(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        t = row.get("timings") or {}
        values.append(float(t.get(key) or 0.0))
    return values


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(q * (len(ordered) - 1))
    return float(ordered[idx])


def _score_band(value: float, *, good: float, acceptable: float, bad: float) -> float:
    # Lower is better (latency bands).
    if value <= good:
        return 100.0
    if value <= acceptable:
        span = max(acceptable - good, 1.0)
        return 100.0 - 15.0 * ((value - good) / span)  # 100 -> 85
    if value <= bad:
        span = max(bad - acceptable, 1.0)
        return 85.0 - 30.0 * ((value - acceptable) / span)  # 85 -> 55
    span = max(bad, 1.0)
    extra = min((value - bad) / span, 1.0)
    return max(25.0, 55.0 - 30.0 * extra)


def _build_metrics_evaluation_report(*, suite_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []
    suite_case_counts: dict[str, int] = {}
    for suite_name, suite in suite_reports.items():
        rows = list(suite.get("results") or [])
        suite_case_counts[suite_name] = len(rows)
        for r in rows:
            row = dict(r)
            row["suite"] = suite_name
            all_rows.append(row)

    total_cases = len(all_rows)
    sql_expected_rows = [r for r in all_rows if _is_sql_expected_case(r)]
    sql_op_expected_rows = [r for r in all_rows if _expected_sql_operation(AuditCase(
        qid=str(r.get("qid") or ""),
        module_group=str(r.get("module_group") or ""),
        question=str(r.get("question") or ""),
        expected_module=str(r.get("expected_module") or ""),
        expected_route=str(r.get("expected_route") or ""),
        expected_intent_family=str(r.get("expected_intent_family") or ""),
        expected_tool_agent=str(r.get("expected_tool_agent") or ""),
        expected_evidence_source=str(r.get("expected_evidence_source") or ""),
        expected_response_shape=str(r.get("expected_response_shape") or ""),
    ))]
    route_correct = sum(1 for r in all_rows if _upper(r.get("actual_route")) == _upper(r.get("expected_route")))
    intent_correct = sum(1 for r in all_rows if _intent_matches(str(r.get("expected_intent_family") or ""), str(r.get("actual_intent_family") or "")))
    sql_op_correct = 0
    for r in sql_op_expected_rows:
        expected_op = _expected_sql_operation(
            AuditCase(
                qid=str(r.get("qid") or ""),
                module_group=str(r.get("module_group") or ""),
                question=str(r.get("question") or ""),
                expected_module=str(r.get("expected_module") or ""),
                expected_route=str(r.get("expected_route") or ""),
                expected_intent_family=str(r.get("expected_intent_family") or ""),
                expected_tool_agent=str(r.get("expected_tool_agent") or ""),
                expected_evidence_source=str(r.get("expected_evidence_source") or ""),
                expected_response_shape=str(r.get("expected_response_shape") or ""),
            )
        )
        if expected_op and str(r.get("actual_sql_operation_tool") or "") == expected_op:
            sql_op_correct += 1

    sql_operation_missing_count = sum(
        1 for r in sql_expected_rows if not str(r.get("actual_sql_operation_tool") or "").strip()
    ) + sum(1 for r in all_rows if str(r.get("failure_category") or "") == "SQL_OPERATION_MISSING")
    routing_error_count = sum(1 for r in all_rows if str(r.get("failure_category") or "") == "ROUTING_ERROR")
    intent_mismatch_count = sum(1 for r in all_rows if str(r.get("failure_category") or "") == "INTENT_MISMATCH")

    unnecessary_calls = 0
    for r in all_rows:
        route = _upper(r.get("actual_route"))
        agents = {_upper(a) for a in (r.get("agents_called") or [])}
        if route == "SQL_ONLY" and ("RAGKNOWLEDGEAGENT" in agents or "MLLOSSAGENT" in agents or "RECOMMENDATIONAGENT" in agents):
            unnecessary_calls += 1
        if route == "RAG_ONLY" and ("MLLOSSAGENT" in agents or "SQLANALYTICSAGENT" in agents):
            unnecessary_calls += 1
        if route == "ML_ONLY" and ("RAGKNOWLEDGEAGENT" in agents):
            unnecessary_calls += 1
    unnecessary_agent_call_rate = _pct(unnecessary_calls, total_cases)

    grounded_fail_categories = {
        "EVIDENCE_INSUFFICIENT",
        "RECOMMENDATION_NOT_GROUNDED",
        "RAG_WEAK_OR_MISSING",
        "SQL_OPERATION_MISSING",
        "CANONICAL_METRIC_INCONSISTENCY",
        "DATA_SOURCE_NOT_COVERED",
    }
    hallucination_like = 0
    grounded_count = 0
    unsupported_cases = [r for r in all_rows if _status_is_unsupported(r)]
    no_data_cases = [r for r in all_rows if _status_is_no_data(r)]
    for r in all_rows:
        failure = str(r.get("failure_category") or "")
        warnings = {_upper(w) for w in (r.get("warning_codes_upper") or [])}
        ungrounded = (
            failure in grounded_fail_categories
            or "NUMERIC_CLAIMS_NOT_GROUNDED" in warnings
            or "RECOMMENDATION_WITHOUT_EVIDENCE" in warnings
            or "MISSING_EXPECTED_ROUTE_EVIDENCE" in warnings
        )
        if ungrounded:
            hallucination_like += 1
        else:
            grounded_count += 1

    unsupported_claim_count = sum(1 for r in unsupported_cases if str(r.get("status") or "") != "PASS")
    evidence_contradiction_count = sum(
        1 for r in all_rows
        if str(r.get("failure_category") or "") == "CANONICAL_METRIC_INCONSISTENCY"
        or "SQL_ML_CONTRADICTION" in {_upper(w) for w in (r.get("warning_codes_upper") or [])}
    )
    no_data_correctness_rate = _pct(sum(1 for r in no_data_cases if str(r.get("status") or "") == "PASS"), len(no_data_cases))
    unsupported_handling_accuracy = _pct(sum(1 for r in unsupported_cases if str(r.get("status") or "") == "PASS"), len(unsupported_cases))

    evidence_availability_ok = 0
    evidence_status_correct_count = 0
    sql_coverage_ok = 0
    rag_routes = [r for r in all_rows if _upper(r.get("actual_route")) == "RAG_ONLY"]
    ml_routes = [r for r in all_rows if _upper(r.get("actual_route")) == "ML_ONLY"]
    recommendation_rows = [r for r in all_rows if str(r.get("module_group") or "") == "recommendations"]
    for r in all_rows:
        route = _upper(r.get("actual_route"))
        sql_status = _upper(r.get("evidence_status_sql"))
        rag_status = _upper(r.get("evidence_status_rag"))
        ml_status = _upper(r.get("evidence_status_ml"))
        if route == "SQL_ONLY":
            if sql_status in {"HAS_EVIDENCE", "PROVEN_NO_DATA", "PARTIAL_EVIDENCE", "UNSUPPORTED", "TOOL_ERROR"}:
                evidence_availability_ok += 1
                sql_coverage_ok += 1
        elif route == "RAG_ONLY":
            if rag_status in {"HAS_EVIDENCE", "PROVEN_NO_DATA", "PARTIAL_EVIDENCE", "UNSUPPORTED", "TOOL_ERROR"}:
                evidence_availability_ok += 1
        elif route == "ML_ONLY":
            if ml_status in {"HAS_EVIDENCE", "PROVEN_NO_DATA", "PARTIAL_EVIDENCE", "UNSUPPORTED", "TOOL_ERROR"}:
                evidence_availability_ok += 1
        else:
            if any(st in {"HAS_EVIDENCE", "PROVEN_NO_DATA", "PARTIAL_EVIDENCE"} for st in {sql_status, rag_status, ml_status}):
                evidence_availability_ok += 1

        if _status_expected_for_rows(r):
            evidence_status_correct_count += 1

    rag_relevance_ok = sum(1 for r in rag_routes if str(r.get("failure_category") or "") != "RAG_WEAK_OR_MISSING")
    ml_relevance_ok = sum(1 for r in ml_routes if str(r.get("failure_category") or "") != "ML_SIGNAL_UNAVAILABLE")
    recommendation_grounded_ok = sum(1 for r in recommendation_rows if bool(r.get("recommendation_grounded")))
    source_pollution_count = sum(1 for r in all_rows if _source_pollution_case(r))

    llm_attempted_rows = [r for r in all_rows if bool(r.get("llm_attempted"))]
    llm_attempted_count = len(llm_attempted_rows)
    llm_changed_numbers_count = _llm_flag_count(all_rows, "LLM_CHANGED_NUMBERS")
    llm_dropped_limitation_count = _llm_flag_count(all_rows, "LLM_DROPPED_LIMITATION")
    llm_changed_entities_count = _llm_flag_count(all_rows, "LLM_CHANGED_PRODUCT_NAMES")
    deterministic_fallback_count = sum(1 for r in all_rows if bool(r.get("llm_fallback_used")))

    number_preservation_rate = 1.0 - _pct(llm_changed_numbers_count, max(llm_attempted_count, 1))
    entity_preservation_rate = 1.0 - _pct(llm_changed_entities_count, max(llm_attempted_count, 1))
    limitation_preservation_rate = 1.0 - _pct(llm_dropped_limitation_count, max(llm_attempted_count, 1))
    unsafe_llm_rewrite_block_rate = _pct(deterministic_fallback_count, max(llm_attempted_count, 1))

    memory_rows = [r for r in all_rows if str(r.get("module_group") or "") == "memory"]
    followup_rows = [
        r for r in memory_rows
        if str(r.get("expected_response_shape") or "") in {
            "sequence_followup_lot",
            "sequence_followup_producer",
            "sequence_followup_product",
            "sequence_first_item",
            "sequence_latency_followup",
        }
    ]
    reset_rows = [
        r for r in memory_rows
        if str(r.get("expected_response_shape") or "") in {
            "sequence_reset_clarification",
            "sequence_topic_switch",
            "sequence_no_stale_lot",
            "sequence_rq_memory_reset",
            "sequence_latency_reset",
            "sequence_reset",
        }
    ]
    clarify_rows = [
        r for r in memory_rows
        if str(r.get("expected_response_shape") or "") in {
            "sequence_ambiguous_clarify",
            "sequence_cross_entity_clarify",
            "sequence_no_lot_inference",
            "sequence_rq_memory_clarify",
            "sequence_reset_clarification",
        }
    ]
    followup_accuracy = _pct(sum(1 for r in followup_rows if str(r.get("status") or "") == "PASS"), len(followup_rows))
    reset_safety_rate = _pct(sum(1 for r in reset_rows if str(r.get("status") or "") == "PASS"), len(reset_rows))
    clarification_accuracy = _pct(sum(1 for r in clarify_rows if str(r.get("status") or "") == "PASS"), len(clarify_rows))
    stale_context_leakage_rate = 1.0 - reset_safety_rate if reset_rows else 0.0

    latency_rows = [dict(r) for r in (suite_reports.get("latency") or {}).get("results", [])]
    latency_values = [float((r.get("timings") or {}).get("total_ms") or r.get("latency_ms") or 0.0) for r in latency_rows]
    sql_ms_values = _value_from_timing(latency_rows, "sql_ms")
    rag_ms_values = _value_from_timing(latency_rows, "rag_ms")
    ml_ms_values = _value_from_timing(latency_rows, "ml_ms")
    llm_ms_values = _value_from_timing(latency_rows, "llm_ms")
    composition_ms_values = _value_from_timing(latency_rows, "composition_ms")
    latency_route_avg: dict[str, float] = {}
    by_route: dict[str, list[float]] = defaultdict(list)
    for r in latency_rows:
        route = str(r.get("actual_route") or "")
        by_route[route].append(float((r.get("timings") or {}).get("total_ms") or r.get("latency_ms") or 0.0))
    for route, vals in by_route.items():
        latency_route_avg[route] = round(sum(vals) / max(1, len(vals)), 2)

    slow_count = sum(1 for v in latency_values if v > 6000.0)
    critical_count = sum(1 for v in latency_values if v > 10000.0)

    family_avg: dict[str, list[float]] = defaultdict(list)
    for r in latency_rows:
        family_avg[str(r.get("module_group") or "")].append(float((r.get("timings") or {}).get("total_ms") or r.get("latency_ms") or 0.0))
    family_avg_comp = {k: round(sum(v) / max(1, len(v)), 2) for k, v in family_avg.items()}
    fastest_families = sorted(family_avg_comp.items(), key=lambda kv: kv[1])[:3]
    slowest_families = sorted(family_avg_comp.items(), key=lambda kv: kv[1], reverse=True)[:3]

    # Subscores
    route_accuracy = _pct(route_correct, total_cases)
    intent_accuracy = _pct(intent_correct, total_cases)
    sql_operation_accuracy = _pct(sql_op_correct, len(sql_op_expected_rows))

    routing_error_penalty = 1.0 - _pct((routing_error_count + intent_mismatch_count + sql_operation_missing_count), max(total_cases, 1))
    routing_subscore = 100.0 * (
        0.40 * route_accuracy
        + 0.20 * intent_accuracy
        + 0.30 * sql_operation_accuracy
        + 0.10 * max(0.0, routing_error_penalty)
    )

    grounded_answer_rate = _pct(grounded_count, total_cases)
    hallucination_proxy_rate = _pct(hallucination_like, total_cases)
    evidence_availability_rate = _pct(evidence_availability_ok, total_cases)
    evidence_status_accuracy = _pct(evidence_status_correct_count, total_cases)
    grounding_subscore = 100.0 * (
        0.30 * grounded_answer_rate
        + 0.25 * (1.0 - hallucination_proxy_rate)
        + 0.15 * evidence_availability_rate
        + 0.15 * evidence_status_accuracy
        + 0.10 * no_data_correctness_rate
        + 0.05 * unsupported_handling_accuracy
    )

    recommendation_grounding_rate = _pct(recommendation_grounded_ok, len(recommendation_rows))
    recommendation_subscore = 100.0 * recommendation_grounding_rate

    memory_subscore = 100.0 * (
        0.35 * followup_accuracy
        + 0.35 * reset_safety_rate
        + 0.20 * clarification_accuracy
        + 0.10 * (1.0 - stale_context_leakage_rate)
    )

    llm_safety_subscore = 100.0 * (
        0.40 * number_preservation_rate
        + 0.25 * entity_preservation_rate
        + 0.25 * limitation_preservation_rate
        + 0.10 * (1.0 - min(unsafe_llm_rewrite_block_rate, 1.0))
    )

    p50_latency = _percentile(latency_values, 0.50)
    p90_latency = _percentile(latency_values, 0.90)
    p95_latency = _percentile(latency_values, 0.95)
    p50_score = _score_band(p50_latency, good=6000.0, acceptable=8000.0, bad=12000.0)
    p90_score = _score_band(p90_latency, good=9000.0, acceptable=11000.0, bad=15000.0)
    p95_score = _score_band(p95_latency, good=9500.0, acceptable=12000.0, bad=16000.0)
    slow_rate = _pct(slow_count, max(len(latency_rows), 1))
    critical_rate = _pct(critical_count, max(len(latency_rows), 1))
    latency_subscore = (
        0.25 * p50_score
        + 0.25 * p90_score
        + 0.20 * p95_score
        + 0.15 * (100.0 * (1.0 - slow_rate))
        + 0.15 * (100.0 * (1.0 - critical_rate))
    )

    overall_weighted_score = (
        0.20 * routing_subscore
        + 0.30 * grounding_subscore
        + 0.10 * recommendation_subscore
        + 0.10 * memory_subscore
        + 0.10 * llm_safety_subscore
        + 0.20 * latency_subscore
    )
    ai_reliability_score = (
        0.20 * routing_subscore
        + 0.40 * grounding_subscore
        + 0.15 * recommendation_subscore
        + 0.15 * memory_subscore
        + 0.10 * llm_safety_subscore
    )

    report = {
        "audit_name": "chatbot_metrics_evaluation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "total_cases": total_cases,
            "suite_case_counts": suite_case_counts,
            "suites": list(suite_reports.keys()),
        },
        "routing_orchestration": {
            "route_accuracy": _round4(route_accuracy),
            "intent_accuracy": _round4(intent_accuracy),
            "sql_operation_accuracy": _round4(sql_operation_accuracy),
            "sql_operation_missing_count": int(sql_operation_missing_count),
            "routing_error_count": int(routing_error_count),
            "intent_mismatch_count": int(intent_mismatch_count),
            "unnecessary_agent_call_rate": _round4(unnecessary_agent_call_rate),
        },
        "grounding_hallucination": {
            "grounded_answer_rate": _round4(grounded_answer_rate),
            "hallucination_proxy_rate": _round4(hallucination_proxy_rate),
            "unsupported_claim_count": int(unsupported_claim_count),
            "evidence_contradiction_count": int(evidence_contradiction_count),
            "no_data_correctness_rate": _round4(no_data_correctness_rate),
            "unsupported_handling_accuracy": _round4(unsupported_handling_accuracy),
            "proxy_note": "Groundedness/hallucination computed from verifier-aligned failure categories and warning flags.",
        },
        "evidence_metrics": {
            "evidence_availability_rate": _round4(evidence_availability_rate),
            "evidence_status_accuracy": _round4(evidence_status_accuracy),
            "sql_evidence_coverage": _round4(
                _pct(sql_coverage_ok, len([r for r in all_rows if _upper(r.get("actual_route")) == "SQL_ONLY"]))
            ),
            "rag_evidence_availability_relevance": _round4(_pct(rag_relevance_ok, len(rag_routes))),
            "ml_evidence_relevance": _round4(_pct(ml_relevance_ok, len(ml_routes))),
            "recommendation_grounding_rate": _round4(recommendation_grounding_rate),
            "source_pollution_rate": _round4(_pct(source_pollution_count, total_cases)),
        },
        "memory_metrics": {
            "followup_accuracy": _round4(followup_accuracy),
            "reset_safety_rate": _round4(reset_safety_rate),
            "clarification_accuracy": _round4(clarification_accuracy),
            "stale_context_leakage_rate": _round4(stale_context_leakage_rate),
        },
        "llm_guardrail_metrics": {
            "llm_attempted_count": int(llm_attempted_count),
            "number_preservation_rate": _round4(number_preservation_rate),
            "entity_preservation_rate": _round4(entity_preservation_rate),
            "limitation_preservation_rate": _round4(limitation_preservation_rate),
            "llm_changed_numbers_count": int(llm_changed_numbers_count),
            "llm_dropped_limitation_count": int(llm_dropped_limitation_count),
            "deterministic_fallback_count": int(deterministic_fallback_count),
            "unsafe_llm_rewrite_block_rate": _round4(unsafe_llm_rewrite_block_rate),
            "proxy_note": "Guardrail rates are proxy metrics based on warning flags and fallback metadata.",
        },
        "latency_metrics": {
            "p50_total_ms": round(p50_latency, 2),
            "p90_total_ms": round(p90_latency, 2),
            "p95_total_ms": round(p95_latency, 2),
            "avg_total_ms_by_route": latency_route_avg,
            "avg_sql_ms": round(sum(sql_ms_values) / max(len(sql_ms_values), 1), 2),
            "avg_rag_ms": round(sum(rag_ms_values) / max(len(rag_ms_values), 1), 2),
            "avg_ml_ms": round(sum(ml_ms_values) / max(len(ml_ms_values), 1), 2),
            "avg_llm_ms": round(sum(llm_ms_values) / max(len(llm_ms_values), 1), 2),
            "avg_composition_ms": round(sum(composition_ms_values) / max(len(composition_ms_values), 1), 2),
            "slow_case_count_gt_6s": int(slow_count),
            "critical_case_count_gt_10s": int(critical_count),
            "fastest_case_families": fastest_families,
            "slowest_case_families": slowest_families,
        },
        "weighted_scores": {
            "routing_orchestration_20pct": round(routing_subscore, 2),
            "evidence_grounding_hallucination_30pct": round(grounding_subscore, 2),
            "recommendation_grounding_10pct": round(recommendation_subscore, 2),
            "memory_safety_10pct": round(memory_subscore, 2),
            "llm_safety_10pct": round(llm_safety_subscore, 2),
            "latency_runtime_20pct": round(latency_subscore, 2),
            "ai_reliability_score": round(ai_reliability_score, 2),
            "runtime_performance_score": round(latency_subscore, 2),
            "overall_ds_ai_chatbot_score": round(overall_weighted_score, 2),
        },
        "remaining_risks": [
            "Latency remains high on several SQL/hybrid paths despite measurable gains.",
            "LLM guardrail metrics are computed as proxy indicators from runtime flags.",
            "Production upload smoke still requires manual validation on safe records.",
        ],
        "suite_reports": {
            key: {
                "audit_mode": value.get("audit_mode"),
                "counts": value.get("counts"),
                "total_cases": value.get("total_cases"),
                "json_report": (value.get("files") or {}).get("json_report"),
                "md_report": (value.get("files") or {}).get("md_report"),
            }
            for key, value in suite_reports.items()
        },
    }
    return report


def _write_metrics_markdown(*, report: dict[str, Any], md_path: Path) -> None:
    ds = report.get("dataset") or {}
    routing = report.get("routing_orchestration") or {}
    grounding = report.get("grounding_hallucination") or {}
    evidence = report.get("evidence_metrics") or {}
    reco_rate = float(evidence.get("recommendation_grounding_rate") or 0.0)
    memory = report.get("memory_metrics") or {}
    llm = report.get("llm_guardrail_metrics") or {}
    lat = report.get("latency_metrics") or {}
    scores = report.get("weighted_scores") or {}

    lines: list[str] = []
    lines.append("# Chatbot Metrics Evaluation (DS/AI Engineering)")
    lines.append("")
    lines.append("## 1. Executive summary")
    lines.append("")
    lines.append(f"- Generated at: `{report.get('generated_at')}`")
    lines.append(f"- Total evaluated cases: `{int(ds.get('total_cases') or 0)}`")
    lines.append(f"- AI reliability score: `{scores.get('ai_reliability_score')}`")
    lines.append(f"- Runtime performance score: `{scores.get('runtime_performance_score')}`")
    lines.append(f"- Overall DS/AI chatbot score: `{scores.get('overall_ds_ai_chatbot_score')}`")
    lines.append("")
    lines.append("## 2. Dataset/case coverage")
    lines.append("")
    lines.append("| Suite | Cases |")
    lines.append("|---|---:|")
    for suite, count in sorted((ds.get("suite_case_counts") or {}).items()):
        lines.append(f"| {suite} | {int(count)} |")
    lines.append("")
    lines.append("## 3. Routing metrics table")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| route_accuracy | {routing.get('route_accuracy')} |")
    lines.append(f"| intent_accuracy | {routing.get('intent_accuracy')} |")
    lines.append(f"| sql_operation_accuracy | {routing.get('sql_operation_accuracy')} |")
    lines.append(f"| sql_operation_missing_count | {routing.get('sql_operation_missing_count')} |")
    lines.append(f"| routing_error_count | {routing.get('routing_error_count')} |")
    lines.append(f"| intent_mismatch_count | {routing.get('intent_mismatch_count')} |")
    lines.append(f"| unnecessary_agent_call_rate | {routing.get('unnecessary_agent_call_rate')} |")
    lines.append("")
    lines.append("## 4. Evidence/grounding metrics table")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| evidence_availability_rate | {evidence.get('evidence_availability_rate')} |")
    lines.append(f"| evidence_status_accuracy | {evidence.get('evidence_status_accuracy')} |")
    lines.append(f"| sql_evidence_coverage | {evidence.get('sql_evidence_coverage')} |")
    lines.append(f"| rag_evidence_availability_relevance | {evidence.get('rag_evidence_availability_relevance')} |")
    lines.append(f"| ml_evidence_relevance | {evidence.get('ml_evidence_relevance')} |")
    lines.append(f"| no_data_correctness_rate | {grounding.get('no_data_correctness_rate')} |")
    lines.append(f"| unsupported_handling_accuracy | {grounding.get('unsupported_handling_accuracy')} |")
    lines.append("")
    lines.append("## 5. Hallucination/safety metrics table")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| grounded_answer_rate | {grounding.get('grounded_answer_rate')} |")
    lines.append(f"| hallucination_proxy_rate | {grounding.get('hallucination_proxy_rate')} |")
    lines.append(f"| unsupported_claim_count | {grounding.get('unsupported_claim_count')} |")
    lines.append(f"| evidence_contradiction_count | {grounding.get('evidence_contradiction_count')} |")
    lines.append(f"| source_pollution_rate | {evidence.get('source_pollution_rate')} |")
    lines.append("")
    lines.append("## 6. Recommendation metrics table")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| recommendation_grounding_rate | {reco_rate:.4f} |")
    lines.append("")
    lines.append("## 7. Memory metrics table")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| followup_accuracy | {memory.get('followup_accuracy')} |")
    lines.append(f"| reset_safety_rate | {memory.get('reset_safety_rate')} |")
    lines.append(f"| clarification_accuracy | {memory.get('clarification_accuracy')} |")
    lines.append(f"| stale_context_leakage_rate | {memory.get('stale_context_leakage_rate')} |")
    lines.append("")
    lines.append("## 8. LLM guardrail metrics table")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| llm_attempted_count | {llm.get('llm_attempted_count')} |")
    lines.append(f"| number_preservation_rate | {llm.get('number_preservation_rate')} |")
    lines.append(f"| entity_preservation_rate | {llm.get('entity_preservation_rate')} |")
    lines.append(f"| limitation_preservation_rate | {llm.get('limitation_preservation_rate')} |")
    lines.append(f"| llm_changed_numbers_count | {llm.get('llm_changed_numbers_count')} |")
    lines.append(f"| llm_dropped_limitation_count | {llm.get('llm_dropped_limitation_count')} |")
    lines.append(f"| deterministic_fallback_count | {llm.get('deterministic_fallback_count')} |")
    lines.append(f"| unsafe_llm_rewrite_block_rate | {llm.get('unsafe_llm_rewrite_block_rate')} |")
    lines.append("")
    lines.append("## 9. Latency metrics table")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| p50_total_ms | {lat.get('p50_total_ms')} |")
    lines.append(f"| p90_total_ms | {lat.get('p90_total_ms')} |")
    lines.append(f"| p95_total_ms | {lat.get('p95_total_ms')} |")
    lines.append(f"| avg_sql_ms | {lat.get('avg_sql_ms')} |")
    lines.append(f"| avg_rag_ms | {lat.get('avg_rag_ms')} |")
    lines.append(f"| avg_ml_ms | {lat.get('avg_ml_ms')} |")
    lines.append(f"| avg_llm_ms | {lat.get('avg_llm_ms')} |")
    lines.append(f"| avg_composition_ms | {lat.get('avg_composition_ms')} |")
    lines.append(f"| slow_case_count_gt_6s | {lat.get('slow_case_count_gt_6s')} |")
    lines.append(f"| critical_case_count_gt_10s | {lat.get('critical_case_count_gt_10s')} |")
    lines.append("")
    lines.append("| Route | Avg total ms |")
    lines.append("|---|---:|")
    for route, avg_ms in sorted((lat.get("avg_total_ms_by_route") or {}).items()):
        lines.append(f"| {route} | {avg_ms} |")
    lines.append("")
    lines.append("| Fastest families | Avg ms |")
    lines.append("|---|---:|")
    for fam, avg in (lat.get("fastest_case_families") or []):
        lines.append(f"| {fam} | {avg} |")
    lines.append("")
    lines.append("| Slowest families | Avg ms |")
    lines.append("|---|---:|")
    for fam, avg in (lat.get("slowest_case_families") or []):
        lines.append(f"| {fam} | {avg} |")
    lines.append("")
    lines.append("## 10. Error analysis / remaining risks")
    lines.append("")
    for risk in (report.get("remaining_risks") or []):
        lines.append(f"- {risk}")
    lines.append("")
    lines.append("## 11. Final DS/AI readiness score")
    lines.append("")
    lines.append("| Component | Weight | Score |")
    lines.append("|---|---:|---:|")
    lines.append(f"| Routing/orchestration | 20% | {scores.get('routing_orchestration_20pct')} |")
    lines.append(f"| Evidence/grounding/hallucination | 30% | {scores.get('evidence_grounding_hallucination_30pct')} |")
    lines.append(f"| Recommendation grounding | 10% | {scores.get('recommendation_grounding_10pct')} |")
    lines.append(f"| Memory safety | 10% | {scores.get('memory_safety_10pct')} |")
    lines.append(f"| LLM safety | 10% | {scores.get('llm_safety_10pct')} |")
    lines.append(f"| Latency/runtime | 20% | {scores.get('latency_runtime_20pct')} |")
    lines.append(f"| Overall DS/AI chatbot score | 100% | {scores.get('overall_ds_ai_chatbot_score')} |")
    lines.append("")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_metrics_evaluation(*, options: AuditRunOptions | None = None) -> dict[str, Any]:
    options = options or AuditRunOptions()
    suite_modes = [
        "baseline",
        "fresh",
        "manual-regression",
        "detail-members-memory",
        "response-quality",
        "latency",
    ]
    suite_reports: dict[str, dict[str, Any]] = {}
    for mode in suite_modes:
        suite_reports[mode] = run_audit(mode=mode, options=options)

    report = _build_metrics_evaluation_report(suite_reports=suite_reports)

    out_dir = ROOT / "artifacts" / "evals"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"chatbot_metrics_evaluation_{ts}.json"
    md_path = out_dir / f"chatbot_metrics_evaluation_{ts}.md"

    report["files"] = {
        "json_report": str(json_path),
        "md_report": str(md_path),
    }

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_metrics_markdown(report=report, md_path=md_path)

    return report


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
    return _run_one_with_timeout(client, headers, question, conversation_id=conversation_id, timeout_s=60.0)


def _run_one_with_timeout(
    client: TestClient,
    headers: dict[str, str],
    question: str,
    *,
    conversation_id: str | None = None,
    timeout_s: float = 60.0,
) -> tuple[int, dict[str, Any], float]:
    payload: dict[str, Any] = {"message": question, "language": "fr"}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    t0 = time.perf_counter()
    try:
        resp = client.post("/chat/agent", headers=headers, json=payload, timeout=timeout_s)
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return 599, {"error": str(exc), "error_type": exc.__class__.__name__}, elapsed
    elapsed = (time.perf_counter() - t0) * 1000.0
    try:
        body = resp.json() if resp.status_code == 200 else {"error": resp.text}
    except Exception:
        body = {"error": resp.text}
    return resp.status_code, body, elapsed


def _is_transient_failure(
    status_code: int,
    body: dict[str, Any],
    elapsed_ms: float,
    *,
    case_timeout_s: float,
    attempt: int,
) -> tuple[bool, str]:
    error_text = str((body or {}).get("error") or "").lower()
    error_type = str((body or {}).get("error_type") or "").lower()
    is_timeout = (
        status_code in {408, 504, 599}
        or "timeout" in error_text
        or "timed out" in error_text
        or "readtimeout" in error_type
    )
    provider_or_conn = any(token in error_text for token in (
        "connection reset",
        "connection aborted",
        "connection refused",
        "temporary failure",
        "service unavailable",
        "provider",
        "upstream",
    ))
    db_saturation = status_code == 503 or "too many connections" in error_text or "pool" in error_text
    first_call_anomaly = attempt == 1 and elapsed_ms >= max(case_timeout_s * 1000.0 * 0.9, 30000.0)
    if is_timeout:
        return True, "timeout"
    if provider_or_conn:
        return True, "provider_or_connection"
    if db_saturation:
        return True, "db_saturation"
    if first_call_anomaly:
        return True, "first_call_latency_anomaly"
    return False, ""


def _execute_warmup(client: TestClient, headers: dict[str, str], *, timeout_s: float) -> list[dict[str, Any]]:
    warmup_steps: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    health = client.get("/health", timeout=timeout_s)
    warmup_steps.append({
        "step": "health",
        "status_code": health.status_code,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
    })
    for label, question in (
        ("chat_members", "Liste des membres"),
        ("chat_rag", "Checklist avant emballage"),
    ):
        sc, body, elapsed_ms = _run_one_with_timeout(client, headers, question, timeout_s=timeout_s)
        warmup_steps.append({
            "step": label,
            "status_code": sc,
            "elapsed_ms": round(elapsed_ms, 2),
            "route": body.get("route"),
            "intent_family": _extract_intent_family(body.get("metadata") or {}),
            "error": body.get("error"),
        })
    return warmup_steps


def run_audit(*, mode: str = "baseline", options: AuditRunOptions | None = None) -> dict[str, Any]:
    os.environ["AI_AUDIT_DEBUG"] = "1"
    options = options or AuditRunOptions()
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
    if options.resume_from:
        start_idx = next((i for i, c in enumerate(cases) if c.qid == options.resume_from), None)
        if start_idx is None:
            raise ValueError(f"Unknown --resume-from case id: {options.resume_from}")
        cases = cases[start_idx:]
    if options.max_cases is not None and options.max_cases > 0:
        cases = cases[: options.max_cases]
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
        warmup_trace: list[dict[str, Any]] = []
        if options.warmup:
            warmup_trace = _execute_warmup(client, headers, timeout_s=options.case_timeout)

        memory_conversation_id: str | None = None
        runtime_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_prefix = "chatbot_whole_app_runtime_audit_fresh" if mode_normalized == "fresh" else ("chatbot_whole_app_runtime_audit_manual_regression" if mode_normalized == "manual-regression" else ("chatbot_whole_app_runtime_audit_detail_members_memory" if mode_normalized == "detail-members-memory" else ("chatbot_whole_app_runtime_audit_response_quality" if mode_normalized == "response-quality" else ("chatbot_whole_app_runtime_audit_latency" if mode_normalized == "latency" else "chatbot_whole_app_runtime_audit"))))
        out_dir = ROOT / "artifacts" / "evals"
        out_dir.mkdir(parents=True, exist_ok=True)
        case_log_path = out_dir / f"{file_prefix}_{runtime_ts}.cases.jsonl"

        for idx, case in enumerate(cases, start=1):
            if not case.expected_response_shape.startswith("sequence_"):
                attempts: list[dict[str, Any]] = []
                final_retry_count = 0
                transient_error_type = ""
                status_code = 0
                body: dict[str, Any] = {}
                elapsed_ms = 0.0
                for attempt in range(1, max(1, options.retry_transient + 1) + 1):
                    status_code, body, elapsed_ms = _run_one_with_timeout(
                        client,
                        headers,
                        case.question,
                        timeout_s=options.case_timeout,
                    )
                    is_transient, transient_kind = _is_transient_failure(
                        status_code,
                        body,
                        elapsed_ms,
                        case_timeout_s=options.case_timeout,
                        attempt=attempt,
                    )
                    attempts.append({
                        "attempt": attempt,
                        "status_code": status_code,
                        "latency_ms": round(elapsed_ms, 2),
                        "route": body.get("route"),
                        "error": body.get("error"),
                        "transient_kind": transient_kind if is_transient else "",
                    })
                    if is_transient and attempt <= options.retry_transient:
                        final_retry_count = attempt
                        transient_error_type = transient_kind
                        continue
                    break
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

                evidence_statuses = _extract_evidence_statuses(metadata)
                source_types = sorted(_evidence_types(body))
                warning_codes = metadata.get("warning_codes") or []
                warning_codes_upper = [str(code).strip().upper() for code in warning_codes if str(code).strip()]
                if not warning_codes_upper:
                    warning_codes_upper = [str(w).strip().upper() for w in (body.get("warnings") or []) if str(w).strip()]
                llm_meta = metadata.get("llm_metadata") or {}

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
                    "evidence_status_sql": evidence_statuses.get("sql"),
                    "evidence_status_ml": evidence_statuses.get("ml"),
                    "evidence_status_rag": evidence_statuses.get("rag"),
                    "source_types": source_types,
                    "agents_called": body.get("agents_used") or [],
                    "evidence_row_count": _extract_evidence_row_count(body, metadata),
                    "recommendation_grounded": _recommendation_grounded(body, metadata),
                    "response_blocks": [str((b or {}).get("type") or "") for b in (body.get("response_blocks") or []) if isinstance(b, dict)],
                    "warnings": body.get("warnings") or [],
                    "warning_codes_upper": warning_codes_upper,
                    "llm_attempted": bool(llm_meta.get("llm_attempted")),
                    "llm_fallback_used": bool(llm_meta.get("fallback_used")),
                    "llm_provider": str(llm_meta.get("provider") or ""),
                    "confidence": _safe_num(body.get("confidence"), 0.0),
                    "final_answer_text": str(body.get("answer") or ""),
                    "latency_ms": round(elapsed_ms, 2),
                    "timings": timings,
                    "latency_classification": _latency_class(float(timings.get("total_ms") or elapsed_ms)),
                    "status": status,
                    "failure_category": failure,
                    "reason": reason,
                    "error_type": transient_error_type or str(body.get("error_type") or ""),
                    "retry_count": final_retry_count,
                    "attempts": attempts,
                }
                results.append(result)
                case_log_row = {
                    "qid": case.qid,
                    "question": case.question,
                    "route": result.get("actual_route"),
                    "sql_operation": result.get("actual_sql_operation_tool"),
                    "evidence_status": {
                        "sql": result.get("evidence_status_sql"),
                        "ml": result.get("evidence_status_ml"),
                        "rag": result.get("evidence_status_rag"),
                    },
                    "latency_ms": result.get("latency_ms"),
                    "error_type": result.get("error_type"),
                    "retry_count": result.get("retry_count"),
                    "final_verdict": result.get("status"),
                    "failure_category": result.get("failure_category"),
                }
                with case_log_path.open("a", encoding="utf-8") as fp:
                    fp.write(json.dumps(case_log_row, ensure_ascii=False) + "\n")
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
            st1, b1, t1 = _run_one_with_timeout(client, headers, q1, timeout_s=options.case_timeout)
            m1 = b1.get("metadata") or {}
            memory_conversation_id = (m1.get("conversation_id") or memory_conversation_id)
            st2, b2, t2 = _run_one_with_timeout(client, headers, q2, conversation_id=memory_conversation_id, timeout_s=options.case_timeout)
            m2 = b2.get("metadata") or {}
            memory_conversation_id = (m2.get("conversation_id") or memory_conversation_id)
            if q3:
                st3, b3, t3 = _run_one_with_timeout(client, headers, q3, conversation_id=memory_conversation_id, timeout_s=options.case_timeout)
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

            evidence_statuses = _extract_evidence_statuses(m3)
            source_types = sorted(_evidence_types(b3))
            warning_codes = m3.get("warning_codes") or []
            warning_codes_upper = [str(code).strip().upper() for code in warning_codes if str(code).strip()]
            if not warning_codes_upper:
                warning_codes_upper = [str(w).strip().upper() for w in (b3.get("warnings") or []) if str(w).strip()]
            llm_meta = m3.get("llm_metadata") or {}

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
                "evidence_status_sql": evidence_statuses.get("sql"),
                "evidence_status_ml": evidence_statuses.get("ml"),
                "evidence_status_rag": evidence_statuses.get("rag"),
                "source_types": source_types,
                "agents_called": b3.get("agents_used") or [],
                "evidence_row_count": _extract_evidence_row_count(b3, m3),
                "recommendation_grounded": _recommendation_grounded(b3, m3),
                "response_blocks": [str((b or {}).get("type") or "") for b in (b3.get("response_blocks") or []) if isinstance(b, dict)],
                "warnings": b3.get("warnings") or [],
                "warning_codes_upper": warning_codes_upper,
                "llm_attempted": bool(llm_meta.get("llm_attempted")),
                "llm_fallback_used": bool(llm_meta.get("fallback_used")),
                "llm_provider": str(llm_meta.get("provider") or ""),
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
                "error_type": str(b3.get("error_type") or ""),
                "retry_count": 0,
                "sequence_details": {
                    "step1": {"status": st1, "route": b1.get("route"), "intent": _extract_intent_family(m1)},
                    "step2": {"status": st2, "route": b2.get("route"), "intent": _extract_intent_family(m2)},
                    "step3": {"status": st3, "route": b3.get("route"), "intent": _extract_intent_family(m3)},
                },
            }
            results.append(result)
            case_log_row = {
                "qid": case.qid,
                "question": case.question,
                "route": result.get("actual_route"),
                "sql_operation": result.get("actual_sql_operation_tool"),
                "evidence_status": {
                    "sql": result.get("evidence_status_sql"),
                    "ml": result.get("evidence_status_ml"),
                    "rag": result.get("evidence_status_rag"),
                },
                "latency_ms": result.get("latency_ms"),
                "error_type": result.get("error_type"),
                "retry_count": result.get("retry_count"),
                "final_verdict": result.get("status"),
                "failure_category": result.get("failure_category"),
            }
            with case_log_path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(case_log_row, ensure_ascii=False) + "\n")
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

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
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
    report["files"]["case_log_jsonl"] = str(case_log_path)
    report["run_options"] = asdict(options)
    report["warmup_trace"] = warmup_trace

    # persist updated file pointers
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run deterministic whole-app chatbot runtime audit.")
    parser.add_argument(
        "--mode",
        choices=["baseline", "fresh", "manual-regression", "detail-members-memory", "response-quality", "latency", "metrics-evaluation"],
        default="baseline",
        help="Audit set to execute: baseline (fixed 60), fresh (paraphrased anti-overfit set), manual-regression (strict semantic families), detail-members-memory, response-quality, latency, or metrics-evaluation.",
    )
    parser.add_argument("--warmup", action="store_true", help="Run non-scored warmup calls before scored cases.")
    parser.add_argument("--max-cases", type=int, default=None, help="Limit number of scored cases for this run.")
    parser.add_argument("--case-timeout", type=float, default=60.0, help="Per request timeout in seconds.")
    parser.add_argument("--retry-transient", type=int, default=0, help="Retry count for transient timeout/provider/db saturation failures.")
    parser.add_argument("--resume-from", type=str, default=None, help="Resume from a specific case id (inclusive).")
    args = parser.parse_args()
    options = AuditRunOptions(
        warmup=bool(args.warmup),
        max_cases=args.max_cases,
        case_timeout=float(args.case_timeout),
        retry_transient=max(0, int(args.retry_transient or 0)),
        resume_from=args.resume_from,
    )
    if args.mode == "metrics-evaluation":
        r = run_metrics_evaluation(options=options)
        print(r["files"]["json_report"])
        print(r["files"]["md_report"])
        print(
            json.dumps(
                {
                    "overall_ds_ai_chatbot_score": (r.get("weighted_scores") or {}).get("overall_ds_ai_chatbot_score"),
                    "ai_reliability_score": (r.get("weighted_scores") or {}).get("ai_reliability_score"),
                    "runtime_performance_score": (r.get("weighted_scores") or {}).get("runtime_performance_score"),
                },
                ensure_ascii=False,
            )
        )
    else:
        r = run_audit(mode=args.mode, options=options)
        print(r["files"]["json_report"])
        print(r["files"]["md_report"])
        print(json.dumps(r["counts"], ensure_ascii=False))
