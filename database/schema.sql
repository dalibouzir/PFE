CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  coop_name VARCHAR(120) NOT NULL,
  region VARCHAR(80) NOT NULL,
  contact_name VARCHAR(120),
  phone VARCHAR(30),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inputs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  member_id UUID NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  product_type VARCHAR(80) NOT NULL,
  quantity_kg NUMERIC(12,2) NOT NULL,
  quality_grade VARCHAR(20),
  collected_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stocks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  member_id UUID NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  product_type VARCHAR(80) NOT NULL,
  location VARCHAR(120),
  quantity_kg NUMERIC(12,2) NOT NULL,
  moisture_pct NUMERIC(5,2),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS process_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  member_id UUID NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  input_id UUID REFERENCES inputs(id),
  step_name VARCHAR(80) NOT NULL,
  input_kg NUMERIC(12,2) NOT NULL,
  output_kg NUMERIC(12,2) NOT NULL,
  duration_hours NUMERIC(8,2),
  performed_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  member_id UUID NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  metric_date DATE NOT NULL,
  loss_pct NUMERIC(6,2),
  efficiency_score NUMERIC(6,2),
  anomaly_flag BOOLEAN DEFAULT FALSE,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source VARCHAR(200) NOT NULL,
  content TEXT NOT NULL,
  embedding VECTOR(3072) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding
ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
