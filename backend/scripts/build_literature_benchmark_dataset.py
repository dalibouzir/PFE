#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import sys
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.utils.stage_normalization import normalize_stage


BENCHMARK_MARKER = "[ML_LITERATURE_BENCHMARK]"
BENCHMARK_BATCH_PREFIX = "BENCH-ML-"
DEFAULT_TARGET_ROWS = 3000
DEFAULT_SEED = 42
DEFAULT_START_DATE = date(2021, 1, 1)
PRODUCTS = ["Mangue", "Arachide", "Mil"]
STAGES = ["Nettoyage", "Séchage", "Tri", "Emballage"]


SOURCE_ENTRIES: List[Dict] = [
    {
        "title": "Post Harvest Losses - losses_estimates - for crop Millets in country Senegal",
        "url": "https://archive.aphlis.net/?c_id=342&co_id=40&form=losses_estimates",
        "crop": "Mil",
        "country_region": "Senegal",
        "relevant_stages": ["Séchage", "Nettoyage", "Tri"],
        "reported_loss_value_or_range": "Country/province cumulative losses mostly around ~8.3% to 10.8%, with outlier 20.5% in one province-year listing.",
        "app_stage_mapping": "Cumulative cereal chain used to calibrate Mil overall risk and upper-tail spikes; not a direct one-to-one stage table for app transformation steps.",
        "reliability_note": "Official APHLIS archive table; model-based estimates from literature + contextual factors.",
        "evidence": "APHLIS states estimates are cumulative across harvesting, drying, handling, storage, and transport; Senegal millet table shows multiple province-year values around 8-11% and one 20.5% spike.",
        "access_date": "2026-05-07",
    },
    {
        "title": "Postharvest losses data tables (APHLIS)",
        "url": "https://www.aphlis.net/en/data/tables/dry-weight-losses/XAF/millet/all-years?metric=tns",
        "crop": "Mil",
        "country_region": "Sub-Saharan Africa / Senegal context",
        "relevant_stages": ["Séchage", "Nettoyage", "Tri"],
        "reported_loss_value_or_range": "Metric definitions and methodology; no direct Senegal stage-by-stage numeric range on this page.",
        "app_stage_mapping": "Used as methodology source for mapping APHLIS handling operations to Nettoyage/Tri and drying to Séchage.",
        "reliability_note": "Official APHLIS documentation page.",
        "evidence": "APHLIS defines % loss as cumulative across drying, handling operations (threshing/shelling/winnowing), storage and transport, with references traceable per estimate.",
        "access_date": "2026-05-07",
    },
    {
        "title": "Key facts about postharvest Sorghum losses in Senegal 2021 (APHLIS)",
        "url": "https://www.aphlis.net/en/data/tables/overview/SN/sorghum/2021",
        "crop": "Mil (proxy via cereal chain behavior)",
        "country_region": "Senegal",
        "relevant_stages": ["Séchage", "Nettoyage", "Tri"],
        "reported_loss_value_or_range": "2021 sorghum chain example: harvesting/field drying 4.55%, threshing/shelling 3.6%, transport from field 2.17%, market storage 2.65%; total 11.6%.",
        "app_stage_mapping": "Field drying informs Séchage baseline; threshing/shelling informs Nettoyage/Tri baseline for cereals.",
        "reliability_note": "Official APHLIS country-year overview with stage-step decomposition.",
        "evidence": "Page reports Senegal sorghum 11.6% total PHL in 2021 and shows stepwise value-chain losses including field drying and threshing/shelling.",
        "access_date": "2026-05-07",
    },
    {
        "title": "Postharvest loss estimates for millet | Africa Knowledge Platform",
        "url": "https://africa-knowledge-platform.ec.europa.eu/dataset/postharvest-loss-estimates-millet",
        "crop": "Mil",
        "country_region": "Africa",
        "relevant_stages": ["Séchage", "Nettoyage", "Tri"],
        "reported_loss_value_or_range": "No fixed numeric Senegal stage range; dataset describes cumulative value-chain % loss and cautions on missing data.",
        "app_stage_mapping": "Supports transparent benchmark assumption labeling where direct stage values are missing.",
        "reliability_note": "EU-JRC Africa Knowledge Platform dataset description using APHLIS model outputs.",
        "evidence": "Dataset states cumulative loss includes harvesting, drying, threshing/shelling, winnowing, storage and transport; warns some gaps are filled with similar-crop/context studies.",
        "access_date": "2026-05-07",
    },
    {
        "title": "ORCHESTRATING SOLUTIONS... mango losses in Senegal",
        "url": "https://topjournals.org/index.php/TAJEAS/article/view/903",
        "crop": "Mangue",
        "country_region": "Senegal",
        "relevant_stages": ["Tri", "Séchage"],
        "reported_loss_value_or_range": "Abstract cites severe fruit-fly impact and references estimates of large production reductions in affected regions.",
        "app_stage_mapping": "Used to justify heavier high-loss tail in mango sorting and some drying scenarios during pressure periods.",
        "reliability_note": "Peer-reviewed journal page with Senegal focus; cited values are broad and should not be used as direct stage rates.",
        "evidence": "Abstract highlights substantial economic losses from fruit fly infestations and major production reductions in parts of Senegal.",
        "access_date": "2026-05-07",
    },
    {
        "title": "Economic Impact of Fruit Flies in Mango Production in Senegal (Virginia Tech thesis)",
        "url": "https://vtechworks.lib.vt.edu/bitstream/handle/10919/82484/Diatta_PM_T_2016.pdf",
        "crop": "Mangue",
        "country_region": "Ziguinchor/Casamance, Senegal",
        "relevant_stages": ["Tri"],
        "reported_loss_value_or_range": "Household-level yearly losses from fruit-fly infestations estimated at 17.09% of average total household income (study context metric, not direct stage % mass loss).",
        "app_stage_mapping": "Supports elevated mango rejection/loss risk scenarios at sorting due to infestation pressure.",
        "reliability_note": "Academic thesis with field survey; economic-loss framing, not process-step mass-loss rates.",
        "evidence": "Abstract reports substantial household losses tied to fruit fly infestations in Ziguinchor and links losses to production/yield effects.",
        "access_date": "2026-05-07",
    },
    {
        "title": "Identification of Post-Harvest Operations... Groundnut by Mycotoxins (DOI:10.4236/as.2021.124026)",
        "url": "https://www.scirp.org/pdf/as_2021042014241041.pdf",
        "crop": "Arachide",
        "country_region": "Chad (contextual African groundnut operations)",
        "relevant_stages": ["Séchage", "Tri", "Emballage"],
        "reported_loss_value_or_range": "Survey reported post-harvest loss bands with 74.7% of respondents in 2-10% range and 25.3% in 10-50% range.",
        "app_stage_mapping": "Used as contextual support for medium/high tails in Arachide drying and sorting when conditions are poor.",
        "reliability_note": "Peer-reviewed but not Senegal-specific; used as contextual range support only.",
        "evidence": "Paper describes drying and storage practices and reports respondent-based loss bands up to 50% under poor post-harvest management.",
        "access_date": "2026-05-07",
    },
    {
        "title": "IITA Senegal Country Status Report (Aflasafe)",
        "url": "https://www.iita.org/wp-content/uploads/2021/03/Senegal-Country-Status-Report_Final-161120.pdf",
        "crop": "Arachide",
        "country_region": "Senegal",
        "relevant_stages": ["Séchage", "Emballage", "Stockage context"],
        "reported_loss_value_or_range": "Reports strong aflatoxin contamination risk and notes mitigation reduced contamination >80% in trials; no direct per-stage mass-loss percentages.",
        "app_stage_mapping": "Supports higher drying-related risk scenarios for groundnut quality degradation and loss pressure.",
        "reliability_note": "Institutional technical report for Senegal context; mostly contamination/economic risk evidence.",
        "evidence": "Report highlights contamination burden and emphasizes drying/storage discipline and mitigation impact in Senegal groundnut chain.",
        "access_date": "2026-05-07",
    },
    {
        "title": "FAO Statistics portal (FAOSTAT access)",
        "url": "https://www.fao.org/statistics/en/",
        "crop": "Mangue/Arachide/Mil context",
        "country_region": "Global/Senegal",
        "relevant_stages": ["All (context only)"],
        "reported_loss_value_or_range": "Production-context source only; no app-stage process-step loss rates.",
        "app_stage_mapping": "Used for macro production context only, not stage-level loss calibration.",
        "reliability_note": "Official FAO statistics entrypoint.",
        "evidence": "FAO page states FAOSTAT provides broad food/agriculture statistics and production context.",
        "access_date": "2026-05-07",
    },
]


