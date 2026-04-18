"use client";

import type { RequestOptions } from "@/lib/api/client";
import type {
  AdminUser,
  AssistantChatResponse,
  AuthUser,
  Batch,
  Cooperative,
  DashboardResponse,
  Field,
  Input,
  KnowledgeChunkListResponse,
  Member,
  ProcessStep,
  Product,
  Recommendation,
  ReferenceMetricListResponse,
  Stock,
  StockAlert,
  TokenResponse,
} from "@/lib/api/types";

const STORE_KEY = "weefarm_demo_state_v1";

class MockApiError extends Error {
  status: number;
  details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

type DemoState = {
  cooperatives: Cooperative[];
  users: AuthUser[];
  members: Member[];
  fields: Field[];
  products: Product[];
  inputs: Input[];
  stocks: Stock[];
  batches: Batch[];
  processSteps: ProcessStep[];
};

function nowIso() {
  return new Date().toISOString();
}

function dateDaysAgo(days: number) {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

function uid(prefix: string) {
  const rand = Math.random().toString(36).slice(2, 10);
  return `${prefix}-${rand}`;
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function defaultState(): DemoState {
  const createdAt = nowIso();

  const cooperative: Cooperative = {
    id: "coop-001",
    name: "WeeFarm Opérations Coopérative",
    region: "Thiès",
    address: "Thiès, Sénégal",
    phone: "+221 77 123 45 67",
    status: "active",
    created_at: createdAt,
    updated_at: createdAt,
  };

  const manager: AuthUser = {
    id: "usr-manager-001",
    full_name: "mohamed ali bouzir",
    email: "manager@weefarm.local",
    phone: "+221 77 223 34 45",
    role: "manager",
    status: "active",
    cooperative_id: cooperative.id,
    created_at: createdAt,
    updated_at: createdAt,
  };

  const admin: AuthUser = {
    id: "usr-admin-001",
    full_name: "Admin WeeFarm",
    email: "admin@weefarm.local",
    phone: "+221 77 000 00 00",
    role: "admin",
    status: "active",
    cooperative_id: null,
    created_at: createdAt,
    updated_at: createdAt,
  };

  const products: Product[] = [
    { id: "prd-mangue", cooperative_id: cooperative.id, name: "Mangue", category: "Fruits", unit: "kg", quality_grade: "A", created_at: createdAt, updated_at: createdAt },
    { id: "prd-oignon", cooperative_id: cooperative.id, name: "Oignon", category: "Légumes", unit: "kg", quality_grade: "A", created_at: createdAt, updated_at: createdAt },
    { id: "prd-arachide", cooperative_id: cooperative.id, name: "Arachide", category: "Oléagineux", unit: "kg", quality_grade: "A", created_at: createdAt, updated_at: createdAt },
    { id: "prd-bissap", cooperative_id: cooperative.id, name: "Bissap", category: "Fleurs", unit: "kg", quality_grade: "B", created_at: createdAt, updated_at: createdAt },
    { id: "prd-mil", cooperative_id: cooperative.id, name: "Mil", category: "Céréales", unit: "kg", quality_grade: "B", created_at: createdAt, updated_at: createdAt },
  ];

  const members: Member[] = [
    {
      id: "mbr-001",
      cooperative_id: cooperative.id,
      code: "MBR-001",
      full_name: "Mamadou Diallo",
      phone: "+221 77 101 10 10",
      village: "Thiès",
      main_product: "Mangue",
      parcel_count: 2,
      area_hectares: 3.1,
      join_date: "2026-01-12",
      specialty: "Mangue",
      status: "active",
      created_at: createdAt,
      updated_at: createdAt,
    },
    {
      id: "mbr-002",
      cooperative_id: cooperative.id,
      code: "MBR-002",
      full_name: "Fatou Ndiaye",
      phone: "+221 77 202 20 20",
      village: "Mboro",
      main_product: "Oignon",
      parcel_count: 3,
      area_hectares: 2.8,
      join_date: "2026-01-25",
      specialty: "Oignon",
      status: "active",
      created_at: createdAt,
      updated_at: createdAt,
    },
    {
      id: "mbr-003",
      cooperative_id: cooperative.id,
      code: "MBR-003",
      full_name: "Abdou Seck",
      phone: "+221 77 303 30 30",
      village: "Pout",
      main_product: "Arachide",
      parcel_count: 2,
      area_hectares: 1.9,
      join_date: "2026-02-03",
      specialty: "Arachide",
      status: "active",
      created_at: createdAt,
      updated_at: createdAt,
    },
  ];

  const fields: Field[] = [
    { id: "fld-001", member_id: "mbr-001", cooperative_id: cooperative.id, location: "Thiès Nord", area: 1.8, soil_type: "argileux", irrigation_type: "goutte-a-goutte", created_at: createdAt, updated_at: createdAt },
    { id: "fld-002", member_id: "mbr-001", cooperative_id: cooperative.id, location: "Thiès Sud", area: 1.3, soil_type: "sableux", irrigation_type: "gravitaire", created_at: createdAt, updated_at: createdAt },
    { id: "fld-003", member_id: "mbr-002", cooperative_id: cooperative.id, location: "Mboro Ouest", area: 2.8, soil_type: "limoneux", irrigation_type: "goutte-a-goutte", created_at: createdAt, updated_at: createdAt },
    { id: "fld-004", member_id: "mbr-003", cooperative_id: cooperative.id, location: "Pout Centre", area: 1.9, soil_type: "argileux", irrigation_type: "pluvial", created_at: createdAt, updated_at: createdAt },
  ];

  const inputs: Input[] = [
    { id: "inp-001", cooperative_id: cooperative.id, member_id: "mbr-001", product_id: "prd-mangue", field_id: "fld-001", date: dateDaysAgo(2), quantity: 480, grade: "A", estimated_value: 112800, status: "validated", created_at: createdAt, updated_at: createdAt },
    { id: "inp-002", cooperative_id: cooperative.id, member_id: "mbr-002", product_id: "prd-oignon", field_id: "fld-003", date: dateDaysAgo(3), quantity: 320, grade: "A", estimated_value: 58880, status: "validated", created_at: createdAt, updated_at: createdAt },
    { id: "inp-003", cooperative_id: cooperative.id, member_id: "mbr-003", product_id: "prd-arachide", field_id: "fld-004", date: dateDaysAgo(4), quantity: 650, grade: "B", estimated_value: 234000, status: "pending", created_at: createdAt, updated_at: createdAt },
    { id: "inp-004", cooperative_id: cooperative.id, member_id: "mbr-001", product_id: "prd-mangue", field_id: "fld-002", date: dateDaysAgo(5), quantity: 920, grade: "A", estimated_value: 216200, status: "validated", created_at: createdAt, updated_at: createdAt },
    { id: "inp-005", cooperative_id: cooperative.id, member_id: "mbr-001", product_id: "prd-mangue", field_id: "fld-001", date: dateDaysAgo(6), quantity: 340, grade: "A", estimated_value: 79900, status: "validated", created_at: createdAt, updated_at: createdAt },
  ];

  const stocks: Stock[] = [
    { id: "stk-001", cooperative_id: cooperative.id, product_id: "prd-mangue", quantity: 1240, threshold: 400, unit: "kg", last_updated: createdAt, created_at: createdAt, updated_at: createdAt },
    { id: "stk-002", cooperative_id: cooperative.id, product_id: "prd-oignon", quantity: 380, threshold: 220, unit: "kg", last_updated: createdAt, created_at: createdAt, updated_at: createdAt },
    { id: "stk-003", cooperative_id: cooperative.id, product_id: "prd-arachide", quantity: 650, threshold: 260, unit: "kg", last_updated: createdAt, created_at: createdAt, updated_at: createdAt },
    { id: "stk-004", cooperative_id: cooperative.id, product_id: "prd-bissap", quantity: 95, threshold: 120, unit: "kg", last_updated: createdAt, created_at: createdAt, updated_at: createdAt },
    { id: "stk-005", cooperative_id: cooperative.id, product_id: "prd-mil", quantity: 45, threshold: 110, unit: "kg", last_updated: createdAt, created_at: createdAt, updated_at: createdAt },
  ];

  const batches: Batch[] = [
    {
      id: "lot-001",
      cooperative_id: cooperative.id,
      product_id: "prd-mangue",
      code: "LOT-MG-001",
      creation_date: dateDaysAgo(18),
      initial_qty: 3200,
      current_qty: 2840,
      status: "in_progress",
      created_by_user_id: manager.id,
      created_at: createdAt,
      updated_at: createdAt,
    },
    {
      id: "lot-002",
      cooperative_id: cooperative.id,
      product_id: "prd-oignon",
      code: "LOT-OI-001",
      creation_date: dateDaysAgo(24),
      initial_qty: 1500,
      current_qty: 1290,
      status: "created",
      created_by_user_id: manager.id,
      created_at: createdAt,
      updated_at: createdAt,
    },
  ];

  const processSteps: ProcessStep[] = [
    { id: "stp-001", batch_id: "lot-001", type: "Tri", date: dateDaysAgo(6), qty_in: 733, qty_out: 707, waste_qty: 26, notes: "Tri initial", status: "completed", duration_minutes: 90, created_at: createdAt, updated_at: createdAt, loss_pct: 3.5, efficiency_pct: 96.5, warning: false },
    { id: "stp-002", batch_id: "lot-001", type: "Sechage", date: dateDaysAgo(5), qty_in: 707, qty_out: 672, waste_qty: 35, notes: "Séchage mécanique", status: "completed", duration_minutes: 140, created_at: createdAt, updated_at: createdAt, loss_pct: 4.9, efficiency_pct: 95.1, warning: false },
    { id: "stp-003", batch_id: "lot-001", type: "Nettoyage", date: dateDaysAgo(4), qty_in: 672, qty_out: 631, waste_qty: 41, notes: "Nettoyage final", status: "completed", duration_minutes: 70, created_at: createdAt, updated_at: createdAt, loss_pct: 6.1, efficiency_pct: 93.9, warning: false },
    { id: "stp-004", batch_id: "lot-001", type: "Conditionnement", date: dateDaysAgo(3), qty_in: 631, qty_out: 618, waste_qty: 13, notes: "Conditionnement", status: "completed", duration_minutes: 80, created_at: createdAt, updated_at: createdAt, loss_pct: 2.0, efficiency_pct: 98.0, warning: false },
  ];

  return {
    cooperatives: [cooperative],
    users: [manager, admin],
    members,
    fields,
    products,
    inputs,
    stocks,
    batches,
    processSteps,
  };
}

function getState(): DemoState {
  const raw = window.localStorage.getItem(STORE_KEY);
  if (!raw) {
    const seeded = defaultState();
    window.localStorage.setItem(STORE_KEY, JSON.stringify(seeded));
    return seeded;
  }
  try {
    return JSON.parse(raw) as DemoState;
  } catch {
    const seeded = defaultState();
    window.localStorage.setItem(STORE_KEY, JSON.stringify(seeded));
    return seeded;
  }
}

function setState(next: DemoState) {
  window.localStorage.setItem(STORE_KEY, JSON.stringify(next));
}

function parsePath(path: string) {
  const [pathname, query = ""] = path.split("?");
  return { pathname, query: new URLSearchParams(query) };
}

function bodyAsObject<T>(body: RequestOptions["body"]): T {
  if (!body) return {} as T;
  if (typeof body === "string") return JSON.parse(body) as T;
  return body as T;
}

function authUserFromHeaders(state: DemoState, headers?: HeadersInit | undefined) {
  const headerObj = headers instanceof Headers ? headers : new Headers(headers || {});
  const auth = headerObj.get("Authorization");
  if (!auth) throw new MockApiError("Non authentifié.", 401);
  const token = auth.replace("Bearer ", "").trim();
  if (token === "demo-admin-token") {
    return state.users.find((user) => user.role === "admin") ?? null;
  }
  return state.users.find((user) => user.role === "manager") ?? null;
}

function mapRecommendation(step: ProcessStep): Recommendation {
  const risk = step.loss_pct >= 15 ? "high" : step.loss_pct >= 8 ? "medium" : "low";
  return {
    batch_id: step.batch_id,
    loss_pct: Number(step.loss_pct.toFixed(2)),
    efficiency_pct: Number(step.efficiency_pct.toFixed(2)),
    anomaly_detected: step.warning || step.loss_pct >= 10,
    anomaly_score: Math.min(Math.round(step.loss_pct * 4.2), 100),
    risk_level: risk,
    suggested_action:
      step.loss_pct >= 10
        ? "Réduire la durée de séchage et vérifier l'humidité du lot avant l'étape suivante."
        : "Maintenir le process actuel et renforcer le contrôle qualité en sortie d'étape.",
    rationale: `Perte observée ${step.loss_pct.toFixed(1)}% sur l'étape ${step.type}.`,
    reasons: [`Perte ${step.loss_pct.toFixed(1)}%`, `Efficacité ${step.efficiency_pct.toFixed(1)}%`],
  };
}

function buildDashboard(state: DemoState): DashboardResponse {
  const totalProduction = state.processSteps.reduce((sum, step) => sum + step.qty_out, 0);
  const avgLoss = state.processSteps.length
    ? state.processSteps.reduce((sum, step) => sum + step.loss_pct, 0) / state.processSteps.length
    : 0;
  const avgEfficiency = state.processSteps.length
    ? state.processSteps.reduce((sum, step) => sum + step.efficiency_pct, 0) / state.processSteps.length
    : 0;
  const alerts: StockAlert[] = state.stocks
    .filter((stock) => stock.quantity < stock.threshold)
    .map((stock) => ({
      stock_id: stock.id,
      product_id: stock.product_id,
      quantity: stock.quantity,
      threshold: stock.threshold,
      unit: stock.unit,
      deficit: Number((stock.threshold - stock.quantity).toFixed(2)),
    }));

  const recentInputs = [...state.inputs].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 8);
  const recentSteps = [...state.processSteps].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 8);
  const recentRecommendations = recentSteps.slice(0, 6).map(mapRecommendation);

  return {
    total_production: Number(totalProduction.toFixed(2)),
    loss_rate: Number(avgLoss.toFixed(2)),
    efficiency_rate: Number(avgEfficiency.toFixed(2)),
    number_of_active_batches: state.batches.filter((batch) => batch.status !== "archived").length,
    stock_alerts: alerts,
    recent_inputs: recentInputs,
    recent_process_steps: recentSteps,
    recent_recommendations: recentRecommendations,
  };
}

export async function mockApiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const state = getState();
  const { pathname, query } = parsePath(path);

