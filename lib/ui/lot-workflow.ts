import type { ProcessStep } from "@/lib/api/types";

export type WorkflowPhase = "pre_harvest" | "post_harvest";

export type WorkflowStageDef = {
  key: string;
  label: string;
  phase: WorkflowPhase;
  icon: string;
  typeTag: string;
  aliases: string[];
};

export const LOT_WORKFLOW_STAGES: WorkflowStageDef[] = [
  {
    key: "pruning",
    label: "Taille et entretien",
    phase: "pre_harvest",
    icon: "🌿",
    typeTag: "pre-recolte",
    aliases: ["taille", "entretien", "pruning"],
  },
  {
    key: "phytosanitary",
    label: "Traitement phytosanitaire",
    phase: "pre_harvest",
    icon: "🛡️",
    typeTag: "pre-recolte",
    aliases: ["phytosanitaire", "traitement phyto", "pesticide", "phyto"],
  },
  {
    key: "irrigation",
    label: "Irrigation",
    phase: "pre_harvest",
    icon: "💧",
    typeTag: "pre-recolte",
    aliases: ["irrigation", "arrosage", "watering"],
  },
  {
    key: "harvest",
    label: "Recolte",
    phase: "pre_harvest",
    icon: "🌾",
    typeTag: "pre-recolte",
    aliases: ["recolte", "harvest"],
  },
  {
    key: "sorting",
    label: "Tri et calibrage",
    phase: "post_harvest",
    icon: "📏",
    typeTag: "tri",
    aliases: ["tri", "calibrage", "sorting"],
  },
  {
    key: "washing",
    label: "Lavage",
    phase: "post_harvest",
    icon: "🧼",
    typeTag: "nettoyage",
    aliases: ["lavage", "nettoyage", "wash", "clean"],
  },
  {
    key: "post_treatment",
    label: "Traitement post-recolte",
    phase: "post_harvest",
    icon: "🧴",
    typeTag: "traitement",
    aliases: ["traitement post", "post-recolte", "post harvest"],
  },
  {
    key: "drying",
    label: "Sechage / ventilation",
    phase: "post_harvest",
    icon: "🌀",
    typeTag: "sechage",
    aliases: ["sechage", "drying", "ventilation", "dry"],
  },
  {
    key: "packaging",
    label: "Emballage (caisses)",
    phase: "post_harvest",
    icon: "📦",
    typeTag: "emballage",
    aliases: ["emballage", "packaging", "conditionnement", "pack"],
  },
  {
    key: "cold_storage",
    label: "Stockage chambre froide",
    phase: "post_harvest",
    icon: "❄️",
    typeTag: "stockage",
    aliases: ["stockage", "chambre froide", "cold storage"],
  },
  {
    key: "shipping",
    label: "Chargement livraison",
    phase: "post_harvest",
    icon: "🚚",
    typeTag: "livraison",
    aliases: ["livraison", "chargement", "shipping", "expedition"],
  },
];

export function phaseLabel(phase: WorkflowPhase) {
  return phase === "pre_harvest" ? "Pre-recolte" : "Post-recolte";
}

export function buildSeasonFromDate(value?: string | null) {
  if (!value) return "";
  const year = Number(value.slice(0, 4));
  if (!Number.isFinite(year) || year <= 0) return "";
  return `${year}-${year + 1}`;
}

export function stageFromType(type: string) {
  const normalized = type.toLowerCase().trim();
  return (
    LOT_WORKFLOW_STAGES.find((stage) => stage.aliases.some((alias) => normalized.includes(alias))) ??
    LOT_WORKFLOW_STAGES.find((stage) => normalized.includes(stage.key))
  );
}

export function stageLabelFromType(type: string) {
  return stageFromType(type)?.label ?? type;
}

export function stageLossKg(step: ProcessStep) {
  return Math.max(step.waste_qty, step.qty_in - step.qty_out, 0);
}