BASE_LOSS_RANGES: Dict[str, Dict[str, Tuple[float, float]]] = {
    "Mil": {
        "Nettoyage": (1.0, 4.0),
        "Séchage": (3.0, 9.0),
        "Tri": (2.0, 8.0),
        "Emballage": (0.5, 3.0),
    },
    "Arachide": {
        "Nettoyage": (1.0, 5.0),
        "Séchage": (3.0, 10.0),
        "Tri": (3.0, 12.0),
        "Emballage": (0.5, 4.0),
    },
    "Mangue": {
        "Nettoyage": (1.0, 4.0),
        "Séchage": (5.0, 15.0),
        "Tri": (5.0, 18.0),
        "Emballage": (1.0, 5.0),
    },
}

HIGH_LOSS_RANGES: Dict[str, Dict[str, Tuple[float, float]]] = {
    "Mil": {
        "Séchage": (10.0, 16.0),
        "Tri": (10.0, 18.0),
    },
    "Arachide": {
        "Séchage": (12.0, 20.0),
        "Tri": (15.0, 25.0),
    },
    "Mangue": {
        "Séchage": (18.0, 35.0),
        "Tri": (20.0, 40.0),
        "Emballage": (6.0, 12.0),
    },
}


@dataclass(frozen=True)
class ScenarioWeights:
    normal: float = 0.43
    noisy_normal: float = 0.16
    low_loss_good_practice: float = 0.08
    medium_drying: float = 0.10
    high_drying: float = 0.05
    medium_sorting: float = 0.07
    high_sorting: float = 0.04
    process_issue: float = 0.03
    unexpected_high_packaging: float = 0.02
    unexpected_low_drying: float = 0.02


