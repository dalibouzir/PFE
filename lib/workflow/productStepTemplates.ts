export type WorkflowPhase = "pre_harvest" | "post_harvest";

type ProductFamily = "mango" | "peanut" | "millet" | "banana" | "bissap" | "unknown";

const PRE_HARVEST_FALLBACK = ["Préparation", "Suivi culture", "Contrôle maturité", "Récolte"];
const POST_HARVEST_FALLBACK = ["Réception / pesée", "Tri", "Nettoyage", "Conditionnement", "Stockage"];

const PRODUCT_PHASE_TEMPLATES: Record<ProductFamily, Record<WorkflowPhase, string[]>> = {
  mango: {
    pre_harvest: [
      "Suivi floraison / fructification",
      "Traitement phytosanitaire",
      "Suivi maturité",
      "Récolte sélective",
    ],
    post_harvest: [
      "Réception / pesée",
      "Tri sous ombre",
      "Désève",
      "Lavage / traitement",
      "Conditionnement",
      "Stockage / livraison",
    ],
  },
  peanut: {
    pre_harvest: ["Préparation du sol", "Semis", "Désherbage", "Suivi maturité", "Arrachage"],
    post_harvest: [
      "Séchage des gousses",
      "Battage / égoussage",
      "Tri",
      "Décorticage si applicable",
      "Stockage sec",
    ],
  },
  millet: {
    pre_harvest: ["Préparation du sol", "Semis", "Désherbage", "Suivi maturité", "Récolte des panicules"],
    post_harvest: ["Séchage", "Battage", "Vannage / nettoyage", "Tri / calibrage", "Ensachage", "Stockage"],
  },
  banana: {
    pre_harvest: ["Suivi du régime", "Protection des régimes", "Contrôle maturité", "Récolte verte"],
    post_harvest: ["Dépattage", "Lavage", "Tri / calibrage", "Emballage", "Stockage / expédition"],
  },
  bissap: {
    pre_harvest: ["Semis", "Désherbage", "Suivi floraison", "Récolte des calices"],
    post_harvest: ["Tri des calices", "Lavage", "Séchage", "Conditionnement", "Stockage"],
  },
  unknown: {
    pre_harvest: PRE_HARVEST_FALLBACK,
    post_harvest: POST_HARVEST_FALLBACK,
  },
};

function normalizeProductName(value?: string | null): string {
  if (!value) return "";
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function resolveProductFamily(productName?: string | null): ProductFamily {
  const text = normalizeProductName(productName);
  if (!text) return "unknown";

  if (text.includes("mango") || text.includes("mangue")) return "mango";
  if (text.includes("peanut") || text.includes("arachide")) return "peanut";
  if (text === "mil" || text.includes("millet") || /\bmil\b/.test(text)) return "millet";
  if (text.includes("banana") || text.includes("banane")) return "banana";
  if (text.includes("bissap") || text.includes("hibiscus")) return "bissap";

  return "unknown";
}

export function getProductStepTemplate(productName: string | null | undefined, phase: WorkflowPhase): string[] {
  const family = resolveProductFamily(productName);
  const template = PRODUCT_PHASE_TEMPLATES[family][phase];
  return [...template];
}
