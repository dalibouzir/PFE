# Senegal Data Sources for ML and RAG

## Goal

This document collects Senegal-focused sources that are close enough to the current WeeFarm scope to support two different pipelines:

1. Structured data for synthetic data generation, feature priors, and benchmark validation in the ML pipeline.
2. Textual context for the RAG assistant so answers are grounded in Senegal-specific agriculture, post-harvest risk, and cooperative operations.

The key rule is simple:

1. Use tables, time series, and numeric indicators for ML.
2. Use manuals, bulletins, value-chain reports, and policy notes for RAG.
3. Do not treat policy PDFs or narrative reports as supervised labels.

## Highest-value sources

### 1. Senegal annual agricultural survey

Source:
`https://microdata.fao.org/index.php/catalog/2522/study-description`

Why it matters:
1. Official survey coverage across all 45 departments of Senegal.
2. Covers rainfed agriculture, horticulture, and fruit growing.
3. Good backbone source for region, crop, plot, household, and production context.

What to use it for:
1. ML priors on region-level crop production context.
2. RAG explanations about where official agricultural data comes from.

Useful extracted facts:
1. The 2022-2023 survey covers all 45 departments.
2. The main agricultural season is July of year `n` to June of year `n+1`.
3. The scope includes rainfed agriculture, livestock, horticulture, and fruit-growing households.

### 2. AGRIDATA national production series for millet

Dataset page:
`https://agridata.ansd.sn/en/dataset/productionmil`

Direct file:
`https://agridata.ansd.sn/dataset/af8f6f25-a60b-4622-81c7-2dc0bdc00d7a/resource/6c5fe9c4-f0f5-4eba-b2e0-14631a077415/download/dapsa.xlsx`

Why it matters:
1. Official DAPSA series with yearly production values.
2. Good national baseline for demand, seasonality, and interannual volatility.

Useful extracted values:
1. `2019`: `807,044.07 t`
2. `2020`: `1,144,854.92 t`
3. `2021`: `1,039,859.75 t`
4. `2022`: `1,097,033.18 t`
5. `2023`: `1,260,709.44 t`

What to use it for:
1. ML: region/crop-level synthetic scaling and yearly production context.
2. RAG: high-level answers about millet importance and volatility in Senegal.

### 3. AGRIDATA national production series for groundnut

Dataset page:
`https://agridata.ansd.sn/en/dataset/productionarachide`

Direct file:
`https://agridata.ansd.sn/dataset/0850be0a-43eb-4b64-b2ff-2061b143f906/resource/0ee6f062-2c0c-4516-bcab-5effc23f0da8/download/dapsa_ind18.xlsx`

Why it matters:
1. Official DAPSA series for Senegal's core cash crop.
2. Good baseline for crop importance, volume, and year-to-year instability.

Useful extracted values:
1. `2019`: `1,421,288.11 t`
2. `2020`: `1,797,486.11 t`
3. `2021`: `1,677,803.56 t`
4. `2022`: `1,501,498.40 t`
5. `2023`: `1,675,328.82 t`

What to use it for:
1. ML: annual crop-weighting, synthetic data scaling, demand context.
2. RAG: explanations about why groundnut is strategically important.

### 4. AGRIDATA mango production endpoint

Dataset page:
`https://agridata.ansd.sn/fr/dataset/productionmangue`

Direct file:
`https://agridata.ansd.sn/dataset/1610fef9-5139-41ef-aecd-7506b25b21d8/resource/d83fb1d9-058d-474d-aac5-ab0a3f81a6aa/download/dhort_ind16.xlsx`

Important note:
1. The current downloadable file appears to be metadata-only, not a filled production series.
2. Keep the page and direct link in the source manifest, but do not assume it gives usable mango volumes by itself.

What to use it for:
1. RAG metadata and traceability.
2. Manual follow-up with DHORT or DAPSA reports if mango numeric series are needed.

### 5. ANACIM agrometeorological bulletins

Example bulletin:
`https://www.anacim.sn/IMG/pdf/bulletin_dec3_aout_2023.pdf`

Why it matters:
1. Senegal official weather and agrometeorology source.
2. Gives station rainfall, comparisons against normal, pest pressure, vegetation status, and market notes.
3. Strong RAG source and a useful structured-feature source if parsed.