def _risk_from_loss(loss_pct: float) -> str:
    if loss_pct >= 12.0:
        return "high"
    if loss_pct >= 6.0:
        return "medium"
    return "low"


def _season_for_month(month: int) -> str:
    if month in {11, 12, 1, 2}:
        return "dry"
    if month in {3, 4, 5}:
        return "hot"
    return "rainy"


def _weighted_choice(rng: random.Random, weights: ScenarioWeights) -> str:
    table = list(weights.__dict__.items())
    pick = rng.random()
    cumulative = 0.0
    for name, prob in table:
        cumulative += prob
        if pick <= cumulative:
            return name
    return table[-1][0]


def _loss_for_stage(
    rng: random.Random,
    product: str,
    stage: str,
    scenario: str,
    month: int,
    is_small_batch: bool,
    stock_pressure_ratio: float,
) -> float:
    lo, hi = BASE_LOSS_RANGES[product][stage]

    # Rainy season (Jun-Oct) increases drying pressure in Senegal climate context.
    if stage == "Séchage" and month in {6, 7, 8, 9, 10}:
        hi += 2.5

    # Mangue sorting is more vulnerable to quality rejection spikes during pressure periods.
    if product == "Mangue" and stage == "Tri" and month in {7, 8, 9, 10}:
        hi += 3.0

    if scenario == "low_loss_good_practice":
        hi = max(lo + 0.4, (lo + hi) * 0.55)
    elif scenario == "noisy_normal":
        lo = max(0.3, lo - 1.0)
        hi = hi + 3.0
    elif scenario == "medium_drying" and stage == "Séchage":
        lo, hi = (max(lo, 8.0), max(hi, 14.0))
    elif scenario == "high_drying" and stage == "Séchage":
        lo, hi = HIGH_LOSS_RANGES[product].get("Séchage", (lo + 2.0, hi + 4.0))
    elif scenario == "medium_sorting" and stage == "Tri":
        lo, hi = (max(lo, 9.0), max(hi, 15.0))
    elif scenario == "high_sorting" and stage == "Tri":
        lo, hi = HIGH_LOSS_RANGES[product].get("Tri", (lo + 4.0, hi + 8.0))
    elif scenario == "unexpected_high_packaging" and stage == "Emballage":
        lo, hi = HIGH_LOSS_RANGES[product].get("Emballage", (6.0, 10.0))
    elif scenario == "unexpected_low_drying" and stage == "Séchage":
        lo, hi = (max(2.0, lo - 2.0), max(4.5, lo + 1.8))
    elif scenario == "process_issue":
        if stage in {"Tri", "Séchage"}:
            lo += 4.0
            hi += 9.0
        elif stage == "Emballage":
            lo += 2.0
            hi += 5.0
        else:
            lo += 1.0
            hi += 3.0

    # Stock pressure can propagate operational stress.
    if stock_pressure_ratio > 1.2:
        if stage in {"Tri", "Séchage"}:
            hi += 2.2
        if stage == "Emballage":
            hi += 1.0

    # Small-batch volatility is realistic.
    if is_small_batch:
        lo = max(0.2, lo - 0.6)
        hi += 1.8

    mode = lo + 0.32 * (hi - lo)
    value = rng.triangular(lo, hi, mode)
    value += rng.gauss(0.0, 0.6)

    # Add rare contradictory cases to avoid pattern-clean synthetic data.
    if stage == "Séchage" and rng.random() < 0.035:
        value *= rng.uniform(0.35, 0.55)
    if stage == "Emballage" and rng.random() < 0.045:
        value += rng.uniform(2.0, 4.5)

    return float(np.clip(value, 0.1, 55.0))


