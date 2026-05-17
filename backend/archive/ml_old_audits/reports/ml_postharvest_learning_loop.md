# WeeFarm Post-Récolte ML Learning Loop

## Objective
Build reliable ML only from real post-récolte operational evidence while preserving current operational safety constraints.

## Loop Structure
1. Lot execution in unchanged operational workflow.
2. Process-step records capture structured evidence (up to 4 stages per lot).
3. Feature layer builds historical + weather + duration context.
4. ML remains advisory unless readiness conditions are met.
5. Recommendations stay rule-based by default.
6. Operator action/outcome feedback accumulates evidence for future policy uplift validation.

## Observation Granularity
Per completed lot, potential stage observations:
- nettoyage
- sechage
- tri
- emballage

Each observation can contribute:
- product
- stage
- qty_in
- qty_out
- loss_pct
- efficiency_pct
- weather features
- duration features
- event timestamps
- recommendation outcome traces

## Truthful ML Positioning
- Current ML outputs are guidance signals.
- Regression/classification are not production-promoted without sufficient `N` and passing gates.
- Anomaly remains exploratory without labeled anomaly truth.
- Recommendation policy remains rule-based until outcome-backed uplift is proven.

## External Context Usage
- External Senegal datasets provide context only.
- They are not equivalent to lot-level supervised labels captured by WeeFarm operations.
- Cold-start priors can support explanation/fallback but cannot be mislabeled as app history.

## Promotion Control
- `ML_PROMOTED` is forbidden unless both conditions pass:
  - dataset readiness threshold
  - model gate status
- Otherwise maintain explicit non-promoted readiness states in API metadata.

## Safety Guarantees
- No database or Alembic migration.
- No workflow changes in pré-récolte/post-récolte/Collecte.
- No stock policy change.
