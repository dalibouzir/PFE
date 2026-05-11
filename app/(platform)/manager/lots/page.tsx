"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { AIInsightsStrip, type AIInsightItem } from "@/components/ui/AIInsightsStrip";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LotAnalyticsPanel } from "@/components/workspace/LotAnalyticsPanel";
import { LotActiveSidebar, type ActiveLotItem } from "@/components/workspace/LotActiveSidebar";
import { LotHeroBanner } from "@/components/workspace/LotHeroBanner";
import { LotProcessTable, type ProcessTableRow } from "@/components/workspace/LotProcessTable";
import { LotProcessTimeline, type TimelineStage } from "@/components/workspace/LotProcessTimeline";
import { LotRecommendationPanel, type LotRecommendationItem } from "@/components/workspace/LotRecommendationPanel";
import { LotWorkspaceTabs, type LotWorkspaceTab } from "@/components/workspace/LotWorkspaceTabs";
import {
  useBatchReferencePreview,
  useBatches,
  useCreateBatch,
  useDeleteBatch,
  useUpdateBatch,
} from "@/hooks/useBatches";
import { useDashboard } from "@/hooks/useDashboard";
import { useCreateProcessStep, useDeleteProcessStep, useProcessSteps, useUpdateProcessStep } from "@/hooks/useProcessSteps";
import { useProducts } from "@/hooks/useProducts";
import { useStocks } from "@/hooks/useStocks";
import type {
  Batch,
  BatchCreate,
  ProcessStep,
  ProcessStepCreate,
  ProcessStepUpdate,
  Recommendation,
} from "@/lib/api/types";
import {
  LOT_WORKFLOW_STAGES,
  buildSeasonFromDate,
  phaseLabel,
  stageFromType,
  stageLabelFromType,
  type WorkflowStageDef,
} from "@/lib/ui/lot-workflow";

const KG_PER_TON = 1000;
const todayIso = new Date().toISOString().slice(0, 10);
const defaultSteps = ["Nettoyage", "Sechage", "Tri", "Emballage"];

type MassUnit = "kg" | "ton";
type StagePreset = Pick<WorkflowStageDef, "key" | "label" | "icon" | "typeTag">;

const batchStatusTone: Record<string, "success" | "warning" | "info" | "danger"> = {
  created: "info",
  in_progress: "warning",
  completed: "success",
  archived: "danger",
};

const batchStatusLabel: Record<string, string> = {
  created: "Cree",
  in_progress: "En cours",
  completed: "Termine",
  archived: "Archive",
};

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
  if (item.risk_level.toLowerCase() === "medium" || item.anomaly_score >= 35 || item.loss_pct >= 10) return "warning";
  return "optimization";
}

function parseImpactedStep(item: Recommendation): string {
  const text = `${item.rationale} ${item.suggested_action}`.toLowerCase();
  const workflowStage = LOT_WORKFLOW_STAGES.find((stage) => stage.aliases.some((alias) => text.includes(alias)));
  return workflowStage?.label ?? "Process global";
}

