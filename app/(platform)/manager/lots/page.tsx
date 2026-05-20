"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { ConfirmActionModal } from "@/components/ui/ConfirmActionModal";
import { ContentAreaLoader } from "@/components/ui/ContentAreaLoader";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ExportActions } from "@/components/ui/table/ExportActions";
import { TableToolbar } from "@/components/ui/table/TableToolbar";
import { LotAnalyticsPanel } from "@/components/workspace/LotAnalyticsPanel";
import { LotActiveSidebar, type ActiveLotItem } from "@/components/workspace/LotActiveSidebar";
import { LotHeroBanner } from "@/components/workspace/LotHeroBanner";
import { LotProcessTable, type ProcessTableRow } from "@/components/workspace/LotProcessTable";
import { LotProcessTimeline, type TimelineStage } from "@/components/workspace/LotProcessTimeline";
import { LotRecommendationPanel, type LotRecommendationItem } from "@/components/workspace/LotRecommendationPanel";
import { LotWorkspaceTabs, type LotWorkspaceTab } from "@/components/workspace/LotWorkspaceTabs";
import {
  useBatchMaterialBalance,
  useBatchReferencePreview,
  useBatches,
  useCreateBatch,
  useStartPostHarvest,
  useUpdateBatch,
} from "@/hooks/useBatches";
import { useDashboard } from "@/hooks/useDashboard";
import { useCompleteProcessStep, useCreateProcessStep, useDeleteProcessStep, useProcessSteps, useUpdateProcessStep } from "@/hooks/useProcessSteps";
import { useProducts } from "@/hooks/useProducts";
import { useStocks } from "@/hooks/useStocks";
import type {
  Batch,
  BatchCreate,
  ProcessStepCompletePayload,
  ProcessStep,
  ProcessStepCreate,
  ProcessStepUpdate,
  Recommendation,
} from "@/lib/api/types";
import { exportRowsToCsv, exportRowsToExcel, exportRowsToPdf, type ExportColumn } from "@/lib/export/client";
import { useTableControls } from "@/lib/table/useTableControls";
import {
  LOT_WORKFLOW_STAGES,
  buildSeasonFromDate,
  phaseLabel,
  stageFromType,
  stageLabelFromType,
  type WorkflowStageDef,
} from "@/lib/ui/lot-workflow";
import { getProductStepTemplate } from "@/lib/workflow/productStepTemplates";

const KG_PER_TON = 1000;
const MINUTES_PER_DAY = 60 * 24;
const todayIso = new Date().toISOString().slice(0, 10);
const defaultSteps = getProductStepTemplate(null, "post_harvest");

type MassUnit = "kg" | "ton";
type StagePreset = Pick<WorkflowStageDef, "key" | "label" | "icon" | "typeTag">;
type PostHarvestFluxMeta = {
  product_id: string;
  grade: string;
  allocated_qty_kg: number;
} | null;

const batchStatusTone: Record<string, "success" | "warning" | "info" | "danger"> = {
  created: "info",
  in_progress: "warning",
  completed: "success",
  archived: "danger",
};

const batchStatusLabel: Record<string, string> = {
  created: "Créé",
  in_progress: "En cours",
  completed: "Terminé",
  archived: "Archivé",
};

function lotPostHarvestStatusLabel(batch: Batch): string {
  if (batch.postharvest_status === "ready_post_recolte" && (batch.collecte_created || batch.stock_in_created)) {
    return "Collecté · En attente Post-récolte";
  }
  if (batch.postharvest_status === "in_post_recolte") return "Post-récolte en cours";
  if (batch.postharvest_status === "post_recolte_completed") return "Post-récolte terminée";
  return batchStatusLabel[batch.status] ?? batch.status;
}

function lotPostHarvestStatusTone(batch: Batch): "success" | "warning" | "info" | "danger" {
  if (batch.postharvest_status === "ready_post_recolte" && (batch.collecte_created || batch.stock_in_created)) return "info";
  if (batch.postharvest_status === "in_post_recolte") return "warning";
  if (batch.postharvest_status === "post_recolte_completed") return "success";
  return batchStatusTone[batch.status] ?? "info";
}

function normalizeTab(raw: string | null): LotWorkspaceTab {
  if (raw === "overview") return "overview";
  if (raw === "analytics") return "analytics";
  if (raw === "recommendations") return "recommendations";
  if (raw === "history") return "history";
  return "process";
}

function toKg(value: number, unit: MassUnit) {
  if (unit === "kg") return value;
  return value * KG_PER_TON;
}

function fromKg(valueKg: number, unit: MassUnit) {
  if (unit === "kg") return valueKg;
  return valueKg / KG_PER_TON;
}

function recommendationPriority(item: Recommendation): LotRecommendationItem["priority"] {
  if (item.risk_level.toLowerCase() === "high" || item.anomaly_score >= 70 || item.loss_pct >= 16) return "critical";
  if (item.risk_level.toLowerCase() === "medium" || item.anomaly_score >= 35 || item.loss_pct >= 10) return "high";
  if (item.loss_pct >= 6) return "medium";
  return "low";
}

function parseImpactedStep(item: Recommendation): string {
  const text = `${item.rationale} ${item.suggested_action}`.toLowerCase();
  const workflowStage = LOT_WORKFLOW_STAGES.find((stage) => stage.aliases.some((alias) => text.includes(alias)));
  return workflowStage?.label ?? "Processus global";
}

function decisionStatusFromRecommendation(item: Recommendation): LotRecommendationItem["decisionStatus"] {
  const risk = item.risk_level.toLowerCase();
  if (risk === "high" || item.anomaly_detected || item.loss_pct >= 16) return "Critique";
  if (risk === "medium" || item.loss_pct >= 10) return "Prioritaire";
  if (item.loss_pct >= 6 || item.efficiency_pct < 90) return "À surveiller";
  return "Stable";
}

function formatPct(value: number): string {
  return `${Math.max(value, 0).toFixed(1).replace(".", ",")} %`;
}

function formatKg(value: number): string {
  return `${Math.max(value, 0).toFixed(1).replace(".", ",")} kg`;
}

function durationDaysFromMinutes(minutes?: number | null): number | undefined {
  if (minutes === null || minutes === undefined) return undefined;
  const days = minutes / MINUTES_PER_DAY;
  return Number.isInteger(days) ? days : Number(days.toFixed(2));
}

function durationMinutesFromDays(days?: number): number | undefined {
  if (days === undefined || days === null || Number.isNaN(days)) return undefined;
  return Math.round(days * MINUTES_PER_DAY);
}

function parsePostHarvestStockMeta(statusNote?: string | null): PostHarvestFluxMeta {
  const raw = (statusNote || "").trim();
  const prefix = "POSTHARVEST_STOCK:";
  if (!raw.startsWith(prefix)) return null;
  try {
    const parsed = JSON.parse(raw.slice(prefix.length).trim()) as Partial<PostHarvestFluxMeta>;
    if (!parsed || typeof parsed !== "object") return null;
    const productId = typeof parsed.product_id === "string" ? parsed.product_id : "";
    const grade = typeof parsed.grade === "string" && parsed.grade.trim() ? parsed.grade.trim() : "Non spécifié";
    const allocated = Number(parsed.allocated_qty_kg ?? 0);
    if (!productId) return null;
    return {
      product_id: productId,
      grade,
      allocated_qty_kg: Number.isFinite(allocated) ? allocated : 0,
    };
  } catch {
    return null;
  }
}

