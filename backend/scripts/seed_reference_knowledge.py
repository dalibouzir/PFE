from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import func, select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.reference import KnowledgeChunk, ReferenceMetric


KNOWLEDGE_SEED_ROWS: list[dict[str, str]] = [
    {
        "source_id": "REF-KNOW-GENERAL-CLEAN-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mil",
        "topic": "nettoyage avant transformation",
        "content": "Avant transformation, organiser un nettoyage en trois contrôles: zone de travail propre et sèche, tri des corps étrangers à la réception, et lavage/désinfection des surfaces de contact. Écarter immédiatement les produits visiblement altérés limite la contamination croisée et les pertes en aval.",
    },
    {
        "source_id": "REF-KNOW-MIL-DRY-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mil",
        "topic": "séchage et réduction des pertes",
        "content": "Pour le mil, démarrer le séchage rapidement après collecte, étaler en couche régulière et maintenir une bonne aération. Contrôler l’humidité de façon périodique et éviter la reprise d’humidité la nuit réduit fortement les pertes post-récolte.",
    },
    {
        "source_id": "REF-KNOW-MANG-DRY-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mangue",
        "topic": "séchage mangue",
        "content": "Pour la mangue, utiliser des tranches homogènes, éviter la surchauffe et protéger les lots de l’humidité ambiante. Un séchage stable, avec retournement contrôlé et vérification de texture, améliore la qualité et limite les rebuts.",
    },
    {
        "source_id": "REF-KNOW-ARAC-DRY-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Arachide",
        "topic": "séchage arachide",
        "content": "Pour l’arachide, réduire les délais avant séchage, protéger des pluies et vérifier l’humidité finale avant ensachage. Les lots insuffisamment secs augmentent le risque de moisissure, de déclassement qualité et de pertes au stockage.",
    },
    {
        "source_id": "REF-KNOW-MANG-SORT-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mangue",
        "topic": "tri mangue",
        "content": "Améliorer le tri des mangues en séparant par maturité, état visuel et défauts mécaniques. Mettre en place une table de tri bien éclairée, des critères de grade simples et un contrôle croisé en fin de lot réduit les erreurs de classement.",
    },
    {
        "source_id": "REF-KNOW-MIL-SORT-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mil",
        "topic": "tri et rejet",
        "content": "Pour le mil, un tri efficace combine retrait précoce des impuretés, séparation par qualité et retrait immédiat des fractions non conformes. Cette discipline diminue les pertes cachées et améliore la constance du produit final.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-PACK-PRECHECK-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mangue",
        "topic": "checklist avant emballage",
        "content": "Checklist avant emballage: vérifier l’humidité finale, retirer les produits endommagés, confirmer la propreté des surfaces, utiliser des contenants secs et intacts, puis étiqueter lot/date/grade. Cette séquence réduit la casse et les reprises en conditionnement.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-CONDITIONING-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Arachide",
        "topic": "conditionnement arachide",
        "content": "Pour le conditionnement des arachides, éviter la surcharge des sacs, limiter les chocs, contrôler l’état des emballages et fermer uniquement sur produit sec. Une manutention douce protège l’intégrité des grains et limite les pertes commerciales.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-QUALITY-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mil",
        "topic": "contrôle qualité",
        "content": "Avant stockage, contrôler au minimum: humidité, odeur anormale, présence d’impuretés, état des emballages et traçabilité du lot. Isoler tout lot douteux et documenter la non-conformité évite la propagation des défauts.",
    },
    {
        "source_id": "REF-KNOW-MIL-STORAGE-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mil",
        "topic": "stockage post-conditionnement",
        "content": "Après conditionnement, stocker en zone sèche et ventilée, sur palettes, avec séparation du sol et des murs. Programmer des contrôles périodiques d’humidité et de nuisibles, et limiter les re-manutentions pour réduire les pertes.",
    },
    {
        "source_id": "REF-KNOW-ARAC-STORAGE-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Arachide",
        "topic": "stockage arachide",
        "content": "Le stockage des arachides doit privilégier ventilation, propreté et rotation des lots. Les contrôles réguliers sur humidité, insectes et moisissures permettent d’agir tôt et de préserver la qualité marchande.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-PHL-001",
        "source_url": "https://africa-knowledge-platform.ec.europa.eu/dataset/postharvest-loss-estimates-millet",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mil",
        "topic": "réduction globale des pertes post-récolte",
        "content": "Réduire durablement les pertes post-récolte repose sur une chaîne disciplinée: nettoyage propre, séchage maîtrisé, tri rapide, conditionnement adapté, stockage contrôlé et suivi des écarts par lot. L’objectif est d’agir étape par étape plutôt que corriger en fin de chaîne.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-HANDLING-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mangue",
        "topic": "manutention et transfert entre étapes",
        "content": "Les pertes augmentent quand les transferts entre séchage, tri, emballage et stockage sont désorganisés. Fixer des rôles clairs, limiter les temps d’attente et protéger les produits pendant les déplacements améliore la stabilité qualité.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-PACK-TRACE-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mangue",
        "topic": "traçabilité en emballage",
        "content": "La traçabilité d’emballage doit inclure au minimum code lot, date de conditionnement, poids net et grade qualité. Cette information facilite le suivi coopératif, la rotation de stock et la gestion des non-conformités.",
    },
]