  if (pathname === "/auth/login" && method === "POST") {
    const payload = bodyAsObject<{ email?: string; password?: string }>(options.body);
    if (!payload.email || !payload.password) throw new MockApiError("Email et mot de passe requis.", 400);
    const isAdmin = payload.email.toLowerCase().includes("admin");
    const tokenResponse: TokenResponse = {
      access_token: isAdmin ? "demo-admin-token" : "demo-manager-token",
      token_type: "bearer",
    };
    return tokenResponse as T;
  }

  if (pathname === "/auth/me" && method === "GET") {
    const user = authUserFromHeaders(state, options.headers);
    if (!user) throw new MockApiError("Utilisateur introuvable.", 404);
    return deepClone(user) as T;
  }

  if (pathname === "/auth/me" && method === "PATCH") {
    const user = authUserFromHeaders(state, options.headers);
    if (!user) throw new MockApiError("Utilisateur introuvable.", 404);
    const payload = bodyAsObject<Partial<AuthUser>>(options.body);
    const idx = state.users.findIndex((row) => row.id === user.id);
    state.users[idx] = { ...state.users[idx], ...payload, updated_at: nowIso() };
    setState(state);
    return deepClone(state.users[idx]) as T;
  }

  if (pathname === "/admin/cooperatives" && method === "GET") return deepClone(state.cooperatives) as T;
  if (pathname === "/admin/users" && method === "GET") return deepClone(state.users as AdminUser[]) as T;
  if (pathname === "/admin/cooperatives" && method === "POST") {
    const payload = bodyAsObject<Partial<Cooperative>>(options.body);
    const row: Cooperative = {
      id: uid("coop"),
      name: payload.name || "Nouvelle coopérative",
      region: payload.region || "Thiès",
      address: payload.address || "Sénégal",
      phone: payload.phone || "+221 77 000 00 00",
      status: payload.status || "active",
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    state.cooperatives.push(row);
    setState(state);
    return deepClone(row) as T;
  }

  if (pathname === "/admin/managers" && method === "POST") {
    const payload = bodyAsObject<{ full_name?: string; email?: string; phone?: string; cooperative_id?: string }>(options.body);
    const row: AdminUser = {
      id: uid("usr"),
      full_name: payload.full_name || "Nouveau manager",
      email: payload.email || `${uid("manager")}@weefarm.local`,
      phone: payload.phone ?? null,
      role: "manager",
      status: "active",
      cooperative_id: payload.cooperative_id || state.cooperatives[0]?.id || null,
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    state.users.push(row);
    setState(state);
    return deepClone(row) as T;
  }

  const adminUserAction = pathname.match(/^\/admin\/users\/([^/]+)\/(disable|enable)$/);
  if (adminUserAction && method === "PATCH") {
    const [, id, action] = adminUserAction;
    const idx = state.users.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Utilisateur introuvable.", 404);
    state.users[idx].status = action === "disable" ? "disabled" : "active";
    state.users[idx].updated_at = nowIso();
    setState(state);
    return deepClone(state.users[idx] as AdminUser) as T;
  }

  const adminUserDelete = pathname.match(/^\/admin\/users\/([^/]+)$/);
  if (adminUserDelete && method === "DELETE") {
    const [, id] = adminUserDelete;
    const idx = state.users.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Utilisateur introuvable.", 404);
    const [deleted] = state.users.splice(idx, 1);
    setState(state);
    return deepClone(deleted as AdminUser) as T;
  }

  if (pathname === "/members" && method === "GET") return deepClone(state.members) as T;
  if (pathname === "/members" && method === "POST") {
    const payload = bodyAsObject<Partial<Member>>(options.body);
    const row: Member = {
      id: uid("mbr"),
      cooperative_id: state.cooperatives[0].id,
      code: payload.code || uid("MBR").toUpperCase(),
      full_name: payload.full_name || "Nouveau membre",
      phone: payload.phone || "+221 77 000 00 00",
      village: payload.village ?? null,
      main_product: payload.main_product ?? null,
      parcel_count: payload.parcel_count ?? 1,
      area_hectares: payload.area_hectares ?? 1,
      join_date: payload.join_date ?? dateDaysAgo(1),
      specialty: payload.specialty ?? payload.main_product ?? null,
      status: payload.status || "active",
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    state.members.push(row);
    setState(state);
    return deepClone(row) as T;
  }

  const memberMatch = pathname.match(/^\/members\/([^/]+)$/);
  if (memberMatch && method === "PATCH") {
    const [, id] = memberMatch;
    const idx = state.members.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Membre introuvable.", 404);
    state.members[idx] = { ...state.members[idx], ...bodyAsObject<Partial<Member>>(options.body), updated_at: nowIso() };
    setState(state);
    return deepClone(state.members[idx]) as T;
  }
  if (memberMatch && method === "DELETE") {
    const [, id] = memberMatch;
    const idx = state.members.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Membre introuvable.", 404);
    state.members[idx] = { ...state.members[idx], status: "inactive", updated_at: nowIso() };
    setState(state);
    return deepClone(state.members[idx]) as T;
  }
  if (memberMatch && method === "GET") {
    const [, id] = memberMatch;
    const row = state.members.find((item) => item.id === id);
    if (!row) throw new MockApiError("Membre introuvable.", 404);
    return deepClone(row) as T;
  }

  if (pathname === "/fields" && method === "GET") return deepClone(state.fields) as T;
  if (pathname === "/fields" && method === "POST") {
    const payload = bodyAsObject<Partial<Field>>(options.body);
    const row: Field = {
      id: uid("fld"),
      member_id: payload.member_id || state.members[0]?.id || "",
      cooperative_id: state.cooperatives[0].id,
      location: payload.location || "Parcelle",
      area: payload.area ?? 1,
      soil_type: payload.soil_type ?? null,
      irrigation_type: payload.irrigation_type ?? null,
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    state.fields.push(row);
    setState(state);
    return deepClone(row) as T;
  }
  const fieldMatch = pathname.match(/^\/fields\/([^/]+)$/);
  if (fieldMatch && method === "PATCH") {
    const [, id] = fieldMatch;
    const idx = state.fields.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Parcelle introuvable.", 404);
    state.fields[idx] = { ...state.fields[idx], ...bodyAsObject<Partial<Field>>(options.body), updated_at: nowIso() };
    setState(state);
    return deepClone(state.fields[idx]) as T;
  }
  if (fieldMatch && method === "DELETE") {
    const [, id] = fieldMatch;
    const idx = state.fields.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Parcelle introuvable.", 404);
    const [row] = state.fields.splice(idx, 1);
    setState(state);
    return deepClone(row) as T;
  }

  if (pathname === "/products" && method === "GET") return deepClone(state.products) as T;
  if (pathname === "/products" && method === "POST") {
    const payload = bodyAsObject<Partial<Product>>(options.body);
    const row: Product = {
      id: uid("prd"),
      cooperative_id: state.cooperatives[0].id,
      name: payload.name || "Produit",
      category: payload.category || "Autre",
      unit: payload.unit || "kg",
      quality_grade: payload.quality_grade ?? null,
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    state.products.push(row);
    setState(state);
    return deepClone(row) as T;
  }
  const productMatch = pathname.match(/^\/products\/([^/]+)$/);
  if (productMatch && method === "PATCH") {
    const [, id] = productMatch;
    const idx = state.products.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Produit introuvable.", 404);
    state.products[idx] = { ...state.products[idx], ...bodyAsObject<Partial<Product>>(options.body), updated_at: nowIso() };
    setState(state);
    return deepClone(state.products[idx]) as T;
  }
  if (productMatch && method === "DELETE") {
    const [, id] = productMatch;
    const idx = state.products.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Produit introuvable.", 404);
    const [row] = state.products.splice(idx, 1);
    setState(state);
    return deepClone(row) as T;
  }

  if (pathname === "/inputs" && method === "GET") return deepClone(state.inputs) as T;
  if (pathname === "/inputs" && method === "POST") {
    const payload = bodyAsObject<Partial<Input>>(options.body);
    const row: Input = {
      id: uid("inp"),
      cooperative_id: state.cooperatives[0].id,
      member_id: payload.member_id || state.members[0].id,
      product_id: payload.product_id || state.products[0].id,
      field_id: payload.field_id ?? null,
      date: payload.date || dateDaysAgo(0),
      quantity: payload.quantity ?? 0,
      grade: payload.grade || "B",
      estimated_value: payload.estimated_value ?? null,
      status: payload.status || "pending",
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    state.inputs.push(row);
    setState(state);
    return deepClone(row) as T;
  }
  const inputMatch = pathname.match(/^\/inputs\/([^/]+)$/);
  if (inputMatch && method === "PATCH") {
    const [, id] = inputMatch;
    const idx = state.inputs.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Collecte introuvable.", 404);
    state.inputs[idx] = { ...state.inputs[idx], ...bodyAsObject<Partial<Input>>(options.body), updated_at: nowIso() };
    setState(state);
    return deepClone(state.inputs[idx]) as T;
  }
  if (inputMatch && method === "DELETE") {
    const [, id] = inputMatch;
    const idx = state.inputs.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Collecte introuvable.", 404);
    const [row] = state.inputs.splice(idx, 1);
    setState(state);
    return deepClone(row) as T;
  }

  if (pathname === "/stocks" && method === "GET") return deepClone(state.stocks) as T;
  if (pathname === "/stocks" && method === "POST") {
    const payload = bodyAsObject<Partial<Stock>>(options.body);
    const row: Stock = {
      id: uid("stk"),
      cooperative_id: state.cooperatives[0].id,
      product_id: payload.product_id || state.products[0].id,
      quantity: payload.quantity ?? 0,
      threshold: payload.threshold ?? 0,
      unit: payload.unit || "kg",
      last_updated: nowIso(),
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    state.stocks.push(row);
    setState(state);
    return deepClone(row) as T;
  }
  const stockAdjustMatch = pathname.match(/^\/stocks\/([^/]+)\/(increase|decrease)$/);
  if (stockAdjustMatch && method === "POST") {
    const [, id, direction] = stockAdjustMatch;
    const payload = bodyAsObject<{ amount?: number }>(options.body);
    const amount = Number(payload.amount ?? 0);
    const idx = state.stocks.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Stock introuvable.", 404);
    const current = state.stocks[idx];
    const nextQuantity = direction === "increase" ? current.quantity + amount : current.quantity - amount;
    state.stocks[idx] = {
      ...current,
      quantity: Math.max(nextQuantity, 0),
      last_updated: nowIso(),
      updated_at: nowIso(),
    };
    setState(state);
    return deepClone(state.stocks[idx]) as T;
  }
  const stockMatch = pathname.match(/^\/stocks\/([^/]+)$/);
  if (stockMatch && method === "PATCH") {
    const [, id] = stockMatch;
    const idx = state.stocks.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Stock introuvable.", 404);
    state.stocks[idx] = { ...state.stocks[idx], ...bodyAsObject<Partial<Stock>>(options.body), updated_at: nowIso(), last_updated: nowIso() };
    setState(state);
    return deepClone(state.stocks[idx]) as T;
  }
  if (stockMatch && method === "DELETE") {
    const [, id] = stockMatch;
    const idx = state.stocks.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Stock introuvable.", 404);
    const [row] = state.stocks.splice(idx, 1);
    setState(state);
    return deepClone(row) as T;
  }

  if (pathname === "/batches" && method === "GET") return deepClone(state.batches) as T;
  if (pathname === "/batches" && method === "POST") {
    const payload = bodyAsObject<Partial<Batch>>(options.body);
    const row: Batch = {
      id: uid("lot"),
      cooperative_id: state.cooperatives[0].id,
      product_id: payload.product_id || state.products[0].id,
      code: payload.code || `LOT-${uid("X").toUpperCase()}`,
      creation_date: payload.creation_date || dateDaysAgo(0),
      initial_qty: payload.initial_qty ?? 0,
      current_qty: payload.initial_qty ?? 0,
      status: "created",
      created_by_user_id: state.users.find((u) => u.role === "manager")?.id || "",
      created_at: nowIso(),
      updated_at: nowIso(),
    };
    state.batches.push(row);
    setState(state);
    return deepClone(row) as T;
  }
  const batchStatusMatch = pathname.match(/^\/batches\/([^/]+)\/status$/);
  if (batchStatusMatch && method === "PATCH") {
    const [, id] = batchStatusMatch;
    const idx = state.batches.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Lot introuvable.", 404);
    const payload = bodyAsObject<{ status?: string }>(options.body);
    state.batches[idx] = { ...state.batches[idx], status: payload.status || state.batches[idx].status, updated_at: nowIso() };
    setState(state);
    return deepClone(state.batches[idx]) as T;
  }
  const batchMatch = pathname.match(/^\/batches\/([^/]+)$/);
  if (batchMatch && method === "PATCH") {
    const [, id] = batchMatch;
    const idx = state.batches.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Lot introuvable.", 404);
    state.batches[idx] = { ...state.batches[idx], ...bodyAsObject<Partial<Batch>>(options.body), updated_at: nowIso() };
    setState(state);
    return deepClone(state.batches[idx]) as T;
  }
  if (batchMatch && method === "DELETE") {
    const [, id] = batchMatch;
    const idx = state.batches.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Lot introuvable.", 404);
    const [row] = state.batches.splice(idx, 1);
    setState(state);
    return deepClone(row) as T;
  }

  if (pathname === "/process-steps" && method === "GET") return deepClone(state.processSteps) as T;
  if (pathname === "/process-steps" && method === "POST") {
    const payload = bodyAsObject<Partial<ProcessStep>>(options.body);
    const qtyIn = Number(payload.qty_in ?? 0);
    const qtyOut = Number(payload.qty_out ?? 0);
    const waste = Number(payload.waste_qty ?? Math.max(qtyIn - qtyOut, 0));
    const row: ProcessStep = {
      id: uid("stp"),
      batch_id: payload.batch_id || state.batches[0].id,
      type: payload.type || "Etape",
      date: payload.date || dateDaysAgo(0),
      qty_in: qtyIn,
      qty_out: qtyOut,
      waste_qty: waste,
      notes: payload.notes ?? null,
      status: payload.status || "completed",
      duration_minutes: payload.duration_minutes ?? null,
      created_at: nowIso(),
      updated_at: nowIso(),
      loss_pct: qtyIn > 0 ? Number(((waste / qtyIn) * 100).toFixed(2)) : 0,
      efficiency_pct: qtyIn > 0 ? Number(((qtyOut / qtyIn) * 100).toFixed(2)) : 0,
      warning: qtyIn > 0 ? waste / qtyIn >= 0.1 : false,
    };
    state.processSteps.push(row);
    const batchIdx = state.batches.findIndex((b) => b.id === row.batch_id);
    if (batchIdx >= 0) {
      state.batches[batchIdx] = { ...state.batches[batchIdx], current_qty: row.qty_out, status: "in_progress", updated_at: nowIso() };
    }
    setState(state);
    return deepClone(row) as T;
  }
  const stepCompleteMatch = pathname.match(/^\/process-steps\/([^/]+)\/complete$/);
  if (stepCompleteMatch && method === "POST") {
    const [, id] = stepCompleteMatch;
    const idx = state.processSteps.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Etape introuvable.", 404);
    state.processSteps[idx] = { ...state.processSteps[idx], status: "completed", updated_at: nowIso(), warning: false };
    setState(state);
    return deepClone(state.processSteps[idx]) as T;
  }
  const stepMatch = pathname.match(/^\/process-steps\/([^/]+)$/);
  if (stepMatch && method === "PATCH") {
    const [, id] = stepMatch;
    const idx = state.processSteps.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Etape introuvable.", 404);
    const next = { ...state.processSteps[idx], ...bodyAsObject<Partial<ProcessStep>>(options.body), updated_at: nowIso() };
    const qtyIn = Number(next.qty_in ?? 0);
    const qtyOut = Number(next.qty_out ?? 0);
    const waste = Number(next.waste_qty ?? Math.max(qtyIn - qtyOut, 0));
    next.loss_pct = qtyIn > 0 ? Number(((waste / qtyIn) * 100).toFixed(2)) : 0;
    next.efficiency_pct = qtyIn > 0 ? Number(((qtyOut / qtyIn) * 100).toFixed(2)) : 0;
    next.warning = next.loss_pct >= 10;
    state.processSteps[idx] = next;
    setState(state);
    return deepClone(next) as T;
  }
  if (stepMatch && method === "DELETE") {
    const [, id] = stepMatch;
    const idx = state.processSteps.findIndex((row) => row.id === id);
    if (idx === -1) throw new MockApiError("Etape introuvable.", 404);
    const [row] = state.processSteps.splice(idx, 1);
    setState(state);
    return deepClone(row) as T;
  }

  if (pathname === "/analytics/dashboard" && method === "GET") return buildDashboard(state) as T;

  const analyticsRecMatch = pathname.match(/^\/analytics\/batches\/([^/]+)\/recommendation$/);
  if (analyticsRecMatch && method === "GET") {
    const [, batchId] = analyticsRecMatch;
    const step = [...state.processSteps].filter((row) => row.batch_id === batchId).sort((a, b) => b.date.localeCompare(a.date))[0];
    if (!step) {
      return {
        batch_id: batchId,
        loss_pct: 0,
        efficiency_pct: 100,
        anomaly_detected: false,
        anomaly_score: 0,
        risk_level: "low",
        suggested_action: "Continuer le processus actuel.",
        rationale: "Aucune anomalie détectée.",
        reasons: ["Aucune perte critique"],
      } as T;
    }
    return mapRecommendation(step) as T;
  }

  const analyticsMetricsMatch = pathname.match(/^\/analytics\/batches\/([^/]+)\/metrics$/);
  if (analyticsMetricsMatch && method === "GET") {
    const [, batchId] = analyticsMetricsMatch;
    const rows = state.processSteps.filter((row) => row.batch_id === batchId);
    return {
      batch_id: batchId,
      total_steps: rows.length,
      avg_loss_pct: rows.length ? rows.reduce((sum, row) => sum + row.loss_pct, 0) / rows.length : 0,
      avg_efficiency_pct: rows.length ? rows.reduce((sum, row) => sum + row.efficiency_pct, 0) / rows.length : 0,
    } as T;
  }

  const analyticsAnomalyMatch = pathname.match(/^\/analytics\/batches\/([^/]+)\/anomaly$/);
  if (analyticsAnomalyMatch && method === "GET") {
    const [, batchId] = analyticsAnomalyMatch;
    const rows = state.processSteps.filter((row) => row.batch_id === batchId);
    const worst = rows.reduce((max, row) => (row.loss_pct > max.loss_pct ? row : max), rows[0]);
    return {
      batch_id: batchId,
      anomaly_detected: rows.some((row) => row.warning),
      anomaly_score: worst ? Math.round(worst.loss_pct * 4) : 0,
      reason: worst ? `Perte élevée sur ${worst.type}` : "RAS",
    } as T;
  }

  if (pathname === "/chat" && method === "POST") {
    const payload = bodyAsObject<{ message?: string }>(options.body);
    const message = (payload.message || "").trim();
    if (!message) throw new MockApiError("Message requis.", 400);

    const dashboard = buildDashboard(state);
    const snapshot: AssistantChatResponse["dashboard"] = {
      cooperative_name: state.cooperatives[0]?.name ?? "WeeFarm",
      region: state.cooperatives[0]?.region ?? "Thiès",
      total_production: dashboard.total_production,
      loss_rate: dashboard.loss_rate,
      efficiency_rate: dashboard.efficiency_rate,
      number_of_active_batches: dashboard.number_of_active_batches,
      stock_alerts: dashboard.stock_alerts.length,
    };

    const response: AssistantChatResponse = {
      success: true,
      message: `Analyse LLM (mode démo): ${message}. Les pertes restent concentrées sur les étapes de séchage/tri. Priorité: contrôler l'humidité et revalider les lots critiques aujourd'hui.`,
      grounded: true,
      mode: "llm",
      llm_provider: "demo",
      llm_model: "weefarm-mock-llm-v1",
      citations: [
        {
          source_id: "LOT-MG-001",
          source_url: "https://weefarm.local/mock/source/lot-mg-001",
          region: "Thiès",
          crop: "Mangue",
          topic: "Séchage",
          excerpt: "Perte supérieure à la moyenne observée sur la phase séchage.",
        },
      ],
      context_metrics: [
        {
          source_id: "MET-THIES-001",
          region: "Thiès",
          crop: "Mangue",
          metric: "loss_rate",
          period: "Semaine courante",
          value: dashboard.loss_rate,
          unit: "%",
          notes: "Données de démonstration",
        },
      ],
      dashboard: snapshot,
    };
    return response as T;
  }

  if (pathname === "/reference/metrics" && method === "GET") {
    const q = (query.get("q") || "").toLowerCase();
    const items = [
      { id: "met-1", source_id: "SEN-AGR-001", country: "Senegal", region: "Thiès", crop: "Mangue", metric: "loss_rate", period: "2026-Q1", value: 12.4, unit: "%", notes: "Référence régionale" },
      { id: "met-2", source_id: "SEN-AGR-002", country: "Senegal", region: "Thiès", crop: "Oignon", metric: "efficiency_rate", period: "2026-Q1", value: 87.1, unit: "%", notes: "Référence process" },
    ].filter((item) => !q || JSON.stringify(item).toLowerCase().includes(q));
    const response: ReferenceMetricListResponse = { total: items.length, items };
    return response as T;
  }

  if (pathname === "/reference/knowledge" && method === "GET") {
    const q = (query.get("q") || "").toLowerCase();
    const items = [
      {
        id: "kg-1",
        source_id: "DOC-POSTHARV-01",
        source_url: "https://weefarm.local/mock/doc/postharvest",
        country: "Senegal",
        region: "Thiès",
        crop: "Mangue",
        topic: "Séchage",
        content: "Réduire le temps d'attente avant séchage et surveiller l'humidité limite les pertes.",
      },
      {
        id: "kg-2",
        source_id: "DOC-STOCK-03",
        source_url: "https://weefarm.local/mock/doc/stock",
        country: "Senegal",
        region: "Thiès",
        crop: "Mil",
        topic: "Stockage",
        content: "Utiliser un seuil critique dynamique réduit les ruptures de stock.",
      },
    ].filter((item) => !q || JSON.stringify(item).toLowerCase().includes(q));
    const response: KnowledgeChunkListResponse = { total: items.length, items };
    return response as T;
  }

  throw new MockApiError(`Endpoint mock non implémenté: ${method} ${pathname}`, 404);
}