export default function LotsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryTab = searchParams.get("tab");
  const queryLot = searchParams.get("lot");

  const batchesQuery = useBatches();
  const productsQuery = useProducts();
  const stocksQuery = useStocks();
  const stepsQuery = useProcessSteps();
  const { data: batches = [] } = batchesQuery;
  const { data: products = [] } = productsQuery;
  const { data: stocks = [] } = stocksQuery;
  const { data: steps = [] } = stepsQuery;
  const { data: dashboard } = useDashboard();

  const createBatch = useCreateBatch();
  const updateBatch = useUpdateBatch();
  const startPostHarvest = useStartPostHarvest();
  const createStep = useCreateProcessStep();
  const completeStep = useCompleteProcessStep();
  const updateStep = useUpdateProcessStep();
  const deleteStep = useDeleteProcessStep();

  const [activeTab, setActiveTab] = useState<LotWorkspaceTab>(() => normalizeTab(queryTab));
  const [query, setQuery] = useState("");
  const [productFilterId, setProductFilterId] = useState("all");
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(queryLot);

  const [lotFormOpen, setLotFormOpen] = useState(false);
  const [stepFormOpen, setStepFormOpen] = useState(false);
  const [editingBatch, setEditingBatch] = useState<Batch | null>(null);
  const [editingStep, setEditingStep] = useState<ProcessStep | null>(null);
  const [completingPendingStep, setCompletingPendingStep] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [postHarvestModalOpen, setPostHarvestModalOpen] = useState(false);
  const [postHarvestProductId, setPostHarvestProductId] = useState<string>("");
  const [postHarvestGrade, setPostHarvestGrade] = useState<string>("");
  const [postHarvestQuantity, setPostHarvestQuantity] = useState<string>("");
  const [postHarvestFormError, setPostHarvestFormError] = useState<string | null>(null);
  const [pendingDeleteStep, setPendingDeleteStep] = useState<ProcessStep | null>(null);
  const tableControls = useTableControls([], "desc");

  const [plannedStepsDraft, setPlannedStepsDraft] = useState<string[]>(defaultSteps);
  const [stepToAdd, setStepToAdd] = useState("");
  const [customStepInput, setCustomStepInput] = useState("");

  const [stepPreset, setStepPreset] = useState<StagePreset | null>(null);
  const [stepTargetOrder, setStepTargetOrder] = useState<number | null>(null);
  const [listPage, setListPage] = useState(1);
  const [listPageSize, setListPageSize] = useState(10);

  const lotForm = useForm<BatchCreate>({
    defaultValues: {
      product_id: "",
      creation_date: todayIso,
      initial_qty: 0,
      unit: "kg",
      process_steps: defaultSteps,
    },
  });
  const stepForm = useForm<ProcessStepCreate>({
    defaultValues: {
      batch_id: "",
      type: "",
      date: todayIso,
      loss_value: 0,
      loss_unit: "kg",
      notes: "",
      duration_minutes: undefined,
    },
  });

  const watchedProductId = lotForm.watch("product_id");
  const watchedLotUnit = (lotForm.watch("unit") || "kg") as MassUnit;
  const previewReference = useBatchReferencePreview(watchedProductId || null);

  const productLookup = useMemo(() => new Map(products.map((p) => [p.id, p.name])), [products]);
  const availableProductIds = useMemo(
    () => new Set(stocks.filter((stock) => stock.available_stock_kg > 0).map((stock) => stock.product_id)),
    [stocks],
  );
  const productsInStock = useMemo(
    () => products.filter((product) => availableProductIds.has(product.id)),
    [products, availableProductIds],
  );

  const filteredBatches = useMemo(() => {
    const base = [...batches]
      .filter((item) =>
        Boolean(
          // Linked pre-harvest lots ready for post-harvest continuation.
          (item.member_id &&
            item.parcel_id &&
            item.preharvest_completed_at &&
            (item.collecte_created || item.stock_in_created) &&
            item.confirmed_weight_kg &&
            item.postharvest_status !== "not_ready_post_recolte") ||
            // Free post-harvest lots (not linked to pre-harvest/collecte).
            (!item.member_id && !item.parcel_id),
        ),
      )
      .sort((a, b) => b.creation_date.localeCompare(a.creation_date));
    return base.filter((item) => {
      const productName = productLookup.get(item.product_id) ?? "";
      const text = `${item.code} ${item.product_id} ${productName}`.toLowerCase();
      return text.includes(query.toLowerCase());
    });
  }, [batches, query, productLookup]);

  const visibleBatches = useMemo(() => {
    const productFiltered = filteredBatches.filter(
      (item) => productFilterId === "all" || item.product_id === productFilterId,
    );
    const sorted = productFiltered.slice().sort((a, b) => a.creation_date.localeCompare(b.creation_date));
    return tableControls.sortOrder === "asc" ? sorted : sorted.reverse();
  }, [filteredBatches, productFilterId, tableControls.sortOrder]);
  const pagedVisibleBatches = useMemo(() => {
    const start = (listPage - 1) * listPageSize;
    return visibleBatches.slice(start, start + listPageSize);
  }, [visibleBatches, listPage, listPageSize]);
  useEffect(() => {
    setListPage(1);
  }, [query, productFilterId, tableControls.sortOrder, listPageSize]);

  const postHarvestProductFilterOptions = useMemo(() => {
    const ids = Array.from(new Set(filteredBatches.map((batch) => batch.product_id)));
    return ids
      .map((id) => ({ id, name: productLookup.get(id) ?? id }))
      .sort((a, b) => a.name.localeCompare(b.name, "fr"));
  }, [filteredBatches, productLookup]);

  const selectedBatch = useMemo(() => {
    if (selectedBatchId) {
      const match = visibleBatches.find((item) => item.id === selectedBatchId);
      if (match) return match;
    }
    return visibleBatches[0] ?? null;
  }, [selectedBatchId, visibleBatches]);
  const selectedBatchFluxMeta = useMemo(
    () => parsePostHarvestStockMeta(selectedBatch?.status_note ?? null),
    [selectedBatch?.status_note],
  );
  const { data: materialBalanceData } = useBatchMaterialBalance(selectedBatch?.id ?? null);
  const requiredLoading = batchesQuery.isLoading || productsQuery.isLoading || stocksQuery.isLoading || stepsQuery.isLoading;
  const requiredError = batchesQuery.isError || productsQuery.isError || stocksQuery.isError || stepsQuery.isError;

  useEffect(() => {
    setActiveTab(normalizeTab(queryTab));
  }, [queryTab]);

  useEffect(() => {
    if (queryLot) setSelectedBatchId(queryLot);
  }, [queryLot]);

  useEffect(() => {
    if (!selectedBatch && visibleBatches.length > 0) {
      setSelectedBatchId(visibleBatches[0].id);
    }
  }, [selectedBatch, visibleBatches]);

  const stepsByBatch = useMemo(() => {
    const grouped = new Map<string, ProcessStep[]>();
    for (const step of steps) {
      const list = grouped.get(step.batch_id) ?? [];
      list.push(step);
      grouped.set(step.batch_id, list);
    }
    for (const [batchId, list] of grouped.entries()) {
      grouped.set(
        batchId,
        list.slice().sort((a, b) => (a.sequence_order - b.sequence_order) || new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
      );
    }
    return grouped;
  }, [steps]);

  const selectedSteps = useMemo(() => {
    if (!selectedBatch) return [];
    return stepsByBatch.get(selectedBatch.id) ?? [];
  }, [stepsByBatch, selectedBatch]);

  const selectedRecommendations = useMemo(() => {
    if (!selectedBatch) return [];
    return (dashboard?.recent_recommendations ?? []).filter((item) => item.batch_id === selectedBatch.id);
  }, [dashboard?.recent_recommendations, selectedBatch]);

  const recommendationCards = useMemo<LotRecommendationItem[]>(() => {
    const fromSignals = selectedRecommendations.map((item) => {
      const priority = recommendationPriority(item);
      const decisionStatus = decisionStatusFromRecommendation(item);
      const impactedStep = parseImpactedStep(item);
      const anomalyText = item.anomaly_detected ? "détectée" : "non détectée";
      const evidence = [
        `Perte cumulée: ${formatPct(item.loss_pct)}`,
        `Efficacité globale: ${formatPct(item.efficiency_pct)}`,
        `Étape la plus contributive: ${impactedStep}`,
        `Anomalie critique: ${anomalyText}`,
      ];

      let mainReason = `Le lot reste stable: perte cumulée ${formatPct(item.loss_pct)} et efficacité ${formatPct(item.efficiency_pct)}.`;
      let recommendedAction =
        "Continuer le suivi normal. Vérifier uniquement l’étape la plus contributive à la perte lors du prochain contrôle.";
      let confidence =
        "Niveau de confiance indicatif. Continuer la collecte terrain pour confirmer la stabilité.";

      if (decisionStatus === "À surveiller") {
        mainReason = `Le lot est à surveiller: perte cumulée ${formatPct(item.loss_pct)} et efficacité ${formatPct(item.efficiency_pct)}.`;
        recommendedAction =
          "Renforcer le contrôle de l’étape la plus contributive, vérifier les écarts de pesée et ajuster la méthode opératoire dès la prochaine exécution.";
        confidence = "Signal utile pour action préventive. Confirmer avec les observations terrain de l’équipe.";
      } else if (decisionStatus === "Prioritaire") {
        mainReason = `Le lot présente un risque prioritaire: perte cumulée ${formatPct(item.loss_pct)} et efficacité ${formatPct(item.efficiency_pct)}.`;
        recommendedAction =
          "Traiter en priorité l’étape la plus contributive, contrôler le bilan matière (quantité entrée/sortie) et corriger immédiatement le protocole opératoire.";
        confidence = "Signal fort d’aide à la décision. Vérification terrain immédiate recommandée.";
      } else if (decisionStatus === "Critique") {
        mainReason = `Situation critique: perte cumulée ${formatPct(item.loss_pct)} et efficacité ${formatPct(item.efficiency_pct)} avec signal d’anomalie élevé.`;
        recommendedAction =
          "Lancer une inspection immédiate: vérifier quantités entrée/sortie, pertes par étape et conditions sensibles (séchage, stockage, humidité), puis appliquer un plan correctif sans délai.";
        confidence = "Alerte élevée. Action immédiate conseillée avant poursuite normale du flux.";
      }

      return {
        id: `${item.batch_id}-${item.anomaly_score}-${item.loss_pct}`,
        title:
          decisionStatus === "Stable"
            ? "Lot stable — priorité faible"
            : decisionStatus === "À surveiller"
              ? "Lot à surveiller — priorité moyenne"
              : decisionStatus === "Prioritaire"
                ? "Lot prioritaire — action rapide recommandée"
                : "Lot critique — intervention immédiate",
        priority,
        decisionStatus,
        focusStage: impactedStep,
        mainReason,
        evidence,
        recommendedAction:
          item.suggested_action && item.suggested_action.trim().length > 0
            ? `${recommendedAction} Point d’attention additionnel: ${item.suggested_action}`
            : recommendedAction,
        confidence,
        caveat:
          "Signal d’aide à la décision. À confirmer avec les observations terrain et le suivi opérationnel.",
      };
    });
    if (fromSignals.length > 0) return fromSignals;
    if (selectedSteps.length === 0) return [];

    const grouped = new Map<string, { stage: string; qtyIn: number; qtyOut: number; lossKg: number; lossPct: number; efficiencyPct: number; count: number }>();
    for (const step of selectedSteps) {
      const key = step.type;
      const current = grouped.get(key) ?? { stage: stageLabelFromType(step.type), qtyIn: 0, qtyOut: 0, lossKg: 0, lossPct: 0, efficiencyPct: 0, count: 0 };
      current.qtyIn += step.qty_in;
      current.qtyOut += step.qty_out;
      current.lossKg += step.normalized_loss_value;
      current.lossPct += step.loss_pct;
      current.efficiencyPct += step.efficiency_pct;
      current.count += 1;
      grouped.set(key, current);
    }
    const stageView = Array.from(grouped.entries()).map(([key, value]) => ({
      key,
      stage: value.stage,
      qtyIn: value.qtyIn,
      qtyOut: value.qtyOut,
      lossKg: value.lossKg,
      lossPct: value.count > 0 ? value.lossPct / value.count : 0,
      efficiencyPct: value.count > 0 ? value.efficiencyPct / value.count : 0,
    }));
    const weakest = stageView.slice().sort((a, b) => b.lossPct - a.lossPct)[0];
    const priority: LotRecommendationItem["priority"] = weakest.lossPct >= 12 ? "critical" : weakest.lossPct >= 8 ? "high" : "medium";
    return [
      {
        id: `stage-${weakest.key}`,
        title:
          weakest.lossPct >= 12
            ? "Lot critique — intervention immédiate"
            : weakest.lossPct >= 8
              ? "Lot prioritaire — action rapide recommandée"
              : "Lot à surveiller — priorité moyenne",
        priority,
        decisionStatus: weakest.lossPct >= 12 ? "Critique" : weakest.lossPct >= 8 ? "Prioritaire" : "À surveiller",
        focusStage: weakest.stage,
        mainReason: `Le lot présente une perte notable sur l’étape ${weakest.stage.toLowerCase()}: ${formatPct(weakest.lossPct)} de perte moyenne et ${formatPct(weakest.efficiencyPct)} d’efficacité.`,
        evidence: [
          `Perte cumulée lot: ${formatPct(selectedBatch?.confirmed_weight_kg ? ((Math.max((selectedBatch.confirmed_weight_kg - (selectedBatch.current_qty ?? 0)), 0) / selectedBatch.confirmed_weight_kg) * 100) : 0)}`,
          `Efficacité globale lot: ${formatPct(selectedBatch?.confirmed_weight_kg ? (((selectedBatch.current_qty ?? 0) / selectedBatch.confirmed_weight_kg) * 100) : 0)}`,
          `Étape la plus contributive: ${weakest.stage}`,
          `Perte sur l’étape: ${formatKg(weakest.lossKg)}`,
        ],
        recommendedAction:
          "Vérifier immédiatement cette étape: bilan matière entrée/sortie, réglages opératoires et points de contrôle qualité. Renforcer le suivi lors du prochain passage.",
        confidence: "Confiance modérée. Données disponibles sur le lot courant uniquement.",
        caveat: "Données insuffisantes pour une conclusion forte sur tendance longue. Continuer la collecte et valider sur le terrain.",
      },
    ];
  }, [selectedRecommendations, selectedSteps, selectedBatch?.confirmed_weight_kg, selectedBatch?.current_qty]);

  const materialBalance = useMemo(() => {
    if (materialBalanceData) {
      return {
        initialKg: materialBalanceData.initial_confirmed_qty,
        currentKg: materialBalanceData.current_qty,
        exitsKg: 0,
        lossesKg: materialBalanceData.total_loss_qty,
        lossPct: materialBalanceData.total_loss_pct,
      };
    }
    const initialKg = selectedBatch?.confirmed_weight_kg ?? 0;
    const currentKg = selectedBatch?.current_qty ?? selectedBatch?.confirmed_weight_kg ?? 0;
    const computedGapKg = Math.max(initialKg - currentKg, 0);
    const lossPct = initialKg > 0 ? (computedGapKg / initialKg) * 100 : 0;
    return { initialKg, currentKg, exitsKg: 0, lossesKg: computedGapKg, lossPct };
  }, [materialBalanceData, selectedBatch?.confirmed_weight_kg, selectedBatch?.current_qty]);

  const stageMetrics = useMemo(() => {
    const stageOrder = new Map<string, number>();
    selectedSteps
      .slice()
      .sort((a, b) => a.sequence_order - b.sequence_order)
      .forEach((step, index) => {
        const key = (step.type || "").toLowerCase();
        if (!stageOrder.has(key)) {
          stageOrder.set(key, index);
        }
      });
    const grouped = new Map<
      string,
      { qtyIn: number; qtyOut: number; loss: number; efficiency: number; count: number; anomalies: number; lossKg: number; status: "pending" | "done" | "cancelled" }
    >();
    selectedSteps.forEach((step) => {
      const key = step.type;
      const current = grouped.get(key) ?? { qtyIn: 0, qtyOut: 0, loss: 0, efficiency: 0, count: 0, anomalies: 0, lossKg: 0, status: "done" as const };
      current.qtyIn += step.qty_in;
      current.qtyOut += step.qty_out;
      current.loss += step.loss_pct;
      current.lossKg += step.normalized_loss_value;
      current.efficiency += step.efficiency_pct;
      current.count += 1;
      if (step.warning || step.loss_pct >= 12) current.anomalies += 1;
      if (step.stage_status === "pending") current.status = "pending";
      if (step.stage_status === "cancelled") current.status = "cancelled";
      grouped.set(key, current);
    });

    return Array.from(grouped.entries())
      .map(([key, values]) => ({
        key,
        stage: stageLabelFromType(key),
        status: values.status,
        qtyIn: values.qtyIn,
        qtyOut: values.qtyOut,
        lossKg: values.lossKg,
        lossPct: values.count > 0 ? values.loss / values.count : 0,
        efficiencyPct: values.count > 0 ? values.efficiency / values.count : 0,
        anomalies: values.anomalies,
      }))
      .sort((a, b) => {
        const orderA = stageOrder.get((a.key || "").toLowerCase()) ?? Number.MAX_SAFE_INTEGER;
        const orderB = stageOrder.get((b.key || "").toLowerCase()) ?? Number.MAX_SAFE_INTEGER;
        return orderA - orderB;
      });
  }, [selectedSteps]);

  const workflowRows = useMemo<ProcessTableRow[]>(() => {
    if (!selectedBatch) return [];
    const ordered = selectedBatch.ordered_process_steps ?? [];
    const executedByOrder = new Map<number, ProcessStep>();
    for (const step of selectedSteps) {
      executedByOrder.set(step.sequence_order, step);
    }

    const nextExecutableOrder = selectedSteps.length < ordered.length ? selectedSteps.length + 1 : null;

    const rows: ProcessTableRow[] = ordered.map((stepName, index) => {
      const order = index + 1;
      const step = executedByOrder.get(order);
      const mapped = stageFromType(stepName) ?? stageFromType(step?.type ?? stepName);
      const status: ProcessTableRow["status"] = step
        ? step.stage_status === "pending"
          ? "current"
          : step.warning
            ? "warning"
            : "done"
        : nextExecutableOrder === order
          ? "current"
          : "pending";

      return {
        key: `planned-${order}`,
        order,
        label: stepName,
        icon: mapped?.icon ?? "🧩",
        typeTag: mapped?.typeTag ?? "process",
        phase: mapped?.phase ?? "post_harvest",
        status,
        isExecutable: !step && nextExecutableOrder === order,
        step,
      };
    });

    const extras = selectedSteps
      .filter((step) => step.sequence_order > ordered.length)
      .map<ProcessTableRow>((step) => ({
        key: `extra-${step.id}`,
        order: step.sequence_order,
        label: step.type,
        icon: "🧩",
        typeTag: "personnalise",
        phase: "post_harvest",
        status: step.warning ? "warning" : "done",
        step,
      }));

    return [...rows, ...extras];
  }, [selectedBatch, selectedSteps]);

  const timelineRows = useMemo<TimelineStage[]>(
    () =>
      workflowRows.map((row) => ({
        key: row.key,
        order: row.order,
        label: row.label,
        icon: row.icon,
        typeTag: row.typeTag,
        phase: row.phase,
        status: row.status,
        qtyOut: row.step?.qty_out,
        lossKg: row.step?.normalized_loss_value,
      })),
    [workflowRows],
  );

  const lotSidebarItems = useMemo<ActiveLotItem[]>(() => {
    return pagedVisibleBatches.map((batch) => {
      const lotSteps = stepsByBatch.get(batch.id) ?? [];
      const total = Math.max(batch.ordered_process_steps.length, 1);
      const done = Math.min(lotSteps.length, total);
      const latest = lotSteps[lotSteps.length - 1];
      const latestStage = latest ? stageFromType(latest.type) : null;
      const progressPct = (done / total) * 100;
      return {
        id: batch.id,
        code: batch.code,
        productName: productLookup.get(batch.product_id) ?? batch.product_id.slice(0, 8),
        seasonLabel: buildSeasonFromDate(batch.creation_date),
        phaseLabel: phaseLabel(latestStage?.phase ?? "post_harvest"),
        stepsDone: done,
        stepsTotal: total,
        currentQty: batch.current_qty,
        unit: batch.unit,
        progressPct,
        statusLabel: lotPostHarvestStatusLabel(batch),
        statusTone: lotPostHarvestStatusTone(batch),
      };
    });
  }, [pagedVisibleBatches, productLookup, stepsByBatch]);

  const lotExportColumns: ExportColumn<Batch>[] = [
    { key: "code", header: "Lot" },
    { key: "creation_date", header: "Date création" },
    { key: "product", header: "Produit", format: (_, row) => productLookup.get(row.product_id) ?? row.product_id },
    { key: "confirmed_weight_kg", header: "Poids confirmé (kg)", format: (_, row) => row.confirmed_weight_kg?.toLocaleString("fr-FR") ?? "—" },
    { key: "current_qty", header: "Stock actuel (kg)", format: (_, row) => row.current_qty?.toLocaleString("fr-FR") ?? "—" },
    { key: "status", header: "Statut", format: (_, row) => lotPostHarvestStatusLabel(row) },
  ];

  const anomalyCount = selectedSteps.filter((step) => step.warning || step.loss_pct >= 12).length;
  const latestRecommendation = recommendationCards[0] ?? null;
  const selectedSeason = selectedBatch ? buildSeasonFromDate(selectedBatch.creation_date) : "";
  const postHarvestInitialQty = materialBalance.initialKg;
  const postHarvestCurrentQty = materialBalance.currentKg;
  const selectedLossPct = materialBalance.lossPct;
  const forecastQty = selectedBatch?.estimated_qty_kg ?? null;
  const forecastGap = useMemo(() => {
    if (forecastQty === null || forecastQty === undefined || !selectedBatch?.confirmed_weight_kg) return null;
    const delta = selectedBatch.confirmed_weight_kg - forecastQty;
    const pct = forecastQty > 0 ? (delta / forecastQty) * 100 : 0;
    return { delta, pct };
  }, [forecastQty, selectedBatch?.confirmed_weight_kg]);

  const selectedProductStock = useMemo(() => {
    if (!watchedProductId) return null;
    return stocks.find((stock) => stock.product_id === watchedProductId) ?? null;
  }, [stocks, watchedProductId]);

  const availableStockKg = selectedProductStock?.available_stock_kg ?? 0;
  const availableStockDisplay = fromKg(availableStockKg, watchedLotUnit);

  const selectedBatchAvailableBuckets = useMemo(() => {
    if (!selectedBatch) return [];
    return stocks
      .filter((row) => row.product_id === selectedBatch.product_id && row.available_stock_kg > 0)
      .sort((a, b) => b.available_stock_kg - a.available_stock_kg);
  }, [selectedBatch, stocks]);

  const selectedBatchCanStartPostHarvest = useMemo(() => {
    if (!selectedBatch) return false;
    const isFreeLot = !selectedBatch.member_id && !selectedBatch.parcel_id;
    if (!isFreeLot) {
      if (selectedBatch.postharvest_status !== "ready_post_recolte") return false;
      if (!(selectedBatch.collecte_created || selectedBatch.stock_in_created)) return false;
    } else {
      if (selectedBatch.postharvest_status === "in_post_recolte" || selectedBatch.postharvest_status === "post_recolte_completed") return false;
    }
    return selectedBatchAvailableBuckets.length > 0;
  }, [selectedBatch, selectedBatchAvailableBuckets.length]);

  const postHarvestGradeOptions = useMemo(() => {
    if (!postHarvestProductId) return [];
    return stocks
      .filter((row) => row.product_id === postHarvestProductId && row.available_stock_kg > 0)
      .sort((a, b) => b.available_stock_kg - a.available_stock_kg)
      .map((row) => ({ grade: row.grade, available: row.available_stock_kg }));
  }, [postHarvestProductId, stocks]);

  const selectedPostHarvestGradeBucket = useMemo(
    () => postHarvestGradeOptions.find((entry) => entry.grade === postHarvestGrade) ?? null,
    [postHarvestGradeOptions, postHarvestGrade],
  );
  const selectedPostHarvestAvailableKg = selectedPostHarvestGradeBucket?.available ?? 0;
  const postHarvestQuantityNumber = Number(postHarvestQuantity);
  const postHarvestQuantityInvalid =
    !Number.isFinite(postHarvestQuantityNumber) ||
    postHarvestQuantityNumber <= 0 ||
    postHarvestQuantityNumber > selectedPostHarvestAvailableKg;
  const postHarvestSubmitDisabled =
    !selectedBatch ||
    !postHarvestProductId ||
    !postHarvestGrade ||
    postHarvestQuantity.trim() === "" ||
    postHarvestQuantityInvalid ||
    startPostHarvest.isPending;
  const selectedBatchFluxRemainingKg = useMemo(() => {
    if (!selectedBatchFluxMeta) return 0;
    return (
      stocks.find(
        (row) => row.product_id === selectedBatchFluxMeta.product_id && row.grade === selectedBatchFluxMeta.grade,
      )?.available_stock_kg ?? 0
    );
  }, [selectedBatchFluxMeta, stocks]);

  useEffect(() => {
    if (!postHarvestModalOpen || !selectedBatch) return;
    const fallbackBucket = selectedBatchAvailableBuckets[0] ?? null;
    setPostHarvestProductId(selectedBatch.product_id);
    setPostHarvestGrade((current) => (current ? current : fallbackBucket?.grade ?? ""));
    setPostHarvestQuantity((current) => {
      if (current.trim()) return current;
      const fallbackQty = fallbackBucket ? Math.max(1, Math.floor(fallbackBucket.available_stock_kg)) : 0;
      return fallbackQty > 0 ? String(fallbackQty) : "";
    });
  }, [postHarvestModalOpen, selectedBatch, selectedBatchAvailableBuckets]);

  const historyItems = useMemo(() => {
    if (!selectedBatch) return [];
    const stepItems = selectedSteps
      .map((step) => ({
        id: step.id,
        title: `${step.sequence_order}. ${stageLabelFromType(step.type)}`,
        detail: `Entrée ${step.qty_in.toFixed(2)} kg · Perte ${step.normalized_loss_value.toFixed(2)} kg · Sortie ${step.qty_out.toFixed(2)} kg`,
        date: step.date,
      }))
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    return [
      {
        id: `batch-${selectedBatch.id}`,
        title: `Lot ${selectedBatch.code} créé`,
        detail: `Stock initial post-récolte ${materialBalance.initialKg.toFixed(2)} kg · Stock actuel ${materialBalance.currentKg.toFixed(2)} kg`,
        date: selectedBatch.creation_date,
      },
      ...stepItems,
    ];
  }, [selectedBatch, selectedSteps, materialBalance.initialKg, materialBalance.currentKg]);

  const missingConditions = useMemo(() => {
    const conditions: string[] = [];
    if (!selectedBatch?.confirmed_weight_kg) conditions.push("poids confirmé indisponible");
    if (selectedSteps.length === 0) conditions.push("aucune étape complétée");
    if (selectedSteps.some((step) => !step.qty_out || step.qty_out <= 0)) conditions.push("quantité sortante manquante sur au moins une étape");
    return conditions;
  }, [selectedBatch?.confirmed_weight_kg, selectedSteps]);

  const analyticsFallbackReason = useMemo(() => {
    if (stageMetrics.length > 0 && (materialBalanceData || selectedBatch?.confirmed_weight_kg)) return null;
    if (missingConditions.length === 0) return "Aucune donnée exploitable disponible.";
    return `Condition(s) manquante(s): ${missingConditions.join(" · ")}.`;
  }, [materialBalanceData, missingConditions, selectedBatch?.confirmed_weight_kg, stageMetrics.length]);

  const recommendationsFallbackReason = analyticsFallbackReason;

  const interpretation = useMemo(() => {
    const ranked = stageMetrics.slice().sort((a, b) => a.lossPct - b.lossPct);
    const best = ranked[0] ?? null;
    const weakest = ranked[ranked.length - 1] ?? null;
    const verdict =
      materialBalance.lossPct >= 12
        ? "Perte cumulée au-dessus du seuil de surveillance. Un plan correctif immédiat est recommandé."
        : materialBalance.lossPct >= 8
          ? "Perte cumulée à surveiller. Ajuster les contrôles sur l'étape la plus contributrice."
          : "Perte cumulée dans une plage acceptable. Maintenir la discipline d'exécution.";
    return {
      bestStage: best?.stage ?? null,
      weakestStage: weakest?.stage ?? null,
      mainLossSource: weakest ? `${weakest.stage} (${weakest.lossPct.toFixed(1)}%)` : null,
      verdict,
    };
  }, [materialBalance.lossPct, stageMetrics]);

  const updateQuery = (nextTab: LotWorkspaceTab, nextLotId?: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", nextTab);
    const lotValue = typeof nextLotId === "string" ? nextLotId : selectedBatch?.id;
    if (lotValue) params.set("lot", lotValue);
    else params.delete("lot");
    router.replace(`/manager/lots?${params.toString()}`, { scroll: false });
  };

  const handleSwitchTab = (tab: LotWorkspaceTab) => {
    setActiveTab(tab);
    updateQuery(tab);
  };

  const handleSelectLot = (lotId: string) => {
    setSelectedBatchId(lotId);
    updateQuery(activeTab, lotId);
  };

  const openEditLot = (batch: Batch) => {
    const productName = productLookup.get(batch.product_id) ?? null;
    const fallbackSteps = getProductStepTemplate(productName, "post_harvest");
    setEditingBatch(batch);
    lotForm.reset({
      product_id: batch.product_id,
      creation_date: batch.creation_date,
      initial_qty: batch.initial_qty,
      unit: (batch.unit || "kg") as MassUnit,
      process_steps: batch.ordered_process_steps?.length ? batch.ordered_process_steps : fallbackSteps,
    });
    setPlannedStepsDraft(batch.ordered_process_steps?.length ? batch.ordered_process_steps : fallbackSteps);
    setStepToAdd("");
    setCustomStepInput("");
    setFormError(null);
    setLotFormOpen(true);
  };

  const openCreateLot = () => {
    const firstProduct = productsInStock[0];
    setEditingBatch(null);
    lotForm.reset({
      product_id: firstProduct?.id ?? "",
      creation_date: todayIso,
      initial_qty: 0,
      unit: "kg",
      process_steps: defaultSteps,
    });
    setPlannedStepsDraft(defaultSteps);
    setStepToAdd("");
    setCustomStepInput("");
    setFormError(null);
    setLotFormOpen(true);
  };

  const expectedInputForOrder = (order: number): number => {
    if (!selectedBatch) return 0;
    if (order <= 1) return Number(selectedBatch.confirmed_weight_kg ?? selectedBatch.current_qty ?? 0);
    const previous = selectedSteps.find((item) => item.sequence_order === order - 1);
    return Number(previous?.qty_out ?? selectedBatch.current_qty ?? 0);
  };

  const openCreateStep = (row?: ProcessTableRow) => {
    if (!selectedBatch) return;
    const target = row ?? workflowRows.find((item) => item.isExecutable);
    if (!target) {
      setFormError("Aucune etape executable pour ce lot.");
      return;
    }
    setEditingStep(null);
    setStepTargetOrder(target.order);
    setCompletingPendingStep(false);
    setStepPreset({ key: target.key, label: target.label, icon: target.icon, typeTag: target.typeTag });
    stepForm.reset({
      batch_id: selectedBatch.id,
      type: target.label,
      date: todayIso,
      qty_in: expectedInputForOrder(target.order),
      loss_value: 0,
      loss_unit: selectedBatch.unit,
      notes: "",
      duration_minutes: undefined,
    });
    setFormError(null);
    setStepFormOpen(true);
  };

  const openEditStep = (step: ProcessStep) => {
    const mapped = stageFromType(step.type);
    setEditingStep(step);
    setStepTargetOrder(step.sequence_order);
    setCompletingPendingStep(step.stage_status === "pending");
    setStepPreset(
      mapped
        ? {
            key: mapped.key,
            label: mapped.label,
            icon: mapped.icon,
            typeTag: mapped.typeTag,
          }
        : null,
    );
    stepForm.reset({
      batch_id: step.batch_id,
      type: step.type,
      date: step.date,
      qty_in: step.qty_in,
      loss_value: step.normalized_loss_value,
      loss_unit: step.loss_unit,
      notes: step.notes ?? "",
      duration_minutes: durationDaysFromMinutes(step.duration_minutes),
    });
    setFormError(null);
    setStepFormOpen(true);
  };

  const closeForms = () => {
    setLotFormOpen(false);
    setStepFormOpen(false);
    setEditingBatch(null);
    setEditingStep(null);
    setCompletingPendingStep(false);
    setFormError(null);
    setStepPreset(null);
    setStepTargetOrder(null);
  };

  const addPlannedStep = (label: string) => {
    const value = label.trim();
    if (!value) return;
    setPlannedStepsDraft((current) => [...current, value]);
  };

  const movePlannedStep = (index: number, direction: -1 | 1) => {
    setPlannedStepsDraft((current) => {
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= current.length) return current;
      const clone = [...current];
      const [item] = clone.splice(index, 1);
      clone.splice(nextIndex, 0, item);
      return clone;
    });
  };

  const submitLot = lotForm.handleSubmit(async (values) => {
    setFormError(null);
    try {
      if (plannedStepsDraft.length === 0) {
        setFormError("Selectionnez au moins une etape de process pour ce lot.");
        return;
      }
      if (editingBatch) {
        const updated = await updateBatch.mutateAsync({
          id: editingBatch.id,
          payload: { process_steps: plannedStepsDraft },
        });
        setSelectedBatchId(updated.id);
      } else {
        if (!availableProductIds.has(values.product_id)) {
          setFormError("Sélectionnez un produit actuellement disponible en stock.");
          return;
        }
        const lotUnit = (values.unit || "kg") as MassUnit;
        const requestedQty = Number(values.initial_qty);
        const requestedQtyKg = toKg(requestedQty, lotUnit);
        if (requestedQtyKg > availableStockKg) {
          setFormError("Impossible de creer ce lot : quantite demandee superieure au stock disponible.");
          return;
        }

        const payload: BatchCreate = {
          product_id: values.product_id,
          creation_date: values.creation_date,
          initial_qty: requestedQty,
          unit: lotUnit,
          process_steps: plannedStepsDraft,
        };

        const created = await createBatch.mutateAsync(payload);
        setSelectedBatchId(created.id);
      }
      closeForms();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer le lot.");
    }
  });

  const submitStep = stepForm.handleSubmit(async (values) => {
    setFormError(null);
    try {
      if (!selectedBatch) {
        setFormError("Selectionnez un lot.");
        return;
      }

      const incomingQty = Number(values.qty_in ?? expectedInputForOrder(stepTargetOrder ?? workflowRows.length + 1));
      const lossKg = Number(values.loss_value ?? 0);
      const computedQtyOut = Math.max(incomingQty - lossKg, 0);

      if (editingStep) {
        if (completingPendingStep) {
          const payload: ProcessStepCompletePayload = {
            date: values.date,
            loss_value: lossKg,
            loss_unit: values.loss_unit,
            notes: values.notes?.trim() || null,
            duration_minutes: durationMinutesFromDays(values.duration_minutes ?? undefined),
          };
          await completeStep.mutateAsync({ id: editingStep.id, payload });
        } else {
          const payload: ProcessStepUpdate = {
            date: values.date,
            qty_out: computedQtyOut,
            loss_unit: values.loss_unit,
            notes: values.notes?.trim() || null,
            duration_minutes: durationMinutesFromDays(values.duration_minutes ?? undefined),
          };
          await updateStep.mutateAsync({ id: editingStep.id, payload });
        }
      } else {
        const computedQtyIn = expectedInputForOrder(stepTargetOrder ?? workflowRows.length + 1);
          const payload: ProcessStepCreate = {
            batch_id: selectedBatch.id,
            type: stepPreset?.label,
            date: values.date,
            qty_in: computedQtyIn,
            loss_value: lossKg,
            loss_unit: values.loss_unit,
            notes: values.notes?.trim() || null,
            duration_minutes: durationMinutesFromDays(values.duration_minutes ?? undefined),
          };
        await createStep.mutateAsync(payload);
      }
      closeForms();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer l'etape.");
    }
  });

  const handleDeleteStep = async (step: ProcessStep) => {
    try {
      await deleteStep.mutateAsync(step.id);
      closeForms();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de supprimer l'etape.");
    }
  };

  const openPostHarvestModal = () => {
    if (!selectedBatch) return;
    if (!selectedBatchCanStartPostHarvest) {
      setFormError("Lot non éligible au démarrage Post-récolte ou stock indisponible.");
      return;
    }
    setPostHarvestFormError(null);
    setPostHarvestModalOpen(true);
  };

  const closePostHarvestModal = () => {
    setPostHarvestModalOpen(false);
    setPostHarvestFormError(null);
  };

  const handleStartPostHarvest = async () => {
    if (!selectedBatch) return;
    setFormError(null);
    setPostHarvestFormError(null);
    if (!postHarvestProductId || !postHarvestGrade) {
      setPostHarvestFormError("Produit et grade sont requis.");
      return;
    }
    if (postHarvestQuantityInvalid) {
      setPostHarvestFormError("La quantité doit être > 0 et ≤ au stock disponible.");
      return;
    }
    try {
      await startPostHarvest.mutateAsync({
        id: selectedBatch.id,
        payload: {
          product_id: postHarvestProductId,
          grade: postHarvestGrade,
          quantity_kg: postHarvestQuantityNumber,
        },
      });
      closePostHarvestModal();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Impossible de démarrer la Post-récolte.";
      setPostHarvestFormError(message);
    }
  };

  const handleEnterStage = (row: ProcessTableRow) => {
    if (!row.isExecutable) return;
    if (!selectedBatch) return;
    if (selectedBatch.postharvest_status === "ready_post_recolte") {
      setFormError("Démarrez d'abord la Post-récolte pour ce lot.");
      return;
    }
    openCreateStep(row);
  };

  const stepModalTitle = editingStep
    ? `${completingPendingStep ? "Completer" : "Modifier"} - ${stepPreset?.label ?? stageLabelFromType(editingStep.type)}`
    : `Executer - ${stepPreset?.label ?? "Etape"}`;

  if (requiredLoading) {
    return (
      <main className="relative min-h-[60vh]">
        <PageIntro title="Flux matière" />
        <ContentAreaLoader
          title="Chargement Flux matière"
          subtitle="Synchronisation des lots, étapes et stocks..."
        />
      </main>
    );
  }

  if (requiredError) {
    return (
      <main>
        <PageIntro title="Flux matière" />
        <section className="premium-card reveal mt-4 rounded-2xl p-4">
          <p className="text-sm text-[var(--danger)]">Impossible de charger les données requises de la page Flux matière.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="min-w-0 overflow-x-hidden">
      <PageIntro title="Flux matière" />
      <section className="premium-card reveal rounded-2xl p-3" style={{ ["--delay" as string]: "30ms" }}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="flex flex-wrap items-center gap-2 sm:col-span-2 xl:col-span-3">
            <button
              type="button"
              onClick={openCreateLot}
              className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold"
            >
              + Nouveau lot Post-récolte
            </button>
            <button
              type="button"
              onClick={() => openCreateStep()}
              className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold"
              disabled={!selectedBatch || selectedBatch.postharvest_status === "ready_post_recolte"}
            >
              + Compléter étape
            </button>
            <button
              type="button"
              onClick={() => handleSwitchTab("recommendations")}
              className="soft-focus rounded-xl border border-[#D0C4FF] bg-[#F3EEFF] px-4 py-2 text-sm font-semibold text-[#6A4DE0] hover:brightness-95"
            >
              Conseils IA
            </button>
          </div>

          <div className="sm:col-span-2 xl:col-span-4">
            <TableToolbar
              search={query}
              onSearchChange={setQuery}
              searchPlaceholder="Rechercher un lot..."
              filters={[
                {
                  key: "product",
                  label: "Filtrer par produit",
                  value: productFilterId,
                  options: [
                    { value: "all", label: "Tous les produits" },
                    ...postHarvestProductFilterOptions.map((product) => ({
                      value: product.id,
                      label: product.name,
                    })),
                  ],
                },
              ]}
              onFilterChange={(key, value) => {
                if (key === "product") setProductFilterId(value);
              }}
              sortOrder={tableControls.sortOrder}
              onSortOrderChange={tableControls.setSortOrder}
              sortAscLabel="Date asc"
              sortDescLabel="Date desc"
              rightActions={
                <div className="flex items-center gap-2">
                  <select value={listPageSize} onChange={(event) => setListPageSize(Number(event.target.value))} className="soft-focus wf-input h-10 min-w-[110px] px-3 text-sm">
                    <option value={10}>10 / page</option>
                    <option value={20}>20 / page</option>
                    <option value={50}>50 / page</option>
                  </select>
                  <ExportActions
                    onCsv={() => exportRowsToCsv({ filename: "lots-post-recolte", title: "Lots Post-récolte", columns: lotExportColumns, rows: visibleBatches })}
                    onExcel={() => exportRowsToExcel({ filename: "lots-post-recolte", title: "Lots Post-récolte", columns: lotExportColumns, rows: visibleBatches })}
                    onPdf={() => exportRowsToPdf({ filename: "lots-post-recolte", title: "Lots Post-récolte", columns: lotExportColumns, rows: visibleBatches })}
                  />
                </div>
              }
            />
          </div>
        </div>
      </section>

      {!selectedBatch ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "60ms" }}>
          <p className="text-sm text-[var(--muted)]">
            Aucun lot prêt pour la Post-récolte. Terminez la Pré-récolte puis créez une Collecte liée au lot.
          </p>
        </section>
      ) : (
        <section className="min-w-0 grid gap-4 xl:grid-cols-[300px_1fr]">
          <aside className="space-y-3">
            <LotActiveSidebar
              items={lotSidebarItems}
              selectedId={selectedBatch.id}
              onSelect={handleSelectLot}
            />
          </aside>

          <div className="min-w-0 space-y-4">
            <LotHeroBanner
              lotCode={selectedBatch.code}
              productName={productLookup.get(selectedBatch.product_id) ?? selectedBatch.product_id.slice(0, 8)}
              seasonLabel={selectedSeason}
              unit={selectedBatch.unit}
              initialQty={postHarvestInitialQty}
              currentQty={postHarvestCurrentQty}
              lossPct={selectedLossPct}
              statusLabel={lotPostHarvestStatusLabel(selectedBatch)}
              statusTone={lotPostHarvestStatusTone(selectedBatch)}
              onEditLot={() => openEditLot(selectedBatch)}
            />
            {forecastGap ? (
              <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "45ms" }}>
                <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Écart prévision / poids confirmé</p>
                <p className="mt-1 text-sm text-[var(--text)]">
                  Prévision: {forecastQty?.toLocaleString("fr-FR")} kg · Poids confirmé: {selectedBatch.confirmed_weight_kg?.toLocaleString("fr-FR")} kg
                </p>
                <p className="mt-1 text-sm font-semibold text-[var(--text)]">
                  Écart: {forecastGap.delta >= 0 ? "+" : ""}
                  {forecastGap.delta.toLocaleString("fr-FR")} kg ({forecastGap.pct.toFixed(1)}%)
                </p>
              </article>
            ) : null}

            <LotWorkspaceTabs activeTab={activeTab} onChange={handleSwitchTab} includeHistory />

            {activeTab === "process" && (
              <section className="min-w-0 space-y-4">
                <LotProcessTimeline stages={timelineRows} />
                <LotProcessTable rows={workflowRows} onEnterStage={handleEnterStage} onEditStep={openEditStep} />
              </section>
            )}

            {activeTab === "overview" && (
              <section className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
                <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "90ms" }}>
                  <h3 className="text-base font-semibold text-[var(--text)]">Vue d&apos;ensemble lot</h3>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                      <p className="text-[11px] text-[var(--muted)]">Etapes executees</p>
                      <p className="text-sm font-semibold text-[var(--text)]">{selectedSteps.length}</p>
                    </div>
                    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                      <p className="text-[11px] text-[var(--muted)]">Anomalies</p>
                      <p className={`text-sm font-semibold ${anomalyCount > 0 ? "text-[var(--danger)]" : "text-[var(--info)]"}`}>{anomalyCount}</p>
                    </div>
                    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                      <p className="text-[11px] text-[var(--muted)]">Pertes Post-récolte</p>
                      <p className="text-sm font-semibold text-[var(--text)]">{materialBalance.lossesKg.toFixed(2)} kg</p>
                    </div>
                    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                      <p className="text-[11px] text-[var(--muted)]">Statut lot</p>
                      <div className="mt-1">
                        <StatusBadge
                          label={lotPostHarvestStatusLabel(selectedBatch)}
                          tone={lotPostHarvestStatusTone(selectedBatch)}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-3">
                    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                      <p className="text-[11px] text-[var(--muted)]">Réf. Pré-récolte</p>
                      <p className="text-sm font-semibold text-[var(--text)]">{selectedBatch.preharvest_reference || selectedBatch.code}</p>
                    </div>
                    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                      <p className="text-[11px] text-[var(--muted)]">Réf. Collecte</p>
                      <p className="text-sm font-semibold text-[var(--text)]">{selectedBatch.collecte_reference || "Référence historique"}</p>
                    </div>
                    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                      <p className="text-[11px] text-[var(--muted)]">Réf. Post-récolte</p>
                      <p className="text-sm font-semibold text-[var(--text)]">{selectedBatch.postharvest_reference || "En attente de démarrage"}</p>
                    </div>
                  </div>
                  <div className="mt-3 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
                    <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Flux Post-récolte sélectionné</p>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      <p className="text-xs text-[var(--muted)]">
                        Réf. Post-récolte: <span className="font-semibold text-[var(--text)]">{selectedBatch.postharvest_reference || "En attente de démarrage"}</span>
                      </p>
                      <p className="text-xs text-[var(--muted)]">
                        Produit: <span className="font-semibold text-[var(--text)]">{productLookup.get(selectedBatchFluxMeta?.product_id || selectedBatch.product_id) ?? selectedBatch.product_id}</span>
                      </p>
                      <p className="text-xs text-[var(--muted)]">
                        Grade: <span className="font-semibold text-[var(--text)]">{selectedBatchFluxMeta?.grade || "Non spécifié"}</span>
                      </p>
                      <p className="text-xs text-[var(--muted)]">
                        Quantité allouée: <span className="font-semibold text-[var(--text)]">{(selectedBatchFluxMeta?.allocated_qty_kg ?? selectedBatch.confirmed_weight_kg ?? 0).toFixed(2)} kg</span>
                      </p>
                      <p className="text-xs text-[var(--muted)] sm:col-span-2">
                        Stock disponible/restant: <span className="font-semibold text-[var(--text)]">{selectedBatchFluxRemainingKg.toFixed(2)} kg</span>
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
                    <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Bilan matière Post-récolte</p>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      <p className="text-xs text-[var(--muted)]">Stock initial Post-récolte: <span className="font-semibold text-[var(--text)]">{materialBalance.initialKg.toFixed(2)} kg</span></p>
                      <p className="text-xs text-[var(--muted)]">Pertes Post-récolte: <span className="font-semibold text-[var(--text)]">{materialBalance.lossesKg.toFixed(2)} kg</span></p>
                      <p className="text-xs text-[var(--muted)]">Sorties stock: <span className="font-semibold text-[var(--text)]">{materialBalance.exitsKg.toFixed(2)} kg</span></p>
                      <p className="text-xs text-[var(--muted)]">Stock actuel: <span className="font-semibold text-[var(--text)]">{materialBalance.currentKg.toFixed(2)} kg</span></p>
                      {materialBalanceData?.final_output_qty !== undefined && materialBalanceData?.final_output_qty !== null ? (
                        <p className="text-xs text-[var(--muted)] sm:col-span-2">
                          Sortie finale Post-récolte: <span className="font-semibold text-[var(--text)]">{materialBalanceData.final_output_qty.toFixed(2)} kg</span>
                        </p>
                      ) : null}
                    </div>
                    <p className="mt-2 text-xs text-[var(--muted)]">Perte %: <span className="font-semibold text-[var(--text)]">{materialBalance.lossPct.toFixed(2)}%</span></p>
                  </div>
                </article>

                <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "110ms" }}>
                  <h3 className="text-base font-semibold text-[var(--text)]">Derniere recommandation IA</h3>
                  {latestRecommendation ? (
                    <div className="mt-3 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-[var(--text)]">{latestRecommendation.title}</p>
                        <StatusBadge
                          label={
                            latestRecommendation.priority === "critical"
                              ? "Critique"
                              : latestRecommendation.priority === "high"
                                ? "Haute"
                                : latestRecommendation.priority === "medium"
                                  ? "Moyenne"
                                  : "Faible"
                          }
                          tone={latestRecommendation.priority === "critical" ? "danger" : latestRecommendation.priority === "high" ? "warning" : "ai"}
                        />
                      </div>
                      <p className="mt-2 text-xs text-[var(--muted)]">{latestRecommendation.mainReason}</p>
                      <p className="mt-2 text-xs font-semibold text-[var(--ai-accent)]">{latestRecommendation.recommendedAction}</p>
                      <button
                        type="button"
                        onClick={() => handleSwitchTab("recommendations")}
                        className="mt-3 text-xs font-semibold text-[var(--ai-accent)] hover:underline"
                      >
                        Voir toutes les recommandations
                      </button>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-[var(--muted)]">Aucune recommandation spécifique pour ce lot.</p>
                  )}
                </article>
              </section>
            )}

            {activeTab === "analytics" && (
              <section className="space-y-4">
                <LotAnalyticsPanel
                  stageMetrics={stageMetrics}
                  initialQty={materialBalance.initialKg}
                  currentQty={materialBalance.currentKg}
                  finalQty={materialBalanceData?.final_output_qty ?? null}
                  totalLossKg={materialBalance.lossesKg}
                  totalLossPct={materialBalance.lossPct}
                  totalEfficiencyPct={materialBalanceData?.total_efficiency_pct ?? (materialBalance.initialKg > 0 ? (materialBalance.currentKg / materialBalance.initialKg) * 100 : 0)}
                  interpretation={interpretation}
                  fallbackReason={analyticsFallbackReason}
                />
              </section>
            )}

            {activeTab === "recommendations" && (
              <section className="space-y-4">
                <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "85ms" }}>
                  <h3 className="text-base font-semibold text-[var(--text)]">Aides à la décision du lot</h3>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    Ces recommandations sont des aides à la décision basées sur les données du lot, les règles métier et les signaux de risque disponibles. Elles ne remplacent pas la validation terrain.
                  </p>
                </article>
                <LotRecommendationPanel items={recommendationCards} fallbackReason={recommendationsFallbackReason} />
              </section>
            )}

            {activeTab === "history" && (
              <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "110ms" }}>
                <h3 className="text-base font-semibold text-[var(--text)]">Journal des mouvements du lot courant</h3>
                <div className="mt-3 space-y-2">
                  {historyItems.length === 0 ? (
                    <p className="text-sm text-[var(--muted)]">Aucun historique disponible.</p>
                  ) : (
                    historyItems.map((item) => (
                      <div key={item.id} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-medium text-[var(--text)]">{item.title}</p>
                          <p className="text-[11px] text-[var(--muted)]">{item.date}</p>
                        </div>
                        <p className="text-xs text-[var(--muted)]">{item.detail}</p>
                      </div>
                    ))
                  )}
                </div>
              </article>
            )}

          </div>
        </section>
      )}

      <LiquidGlassModal
        open={postHarvestModalOpen}
        onClose={closePostHarvestModal}
        title="Nouveau lot Post-récolte"
        subtitle="Sélectionnez le stock à transformer."
        closeLabel="✕"
        size="md"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={closePostHarvestModal}>
              Annuler
            </button>
            <button
              type="button"
              onClick={handleStartPostHarvest}
              className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold"
              disabled={postHarvestSubmitDisabled}
            >
              {startPostHarvest.isPending ? "Démarrage..." : "Démarrer Post-récolte"}
            </button>
          </div>
        }
      >
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Produit
              <select
                value={postHarvestProductId}
                onChange={(event) => setPostHarvestProductId(event.target.value)}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                disabled
              >
                <option value={selectedBatch?.product_id ?? ""}>
                  {selectedBatch ? (productLookup.get(selectedBatch.product_id) ?? selectedBatch.product_id) : "Sélectionner"}
                </option>
              </select>
              <p className="mt-1 text-xs text-[var(--muted)]">
                Produit verrouillé sur le produit du lot sélectionné.
              </p>
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Grade/qualité
              <select
                value={postHarvestGrade}
                onChange={(event) => setPostHarvestGrade(event.target.value)}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
              >
                <option value="" disabled>
                  Sélectionner
                </option>
                {postHarvestGradeOptions.map((entry) => (
                  <option key={entry.grade} value={entry.grade}>
                    {entry.grade}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="block text-sm font-medium text-[var(--text)]">
            Quantité à allouer (kg)
            <input
              type="number"
              min={0.01}
              step="0.01"
              value={postHarvestQuantity}
              onChange={(event) => setPostHarvestQuantity(event.target.value)}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
            />
          </label>

          <div className="rounded-xl border border-[#BDD6FB] bg-[#EEF5FF] px-3 py-2 text-xs text-[#2F80ED]">
            Disponible: {selectedPostHarvestAvailableKg.toFixed(2)} kg
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 text-xs text-[var(--muted)]">
            <p>Réf. Pré-récolte: <span className="font-semibold text-[var(--text)]">{selectedBatch?.preharvest_reference || "—"}</span></p>
            <p>Réf. Collecte: <span className="font-semibold text-[var(--text)]">{selectedBatch?.collecte_reference || "—"}</span></p>
          </div>

          {postHarvestQuantity.trim() !== "" && postHarvestQuantityInvalid ? (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              Quantité invalide: elle doit être supérieure à 0 et inférieure ou égale au stock disponible.
            </p>
          ) : null}
          {postHarvestFormError ? (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {postHarvestFormError}
            </p>
          ) : null}
        </div>
      </LiquidGlassModal>

      <LiquidGlassModal
        open={lotFormOpen}
        onClose={closeForms}
        title={editingBatch ? `Modifier lot - ${editingBatch.code}` : "Nouveau lot - Flux de matiere"}
        subtitle={
          editingBatch
            ? "Le formulaire est pre-rempli avec les donnees du lot selectionne."
            : "Le lot reserve le stock disponible et conserve la sequence ordonnee des etapes."
        }
        closeLabel="✕"
        size="md"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={closeForms}>
              Annuler
            </button>
            <button type="submit" form="lot-form" className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" disabled={lotForm.formState.isSubmitting}>
              {lotForm.formState.isSubmitting ? "Enregistrement..." : editingBatch ? "Mettre a jour le lot" : "Creer le lot"}
            </button>
          </div>
        }
      >
        <form id="lot-form" onSubmit={submitLot} className="space-y-3">
          <input type="hidden" {...lotForm.register("creation_date", { required: "Date requise." })} />

          <label className="block text-sm font-medium text-[var(--text)]">
            Reference du lot (auto)
            <input
              value={editingBatch?.code ?? previewReference.data?.code ?? "..."}
              readOnly
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
              placeholder="LOT-XXXX-001"
            />
          </label>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Produit
              <select
                {...lotForm.register("product_id", { required: "Produit requis." })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                disabled={Boolean(editingBatch)}
              >
                <option value="" disabled>
                  Selectionner
                </option>
                {productsInStock.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Unite
              <select
                {...lotForm.register("unit", { required: "Unite requise." })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                disabled={Boolean(editingBatch)}
              >
                <option value="kg">kg</option>
                <option value="ton">ton</option>
              </select>
            </label>

            <label className="block text-sm font-medium text-[var(--text)] sm:col-span-2">
              Quantite demandee
              <input
                type="number"
                step="0.01"
                min="0"
                {...lotForm.register("initial_qty", { required: "Quantite requise.", valueAsNumber: true })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                readOnly={Boolean(editingBatch)}
              />
            </label>
          </div>

          {editingBatch ? (
            <div className="rounded-xl border border-[#E6D9B8] bg-[#FFF7E7] px-3 py-2 text-xs text-[#8A6B25]">
              Edition lot: produit, unite et quantite initiale affiches depuis le lot courant.
            </div>
          ) : (
            <div className="rounded-xl border border-[#BDD6FB] bg-[#EEF5FF] px-3 py-2 text-xs text-[#2F80ED]">
              Stock disponible: {availableStockDisplay.toFixed(2)} {watchedLotUnit}
              {selectedProductStock ? ` (=${availableStockKg.toFixed(2)} kg)` : ""}
            </div>
          )}
          {!editingBatch && productsInStock.length === 0 ? (
            <div className="rounded-xl border border-[#F2D8C7] bg-[#FFF4EE] px-3 py-2 text-xs text-[#9B4B2A]">
              Aucun produit n&apos;a de stock disponible pour créer un lot.
            </div>
          ) : null}

          <div className="space-y-2 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
            <p className="text-sm font-semibold text-[var(--text)]">Etapes ordonnees</p>
            <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
              <select value={stepToAdd} onChange={(event) => setStepToAdd(event.target.value)} className="wf-input h-10 w-full px-3 text-sm">
                <option value="">Choisir une etape standard</option>
                {LOT_WORKFLOW_STAGES.map((stage) => (
                  <option key={stage.key} value={stage.label}>
                    {stage.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold"
                onClick={() => {
                  if (!stepToAdd) return;
                  addPlannedStep(stepToAdd);
                  setStepToAdd("");
                }}
              >
                Ajouter
              </button>
            </div>
            <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
              <input
                value={customStepInput}
                onChange={(event) => setCustomStepInput(event.target.value)}
                className="wf-input h-10 w-full px-3 text-sm"
                placeholder="Ajouter une etape personnalisee"
              />
              <button
                type="button"
                className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold"
                onClick={() => {
                  const value = customStepInput.trim();
                  if (!value) return;
                  addPlannedStep(value);
                  setCustomStepInput("");
                }}
              >
                Ajouter perso
              </button>
            </div>

            <div className="space-y-1">
              {plannedStepsDraft.length === 0 ? (
                <p className="text-xs text-[var(--muted)]">Aucune etape selectionnee.</p>
              ) : (
                plannedStepsDraft.map((stepName, index) => (
                  <div key={`${stepName}-${index}`} className="flex items-center justify-between gap-2 rounded-lg border border-[var(--line)] bg-white px-2 py-1.5">
                    <p className="text-xs text-[var(--text)]">
                      {index + 1}. {stepName}
                    </p>
                    <div className="flex items-center gap-1">
                      <button type="button" className="text-xs font-semibold text-[var(--primary)]" onClick={() => movePlannedStep(index, -1)}>
                        ↑
                      </button>
                      <button type="button" className="text-xs font-semibold text-[var(--primary)]" onClick={() => movePlannedStep(index, 1)}>
                        ↓
                      </button>
                      <button
                        type="button"
                        className="text-xs font-semibold text-[var(--danger)]"
                        onClick={() => setPlannedStepsDraft((current) => current.filter((_, i) => i !== index))}
                      >
                        Retirer
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {formError && <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">{formError}</p>}
        </form>
      </LiquidGlassModal>

      <LiquidGlassModal
        open={stepFormOpen}
        onClose={closeForms}
        title={stepModalTitle}
        subtitle={selectedBatch ? `Lot ${selectedBatch.code}` : "Selectionnez un lot"}
        closeLabel="✕"
        size="md"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="submit" form="step-form" className="soft-focus wf-btn-primary flex-1 px-4 py-2 text-sm font-semibold" disabled={stepForm.formState.isSubmitting}>
              {stepForm.formState.isSubmitting ? "Enregistrement..." : completingPendingStep ? "Completer etape" : "Enregistrer"}
            </button>
            <button type="button" className="soft-focus wf-btn-secondary flex-1 px-4 py-2 text-sm font-semibold" onClick={closeForms}>
              Annuler
            </button>
          </div>
        }
      >
        <form id="step-form" onSubmit={submitStep} className="space-y-3">
          <input type="hidden" {...stepForm.register("batch_id", { required: "Lot requis." })} />

          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">{stepPreset?.icon ?? "🧩"}</span>
              <div>
                <p className="text-sm font-semibold text-[var(--text)]">{stepPreset?.label ?? (stepForm.watch("type") || "Etape")}</p>
                <p className="text-xs text-[var(--muted)]">{stepPreset?.typeTag ?? "personnalise"}</p>
              </div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Quantite entrante (kg)
              <input
                type="number"
                step="0.01"
                min="0"
                {...stepForm.register("qty_in", { valueAsNumber: true })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                readOnly
              />
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Quantité perte (kg)
              <input
                type="number"
                step="0.01"
                min="0"
                {...stepForm.register("loss_value", {
                  required: "Quantité perte requise.",
                  valueAsNumber: true,
                  validate: (value) => Number(value) >= 0 || "La perte doit être positive.",
                })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
              />
            </label>
          </div>
          <p className="text-xs text-[var(--muted)]">
            Quantité sortante calculée automatiquement = Entrante - Perte.
          </p>

          <input type="hidden" {...stepForm.register("loss_unit")} />

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Date d&apos;execution
              <input
                type="date"
                {...stepForm.register("date")}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
              />
            </label>
            <label className="block text-sm font-medium text-[var(--text)]">
              Durée (jours)
              <input
                type="number"
                min="0"
                step="0.1"
                {...stepForm.register("duration_minutes", { required: "Durée requise.", valueAsNumber: true })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
              />
            </label>
          </div>

          <label className="block text-sm font-medium text-[var(--text)]">
            Notes / Observations
            <textarea {...stepForm.register("notes")} className="wf-input mt-2 min-h-[84px] w-full px-3 py-2 text-sm" placeholder="Observations sur cette etape..." />
          </label>

          {editingStep && (
            <button
              type="button"
              onClick={() => setPendingDeleteStep(editingStep)}
              className="text-xs font-semibold text-[var(--danger)] hover:underline"
            >
              Supprimer cette etape
            </button>
          )}

          {formError && <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">{formError}</p>}
        </form>
      </LiquidGlassModal>
      <ConfirmActionModal
        open={Boolean(pendingDeleteStep)}
        title="Supprimer l'étape"
        message="Cette action supprimera cette étape de process."
        confirmLabel="Supprimer"
        onCancel={() => setPendingDeleteStep(null)}
        onConfirm={() => {
          if (!pendingDeleteStep) return;
          void handleDeleteStep(pendingDeleteStep);
          setPendingDeleteStep(null);
        }}
      />
    </main>
  );
}