def _product_qty_range(product: str) -> Tuple[float, float]:
    if product == "Mangue":
        return (280.0, 1400.0)
    if product == "Arachide":
        return (420.0, 2100.0)
    return (520.0, 2600.0)


def _stock_level_for_product(rng: random.Random, product: str, batch_size: float, scenario: str) -> float:
    if product == "Mangue":
        base = rng.uniform(300.0, 2800.0)
    elif product == "Arachide":
        base = rng.uniform(250.0, 3600.0)
    else:
        base = rng.uniform(200.0, 4200.0)

    if scenario in {"high_drying", "high_sorting", "process_issue"}:
        base *= rng.uniform(1.15, 1.55)
    if scenario == "low_loss_good_practice":
        base *= rng.uniform(0.8, 1.0)

    # Keep some high-volume normal cases.
    if rng.random() < 0.10:
        base = max(base, batch_size * rng.uniform(1.2, 1.8))

    return round(max(0.0, base), 3)


def _build_rows(target_rows: int, seed: int, start_date: date) -> pd.DataFrame:
    rng = random.Random(seed)
    np.random.seed(seed)

    scenario_weights = ScenarioWeights()
    rows: List[Dict] = []
    batch_count = int(math.ceil(target_rows / len(STAGES)))

    for batch_index in range(batch_count):
        product = rng.choice(PRODUCTS)
        scenario = _weighted_choice(rng, scenario_weights)
        date_offset = batch_index
        batch_date = start_date + timedelta(days=date_offset)
        batch_id = f"{BENCHMARK_BATCH_PREFIX}{batch_index + 1:05d}"
        coop_id = f"benchmark-coop-{(batch_index % 6) + 1:02d}"

        qty_lo, qty_hi = _product_qty_range(product)
        batch_size = rng.uniform(qty_lo, qty_hi)
        if rng.random() < 0.12:
            batch_size *= rng.uniform(0.35, 0.65)
        is_small_batch = batch_size < ((qty_lo + qty_hi) * 0.35)

        stock_level = _stock_level_for_product(rng, product, batch_size, scenario)
        stock_pressure_ratio = stock_level / max(batch_size, 1e-6)

        qty_in = float(batch_size)
        for stage_order, stage in enumerate(STAGES, start=1):
            step_date = batch_date + timedelta(days=stage_order - 1)
            loss_pct = _loss_for_stage(
                rng=rng,
                product=product,
                stage=stage,
                scenario=scenario,
                month=step_date.month,
                is_small_batch=is_small_batch,
                stock_pressure_ratio=stock_pressure_ratio,
            )
            qty_out = max(0.0, qty_in * (1.0 - loss_pct / 100.0))

            rows.append(
                {
                    "batch_id": batch_id,
                    "cooperative_id": coop_id,
                    "product": product,
                    "process_type": stage,
                    "stage_canonical": normalize_stage(stage),
                    "qty_in": round(qty_in, 3),
                    "qty_out": round(qty_out, 3),
                    "batch_size": round(batch_size, 3),
                    "batch_current_qty": round(qty_out, 3),
                    "stock_level": round(stock_level, 3),
                    "date": step_date.isoformat(),
                    "season": _season_for_month(step_date.month),
                    "scenario": scenario,
                    "source_marker": BENCHMARK_MARKER,
                    "notes": (
                        f"{BENCHMARK_MARKER} scenario={scenario} product={product} "
                        f"stage={stage} source_profile=literature_informed"
                    ),
                }
            )
            qty_in = qty_out

    df = pd.DataFrame(rows)
    qty_in = pd.to_numeric(df["qty_in"], errors="coerce").fillna(0.0)
    qty_out = pd.to_numeric(df["qty_out"], errors="coerce").fillna(0.0)
    df["loss_pct"] = np.where(qty_in > 0, ((qty_in - qty_out) / qty_in) * 100.0, 0.0)
    df["loss_pct"] = pd.Series(df["loss_pct"]).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    df["efficiency_pct"] = np.where(qty_in > 0, qty_out / qty_in, 0.0)
    df["efficiency_pct"] = pd.Series(df["efficiency_pct"]).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    df["risk_level"] = df["loss_pct"].apply(_risk_from_loss)
    return df.head(target_rows).copy()


