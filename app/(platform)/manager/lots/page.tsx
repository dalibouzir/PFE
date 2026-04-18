"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LotAnalyticsPanel } from "@/components/workspace/LotAnalyticsPanel";
import { LotActiveSidebar, type ActiveLotItem } from "@/components/workspace/LotActiveSidebar";
import { LotHeroBanner } from "@/components/workspace/LotHeroBanner";
import { LotProcessTable, type ProcessTableRow } from "@/components/workspace/LotProcessTable";
import { LotProcessTimeline, type TimelineStage } from "@/components/workspace/LotProcessTimeline";
import { LotRecommendationPanel, type LotRecommendationItem } from "@/components/workspace/LotRecommendationPanel";
import { LotWorkspaceTabs, type LotWorkspaceTab } from "@/components/workspace/LotWorkspaceTabs";
import { useBatches, useCreateBatch, useDeleteBatch, useUpdateBatch, useUpdateBatchStatus } from "@/hooks/useBatches";
import { useDashboard } from "@/hooks/useDashboard";
import { useCreateProcessStep, useDeleteProcessStep, useProcessSteps, useUpdateProcessStep } from "@/hooks/useProcessSteps";
import { useProducts } from "@/hooks/useProducts";
import type { Batch, BatchCreate, BatchStatusUpdate, ProcessStep, ProcessStepCreate, Recommendation } from "@/lib/api/types";
import {
  LOT_WORKFLOW_STAGES,
  buildSeasonFromDate,
  phaseLabel,
  stageFromType,
  stageLabelFromType,
  stageLossKg,
  type WorkflowStageDef,
} from "@/lib/ui/lot-workflow";

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

const todayIso = new Date().toISOString().slice(0, 10);

type StagePreset = Pick<WorkflowStageDef, "key" | "label" | "icon" | "typeTag">;