REFERENCE_METRIC_ROWS: list[dict[str, Any]] = [
    {
        "source_id": "REF-MET-MIL-DRY-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mil",
        "metric": "post_harvest_loss_pct_range_drying",
        "period": "2018-2024",
        "value": 10.0,
        "unit": "%",
        "notes": "Reference assumption from public post-harvest literature; indicative range often discussed around 7-13%. Source: APHLIS https://www.aphlis.net/en",
    },
    {
        "source_id": "REF-MET-MIL-SORT-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mil",
        "metric": "post_harvest_loss_pct_range_sorting",
        "period": "2018-2024",
        "value": 5.0,
        "unit": "%",
        "notes": "Reference assumption from public literature; indicative sorting/rejection range around 3-7%.",
    },
    {
        "source_id": "REF-MET-MIL-STORAGE-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mil",
        "metric": "post_harvest_loss_pct_range_storage",
        "period": "2018-2024",
        "value": 7.0,
        "unit": "%",
        "notes": "Reference assumption based on public post-harvest sources; indicative handling/storage range around 4-10%.",
    },
    {
        "source_id": "REF-MET-MANG-DRY-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mangue",
        "metric": "post_harvest_loss_pct_range_drying",
        "period": "2018-2024",
        "value": 12.0,
        "unit": "%",
        "notes": "Literature-informed mango drying reference range often discussed around 8-16%; not cooperative measurement.",
    },
    {
        "source_id": "REF-MET-MANG-SORT-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mangue",
        "metric": "post_harvest_loss_pct_range_sorting",
        "period": "2018-2024",
        "value": 6.0,
        "unit": "%",
        "notes": "Literature-informed mango sorting/rejection reference around 4-8%; for external benchmark context.",
    },
    {
        "source_id": "REF-MET-MANG-PACK-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mangue",
        "metric": "post_harvest_loss_pct_range_packaging",
        "period": "2018-2024",
        "value": 4.0,
        "unit": "%",
        "notes": "Reference assumption for packaging/handling quality losses around 2-6%; source context includes FAO public datasets https://www.fao.org/faostat/.",
    },
    {
        "source_id": "REF-MET-ARAC-DRY-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Arachide",
        "metric": "post_harvest_loss_pct_range_drying",
        "period": "2018-2024",
        "value": 9.0,
        "unit": "%",
        "notes": "Groundnut drying reference assumption from literature and regional sources; indicative range around 6-12%.",
    },
    {
        "source_id": "REF-MET-ARAC-SORT-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Arachide",
        "metric": "post_harvest_loss_pct_range_sorting",
        "period": "2018-2024",
        "value": 5.0,
        "unit": "%",
        "notes": "Groundnut sorting/rejection reference range commonly discussed around 3-7%.",
    },
    {
        "source_id": "REF-MET-ARAC-STORAGE-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Arachide",
        "metric": "post_harvest_loss_pct_range_storage",
        "period": "2018-2024",
        "value": 8.0,
        "unit": "%",
        "notes": "Groundnut storage/handling reference assumption around 5-11%; external benchmark only.",
    },
    {
        "source_id": "REF-MET-MIL-TOTAL-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mil",
        "metric": "post_harvest_loss_pct_range_total",
        "period": "2018-2024",
        "value": 17.0,
        "unit": "%",
        "notes": "Literature-informed total post-harvest reference assumption around 12-22%; not a cooperative live KPI.",
    },
    {
        "source_id": "REF-MET-MANG-TOTAL-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Mangue",
        "metric": "post_harvest_loss_pct_range_total",
        "period": "2018-2024",
        "value": 20.0,
        "unit": "%",
        "notes": "Literature-informed mango total post-harvest reference assumption around 15-25%; for external comparison.",
    },
    {
        "source_id": "REF-MET-ARAC-TOTAL-001",
        "country": "Senegal",
        "region": "Afrique de l'Ouest",
        "crop": "Arachide",
        "metric": "post_harvest_loss_pct_range_total",
        "period": "2018-2024",
        "value": 15.0,
        "unit": "%",
        "notes": "Literature-informed groundnut total post-harvest reference assumption around 10-20%; external benchmark only.",
    },
]


