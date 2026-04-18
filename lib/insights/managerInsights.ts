import type { DashboardResponse, Recommendation } from "@/lib/api/types";

export type Severity = "critical" | "warning" | "optimization";
export type StageSeverity = "critical" | "warning" | "healthy";

export type RecommendationCard = {
  id: string;
  severity: Severity;
  badge: "P1" | "P2" | "P3";
  title: string;
  explanation: string;
  impact: string;
  action: string;
  stage: string;
  batchLabel: string;
  lossPct: number;
  efficiencyPct: number;
};

export type ActionItem = {
  id: string;
  severity: Severity;
  urgency: "Immediate" | "Aujourd'hui" | "Suivi";
  issue: string;
  cause: string;
  impact: string;
  action: string;
  stage: string;
  batchLabel: string;
  owner: string;
  dueBy: string;
  expectedGain: string;
  signalScore: number;
};

export type StageInsight = {
  key: string;
  label: string;
  severity: StageSeverity;
  avgLoss: number;
  avgEfficiency: number;
  lossDelta: number;
  efficiencyDelta: number;
  count: number;
  explanation: string;
  nextAction: string;
  affectedBatches: string[];
  anomalous: boolean;
};

export type InsightCard = {
  id: string;
  severity: StageSeverity | "optimization";
  title: string;
  message: string;
  action: string;
};

export type PriorityStrip = {
  severity: "critical" | "warning" | "ok";
  headline: string;
  message: string;
  recommendation: string;
  actionId: string | null;
};

const STAGE_ORDER = ["cleaning", "drying", "sorting", "packaging"] as const;

const STAGE_ACTIONS: Record<(typeof STAGE_ORDER)[number], string> = {
  cleaning: "Reviser calibration et checklists avant la prochaine sequence.",
  drying: "Ajuster duree de sechage et controle humidite sur les prochains lots.",
  sorting: "Recalibrer les criteres de tri avant la prochaine rotation.",
  packaging: "Verifier la qualite emballage et la cadence de conditionnement.",
};

function toStageLabel(stage: string): string {
  if (stage === "cleaning") return "Nettoyage";
  if (stage === "drying") return "Sechage";
  if (stage === "sorting") return "Tri";
  if (stage === "packaging") return "Conditionnement";
  return stage.charAt(0).toUpperCase() + stage.slice(1).toLowerCase();
}

function shortBatch(batchId: string): string {
  return batchId.slice(0, 8).toUpperCase();
}

function parseStageFromRecommendation(item: Recommendation): string {
  const text = `${item.rationale} ${item.suggested_action}`.toLowerCase();
  const match = STAGE_ORDER.find((stage) => text.includes(stage));
  return match ?? "process";
}

function recommendationSeverity(item: Recommendation): Severity {
  const risk = item.risk_level.toLowerCase();
  if (risk === "high" || item.anomaly_score >= 70 || item.loss_pct >= 18) return "critical";
  if (risk === "medium" || item.anomaly_score >= 35 || item.loss_pct >= 12) return "warning";
  return "optimization";
}

function recommendationBadge(severity: Severity): "P1" | "P2" | "P3" {
  if (severity === "critical") return "P1";
  if (severity === "warning") return "P2";
  return "P3";
}

function stageSeverity(avgLoss: number, avgEfficiency: number): StageSeverity {
  if (avgLoss >= 12 || avgEfficiency < 85) return "critical";
  if (avgLoss >= 7 || avgEfficiency < 90) return "warning";
  return "healthy";
}

function stageRank(severity: StageSeverity): number {
  if (severity === "critical") return 0;
  if (severity === "warning") return 1;
  return 2;
}

function trendArrow(value: number): string {
  if (Math.abs(value) < 0.15) return "->";
  return value > 0 ? "↑" : "↓";
}

function sanitizeAction(rawAction: string, severity: Severity): string {
  if (severity === "optimization") {
    return "Continuer le process actuel et monitorer la tendance sur 24h.";
  }
  if (!rawAction.trim()) {
    return severity === "critical"
      ? "Prioriser ce point sur le prochain point terrain."
      : "Corriger ce point avant la prochaine cloture de lot.";
  }
  return rawAction.trim();
}

function ownerForStage(stage: string): string {
  const normalized = stage.toLowerCase();
  if (normalized.includes("sech")) return "Equipe sechage";
  if (normalized.includes("tri")) return "Equipe tri";
  if (normalized.includes("nettoy")) return "Equipe nettoyage";
  if (normalized.includes("condition")) return "Equipe conditionnement";
  if (normalized.includes("stock")) return "Responsable stock";
  return "Manager de production";
}

function dueByForUrgency(urgency: ActionItem["urgency"]): string {
  if (urgency === "Immediate") return "Dans 2h";
  if (urgency === "Aujourd'hui") return "Avant 18:00";
  return "Cette semaine";
}

function expectedGain(severity: Severity): string {
  if (severity === "critical") return "-2.0 pts perte estimee";
  if (severity === "warning") return "-1.0 pt perte estimee";
  return "+0.5 pt efficacite estimee";
}