def _write_sources(artifacts_dir: Path) -> None:
    json_path = artifacts_dir / "benchmark_sources.json"
    md_path = artifacts_dir / "benchmark_sources.md"

    json_path.write_text(json.dumps(SOURCE_ENTRIES, indent=2, ensure_ascii=False))

    lines: List[str] = []
    lines.append("# Literature Sources for ML Benchmark")
    lines.append("")
    lines.append("This file documents source-backed references used to shape the literature-informed benchmark dataset.")
    lines.append("It is not cooperative operational data and must not be used to claim production accuracy.")
    lines.append("")
    for idx, item in enumerate(SOURCE_ENTRIES, start=1):
        lines.append(f"## {idx}. {item['title']}")
        lines.append(f"- URL: {item['url']}")
        lines.append(f"- Crop: {item['crop']}")
        lines.append(f"- Country/Region: {item['country_region']}")
        lines.append(f"- Relevant stages: {', '.join(item['relevant_stages'])}")
        lines.append(f"- Reported value/range: {item['reported_loss_value_or_range']}")
        lines.append(f"- Mapping to app stage: {item['app_stage_mapping']}")
        lines.append(f"- Reliability note: {item['reliability_note']}")
        lines.append(f"- Evidence: {item['evidence']}")
        lines.append(f"- Access date: {item['access_date']}")
        lines.append("")
    md_path.write_text("\n".join(lines))