Useful extracted facts from the late-August 2023 bulletin:
1. The bulletin compares station rainfall against the `1991-2020` normal.
2. Example cumulative rainfall normals by 31 August show a strong North-South gradient:
3. `Saint-Louis`: `143.6 mm`
4. `Bambey`: `341.4 mm`
5. `Kaolack`: `390.4 mm`
6. `Kaffrine`: `427.1 mm`
7. `Kolda`: `718.8 mm`
8. `Ziguinchor`: `909.2 mm`
9. `Cap Skirring`: `848.1 mm`
10. The same bulletin mentions pest pressure on `arachide` and `mil`.
11. It also mentions price references such as `445 F CFA/kg` for `mil souna`, `590 F CFA/kg` for `arachide coque`, and `1075 F CFA/kg` for `arachide decortiquee`.

What to use it for:
1. ML: weather-risk context, region-level humidity/rainfall priors, optional historical market features.
2. RAG: near-operational climate and pest context for grounded assistant answers.

### 6. World Bank Climate Knowledge Portal for Senegal

Source:
`https://climateknowledgeportal.worldbank.org/country/senegal/climate-data-historical`

Why it matters:
1. Historical climatology for Senegal based on observed data.
2. Useful for monthly seasonality, rainfall/drought framing, and region comparisons.

Useful extracted facts:
1. The current climatology shown is `1991-2020`.
2. The page is built from observed historical data and supports monthly seasonal-cycle analysis.
3. The portal explicitly highlights agriculture, water management, drought, and flood-risk planning as use cases.

What to use it for:
1. ML: monthly climate priors by region.
2. RAG: climate background context.

### 7. RVO Senegal Agricultural Value Chain Study

Source:
`https://english.rvo.nl/sites/default/files/2021/02/Senegal-Agricultural-Value-Chain-Study.pdf`

Why it matters:
1. Best single source found for Senegal mango chain structure, post-harvest constraints, and processing opportunities.
2. Strong RAG source and also a source of realistic scenario assumptions for synthetic data.

Useful extracted facts:
1. Estimated annual mango production is `65,000 to 75,000 tons`.
2. `Centre and Niayes` produce about `25,000 tons`.
3. `Casamance` produces about `40,000 to 50,000 tons`.
4. Most of the `16,000 tons` of fresh exports come from `Centre and Niayes`.
5. The main market window for Senegalese fresh mango in the EU is `July to September`.
6. In Casamance, only about `1,000 tons` are allegedly exported via Dakar exporters.
7. About two-thirds of Casamance mango is consumed near source or not sold because of `fruit fly infestation`, other pests and diseases, overripeness, or undesirable varieties.
8. The study explicitly identifies a `processing opportunity in Casamance` for `juice`, `dried fruit`, and `frozen cubes`.
9. It also flags a `yield gap` and `water scarcity / groundwater pressure` in the Centre and Niayes zones.

What to use it for:
1. ML: synthetic scenario generation for mango batches by region.
2. RAG: high-value operational context for the assistant.

### 8. FAO mango post-harvest operations compendium

Source:
`https://www.fao.org/fileadmin/user_upload/inpho/docs/Post_Harvest_Compendium_-_Mango.pdf`

Why it matters:
1. Not Senegal-specific, but very useful as agronomic and post-harvest best-practice context.
2. Should go into the RAG corpus, not directly into supervised labels.

Useful extracted facts:
1. The ideal post-harvest storage temperature for mangoes is stated as `12 C`.
2. Properly stored mango shelf life is described as `1 to 2 weeks`.
3. Mature green fruit can remain at room temperature for about `4 to 10 days`, depending on variety.
4. Fruit is often precooled to `10 to 12 C` before storage.
5. Poor harvesting and handling can push post-harvest losses into the `25 to 40 percent` range from harvest to consumption.
6. Harvesting with `8 to 10 mm` stalks helps reduce sap burn and storage disease risk.
7. The compendium repeatedly stresses sorting out bruised, immature, overripe, damaged, and diseased fruits before packing.

What to use it for:
1. ML: only as default rule thresholds or synthetic generation priors.
2. RAG: direct agronomic guidance for assistant answers.

### 9. FAO post-harvest grain storage references for Senegal millet

Sources:
`https://www.fao.org/4/AC301E/AC301e04.htm`
`https://www.fao.org/4/t0818e/T0818E08.htm`

Why it matters:
1. Useful for cereal storage context close to Senegal millet workflows.
2. Better suited to RAG and rule priors than supervised target labels.

Useful extracted facts:
1. FAO cites losses during storage over `30 months` in traditional granaries in Senegal of about `2.2 percent` for millet.
2. FAO also cites Senegal studies where properly dried and threshed sorghum and millet mixed with `30 percent sand` had reduced storage losses.

What to use it for:
1. ML: storage-loss priors and anomaly threshold design.
2. RAG: grain storage recommendations and background explanations.

### 10. IITA / Aflasafe Senegal country status report

Source:
`https://www.iita.org/wp-content/uploads/2021/03/Senegal-Country-Status-Report_Final-161120.pdf`