export default function LotsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryTab = searchParams.get("tab");
  const queryLot = searchParams.get("lot");

  const { data: batches = [] } = useBatches();
  const { data: products = [] } = useProducts();
  const { data: stocks = [] } = useStocks();
  const { data: steps = [] } = useProcessSteps();
  const { data: dashboard } = useDashboard();

  const createBatch = useCreateBatch();
  const updateBatch = useUpdateBatch();
  const deleteBatch = useDeleteBatch();
  const createStep = useCreateProcessStep();
  const updateStep = useUpdateProcessStep();
  const deleteStep = useDeleteProcessStep();

  const [activeTab, setActiveTab] = useState<LotWorkspaceTab>(() => normalizeTab(queryTab));
  const [query, setQuery] = useState("");
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(queryLot);

  const [lotFormOpen, setLotFormOpen] = useState(false);
  const [stepFormOpen, setStepFormOpen] = useState(false);
  const [editingBatch, setEditingBatch] = useState<Batch | null>(null);
  const [editingStep, setEditingStep] = useState<ProcessStep | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const [plannedStepsDraft, setPlannedStepsDraft] = useState<string[]>(defaultSteps);
  const [stepToAdd, setStepToAdd] = useState("");
  const [customStepInput, setCustomStepInput] = useState("");

  const [stepPreset, setStepPreset] = useState<StagePreset | null>(null);

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

  const filteredBatches = useMemo(() => {
    const base = [...batches].sort((a, b) => b.creation_date.localeCompare(a.creation_date));
    return base.filter((item) => {
      const productName = productLookup.get(item.product_id) ?? "";
      const text = `${item.code} ${item.product_id} ${productName}`.toLowerCase();
      return text.includes(query.toLowerCase());
    });
  }, [batches, query, productLookup]);

  const selectedBatch = useMemo(() => {
    if (selectedBatchId) {
      const match = filteredBatches.find((item) => item.id === selectedBatchId);
      if (match) return match;
    }
    return filteredBatches[0] ?? null;
  }, [filteredBatches, selectedBatchId]);

  useEffect(() => {
    setActiveTab(normalizeTab(queryTab));
  }, [queryTab]);

  useEffect(() => {
    if (queryLot) setSelectedBatchId(queryLot);
  }, [queryLot]);

  useEffect(() => {
    if (!selectedBatch && filteredBatches.length > 0) {
      setSelectedBatchId(filteredBatches[0].id);
    }
  }, [filteredBatches, selectedBatch]);

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
    return selectedRecommendations.map((item) => {
      const priority = recommendationPriority(item);
      return {
        id: `${item.batch_id}-${item.anomaly_score}-${item.loss_pct}`,
        title:
          priority === "critical"
            ? `Priorite critique lot ${item.batch_id.slice(0, 8)}`
            : priority === "warning"
              ? `Correction recommandee lot ${item.batch_id.slice(0, 8)}`
              : `Optimisation lot ${item.batch_id.slice(0, 8)}`,
        priority,
        rationale: item.reasons[0] ?? item.rationale,
        impactedStep: parseImpactedStep(item),
        expectedEffect: `Perte cible < ${Math.max(item.loss_pct - 2, 0).toFixed(1)}%`,
        action: item.suggested_action || "Poursuivre le monitoring avec un point de controle terrain.",
      };
    });
  }, [selectedRecommendations]);

  const lotTotals = useMemo(() => {
    const qtyIn = selectedSteps.reduce((sum, step) => sum + step.qty_in, 0);
    const qtyOut = selectedSteps.reduce((sum, step) => sum + step.qty_out, 0);
    const lossKg = selectedSteps.reduce((sum, step) => sum + step.normalized_loss_value, 0);
    const efficiencyPct = qtyIn > 0 ? (qtyOut / qtyIn) * 100 : 0;
    return { qtyIn, qtyOut, lossKg, efficiencyPct };
  }, [selectedSteps]);

  const stageMetrics = useMemo(() => {
    const grouped = new Map<
      string,
      { qtyIn: number; qtyOut: number; loss: number; efficiency: number; count: number; anomalies: number }
    >();
    selectedSteps.forEach((step) => {
      const key = stageLabelFromType(step.type);
      const current = grouped.get(key) ?? { qtyIn: 0, qtyOut: 0, loss: 0, efficiency: 0, count: 0, anomalies: 0 };
      current.qtyIn += step.qty_in;
      current.qtyOut += step.qty_out;
      current.loss += step.loss_pct;
      current.efficiency += step.efficiency_pct;
      current.count += 1;
      if (step.warning || step.loss_pct >= 12) current.anomalies += 1;
      grouped.set(key, current);
    });

    return Array.from(grouped.entries()).map(([stage, values]) => ({
      stage,
      qtyIn: values.qtyIn,
      qtyOut: values.qtyOut,
      lossPct: values.count > 0 ? values.loss / values.count : 0,
      efficiencyPct: values.count > 0 ? values.efficiency / values.count : 0,
      anomalies: values.anomalies,
    }));
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
        ? step.warning
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
    return filteredBatches.map((batch) => {
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
        statusLabel: batchStatusLabel[batch.status] ?? batch.status,
        statusTone: batchStatusTone[batch.status] ?? "info",
      };
    });
  }, [filteredBatches, stepsByBatch, productLookup]);

  const anomalyCount = selectedSteps.filter((step) => step.warning || step.loss_pct >= 12).length;
  const latestRecommendation = recommendationCards[0] ?? null;
  const selectedSeason = selectedBatch ? buildSeasonFromDate(selectedBatch.creation_date) : "";
  const selectedLossPct = selectedBatch?.initial_qty
    ? Math.max(((selectedBatch.initial_qty - selectedBatch.current_qty) / selectedBatch.initial_qty) * 100, 0)
    : 0;

  const selectedProductStock = useMemo(() => {
    if (!watchedProductId) return null;
    return stocks.find((stock) => stock.product_id === watchedProductId) ?? null;
  }, [stocks, watchedProductId]);

  const availableStockKg = selectedProductStock?.available_stock_kg ?? 0;
  const availableStockDisplay = fromKg(availableStockKg, watchedLotUnit);

  const historyItems = useMemo(() => {
    if (!selectedBatch) return [];
    const stepItems = selectedSteps
      .map((step) => ({
        id: step.id,
        title: `${step.sequence_order}. ${stageLabelFromType(step.type)}`,
        detail: `In ${step.qty_in.toFixed(2)} kg · Perte ${step.normalized_loss_value.toFixed(2)} kg · Out ${step.qty_out.toFixed(2)} kg`,
        date: step.date,
      }))
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    return [
      {
        id: `batch-${selectedBatch.id}`,
        title: `Lot ${selectedBatch.code} cree`,
        detail: `Quantite initiale ${selectedBatch.initial_qty.toFixed(2)} ${selectedBatch.unit}`,
        date: selectedBatch.creation_date,
      },
      ...stepItems,
    ];
  }, [selectedBatch, selectedSteps]);

  const postHarvestInsights = useMemo<AIInsightItem[]>(() => {
    if (!selectedBatch) return [];

    const highRiskCount = selectedRecommendations.filter((item) => item.risk_level.toLowerCase() === "high").length;
    const worstStage = stageMetrics
      .slice()
      .sort((a, b) => b.lossPct - a.lossPct)[0];
    const anomalyTone: AIInsightItem["tone"] = anomalyCount > 0 ? "warning" : "success";
    const items: AIInsightItem[] = [
      {
        id: "served-risk-method",
        title: "Methode risque active",
        message: "Risque servi par seuil sur perte predite (thresholded_predicted_loss).",
        tone: "info",
        meta: "Utiliser ce signal pour prioriser les actions, pas pour conclure seul la cause.",
      },
      {
        id: "anomaly-signal",
        title: anomalyCount > 0 ? "Anomalies a verifier" : "Pas d'anomalie critique detectee",
        message:
          anomalyCount > 0
            ? `${anomalyCount} etape(s) avec signal d'ecart sur ce lot.`
            : "Les etapes executees restent dans une plage operationnelle attendue.",
        tone: anomalyTone,
      },
    ];

    if (worstStage) {
      items.push({
        id: "worst-stage",
        title: `Etape sous pression: ${worstStage.stage}`,
        message: `Perte moyenne ${worstStage.lossPct.toFixed(1)}% · efficacite ${worstStage.efficiencyPct.toFixed(1)}%.`,
        tone: worstStage.lossPct >= 12 ? "critical" : worstStage.lossPct >= 8 ? "warning" : "info",
      });
    }

    items.push({
      id: "high-risk-rows",
      title: highRiskCount > 0 ? "Lots a risque eleve detectes" : "Aucun risque eleve dans les recents",
      message:
        highRiskCount > 0
          ? `${highRiskCount} recommandation(s) marquee(s) HIGH pour ce lot.`
          : "Continuer le suivi des prochaines etapes pour confirmer la stabilite.",
      tone: highRiskCount > 0 ? "critical" : "success",
      actionLabel: "Voir les recommandations",
      href: "/manager/lots?tab=recommendations",
    });
    return items;
  }, [selectedBatch, selectedRecommendations, stageMetrics, anomalyCount]);

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

  const openCreateLot = () => {
    setEditingBatch(null);
    lotForm.reset({
      product_id: products[0]?.id ?? "",
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

  const openEditLot = (batch: Batch) => {
    setEditingBatch(batch);
    lotForm.reset({
      product_id: batch.product_id,
      creation_date: batch.creation_date,
      initial_qty: batch.initial_qty,
      unit: (batch.unit || "kg") as MassUnit,
      process_steps: batch.ordered_process_steps?.length ? batch.ordered_process_steps : defaultSteps,
    });
    setPlannedStepsDraft(batch.ordered_process_steps?.length ? batch.ordered_process_steps : defaultSteps);
    setStepToAdd("");
    setCustomStepInput("");
    setFormError(null);
    setLotFormOpen(true);
  };

  const openCreateStep = (row?: ProcessTableRow) => {
    if (!selectedBatch) return;
    const target = row ?? workflowRows.find((item) => item.isExecutable);
    if (!target) {
      setFormError("Aucune etape executable pour ce lot.");
      return;
    }
    setEditingStep(null);
    setStepPreset({ key: target.key, label: target.label, icon: target.icon, typeTag: target.typeTag });
    stepForm.reset({
      batch_id: selectedBatch.id,
      type: target.label,
      date: todayIso,
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
      loss_value: step.loss_value,
      loss_unit: step.loss_unit,
      notes: step.notes ?? "",
      duration_minutes: step.duration_minutes ?? undefined,
    });
    setFormError(null);
    setStepFormOpen(true);
  };

  const closeForms = () => {
    setLotFormOpen(false);
    setStepFormOpen(false);
    setEditingBatch(null);
    setFormError(null);
    setStepPreset(null);
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

      if (editingStep) {
        const payload: ProcessStepUpdate = {
          date: values.date,
          loss_value: Number(values.loss_value),
          loss_unit: values.loss_unit,
          notes: values.notes?.trim() || null,
          duration_minutes: values.duration_minutes ? Number(values.duration_minutes) : undefined,
        };
        await updateStep.mutateAsync({ id: editingStep.id, payload });
      } else {
        const payload: ProcessStepCreate = {
          batch_id: selectedBatch.id,
          type: stepPreset?.label,
          date: values.date,
          loss_value: Number(values.loss_value),
          loss_unit: values.loss_unit,
          notes: values.notes?.trim() || null,
          duration_minutes: values.duration_minutes ? Number(values.duration_minutes) : undefined,
        };
        await createStep.mutateAsync(payload);
      }
      closeForms();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer l'etape.");
    }
  });

  const handleDeleteLot = async (batch: Batch) => {
    if (!window.confirm("Supprimer ce lot ?")) return;
    try {
      await deleteBatch.mutateAsync(batch.id);
      if (selectedBatch?.id === batch.id) {
        setSelectedBatchId(null);
      }
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de supprimer le lot.");
    }
  };

  const handleDeleteStep = async (step: ProcessStep) => {
    if (!window.confirm("Supprimer cette etape ?")) return;
    try {
      await deleteStep.mutateAsync(step.id);
      closeForms();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de supprimer l'etape.");
    }
  };

  const handleEnterStage = (row: ProcessTableRow) => {
    if (!row.isExecutable) return;
    openCreateStep(row);
  };

  const stepModalTitle = editingStep
    ? `Modifier - ${stepPreset?.label ?? stageLabelFromType(editingStep.type)}`
    : `Executer - ${stepPreset?.label ?? "Etape"}`;

  return (
    <main className="min-w-0 overflow-x-hidden">
      <PageIntro title="Flux matiere" />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "30ms" }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={openCreateLot} className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold">
              + Nouveau lot
            </button>
            <button type="button" onClick={() => openCreateStep()} className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" disabled={!selectedBatch}>
              + Executer etape
            </button>
            <button
              type="button"
              onClick={() => handleSwitchTab("recommendations")}
              className="soft-focus rounded-xl border border-[#D0C4FF] bg-[#F3EEFF] px-4 py-2 text-sm font-semibold text-[#6A4DE0] hover:brightness-95"
            >
              Conseils IA
            </button>
          </div>

          <div className="w-full sm:w-[320px]">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="soft-focus wf-input w-full px-3 py-2.5 text-sm"
              placeholder="Rechercher un lot..."
            />
          </div>
        </div>
      </section>

      {!selectedBatch ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "60ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucun lot disponible. Creez un lot pour demarrer le pilotage.</p>
        </section>
      ) : (
        <section className="min-w-0 grid gap-4 xl:grid-cols-[300px_1fr]">
          <LotActiveSidebar
            items={lotSidebarItems}
            selectedId={selectedBatch.id}
            onSelect={handleSelectLot}
            onCreateLot={openCreateLot}
          />

          <div className="min-w-0 space-y-4">
            <LotHeroBanner
              lotCode={selectedBatch.code}
              productName={productLookup.get(selectedBatch.product_id) ?? selectedBatch.product_id.slice(0, 8)}
              seasonLabel={selectedSeason}
              unit={selectedBatch.unit}
              initialQty={selectedBatch.initial_qty}
              currentQty={selectedBatch.current_qty}
              lossPct={selectedLossPct}
              statusLabel={batchStatusLabel[selectedBatch.status] ?? selectedBatch.status}
              statusTone={batchStatusTone[selectedBatch.status] ?? "info"}
              onEditLot={() => openEditLot(selectedBatch)}
            />

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
                      <p className="text-[11px] text-[var(--muted)]">Efficacite globale</p>
                      <p className="text-sm font-semibold text-[var(--text)]">{lotTotals.efficiencyPct.toFixed(1)}%</p>
                    </div>
                    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                      <p className="text-[11px] text-[var(--muted)]">Statut lot</p>
                      <div className="mt-1">
                        <StatusBadge
                          label={batchStatusLabel[selectedBatch.status] ?? selectedBatch.status}
                          tone={batchStatusTone[selectedBatch.status] ?? "info"}
                        />
                      </div>
                    </div>
                  </div>
                </article>

                <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "110ms" }}>
                  <h3 className="text-base font-semibold text-[var(--text)]">Derniere recommandation IA</h3>
                  {latestRecommendation ? (
                    <div className="mt-3 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-[var(--text)]">{latestRecommendation.title}</p>
                        <StatusBadge
                          label={latestRecommendation.priority === "critical" ? "Prioritaire" : latestRecommendation.priority === "warning" ? "Important" : "Optimisation"}
                          tone={latestRecommendation.priority === "critical" ? "danger" : latestRecommendation.priority === "warning" ? "warning" : "ai"}
                        />
                      </div>
                      <p className="mt-2 text-xs text-[var(--muted)]">{latestRecommendation.rationale}</p>
                      <p className="mt-2 text-xs font-semibold text-[var(--ai-accent)]">{latestRecommendation.expectedEffect}</p>
                      <button
                        type="button"
                        onClick={() => handleSwitchTab("recommendations")}
                        className="mt-3 text-xs font-semibold text-[var(--ai-accent)] hover:underline"
                      >
                        Voir toutes les recommandations
                      </button>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-[var(--muted)]">Aucune recommandation specifique pour ce lot.</p>
                  )}
                </article>
              </section>
            )}

            {activeTab === "analytics" && (
              <section className="space-y-4">
                <AIInsightsStrip
                  title="Insights IA post-recolte"
                  subtitle="Signaux de priorisation pour le lot actif."
                  items={postHarvestInsights}
                />
                <LotAnalyticsPanel
                  stageMetrics={stageMetrics}
                  totals={{
                    qtyIn: lotTotals.qtyIn,
                    qtyOut: lotTotals.qtyOut,
                    lossKg: lotTotals.lossKg,
                    efficiencyPct: lotTotals.efficiencyPct,
                  }}
                  anomalyCount={anomalyCount}
                />
              </section>
            )}

            {activeTab === "recommendations" && (
              <section className="space-y-4">
                <AIInsightsStrip
                  title="Synthese IA du lot"
                  subtitle="Les recommandations restent une aide, a confirmer sur le terrain."
                  items={postHarvestInsights}
                />
                <LotRecommendationPanel items={recommendationCards} />
              </section>
            )}

            {activeTab === "history" && (
              <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "110ms" }}>
                <h3 className="text-base font-semibold text-[var(--text)]">Historique lot</h3>
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

            <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "140ms" }}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Gestion lot</p>
                  <p className="text-sm font-medium text-[var(--text)]">
                    Lot {selectedBatch.code} · {productLookup.get(selectedBatch.product_id) ?? selectedBatch.product_id.slice(0, 8)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <button type="button" className="text-xs font-semibold text-[var(--danger)] hover:underline" onClick={() => handleDeleteLot(selectedBatch)}>
                    Supprimer lot
                  </button>
                </div>
              </div>
            </article>
          </div>
        </section>
      )}

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
                {products.map((product) => (
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
              {stepForm.formState.isSubmitting ? "Enregistrement..." : "Enregistrer"}
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
              Perte
              <input
                type="number"
                step="0.01"
                min="0"
                {...stepForm.register("loss_value", { required: "Perte requise.", valueAsNumber: true })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
              />
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Unite perte
              <select {...stepForm.register("loss_unit")} className="wf-input mt-2 h-11 w-full px-3 text-sm">
                <option value="kg">kg</option>
                <option value="ton">ton</option>
              </select>
            </label>
          </div>

          <label className="block text-sm font-medium text-[var(--text)]">
            Date d&apos;execution
            <input
              type="date"
              {...stepForm.register("date")}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
            />
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Notes / Observations
            <textarea {...stepForm.register("notes")} className="wf-input mt-2 min-h-[84px] w-full px-3 py-2 text-sm" placeholder="Observations sur cette etape..." />
          </label>

          {editingStep && (
            <button
              type="button"
              onClick={() => handleDeleteStep(editingStep)}
              className="text-xs font-semibold text-[var(--danger)] hover:underline"
            >
              Supprimer cette etape
            </button>
          )}

          {formError && <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">{formError}</p>}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