function normalizeTab(raw: string | null): LotWorkspaceTab {
  if (raw === "overview") return "overview";
  if (raw === "analytics") return "analytics";
  if (raw === "recommendations") return "recommendations";
  if (raw === "history") return "history";
  return "process";
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

function resolveStageStatus(step?: ProcessStep): "done" | "pending" | "warning" {
  if (!step) return "pending";
  return step.warning ? "warning" : "done";
}

export default function LotsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryTab = searchParams.get("tab");
  const queryLot = searchParams.get("lot");

  const { data: batches = [] } = useBatches();
  const { data: products = [] } = useProducts();
  const { data: steps = [] } = useProcessSteps();
  const { data: dashboard } = useDashboard();

  const createBatch = useCreateBatch();
  const updateBatch = useUpdateBatch();
  const updateBatchStatus = useUpdateBatchStatus();
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

  const [lotSeason, setLotSeason] = useState("");
  const [lotSurfaceHa, setLotSurfaceHa] = useState("1");
  const [stepPreset, setStepPreset] = useState<StagePreset | null>(null);

  const lotForm = useForm<BatchCreate>({
    defaultValues: { product_id: "", code: "", creation_date: todayIso, initial_qty: 0 },
  });
  const stepForm = useForm<ProcessStepCreate>({
    defaultValues: {
      batch_id: "",
      type: "",
      date: todayIso,
      qty_in: 0,
      qty_out: 0,
      waste_qty: 0,
      notes: "",
      status: "completed",
      duration_minutes: undefined,
    },
  });

  const watchQtyIn = Number(stepForm.watch("qty_in") ?? 0);
  const watchWaste = Number(stepForm.watch("waste_qty") ?? 0);
  const computedNet = Math.max(watchQtyIn - watchWaste, 0);
  const computedLossPct = watchQtyIn > 0 ? (watchWaste / watchQtyIn) * 100 : 0;

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
        list.slice().sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()),
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
    const lossKg = selectedSteps.reduce((sum, step) => sum + stageLossKg(step), 0);
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
    const stageStep = new Map<string, ProcessStep>();
    const customRows: ProcessTableRow[] = [];

    selectedSteps.forEach((step) => {
      const mapped = stageFromType(step.type);
      if (!mapped) {
        customRows.push({
          key: `custom-${step.id}`,
          label: stageLabelFromType(step.type),
          icon: "🧩",
          typeTag: "personnalise",
          phase: "post_harvest",
          status: resolveStageStatus(step),
          step,
        });
        return;
      }
      stageStep.set(mapped.key, step);
    });

    const ordered = LOT_WORKFLOW_STAGES.map<ProcessTableRow>((stage) => ({
      key: stage.key,
      label: stage.label,
      icon: stage.icon,
      typeTag: stage.typeTag,
      phase: stage.phase,
      step: stageStep.get(stage.key),
      status: resolveStageStatus(stageStep.get(stage.key)),
    }));

    return [...ordered, ...customRows];
  }, [selectedSteps]);

  const timelineRows = useMemo<TimelineStage[]>(
    () =>
      workflowRows
        .filter((row) => !row.key.startsWith("custom-"))
        .map((row) => ({
          key: row.key,
          label: row.label,
          icon: row.icon,
          typeTag: row.typeTag,
          phase: row.phase,
          status: row.status,
          qtyOut: row.step?.qty_out,
          lossKg: row.step ? stageLossKg(row.step) : undefined,
        })),
    [workflowRows],
  );

  const lotSidebarItems = useMemo<ActiveLotItem[]>(() => {
    return filteredBatches.map((batch) => {
      const lotSteps = stepsByBatch.get(batch.id) ?? [];
      const matched = lotSteps.map((step) => stageFromType(step.type)).filter((item): item is WorkflowStageDef => Boolean(item));
      const uniqueDone = new Set(matched.map((item) => item.key)).size;
      const latest = matched[matched.length - 1];
      const progressPct = (uniqueDone / LOT_WORKFLOW_STAGES.length) * 100;
      return {
        id: batch.id,
        code: batch.code,
        productName: productLookup.get(batch.product_id) ?? batch.product_id.slice(0, 8),
        seasonLabel: buildSeasonFromDate(batch.creation_date),
        phaseLabel: phaseLabel(latest?.phase ?? "pre_harvest"),
        stepsDone: uniqueDone,
        stepsTotal: LOT_WORKFLOW_STAGES.length,
        currentQty: batch.current_qty,
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

  const historyItems = useMemo(() => {
    if (!selectedBatch) return [];
    const stepItems = selectedSteps
      .map((step) => ({
        id: step.id,
        title: stageLabelFromType(step.type),
        detail: `In ${step.qty_in.toFixed(1)} kg · Out ${step.qty_out.toFixed(1)} kg · Perte ${step.loss_pct.toFixed(1)}%`,
        date: step.date,
      }))
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    return [
      {
        id: `batch-${selectedBatch.id}`,
        title: `Lot ${selectedBatch.code} cree`,
        detail: `Quantite initiale ${selectedBatch.initial_qty.toFixed(1)} kg`,
        date: selectedBatch.creation_date,
      },
      ...stepItems,
    ];
  }, [selectedBatch, selectedSteps]);

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
    lotForm.reset({ product_id: products[0]?.id ?? "", code: "", creation_date: todayIso, initial_qty: 0 });
    setLotSeason(buildSeasonFromDate(todayIso));
    setLotSurfaceHa("1");
    setFormError(null);
    setLotFormOpen(true);
  };

  const openEditLot = (batch: Batch) => {
    setEditingBatch(batch);
    lotForm.reset({
      product_id: batch.product_id,
      code: batch.code,
      creation_date: batch.creation_date,
      initial_qty: batch.initial_qty,
    });
    setLotSeason(buildSeasonFromDate(batch.creation_date));
    setLotSurfaceHa("1");
    setFormError(null);
    setLotFormOpen(true);
  };

  const openCreateStep = (preset?: StagePreset) => {
    setEditingStep(null);
    setStepPreset(preset ?? null);
    stepForm.reset({
      batch_id: selectedBatch?.id ?? batches[0]?.id ?? "",
      type: preset?.label ?? "",
      date: todayIso,
      qty_in: 0,
      qty_out: 0,
      waste_qty: 0,
      notes: "",
      status: "completed",
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
      qty_in: step.qty_in,
      qty_out: step.qty_out,
      waste_qty: stageLossKg(step),
      notes: step.notes ?? "",
      status: step.status,
      duration_minutes: step.duration_minutes ?? undefined,
    });
    setFormError(null);
    setStepFormOpen(true);
  };

  const closeForms = () => {
    setLotFormOpen(false);
    setStepFormOpen(false);
    setFormError(null);
    setStepPreset(null);
  };

  const submitLot = lotForm.handleSubmit(async (values) => {
    setFormError(null);
    try {
      const payload: BatchCreate = {
        product_id: values.product_id,
        code: values.code.trim(),
        creation_date: values.creation_date,
        initial_qty: Number(values.initial_qty),
      };

      if (editingBatch) {
        await updateBatch.mutateAsync({ id: editingBatch.id, payload });
      } else {
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
      const qtyIn = Number(values.qty_in);
      const wasteQty = Math.max(Number(values.waste_qty ?? 0), 0);
      const qtyOut = Math.max(qtyIn - wasteQty, 0);

      const payload: ProcessStepCreate = {
        batch_id: values.batch_id,
        type: (values.type?.trim() || stepPreset?.label || "Etape personnalisee").trim(),
        date: values.date,
        qty_in: qtyIn,
        qty_out: qtyOut,
        waste_qty: wasteQty,
        notes: values.notes?.trim() || null,
        status: values.status || "completed",
        duration_minutes: values.duration_minutes ? Number(values.duration_minutes) : undefined,
      };

      if (editingStep) {
        await updateStep.mutateAsync({ id: editingStep.id, payload });
      } else {
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
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de supprimer l'etape.");
    }
  };

  const handleBatchStatusChange = async (batch: Batch, status: string) => {
    try {
      const payload: BatchStatusUpdate = { status };
      await updateBatchStatus.mutateAsync({ id: batch.id, payload });
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de modifier le statut.");
    }
  };

  const handleOpenCustomStep = () => {
    if (activeTab !== "process") handleSwitchTab("process");
    openCreateStep();
  };

  const handleEnterStage = (row: ProcessTableRow) => {
    openCreateStep({
      key: row.key,
      label: row.label,
      icon: row.icon,
      typeTag: row.typeTag,
    });
  };

  const stepModalTitle = editingStep
    ? `Saisir - ${stepPreset?.label ?? stageLabelFromType(editingStep.type)}`
    : `Saisir - ${stepPreset?.label ?? "Etape personnalisee"}`;

  return (
    <main className="min-w-0 overflow-x-hidden">
      <PageIntro
        title="Flux matiere"
        subtitle="Workspace lot-centrique: suivi des etapes, pertes, analytique et recommandations dans un seul ecran."
      />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "30ms" }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={openCreateLot} className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold">
              + Nouveau lot
            </button>
            <button type="button" onClick={handleOpenCustomStep} className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold">
              + Etape personnalisee
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
                      <select
                        value={selectedBatch.status}
                        onChange={(event) => handleBatchStatusChange(selectedBatch, event.target.value)}
                        className="wf-input mt-1 w-full px-2 py-1 text-xs"
                      >
                        <option value="created">Cree</option>
                        <option value="in_progress">En cours</option>
                        <option value="completed">Termine</option>
                        <option value="archived">Archive</option>
                      </select>
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
            )}

            {activeTab === "recommendations" && <LotRecommendationPanel items={recommendationCards} />}

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
                  <button type="button" className="text-xs font-semibold text-[var(--primary)] hover:underline" onClick={() => openEditLot(selectedBatch)}>
                    Modifier lot
                  </button>
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
        title={editingBatch ? "Modifier lot - Flux de matiere" : "Nouveau lot - Flux de matiere"}
        subtitle="Le lot reste la racine de toutes les vues operationnelles."
        closeLabel="✕"
        size="md"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={closeForms}>
              Annuler
            </button>
            <button type="submit" form="lot-form" className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" disabled={lotForm.formState.isSubmitting}>
              {lotForm.formState.isSubmitting ? "Enregistrement..." : editingBatch ? "Mettre a jour lot" : "Creer le lot"}
            </button>
          </div>
        }
      >
        <form id="lot-form" onSubmit={submitLot} className="space-y-3">
          <input type="hidden" {...lotForm.register("creation_date", { required: "Date requise." })} />

          <label className="block text-sm font-medium text-[var(--text)]">
            Reference du lot
            <input
              {...lotForm.register("code", { required: "Code requis." })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
              placeholder="LOT-MO4LMN8P"
            />
          </label>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Culture
              <select {...lotForm.register("product_id", { required: "Produit requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
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
              Saison
              <input
                value={lotSeason}
                onChange={(event) => setLotSeason(event.target.value)}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                placeholder="2024-2025"
              />
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Surface (ha)
              <input
                value={lotSurfaceHa}
                onChange={(event) => setLotSurfaceHa(event.target.value)}
                type="number"
                min="0"
                step="0.1"
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
              />
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Qte initiale prevue (kg)
              <input
                type="number"
                step="0.1"
                min="0"
                {...lotForm.register("initial_qty", { required: "Quantite requise.", valueAsNumber: true })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
              />
            </label>
          </div>

          <div className="rounded-xl border border-[#BDD6FB] bg-[#EEF5FF] px-3 py-2 text-xs text-[#2F80ED]">
            12 etapes standards disponibles: 4 pre-recolte + 8 post-recolte.
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
          <input type="hidden" {...stepForm.register("status")} />

          {stepPreset ? (
            <input type="hidden" {...stepForm.register("type", { required: "Type requis." })} />
          ) : (
            <label className="block text-sm font-medium text-[var(--text)]">
              Nom de l&apos;etape
              <input
                {...stepForm.register("type", { required: "Type requis." })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                placeholder="Etape personnalisee"
              />
            </label>
          )}

          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">{stepPreset?.icon ?? "🧩"}</span>
              <div>
                <p className="text-sm font-semibold text-[var(--text)]">{stepPreset?.label ?? (stepForm.watch("type") || "Etape personnalisee")}</p>
                <p className="text-xs text-[var(--muted)]">{stepPreset?.typeTag ?? "personnalise"}</p>
              </div>
            </div>
          </div>

          <label className="block text-sm font-medium text-[var(--text)]">
            Quantite (kg)
            <input
              type="number"
              step="0.1"
              min="0"
              {...stepForm.register("qty_in", { required: "Quantite requise.", valueAsNumber: true })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
            />
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Pertes (kg)
            <input
              type="number"
              step="0.1"
              min="0"
              {...stepForm.register("waste_qty", { valueAsNumber: true })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
            />
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Date de realisation
            <input
              type="date"
              {...stepForm.register("date", { required: "Date requise." })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
            />
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Notes / Observations
            <textarea {...stepForm.register("notes")} className="wf-input mt-2 min-h-[84px] w-full px-3 py-2 text-sm" placeholder="Observations sur cette etape..." />
          </label>

          <div className="rounded-xl border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs font-medium text-[#b23b3b]">
            Taux de perte: {computedLossPct.toFixed(1)}% · Quantite nette: {computedNet.toFixed(1)} kg
          </div>

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
