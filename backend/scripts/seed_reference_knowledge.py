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
        "source_id": "REF-KNOW-MIL-DRY-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mil",
        "topic": "drying losses",
        "content": "Literature and post-harvest references commonly associate millet drying losses with high humidity, limited airflow, uneven layer thickness, and weak moisture control. This is reference knowledge for comparison, not cooperative measurement.",
    },
    {
        "source_id": "REF-KNOW-MIL-SORT-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mil",
        "topic": "sorting and rejection losses",
        "content": "Post-harvest references commonly link millet sorting losses to mixed maturity, foreign matter contamination, and delayed sorting after drying. Prevention usually emphasizes earlier sorting, cleaner intake, and basic grade rules.",
    },
    {
        "source_id": "REF-KNOW-MIL-STORAGE-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mil",
        "topic": "storage and handling",
        "content": "Reference guidance for millet storage highlights moisture reabsorption, pest pressure, and repeated bag handling as common contributors to losses. Typical mitigation includes dry storage, periodic checks, and reduced handling cycles.",
    },
    {
        "source_id": "REF-KNOW-MANG-DRY-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mangue",
        "topic": "drying losses",
        "content": "Literature-informed mango drying references often associate losses with unstable slice thickness, overheating, prolonged drying duration, and poor humidity management. This guidance is external reference context only.",
    },
    {
        "source_id": "REF-KNOW-MANG-HUMID-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mangue",
        "topic": "humidity and moisture control",
        "content": "Post-harvest references commonly note that mango moisture control strongly affects final quality and shrinkage. Practical guidance favors controlled airflow, regular moisture checks, and rapid transition to protected storage.",
    },
    {
        "source_id": "REF-KNOW-MANG-PACK-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mangue",
        "topic": "packaging and handling",
        "content": "Reference knowledge for mango packaging links bruising and rejection to rough handling and weak packaging integrity. Suggested controls include gentler handling, better tray support, and moisture-safe packaging materials.",
    },
    {
        "source_id": "REF-KNOW-ARAC-DRY-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Arachide",
        "topic": "drying losses",
        "content": "Groundnut post-harvest references commonly connect drying losses to delayed drying starts, incomplete shell drying, and exposure to rain/humidity. Mitigation usually prioritizes rapid drying start and controlled final moisture.",
    },
    {
        "source_id": "REF-KNOW-ARAC-STORAGE-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Arachide",
        "topic": "storage and handling",
        "content": "Reference documents for groundnut storage often highlight mold risk, insect damage, and repeated sack movement as major loss drivers. Better ventilation, dry storage, and handling discipline are common recommendations.",
    },
    {
        "source_id": "REF-KNOW-ARAC-SORT-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Arachide",
        "topic": "sorting and rejection",
        "content": "Literature-informed references indicate groundnut sorting losses increase when incoming lots are mixed-quality and visual defects are detected late. Early grading and cleaner intake are commonly recommended.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-PHL-001",
        "source_url": "https://africa-knowledge-platform.ec.europa.eu/dataset/postharvest-loss-estimates-millet",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mil",
        "topic": "general post-harvest loss prevention",
        "content": "Across post-harvest literature, recurring prevention themes include rapid drying after intake, moisture tracking, stage-level loss monitoring, and process discipline. This is a reference assumption, not a cooperative KPI.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-HANDLING-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mangue",
        "topic": "handling sequence quality",
        "content": "Reference guidance emphasizes that poor handoff timing between drying, sorting, and packaging can increase both direct losses and quality downgrades. Coordinated stage timing is commonly recommended.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-MOISTURE-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Arachide",
        "topic": "moisture and quality stability",
        "content": "Post-harvest references repeatedly link unstable moisture to elevated spoilage and rejection risk. Practical recommendations include monitoring moisture checkpoints and minimizing humid exposure before storage.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-PACK-PRECHECK-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mangue",
        "topic": "precautions before packaging",
        "content": "Avant emballage, les références post-récolte recommandent de vérifier l’humidité finale, retirer les produits abîmés, nettoyer les surfaces de contact, et confirmer que l’emballage est sec et intact. Cette précaution réduit les pertes et la casse en conditionnement.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-CONDITIONING-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mil",
        "topic": "conditioning standard procedure",
        "content": "Une procédure simple de conditionnement inclut: tri préalable par grade, contenants propres et secs, remplissage contrôlé, éviter la compression, puis fermeture après contrôle d’humidité. L’objectif est de limiter la casse pendant l’emballage et la manutention.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-BREAKAGE-001",
        "source_url": "https://africa-knowledge-platform.ec.europa.eu/dataset/postharvest-loss-estimates-millet",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Arachide",
        "topic": "breakage prevention during handling and packaging",
        "content": "Le risque de casse augmente avec la manutention brutale, les sacs surchargés, et l’empilage instable. Les contrôles recommandés sont: limiter la hauteur de chute, renforcer les emballages faibles, réduire l’écrasement, et maintenir une hauteur d’empilage sûre pendant conditionnement.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-PACK-TRACE-001",
        "source_url": "https://www.fao.org/faostat/",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mangue",
        "topic": "packaging traceability fields",
        "content": "La traçabilité d’emballage doit inclure: code lot, date de conditionnement, poids net, et grade qualité sur chaque unité ou palette. Cette discipline améliore la rotation de stock et la capacité de contrôle coopératif.",
    },
    {
        "source_id": "REF-KNOW-GENERAL-POSTPACK-STORAGE-001",
        "source_url": "https://www.aphlis.net/en",
        "country": "Senegal",
        "region": "West Africa",
        "crop": "Mil",
        "topic": "storage after conditioning",
        "content": "Après conditionnement, le stockage recommandé utilise des zones sèches et ventilées, des palettes séparées du sol/murs, et des contrôles d’humidité périodiques. Limiter les re-manutentions réduit la casse et la dégradation qualité après emballage.",
    },
]

REFERENCE_METRIC_ROWS: list[dict[str, Any]] = [
    {
        "source_id": "REF-MET-MIL-DRY-001",
        "country": "Senegal",
        "region": "West Africa",
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
        "region": "West Africa",
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
        "region": "West Africa",
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
        "region": "West Africa",
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
        "region": "West Africa",
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
        "region": "West Africa",
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
        "region": "West Africa",
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
        "region": "West Africa",
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
        "region": "West Africa",
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
        "region": "West Africa",
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
        "region": "West Africa",
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
        "region": "West Africa",
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
        metric_inserted = 0
        metric_updated = 0

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