Why it matters:
1. Strong Senegal-specific groundnut and aflatoxin context.
2. Very useful for both RAG and synthetic anomaly generation around poor drying and storage.

Useful extracted facts:
1. Wet-harvested groundnuts left on the ground for several days are highlighted as a high-risk contamination pattern.
2. One cited Senegal finding reports `6 to 109 ppb` aflatoxin in artisanal groundnut oils.
3. Groundnut cake samples are reported at `18.97 to 389 ppb`.
4. Aflasafe SN01 was tested in `2010-2014` in `Diourbel` and `Kaolack`.
5. The report says Aflasafe SN01 reduced aflatoxin contamination by `more than 80 percent`, with even greater reduction during storage.
6. The report also notes millet, maize, sorghum, and rice in the wider cereal context.

What to use it for:
1. ML: synthetic high-risk groundnut storage scenarios and outcome labels.
2. RAG: recommendations around drying, storage, and aflatoxin prevention.

### 11. MASAE note on groundnut collection equipment

Source:
`https://agriculture.gouv.sn/modernisation-agricole-au-service-du-developpement-reintroduction-des-cribles-et-tarares-pour-une-filiere-arachide-competitive/`

Why it matters:
1. Recent Senegal government operational context for the groundnut chain.
2. Strong RAG context for explaining current modernization efforts.

Useful extracted facts from the published note:
1. PMAS `2026-2030` plans `20,000 cribles` and `1,500 tarares`.
2. The equipment is intended for `1,200` groundnut seed collection points.
3. For the `2025-2026` campaign, the state notes `1,900 cribles` and `100 tarares`.

What to use it for:
1. RAG only.
2. Do not treat this as ML supervision data.

## What should go into ML tables

Use these as structured inputs or priors:

1. National production series for `mil` and `arachide`.
2. Region-level rainfall normals and observed seasonal deviations from ANACIM and World Bank climate data.
3. Crop-region mappings: `Centre/Niayes`, `Casamance`, `Kaffrine`, `Kaolack`, `Diourbel`, `Kolda`, `Ziguinchor`, `Saint-Louis`, etc.
4. Historical market snapshots from bulletins as weak features, not ground truth.
5. Synthetic process-stage rows derived from Senegal crop and climate context plus FAO post-harvest rules.

Recommended ML features:

1. `country`, `region`, `agroecological_zone`, `crop`, `season_month`
2. `rainfall_normal_mm`, `rainfall_observed_mm`, `temperature_band`
3. `batch_size_kg`, `qty_in`, `qty_out`, `loss_pct`
4. `stage`, `duration_minutes`, `moisture_pct`, `storage_days`
5. `pest_pressure_flag`, `fruit_fly_flag`, `aflatoxin_risk_flag`
6. `market_price_fcfa_kg`, `export_grade_candidate`, `cooperative_scale`

## What should go into the RAG corpus

Chunk these as text documents:

1. RVO mango value-chain sections on production zones, export windows, fruit fly losses, and processing constraints.
2. ANACIM agrometeorological bulletins with rainfall, pests, vegetation, and market summaries.
3. FAO mango post-harvest best-practice sections on harvesting, grading, packing, bruising, and storage temperature.
4. FAO millet storage references for Senegal.
5. IITA aflatoxin and groundnut handling context.
6. MASAE modernization and mechanization notes for the groundnut chain.

Recommended RAG chunk tags:

1. `country: senegal`
2. `source_type: bulletin | manual | value_chain_report | policy_note`
3. `crop: mango | groundnut | millet`
4. `topic: climate | storage | pest | processing | logistics | prices | aflatoxin`
5. `region: niayes | casamance | kaolack | kaffrine | ziguinchor | kolda | saint-louis`

## Gaps that still need synthetic generation

These are still missing as clean Senegal process labels:

1. Stage-by-stage real cooperative yield data for cleaning, drying, sorting, and packaging.
2. Consistent mango batch records with moisture, bruising, grading, and rejection reason.
3. Cooperative-level groundnut storage duration, moisture, and fungal testing rows.
4. Operator feedback loops linking recommendation to observed outcome.

So the right MVP strategy is:

1. Use official Senegal crop, climate, and chain data as the realism layer.
2. Generate synthetic process-stage rows on top of that realism layer.
3. Feed the textual source documents into RAG as context.

## Recommended next step

Build two local assets from this research:

1. `senegal_structured_priors.csv`
2. `senegal_rag_corpus/` with chunked markdown or jsonl documents

The structured file should contain only normalized numeric/context fields.
The RAG corpus should keep textual explanation, guidance, and policy context.
