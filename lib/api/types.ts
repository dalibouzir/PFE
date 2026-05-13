export type UserRole = "admin" | "owner" | "manager" | "viewer";

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
  internal_code?: string;
  full_name: string;
  phone: string;
  village?: string | null;
  notes?: string | null;
  main_product?: string | null;
  secondary_products?: string | null;
  products?: string[] | null;
  parcel_count: number;
  area_hectares: number;
  join_date?: string | null;
  specialty?: string | null;
  status: MemberStatus;
  created_at: string;
  updated_at: string;
};

export type MemberCreate = {
  full_name: string;
  phone: string;
  village?: string | null;
  notes?: string | null;
  main_product?: string | null;
  secondary_products?: string | null;
  products?: string[] | null;
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

export type Parcel = {
  id: string;
  cooperative_id: string;
  member_id: string;
  name: string;
  surface_ha: number;
  main_culture: string;
  variety?: string | null;
  tree_count?: number | null;
  created_at: string;
  updated_at: string;
};

export type ParcelCreate = {
  farmer_id: string;
  name: string;
  surface_ha: number;
  main_culture: string;
  variety?: string | null;
  tree_count?: number | null;
};

export type ParcelUpdate = Partial<Omit<ParcelCreate, "farmer_id">>;

export type PreHarvestStepStatus = "pending" | "completed";

export type PreHarvestStep = {
  id: string;
  cooperative_id: string;
  parcel_id: string;
  member_id: string;
  step_order: number;
  step_key: string;
  category: string;
  label: string;
  icon: string;
  status: PreHarvestStepStatus;
  quantity_value?: number | null;
  quantity_unit?: string | null;
  operation_cost_fcfa?: number | null;
  realization_date?: string | null;
  observations?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type PreHarvestStepUpdate = {
  quantity_value?: number | null;
  quantity_unit?: string | null;
  operation_cost_fcfa?: number | null;
  realization_date: string;
  observations?: string | null;
};

export type GlobalCharge = {
  id: string;
  cooperative_id: string;
  member_id: string;
  parcel_id?: string | null;
  pre_harvest_step_id?: string | null;
  batch_id?: string | null;
  process_step_id?: string | null;
  charge_type: string;
  label: string;
  amount_fcfa: number;
  date: string;
  notes?: string | null;
  source_type: string;
  treasury_transaction_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type GlobalChargeCreate = {
  farmer_id: string;
  parcel_id?: string | null;
  charge_type: string;
  label: string;
  amount_fcfa: number;
  date: string;
  notes?: string | null;
};

export type GlobalChargeUpdate = Partial<Omit<GlobalChargeCreate, "farmer_id">>;

export type FarmerChargesResponse = {
  total_amount_fcfa: number;
  items: GlobalCharge[];
};

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
  unit?: "kg" | "ton";
  grade: string;
  estimated_value?: number | null;
  status?: string;
};

export type InputUpdate = Partial<InputCreate>;

export type FarmerAdvanceStatus = "active" | "cancelled";

export type FarmerAdvance = {
  id: string;
  cooperative_id: string;
  farmer_id: string;
  amount_fcfa: number;
  reason: string;
  advance_date: string;
  note?: string | null;
  status: FarmerAdvanceStatus;
  treasury_transaction_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type FarmerAdvanceCreate = {
  farmer_id: string;
  amount_fcfa: number;
  reason: string;
  advance_date: string;
  note?: string | null;
};

export type FarmerAdvanceUpdate = Partial<FarmerAdvanceCreate>;

export type FarmerAdvanceSummaryRow = {
  farmer_id: string;
  farmer_name: string;
  total_collected_quantity: number;
  total_amount_given: number;
  cost_per_kg?: number | null;
  last_modified: string;
  number_of_advances: number;
};

export type FarmerAdvanceSummaryStats = {
  total_advanced: number;
  total_advances_count: number;
  affected_farmers_count: number;
  average_cost_per_kg?: number | null;
};

export type FarmerAdvanceSummaryResponse = {
  items: FarmerAdvanceSummaryRow[];
  stats: FarmerAdvanceSummaryStats;
};

export type FarmerAdvanceFarmerSummary = {
  farmer_id: string;
  farmer_name: string;
  total_collected_quantity: number;
  total_amount_given: number;
  cost_per_kg?: number | null;
  last_modified: string;
  number_of_advances: number;
};

export type FarmerAdvanceFarmerDetailResponse = {
  summary: FarmerAdvanceFarmerSummary;
  advances: FarmerAdvance[];
};

export type TreasuryTransactionType = "income" | "expense";
export type TreasuryTransactionStatus = "recorded" | "cancelled";

export type TreasuryTransaction = {
  id: string;
  cooperative_id: string;
  reference: string;
  transaction_date: string;
  type: TreasuryTransactionType;
  category: string;
  label: string;
  amount_fcfa: number;
  note?: string | null;
  status: TreasuryTransactionStatus;
  source_type: string;
  source_id?: string | null;
  farmer_id?: string | null;
  farmer_name?: string | null;
  created_at: string;
  updated_at: string;
};

export type TreasuryTransactionCreate = {
  transaction_date: string;
  type: TreasuryTransactionType;
  category: string;
  label: string;
  amount_fcfa: number;
  note?: string | null;
  source_type?: string;
  farmer_id?: string | null;
};

export type TreasuryTransactionUpdate = Partial<TreasuryTransactionCreate>;

export type TreasuryStats = {
  total_given: number;
  total_expenses: number;
  total_income: number;
  current_balance: number;
};

export type Stock = {
  id: string;
  cooperative_id: string;
  product_id: string;
  quantity: number;
  threshold: number;
  total_stock: number;
  available_stock: number;
  reserved_in_lots: number;
  processed_output: number;
  total_stock_kg: number;
  available_stock_kg: number;
  reserved_in_lots_kg: number;
  processed_output_kg: number;
  threshold_kg: number;
  unit: string;
  last_updated: string;
  created_at: string;
  updated_at: string;
};

export type StockCreate = {
  product_id: string;
  quantity?: number;
  threshold: number;
  unit: "kg" | "ton";
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
  unit: "kg" | "ton";
  ordered_process_steps: string[];
  initial_qty: number;
  current_qty: number;
  initial_qty_display: number;
  current_qty_display: number;
  status: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
};

export type BatchCreate = {
  product_id: string;
  creation_date: string;
  initial_qty: number;
  unit: "kg" | "ton";
  process_steps: string[];
};

export type BatchUpdate = {
  process_steps?: string[];
};

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
  deficit_kg: number;
};

export type ProcessStep = {
  id: string;
  batch_id: string;
  sequence_order: number;
  type: string;
  date: string;
  loss_value: number;
  loss_unit: "kg" | "ton";
  normalized_loss_value: number;
  qty_in: number;
  qty_out: number;
  waste_qty: number;
  notes?: string | null;
  status: string;
  executed_at?: string | null;
  duration_minutes?: number | null;
  created_at: string;
  updated_at: string;
  loss_pct: number;
  efficiency_pct: number;
  warning: boolean;
};

export type ProcessStepCreate = {
  batch_id: string;
  type?: string;
  date?: string;
  loss_value: number;
  loss_unit: "kg" | "ton";
  notes?: string | null;
  duration_minutes?: number | null;
};

export type ProcessStepUpdate = Partial<ProcessStepCreate>;

export type BatchReferencePreview = {
  code: string;
};

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

export type ChatUIBlock = {
  type: string;
  title: string;
  payload: Record<string, unknown>;
};

export type AssistantChatRequest = {
  session_id?: string;
  message: string;
  top_k?: number;
};

export type AssistantChatResponse = {
  success: boolean;
  session_id: string;
  user_message_id?: string | null;
  assistant_message_id?: string | null;
  message: string;
  grounded: boolean;
  mode: string;
  llm_provider?: string | null;
  llm_model?: string | null;
  citations: ChatCitation[];
  context_metrics: ChatMetricFact[];
  dashboard?: ChatDashboardSnapshot | null;
  ui_blocks: ChatUIBlock[];
};

export type AgentRoute =
  | "SQL_ONLY"
  | "RAG_ONLY"
  | "ML_ONLY"
  | "RECOMMENDATION_ONLY"
  | "HYBRID_SQL_RAG"
  | "HYBRID_SQL_ML"
  | "HYBRID_RAG_RECOMMENDATION"
  | "HYBRID_FULL"
  | "SMALL_TALK"
  | "OUT_OF_SCOPE";

export type AgentSource = {
  type: "sql" | "rag" | "ml" | string;
  table?: string;
  label?: string;
  record_count?: number;
  related_batch?: string;
  related_product?: string;
  related_stage?: string;
  document_id?: string;
  chunk_id?: string;
  title?: string;
  topic?: string;
  score?: number;
  model?: string;
  risk_level?: string;
};

export type AgentChatRequest = {
  message: string;
  conversation_id?: string | null;
  user_id?: string | null;
  language?: string | null;
};

export type AgentChatResponse = {
  answer: string;
  route: AgentRoute;
  agents_used: string[];
  response_blocks?: AgentResponseBlock[];
  sources: AgentSource[];
  confidence: number;
  warnings: string[];
  metadata: Record<string, unknown>;
};

export type AgentResponseBlock = {
  type:
    | "summary"
    | "table"
    | "recommendations"
    | "best_practices"
    | "chart"
    | "sources"
    | "warnings"
    | string;
  title?: string;
  content?: string;
  columns?: string[];
  rows?: Array<Array<string | number>>;
  items?: Array<Record<string, unknown> | string>;
  chart_type?: "bar" | "line" | string;
  x_key?: string;
  y_key?: string;
  data?: Array<Record<string, unknown>>;
};

export type ChatSession = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview?: string | null;
  last_message_at?: string | null;
};

export type ChatSessionCreate = {
  title?: string | null;
};

export type ChatMessage = {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  mode?: string | null;
  llm_provider?: string | null;
  llm_model?: string | null;
  citations: ChatCitation[];
  context_metrics: ChatMetricFact[];
  dashboard?: ChatDashboardSnapshot | null;
  ui_blocks: ChatUIBlock[];
};

export type ChatMessageCreate = {
  message: string;
};

export type CatalogStatus = "active" | "hidden";
export type CommercialOrderStatus =
  | "received"
  | "confirmed"
  | "preparing"
  | "ready"
  | "delivered"
  | "paid"
  | "refused";
export type CommercialInvoiceStatus = "pending" | "paid";

export type CatalogProduct = {
  id: string;
  cooperative_id: string;
  source_product_id?: string | null;
  source_product_name?: string | null;
  name: string;
  description?: string | null;
  category: string;
  sale_unit: "kg" | "ton";
  icon?: string | null;
  sale_price_fcfa: number;
  cost_price_fcfa: number;
  min_order_qty: number;
  total_stock: number;
  reserved_stock: number;
  available_stock: number;
  total_stock_kg: number;
  reserved_stock_kg: number;
  available_stock_kg: number;
  margin_percent: number;
  status: CatalogStatus;
  low_stock: boolean;
  created_at: string;
  updated_at: string;
};

export type CatalogProductCreate = {
  source_product_id: string;
  name: string;
  description?: string | null;
  category: string;
  sale_unit: "kg" | "ton";
  icon?: string | null;
  sale_price_fcfa: number;
  cost_price_fcfa: number;
  min_order_qty: number;
  allocated_quantity: number;
};

export type CatalogProductUpdate = Partial<
  Omit<CatalogProductCreate, "source_product_id" | "allocated_quantity">
>;

export type CommercialOrderLine = {
  id: string;
  catalog_product_id: string;
  product_name: string;
  unit: "kg" | "ton";
  quantity: number;
  unit_price_fcfa: number;
  line_total_fcfa: number;
};

export type CommercialOrder = {
  id: string;
  cooperative_id: string;
  order_number: string;
  customer_name: string;
  customer_phone?: string | null;
  customer_email?: string | null;
  customer_address?: string | null;
  payment_method?: string | null;
  notes?: string | null;
  status: CommercialOrderStatus;
  subtotal_fcfa: number;
  tax_rate: number;
  tax_amount_fcfa: number;
  total_amount_fcfa: number;
  source: string;
  locked: boolean;
  received_at: string;
  confirmed_at?: string | null;
  preparing_at?: string | null;
  ready_at?: string | null;
  delivered_at?: string | null;
  paid_at?: string | null;
  refused_at?: string | null;
  refused_reason?: string | null;
  lines: CommercialOrderLine[];
  created_at: string;
  updated_at: string;
};

export type CommercialOrderIntake = {
  customer_name: string;
  customer_phone?: string | null;
  customer_email?: string | null;
  customer_address?: string | null;
  payment_method?: string | null;
  notes?: string | null;
  lines: Array<{
    catalog_product_id: string;
    quantity: number;
  }>;
};

export type CommercialOrderStatusUpdate = {
  status: CommercialOrderStatus;
  refused_reason?: string | null;
};

export type CommercialOrderStats = {
  total: number;
  received: number;
  confirmed: number;
  preparing: number;
  ready: number;
  delivered: number;
  paid: number;
  refused: number;
  new_count: number;
  in_progress_count: number;
  paid_this_month_fcfa: number;
};

export type CommercialInvoiceLine = {
  id: string;
  description: string;
  unit: string;
  quantity: number;
  unit_price_fcfa: number;
  line_total_fcfa: number;
};

export type CommercialInvoice = {
  id: string;
  cooperative_id: string;
  order_id: string;
  order_number: string;
  invoice_number: string;
  issue_date: string;
  due_date?: string | null;
  status: CommercialInvoiceStatus;
  customer_name: string;
  customer_phone?: string | null;
  customer_email?: string | null;
  customer_address?: string | null;
  subtotal_fcfa: number;
  tax_rate: number;
  tax_amount_fcfa: number;
  total_amount_fcfa: number;
  paid_at?: string | null;
  lines: CommercialInvoiceLine[];
  created_at: string;
  updated_at: string;
};

export type CommercialInvoiceStats = {
  total_invoiced_fcfa: number;
  paid_fcfa: number;
  pending_fcfa: number;
  paid_rate_percent: number;
};
