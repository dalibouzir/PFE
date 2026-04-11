INSERT INTO members (coop_name, region, contact_name, phone)
VALUES ('Casamance Mango Cooperative', 'Ziguinchor', 'Aissatou Ndiaye', '+221770000001')
ON CONFLICT DO NOTHING;

WITH coop AS (
  SELECT id FROM members WHERE coop_name = 'Casamance Mango Cooperative' LIMIT 1
)
INSERT INTO inputs (member_id, product_type, quantity_kg, quality_grade, collected_at)
SELECT id, 'mango', 1000.00, 'A', NOW() - INTERVAL '1 day' FROM coop;

WITH coop AS (
  SELECT id FROM members WHERE coop_name = 'Casamance Mango Cooperative' LIMIT 1
)
INSERT INTO process_steps (member_id, step_name, input_kg, output_kg, duration_hours, performed_at)
SELECT id, 'drying', 1000.00, 780.00, 16.00, NOW() FROM coop;

WITH coop AS (
  SELECT id FROM members WHERE coop_name = 'Casamance Mango Cooperative' LIMIT 1
)
INSERT INTO metrics (member_id, metric_date, loss_pct, efficiency_score, anomaly_flag, notes)
SELECT id, CURRENT_DATE, 22.00, 95.12, TRUE, 'Mango drying loss is above threshold.' FROM coop;