def build_dataset(output_csv: Path, output_metadata: Path, output_methodology: Path, target_rows: int, seed: int) -> Dict:
    artifacts_dir = output_csv.parent
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    _write_sources(artifacts_dir)
    df = _build_rows(target_rows=target_rows, seed=seed, start_date=DEFAULT_START_DATE)
    df.to_csv(output_csv, index=False)

    risk_dist = df["risk_level"].value_counts(dropna=False).to_dict()
    metadata = {
        "dataset_type": "literature_informed_benchmark",
        "marker": BENCHMARK_MARKER,
        "batch_prefix": BENCHMARK_BATCH_PREFIX,
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "seed": seed,
        "row_count": int(len(df)),
        "batch_count": int(df["batch_id"].nunique()),
        "product_distribution": {str(k): int(v) for k, v in df["product"].value_counts(dropna=False).to_dict().items()},
        "stage_distribution": {str(k): int(v) for k, v in df["process_type"].value_counts(dropna=False).to_dict().items()},
        "risk_distribution": {str(k): int(v) for k, v in risk_dist.items()},
        "loss_distribution": {
            "mean": float(df["loss_pct"].mean()),
            "median": float(df["loss_pct"].median()),
            "p90": float(df["loss_pct"].quantile(0.90)),
            "p95": float(df["loss_pct"].quantile(0.95)),
            "max": float(df["loss_pct"].max()),
        },
        "source_count": len(SOURCE_ENTRIES),
        "sources_file_json": str((artifacts_dir / "benchmark_sources.json").as_posix()),
        "sources_file_md": str((artifacts_dir / "benchmark_sources.md").as_posix()),
        "assumption_policy": {
            "direct_source_ranges": [
                "APHLIS cumulative country/province and value-chain context for cereals",
                "SCIRP groundnut post-harvest loss bands (contextual, non-Senegal)",
            ],
            "assumption_derived_ranges": [
                "Mango stage-level ranges inferred from Senegal fruit-fly literature and horticultural post-harvest context",
                "Arachide and Mil stage decomposition where APHLIS provides cumulative or proxy value-chain context",
            ],
        },
        "not_for_production_training": True,
    }
    output_metadata.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))

    methodology_lines = [
        "# Literature-Informed Benchmark Methodology",
        "",
        "## Purpose",
        "This dataset is a literature-informed benchmark to test ML architecture behavior under source-backed distributions.",
        "It is not cooperative operational data and must not be used to claim production accuracy.",
        "",
        "## Data generation approach",
        "- Rows generated as process-step records with BENCH-ML-* batch IDs and [ML_LITERATURE_BENCHMARK] markers.",
        "- Products: Mangue, Arachide, Mil.",
        "- Stages: Nettoyage, Séchage, Tri, Emballage.",
        "- Loss ranges start from source-informed priors and are perturbed with seasonality, scenario noise, stock-pressure effects, and small-batch volatility.",
        "- Contradictory cases are injected (e.g., low drying loss during risky season, medium packaging loss, high sorting loss in otherwise normal periods).",
        "",
        "## Source mapping policy",
        "- APHLIS and AKP are used as primary cereal post-harvest references.",
        "- Mango and groundnut stage tails are partially assumption-derived where direct Senegal stage percentages are unavailable.",
        "- Each source entry is tracked in benchmark_sources.json/md with reliability notes.",
        "",
        "## Important limits",
        "- This is synthetic benchmark data informed by literature, not real cooperative trace data.",
        "- It can test potential and architecture sensitivity, but cannot validate production accuracy.",
    ]
    output_methodology.write_text("\n".join(methodology_lines))
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Build literature-informed benchmark dataset for ML architecture testing.")
    parser.add_argument("--output-csv", default="artifacts/literature_benchmark_dataset.csv")
    parser.add_argument("--output-metadata", default="artifacts/literature_benchmark_metadata.json")
    parser.add_argument("--output-methodology", default="artifacts/literature_benchmark_methodology.md")
    parser.add_argument("--target-rows", type=int, default=DEFAULT_TARGET_ROWS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    output_csv = Path(args.output_csv)
    output_metadata = Path(args.output_metadata)
    output_methodology = Path(args.output_methodology)

    metadata = build_dataset(
        output_csv=output_csv,
        output_metadata=output_metadata,
        output_methodology=output_methodology,
        target_rows=max(3000, int(args.target_rows)),
        seed=int(args.seed),
    )

    print(f"Saved benchmark dataset: {output_csv}")
    print(f"Saved benchmark metadata: {output_metadata}")
    print(f"Saved benchmark methodology: {output_methodology}")
    print(f"Rows: {metadata['row_count']}")
    print(f"Risk distribution: {metadata['risk_distribution']}")


if __name__ == "__main__":
    main()
