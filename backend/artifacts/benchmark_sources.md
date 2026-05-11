# Literature Sources for ML Benchmark

This file documents source-backed references used to shape the literature-informed benchmark dataset.
It is not cooperative operational data and must not be used to claim production accuracy.

## 1. Post Harvest Losses - losses_estimates - for crop Millets in country Senegal
- URL: https://archive.aphlis.net/?c_id=342&co_id=40&form=losses_estimates
- Crop: Mil
- Country/Region: Senegal
- Relevant stages: Séchage, Nettoyage, Tri
- Reported value/range: Country/province cumulative losses mostly around ~8.3% to 10.8%, with outlier 20.5% in one province-year listing.
- Mapping to app stage: Cumulative cereal chain used to calibrate Mil overall risk and upper-tail spikes; not a direct one-to-one stage table for app transformation steps.
- Reliability note: Official APHLIS archive table; model-based estimates from literature + contextual factors.
- Evidence: APHLIS states estimates are cumulative across harvesting, drying, handling, storage, and transport; Senegal millet table shows multiple province-year values around 8-11% and one 20.5% spike.
- Access date: 2026-05-07

## 2. Postharvest losses data tables (APHLIS)
- URL: https://www.aphlis.net/en/data/tables/dry-weight-losses/XAF/millet/all-years?metric=tns
- Crop: Mil
- Country/Region: Sub-Saharan Africa / Senegal context
- Relevant stages: Séchage, Nettoyage, Tri
- Reported value/range: Metric definitions and methodology; no direct Senegal stage-by-stage numeric range on this page.
- Mapping to app stage: Used as methodology source for mapping APHLIS handling operations to Nettoyage/Tri and drying to Séchage.
- Reliability note: Official APHLIS documentation page.
- Evidence: APHLIS defines % loss as cumulative across drying, handling operations (threshing/shelling/winnowing), storage and transport, with references traceable per estimate.
- Access date: 2026-05-07

## 3. Key facts about postharvest Sorghum losses in Senegal 2021 (APHLIS)
- URL: https://www.aphlis.net/en/data/tables/overview/SN/sorghum/2021
- Crop: Mil (proxy via cereal chain behavior)
- Country/Region: Senegal
- Relevant stages: Séchage, Nettoyage, Tri
- Reported value/range: 2021 sorghum chain example: harvesting/field drying 4.55%, threshing/shelling 3.6%, transport from field 2.17%, market storage 2.65%; total 11.6%.
- Mapping to app stage: Field drying informs Séchage baseline; threshing/shelling informs Nettoyage/Tri baseline for cereals.
- Reliability note: Official APHLIS country-year overview with stage-step decomposition.
- Evidence: Page reports Senegal sorghum 11.6% total PHL in 2021 and shows stepwise value-chain losses including field drying and threshing/shelling.
- Access date: 2026-05-07

## 4. Postharvest loss estimates for millet | Africa Knowledge Platform
- URL: https://africa-knowledge-platform.ec.europa.eu/dataset/postharvest-loss-estimates-millet
- Crop: Mil
- Country/Region: Africa
- Relevant stages: Séchage, Nettoyage, Tri
- Reported value/range: No fixed numeric Senegal stage range; dataset describes cumulative value-chain % loss and cautions on missing data.
- Mapping to app stage: Supports transparent benchmark assumption labeling where direct stage values are missing.
- Reliability note: EU-JRC Africa Knowledge Platform dataset description using APHLIS model outputs.
- Evidence: Dataset states cumulative loss includes harvesting, drying, threshing/shelling, winnowing, storage and transport; warns some gaps are filled with similar-crop/context studies.
- Access date: 2026-05-07

## 5. ORCHESTRATING SOLUTIONS... mango losses in Senegal
- URL: https://topjournals.org/index.php/TAJEAS/article/view/903
- Crop: Mangue
- Country/Region: Senegal
- Relevant stages: Tri, Séchage
- Reported value/range: Abstract cites severe fruit-fly impact and references estimates of large production reductions in affected regions.
- Mapping to app stage: Used to justify heavier high-loss tail in mango sorting and some drying scenarios during pressure periods.
- Reliability note: Peer-reviewed journal page with Senegal focus; cited values are broad and should not be used as direct stage rates.
- Evidence: Abstract highlights substantial economic losses from fruit fly infestations and major production reductions in parts of Senegal.
- Access date: 2026-05-07

## 6. Economic Impact of Fruit Flies in Mango Production in Senegal (Virginia Tech thesis)
- URL: https://vtechworks.lib.vt.edu/bitstream/handle/10919/82484/Diatta_PM_T_2016.pdf
- Crop: Mangue
- Country/Region: Ziguinchor/Casamance, Senegal
- Relevant stages: Tri
- Reported value/range: Household-level yearly losses from fruit-fly infestations estimated at 17.09% of average total household income (study context metric, not direct stage % mass loss).
- Mapping to app stage: Supports elevated mango rejection/loss risk scenarios at sorting due to infestation pressure.
- Reliability note: Academic thesis with field survey; economic-loss framing, not process-step mass-loss rates.
- Evidence: Abstract reports substantial household losses tied to fruit fly infestations in Ziguinchor and links losses to production/yield effects.
- Access date: 2026-05-07

## 7. Identification of Post-Harvest Operations... Groundnut by Mycotoxins (DOI:10.4236/as.2021.124026)
- URL: https://www.scirp.org/pdf/as_2021042014241041.pdf
- Crop: Arachide
- Country/Region: Chad (contextual African groundnut operations)
- Relevant stages: Séchage, Tri, Emballage
- Reported value/range: Survey reported post-harvest loss bands with 74.7% of respondents in 2-10% range and 25.3% in 10-50% range.
- Mapping to app stage: Used as contextual support for medium/high tails in Arachide drying and sorting when conditions are poor.
- Reliability note: Peer-reviewed but not Senegal-specific; used as contextual range support only.
- Evidence: Paper describes drying and storage practices and reports respondent-based loss bands up to 50% under poor post-harvest management.
- Access date: 2026-05-07

## 8. IITA Senegal Country Status Report (Aflasafe)
- URL: https://www.iita.org/wp-content/uploads/2021/03/Senegal-Country-Status-Report_Final-161120.pdf
- Crop: Arachide
- Country/Region: Senegal
- Relevant stages: Séchage, Emballage, Stockage context
- Reported value/range: Reports strong aflatoxin contamination risk and notes mitigation reduced contamination >80% in trials; no direct per-stage mass-loss percentages.
- Mapping to app stage: Supports higher drying-related risk scenarios for groundnut quality degradation and loss pressure.
- Reliability note: Institutional technical report for Senegal context; mostly contamination/economic risk evidence.
- Evidence: Report highlights contamination burden and emphasizes drying/storage discipline and mitigation impact in Senegal groundnut chain.
- Access date: 2026-05-07

## 9. FAO Statistics portal (FAOSTAT access)
- URL: https://www.fao.org/statistics/en/
- Crop: Mangue/Arachide/Mil context
- Country/Region: Global/Senegal
- Relevant stages: All (context only)
- Reported value/range: Production-context source only; no app-stage process-step loss rates.
- Mapping to app stage: Used for macro production context only, not stage-level loss calibration.
- Reliability note: Official FAO statistics entrypoint.
- Evidence: FAO page states FAOSTAT provides broad food/agriculture statistics and production context.
- Access date: 2026-05-07
