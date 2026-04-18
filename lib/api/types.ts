export type UserRole = "admin" | "manager";

export type UserStatus = "active" | "disabled";

export type AuthUser = {
  id: string;
  full_name: string;
  email: string;
  phone?: string | null;
  role: UserRole;
  status: UserStatus;
  cooperative_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type AuthUserUpdate = {
  full_name?: string;
  email?: string;
  phone?: string | null;
  password?: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type CooperativeStatus = "active" | "onboarding" | "suspended";

export type Cooperative = {
  id: string;
  name: string;
  region: string;
  address: string;
  phone: string;
  status: CooperativeStatus;
  created_at: string;
  updated_at: string;
};

export type CooperativeCreate = {
  name: string;
  region: string;
  address: string;
  phone: string;
  status?: CooperativeStatus;
};

export type AdminUser = {
  id: string;
  full_name: string;
  email: string;
  phone?: string | null;
  role: UserRole;
  status: UserStatus;
  cooperative_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type ManagerCreate = {
  full_name: string;
  email: string;
  password: string;
  phone?: string | null;
  cooperative_id: string;
};

export type MemberStatus = "active" | "inactive" | "seasonal";

export type Member = {
  id: string;
  cooperative_id: string;
  code: string;
  full_name: string;
  phone: string;
  village?: string | null;
  main_product?: string | null;
  parcel_count: number;
  area_hectares: number;
  join_date?: string | null;
  specialty?: string | null;
  status: MemberStatus;
  created_at: string;
  updated_at: string;
};

export type MemberCreate = {
  code?: string;
  full_name: string;
  phone: string;
  village?: string | null;
  main_product?: string | null;
  parcel_count?: number;
  area_hectares?: number;
  join_date?: string | null;
  specialty?: string | null;
  status?: MemberStatus;
};

export type MemberUpdate = Partial<MemberCreate>;

export type Field = {
  id: string;
  member_id: string;
  cooperative_id: string;
  location: string;
  area: number;
  soil_type?: string | null;
  irrigation_type?: string | null;
  created_at: string;
  updated_at: string;
};

export type FieldCreate = {
  member_id: string;
  location: string;
  area: number;
  soil_type?: string | null;
  irrigation_type?: string | null;
};

export type FieldUpdate = Partial<FieldCreate>;

export type Product = {
  id: string;
  cooperative_id: string;
  name: string;
  category: string;
  unit: string;
  quality_grade?: string | null;
  created_at: string;
  updated_at: string;
};

export type ProductCreate = {
  name: string;
  category: string;
  unit: string;
  quality_grade?: string | null;
};

export type ProductUpdate = Partial<ProductCreate>;

export type Input = {
  id: string;
  cooperative_id: string;
  member_id: string;
  product_id: string;
  field_id?: string | null;
  date: string;
  quantity: number;
  grade: string;
  estimated_value?: number | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type InputCreate = {
  member_id: string;
  product_id: string;
  field_id?: string | null;
  date: string;
  quantity: number;
  grade: string;
  estimated_value?: number | null;
  status?: string;
};

export type InputUpdate = Partial<InputCreate>;

export type Stock = {
  id: string;
  cooperative_id: string;
  product_id: string;
  quantity: number;
  threshold: number;
  unit: string;
  last_updated: string;
  created_at: string;
  updated_at: string;
};

export type StockCreate = {
  product_id: string;
  quantity: number;
  threshold: number;
  unit: string;
};

export type StockUpdate = {
  threshold?: number;
  unit?: string;
};

export type StockAdjustment = {
  amount: number;
};

export type Batch = {
  id: string;
  cooperative_id: string;
  product_id: string;
  code: string;
  creation_date: string;
  initial_qty: number;
  current_qty: number;
  status: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type BatchCreate = {
  product_id: string;
  code: string;
  creation_date: string;
  initial_qty: number;
};

export type BatchUpdate = Partial<BatchCreate>;

export type BatchStatusUpdate = {
  status: string;
};

export type StockAlert = {
  stock_id: string;
  product_id: string;
  quantity: number;
  threshold: number;
  unit: string;
  deficit: number;
};

export type ProcessStep = {
  id: string;
  batch_id: string;
  type: string;
  date: string;
  qty_in: number;
  qty_out: number;
  waste_qty: number;
  notes?: string | null;
  status: string;
  duration_minutes?: number | null;
  created_at: string;
  updated_at: string;
  loss_pct: number;
  efficiency_pct: number;
  warning: boolean;
};

export type ProcessStepCreate = {
  batch_id: string;
  type: string;
  date: string;
  qty_in: number;
  qty_out: number;
  waste_qty?: number | null;
  notes?: string | null;
  status?: string;
  duration_minutes?: number | null;
};

export type ProcessStepUpdate = Partial<ProcessStepCreate>;

export type Recommendation = {
  batch_id: string;
  loss_pct: number;
  efficiency_pct: number;
  anomaly_detected: boolean;
  anomaly_score: number;
  risk_level: string;
  suggested_action: string;
  rationale: string;
  reasons: string[];
};

export type DashboardResponse = {
  total_production: number;
  loss_rate: number;
  efficiency_rate: number;
  number_of_active_batches: number;
  stock_alerts: StockAlert[];
  recent_inputs: Input[];
  recent_process_steps: ProcessStep[];
  recent_recommendations: Recommendation[];
};


export type ReferenceMetric = {
  id: string;
  source_id: string;
  country: string;
  region: string;
  crop: string;
  metric: string;
  period: string;
  value: number;
  unit: string;
  notes?: string | null;
};

export type KnowledgeChunk = {
  id: string;
  source_id: string;
  source_url: string;
  country: string;
  region: string;
  crop: string;
  topic: string;
  content: string;
};

export type ReferenceMetricListResponse = {
  total: number;
  items: ReferenceMetric[];
};

export type KnowledgeChunkListResponse = {
  total: number;
  items: KnowledgeChunk[];
};

export type ChatCitation = {
  source_id: string;
  source_url: string;
  region: string;
  crop: string;
  topic: string;
  excerpt: string;
};

export type ChatMetricFact = {
  source_id: string;
  region: string;
  crop: string;
  metric: string;
  period: string;
  value: number;
  unit: string;
  notes?: string | null;
};

export type ChatDashboardSnapshot = {
  cooperative_name?: string | null;
  region?: string | null;
  total_production: number;
  loss_rate: number;
  efficiency_rate: number;
  number_of_active_batches: number;
  stock_alerts: number;
};

export type AssistantChatRequest = {
  message: string;
  top_k?: number;
};

export type AssistantChatResponse = {
  success: boolean;
  message: string;
  grounded: boolean;
  mode: string;
  llm_provider?: string | null;
  llm_model?: string | null;
  citations: ChatCitation[];
  context_metrics: ChatMetricFact[];
  dashboard?: ChatDashboardSnapshot | null;
};