def seed_reference_knowledge() -> dict[str, Any]:
    db = SessionLocal()
    try:
        knowledge_inserted = 0
        knowledge_updated = 0
        knowledge_deleted = 0
        metric_inserted = 0
        metric_updated = 0

        valid_knowledge_ids = {row["source_id"] for row in KNOWLEDGE_SEED_ROWS}
        stale_knowledge_rows = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.source_id.like("REF-KNOW-%"))).all()
        for row in stale_knowledge_rows:
            if row.source_id not in valid_knowledge_ids:
                db.delete(row)
                knowledge_deleted += 1

        for payload in KNOWLEDGE_SEED_ROWS:
            row = db.scalar(select(KnowledgeChunk).where(KnowledgeChunk.source_id == payload["source_id"]).limit(1))
            if row is None:
                db.add(KnowledgeChunk(**payload))
                knowledge_inserted += 1
                continue
            changed = False
            for key, value in payload.items():
                if getattr(row, key) != value:
                    setattr(row, key, value)
                    changed = True
            if changed:
                knowledge_updated += 1

        for payload in REFERENCE_METRIC_ROWS:
            row = db.scalar(select(ReferenceMetric).where(ReferenceMetric.source_id == payload["source_id"]).limit(1))
            if row is None:
                db.add(ReferenceMetric(**payload))
                metric_inserted += 1
                continue
            changed = False
            for key, value in payload.items():
                if getattr(row, key) != value:
                    setattr(row, key, value)
                    changed = True
            if changed:
                metric_updated += 1

        db.commit()

        total_knowledge = db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0
        total_metrics = db.scalar(select(func.count()).select_from(ReferenceMetric)) or 0

        return {
            "knowledge_chunks": {
                "inserted": int(knowledge_inserted),
                "updated": int(knowledge_updated),
                "deleted": int(knowledge_deleted),
                "total": int(total_knowledge),
            },
            "reference_metrics": {
                "inserted": int(metric_inserted),
                "updated": int(metric_updated),
                "total": int(total_metrics),
            },
            "coverage": {
                "crops": sorted({row["crop"] for row in KNOWLEDGE_SEED_ROWS}),
                "knowledge_topics": sorted({row["topic"] for row in KNOWLEDGE_SEED_ROWS}),
                "metric_names": sorted({row["metric"] for row in REFERENCE_METRIC_ROWS}),
            },
        }
    finally:
        db.close()


def main() -> None:
    report = seed_reference_knowledge()
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