export function buildStageInsights(data: DashboardResponse): StageInsight[] {
  const allSteps = data.recent_process_steps;
  const baselineLoss =
    allSteps.length > 0 ? allSteps.reduce((sum, step) => sum + step.loss_pct, 0) / allSteps.length : 0;
  const baselineEfficiency =
    allSteps.length > 0 ? allSteps.reduce((sum, step) => sum + step.efficiency_pct, 0) / allSteps.length : 100;

  return STAGE_ORDER.map((stage) => {
    const steps = allSteps.filter((step) => step.type.toLowerCase() === stage);
    if (steps.length === 0) {
      return {
        key: stage,
        label: toStageLabel(stage),
        severity: "healthy",
        avgLoss: 0,
        avgEfficiency: 100,
        lossDelta: -baselineLoss,
        efficiencyDelta: 100 - baselineEfficiency,
        count: 0,
        explanation: "Pas d'execution recente. Stade sous controle.",
        nextAction: "Maintenir le controle standard.",
        affectedBatches: [],
        anomalous: false,
      };
    }

    const avgLoss = steps.reduce((sum, step) => sum + step.loss_pct, 0) / steps.length;
    const avgEfficiency = steps.reduce((sum, step) => sum + step.efficiency_pct, 0) / steps.length;
    const severity = stageSeverity(avgLoss, avgEfficiency);
    const anomalous = severity === "critical" || steps.some((step) => step.warning);
    const explanation =
      severity === "critical"
        ? `Perte moyenne ${avgLoss.toFixed(1)}%: derive critique sur ce stade.`
        : severity === "warning"
          ? `Perte moyenne ${avgLoss.toFixed(1)}%: deviation au-dessus du niveau attendu.`
          : `Stade stable avec efficacite moyenne ${avgEfficiency.toFixed(1)}%.`;

    return {
      key: stage,
      label: toStageLabel(stage),
      severity,
      avgLoss,
      avgEfficiency,
      lossDelta: avgLoss - baselineLoss,
      efficiencyDelta: avgEfficiency - baselineEfficiency,
      count: steps.length,
      explanation,
      nextAction: STAGE_ACTIONS[stage],
      affectedBatches: Array.from(new Set(steps.map((step) => step.batch_id))),
      anomalous,
    };
  });
}

export function buildRecommendationCards(data: DashboardResponse): RecommendationCard[] {
  const mapped = data.recent_recommendations.map((item) => {
    const severity = recommendationSeverity(item);
    const stage = parseStageFromRecommendation(item);
    const batch = shortBatch(item.batch_id);

    return {
      id: item.batch_id,
      severity,
      badge: recommendationBadge(severity),
      title:
        severity === "critical"
          ? `Prioriser lot ${batch} (${toStageLabel(stage)})`
          : severity === "warning"
            ? `Corriger lot ${batch} (${toStageLabel(stage)})`
            : `Maintenir lot ${batch} stable`,
      explanation:
        item.reasons[0] ??
        (severity === "optimization"
          ? "Le lot reste dans la plage normale."
          : "Une variation operationnelle a ete detectee."),
      impact: `Perte ${item.loss_pct.toFixed(1)}% · Efficacite ${item.efficiency_pct.toFixed(1)}% · Risque ${item.risk_level.toLowerCase()}`,
      action: sanitizeAction(item.suggested_action, severity),
      stage: stage === "process" ? "Process global" : toStageLabel(stage),
      batchLabel: batch,
      lossPct: item.loss_pct,
      efficiencyPct: item.efficiency_pct,
    };
  });

  if (mapped.length > 0) {
    return mapped.sort((a, b) => {
      const rank: Record<Severity, number> = { critical: 0, warning: 1, optimization: 2 };
      return rank[a.severity] - rank[b.severity];
    });
  }

  return [
    {
      id: "stable-default",
      severity: "optimization",
      badge: "P3",
      title: "Systeme stable",
      explanation: "Aucune alerte critique detectee sur les lots recents.",
      impact: "Operations stables sur les dernieres executions.",
      action: "Continuer le process actuel et monitorer la tendance sur 24h.",
      stage: "Process global",
      batchLabel: "N/A",
      lossPct: 0,
      efficiencyPct: 100,
    },
  ];
}

export function buildActionItems(
  recommendations: RecommendationCard[],
  stages: StageInsight[],
  stockAlerts: DashboardResponse["stock_alerts"],
): ActionItem[] {
  const directActions: ActionItem[] = recommendations.slice(0, 4).map((item) => ({
    id: item.id,
    severity: item.severity,
    urgency: item.severity === "critical" ? "Immediate" : item.severity === "warning" ? "Aujourd'hui" : "Suivi",
    issue: item.title,
    cause: item.explanation,
    impact: item.impact,
    action: item.action,
    stage: item.stage,
    batchLabel: item.batchLabel,
    owner: ownerForStage(item.stage),
    dueBy: dueByForUrgency(item.severity === "critical" ? "Immediate" : item.severity === "warning" ? "Aujourd'hui" : "Suivi"),
    expectedGain: expectedGain(item.severity),
    signalScore: Math.round((item.severity === "critical" ? 90 : item.severity === "warning" ? 70 : 50) + item.lossPct - (item.efficiencyPct - 80) * 0.5),
  }));

  const abnormalStages: ActionItem[] = stages
    .filter((stage) => stage.severity !== "healthy")
    .sort((a, b) => stageRank(a.severity) - stageRank(b.severity))
    .map((stage) => {
      const severity: Severity = stage.severity === "critical" ? "critical" : "warning";
      const urgency: ActionItem["urgency"] = stage.severity === "critical" ? "Immediate" : "Aujourd'hui";
      return {
        id: `stage-${stage.key}`,
        severity,
        urgency,
        issue: `${stage.label} hors plage`,
        cause: stage.explanation,
        impact: `Perte ${stage.avgLoss.toFixed(1)}% (${trendArrow(stage.lossDelta)} ${Math.abs(stage.lossDelta).toFixed(1)} pts vs base)`,
        action: stage.nextAction,
        stage: stage.label,
        batchLabel: stage.affectedBatches[0] ? shortBatch(stage.affectedBatches[0]) : "N/A",
        owner: ownerForStage(stage.label),
        dueBy: dueByForUrgency(urgency),
        expectedGain: expectedGain(severity),
        signalScore: Math.round((severity === "critical" ? 88 : 68) + stage.avgLoss - (stage.avgEfficiency - 85) * 0.5),
      };
    });

  const stockActions: ActionItem[] = stockAlerts.slice(0, 1).map((stock) => ({
    id: `stock-${stock.stock_id}`,
    severity: "warning" as const,
    urgency: "Aujourd'hui" as const,
    issue: "Stock sous seuil",
    cause: `Le produit ${shortBatch(stock.product_id)} est sous le seuil defini.`,
    impact: `Deficit ${stock.deficit.toFixed(1)} ${stock.unit}`,
    action: "Reallouer les apports et planifier la collecte avant fin de journee.",
    stage: "Stock",
    batchLabel: "N/A",
    owner: "Responsable stock",
    dueBy: "Avant 17:00",
    expectedGain: "Eviter rupture de lot",
    signalScore: Math.round(65 + stock.deficit),
  }));

  const merged = [...directActions, ...abnormalStages, ...stockActions];
  const deduped: ActionItem[] = [];
  const seen = new Set<string>();

  for (const item of merged) {
    const key = `${item.issue}|${item.stage}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(item);
  }

  return deduped.slice(0, 4);
}

export function buildPriorityStrip(data: DashboardResponse, actionItems: ActionItem[]): PriorityStrip {
  const critical = actionItems.find((item) => item.severity === "critical");
  if (critical) {
    return {
      severity: "critical",
      headline: "Critical - action immediate requise",
      message: `${critical.issue}. ${critical.impact}`,
      recommendation: critical.action,
      actionId: critical.id,
    };
  }

  const warning = actionItems.find((item) => item.severity === "warning");
  if (warning) {
    return {
      severity: "warning",
      headline: "Warning - prioriser aujourd'hui",
      message: `${warning.issue}. ${warning.impact}`,
      recommendation: warning.action,
      actionId: warning.id,
    };
  }

  const optimization = actionItems[0];
  return {
    severity: "ok",
    headline: "Systeme stable",
    message: `Perte globale ${data.loss_rate.toFixed(1)}% · Efficacite ${data.efficiency_rate.toFixed(1)}%.`,
    recommendation: optimization?.action ?? "Continuer le process actuel et monitorer les tendances.",
    actionId: optimization?.id ?? null,
  };
}

export function buildOperationalInsights(
  data: DashboardResponse,
  stages: StageInsight[],
  actionItems: ActionItem[],
): InsightCard[] {
  const cards: InsightCard[] = [];
  const abnormal = stages
    .filter((stage) => stage.severity !== "healthy")
    .sort((a, b) => stageRank(a.severity) - stageRank(b.severity))[0];

  if (abnormal) {
    cards.push({
      id: "abnormal-stage",
      severity: abnormal.severity,
      title: `${abnormal.label} sous pression`,
      message: `${abnormal.explanation} Impact sur ${abnormal.count} lots recents.`,
      action: abnormal.nextAction,
    });
  }

  if (data.stock_alerts.length > 0) {
    const top = data.stock_alerts[0];
    cards.push({
      id: "stock-alert",
      severity: "warning",
      title: "Risque stock",
      message: `Deficit ${top.deficit.toFixed(1)} ${top.unit} detecte sur ${shortBatch(top.product_id)}.`,
      action: "Prioriser le reapprovisionnement avant la prochaine sequence de lots.",
    });
  }

  if (actionItems.every((item) => item.severity === "optimization")) {
    cards.unshift({
      id: "stable-summary",
      severity: "healthy",
      title: "Systeme stable",
      message: "Aucune alerte critique ou warning detectee.",
      action: "Focus sur les opportunites d'optimisation.",
    });
  }

  if (cards.length === 0) {
    cards.push({
      id: "default-insight",
      severity: "optimization",
      title: "Operations sous controle",
      message: "Le systeme reste stable sans derive notable.",
      action: "Continuer la routine de suivi.",
    });
  }

  return cards.slice(0, 4);
}

