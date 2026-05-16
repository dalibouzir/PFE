"use client";

import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  useActivatePreHarvest,
  useApproveBatchCharge,
  useBatches,
  useCompletePreHarvest,
  useCreateBatch,
  useStopPreHarvest,
  useUpdatePreHarvestStepStatuses,
  useUpdateBatch,
} from "@/hooks/useBatches";
import { useProducts } from "@/hooks/useProducts";
import {
  useCompletePreHarvestStep,
  useCreateParcel,
  useFarmers,
  useParcels,
  usePreHarvestSteps,
  useUpdatePreHarvestStep,
} from "@/hooks/useParcellesCulture";
import type { Batch, BatchCreate, ParcelCreate, PreHarvestStep, PreHarvestStepUpdate } from "@/lib/api/types";
import { getProductStepTemplate } from "@/lib/workflow/productStepTemplates";

type LotForm = {
  member_id: string;
  product_id: string;
  surface_ha: number;
  expected_yield_kg_per_ha: number;
  expected_losses_kg: number;
  estimated_charge_fcfa?: number;
};

type StepForm = {
  quantity_value?: number;
  quantity_unit: string;
  operation_cost_fcfa?: number;
  realization_date: string;
  observations: string;
};

type WorkflowDraftStep = {
  id: string;
  name: string;
  details: string;
};

type PreHarvestExecutionStatus = "todo" | "in_progress" | "done";

const CATEGORY_TONE: Record<string, string> = {
  entretien: "bg-[#FFEFD7] text-[#B25A00]",
  traitement: "bg-[#FFE6E6] text-[#A53A3A]",
  fertilisation: "bg-[#EAF8EE] text-[#0F7A3B]",
  irrigation: "bg-[#EAF5FF] text-[#2A5FB3]",
  recolte: "bg-[#FFF1E5] text-[#B65C1A]",
  transport: "bg-[#EFF1F6] text-[#4F5F78]",
};

const STEP_QUANTITY_LABEL: Record<string, string> = {
  pruning: "Quantité (arbres)",
  phytosanitary_treatment: "Quantité / dose",
  fertilization: "Quantité",
  irrigation: "Volume / quantité",
  harvest: "Quantité récoltée",
  transport_to_storage: "Quantité transportée",
};

const INVALID_PRODUCT_TERMS = [
  "pre-recolte",
  "post-recolte",
  "workflow",
  "etape",
  "step",
  "nettoyage",
  "tri",
  "sechage",
  "conditionnement",
  "stockage",
  "traitement",
  "recolte",
];

function splitTokens(raw?: string | null) {
  if (!raw) return [];
  return raw
    .split(/[;,/|]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeText(raw?: string | null) {
  if (!raw) return "";
  return raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function isValidAgriculturalProductName(name?: string | null) {
  const normalized = normalizeText(name);
  if (!normalized) return false;
  return !INVALID_PRODUCT_TERMS.some((term) => normalized.includes(term));
}

function getPreHarvestState(batch: Batch): "preparation" | "active" | "ready_post_recolte" {
  if (batch.preharvest_completed_at && batch.confirmed_weight_kg) return "ready_post_recolte";
  if (batch.preharvest_activated_at && !batch.preharvest_completed_at) return "active";
  return "preparation";
}

function stateLabel(state: "preparation" | "active" | "ready_post_recolte") {
  if (state === "ready_post_recolte") return "Prêt Post-récolte";
  if (state === "active") return "Actif";
  return "Préparation";
}

function stateTone(state: "preparation" | "active" | "ready_post_recolte"): "warning" | "info" | "success" {
  if (state === "ready_post_recolte") return "success";
  if (state === "active") return "info";
  return "warning";
}

function getWorkflowStepEmoji(stepText: string, index: number): string {
  const text = stepText.toLowerCase();
  if (text.includes("préparation") || text.includes("demarrage") || text.includes("démarrage")) return "🌱";
  if (text.includes("traitement")) return "🧪";
  if (text.includes("suivi") || text.includes("controle") || text.includes("contrôle")) return "👀";
  if (text.includes("récolte") || text.includes("recolte")) return "🌾";
  if (text.includes("conditionnement")) return "📦";
  if (index === 0) return "🌱";
  return "✅";
}

function getFrenchErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error) || !error.message) return fallback;
  if (error.message.includes("Only the latest completed step can be edited")) {
    return "Seule la dernière étape terminée peut être modifiée.";
  }
  if (error.message.includes("Pre-harvest step not found")) {
    return "Étape de pré-récolte introuvable.";
  }
  return error.message;
}

export default function ParcellesCulturePage() {
  const [search, setSearch] = useState("");
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [lotModalOpen, setLotModalOpen] = useState(false);
  const [stepModalOpen, setStepModalOpen] = useState(false);
  const [workflowModalOpen, setWorkflowModalOpen] = useState(false);
  const [confirmWeightModalOpen, setConfirmWeightModalOpen] = useState(false);
  const [confirmedWeightInput, setConfirmedWeightInput] = useState("");
  const [annexOpen, setAnnexOpen] = useState(false);
  const [activeStep, setActiveStep] = useState<PreHarvestStep | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [workflowStepsDraft, setWorkflowStepsDraft] = useState<WorkflowDraftStep[]>([]);
  const [isCreatingLot, setIsCreatingLot] = useState(false);
  const [pendingAction, setPendingAction] = useState<
    | null
    | "activate"
    | "stop"
    | "approve_charge"
    | "complete_preharvest"
    | "save_workflow"
    | "update_step_status"
  >(null);

  const farmersQuery = useFarmers();
  const { data: products = [] } = useProducts();
  const { data: batches = [] } = useBatches();

  const createBatch = useCreateBatch();
  const updateBatch = useUpdateBatch();
  const approveBatchCharge = useApproveBatchCharge();
  const activatePreHarvest = useActivatePreHarvest();
  const stopPreHarvest = useStopPreHarvest();
  const updatePreHarvestStepStatuses = useUpdatePreHarvestStepStatuses();
  const completePreHarvest = useCompletePreHarvest();
  const createParcel = useCreateParcel();
  const updateStep = useUpdatePreHarvestStep();
  const completeStep = useCompletePreHarvestStep();

  const farmers = useMemo(() => farmersQuery.data ?? [], [farmersQuery.data]);
  const farmersById = useMemo(() => new Map(farmers.map((item) => [item.id, item])), [farmers]);
  const productsById = useMemo(() => new Map(products.map((item) => [item.id, item])), [products]);

  const preHarvestLots = useMemo(() => {
    const rows = batches.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    const needle = search.trim().toLowerCase();
    if (!needle) return rows;

    return rows.filter((item) => {
      const farmerName = item.member_id ? farmersById.get(item.member_id)?.full_name ?? "" : "";
      const productName = productsById.get(item.product_id)?.name ?? "";
      const text = `${item.code} ${farmerName} ${productName}`.toLowerCase();
      return text.includes(needle);
    });
  }, [batches, farmersById, productsById, search]);

  const selectedBatch = useMemo(() => {
    if (!selectedBatchId) return preHarvestLots[0] ?? null;
    return preHarvestLots.find((item) => item.id === selectedBatchId) ?? preHarvestLots[0] ?? null;
  }, [preHarvestLots, selectedBatchId]);

  useEffect(() => {
    if (!selectedBatch && preHarvestLots.length > 0) {
      setSelectedBatchId(preHarvestLots[0].id);
      return;
    }
    if (selectedBatchId && !preHarvestLots.find((item) => item.id === selectedBatchId)) {
      setSelectedBatchId(preHarvestLots[0]?.id ?? null);
    }
  }, [preHarvestLots, selectedBatch, selectedBatchId]);

  const selectedLotState = useMemo(
    () => (selectedBatch ? getPreHarvestState(selectedBatch) : null),
    [selectedBatch],
  );

  const activeExecutionSteps = useMemo(() => {
    if (!selectedBatch) return [];
    const persisted = selectedBatch.preharvest_step_statuses ?? [];
    if (persisted.length > 0) return persisted;
    return (selectedBatch.ordered_process_steps ?? []).map((label, index) => ({
      index,
      name: label,
      status: "todo" as PreHarvestExecutionStatus,
      updated_at: null,
    }));
  }, [selectedBatch]);
  const activeExecutionCompletedCount = useMemo(
    () => activeExecutionSteps.filter((step) => step.status === "done").length,
    [activeExecutionSteps],
  );
  const activeExecutionProgress = useMemo(() => {
    if (activeExecutionSteps.length === 0) return 0;
    return Math.round((activeExecutionCompletedCount / activeExecutionSteps.length) * 100);
  }, [activeExecutionCompletedCount, activeExecutionSteps.length]);
  const allExecutionStepsDone = useMemo(() => {
    if (activeExecutionSteps.length === 0) return false;
    return activeExecutionSteps.every((step) => step.status === "done");
  }, [activeExecutionSteps]);
  const executionStarted = useMemo(
    () => activeExecutionSteps.some((step) => step.status === "in_progress" || step.status === "done"),
    [activeExecutionSteps],
  );

  const selectedFarmer = useMemo(() => {
    if (!selectedBatch?.member_id) return null;
    return farmersById.get(selectedBatch.member_id) ?? null;
  }, [selectedBatch, farmersById]);
  const selectedFarmerParcelsQuery = useParcels(selectedBatch?.member_id ?? null);
  const selectedFarmerParcels = useMemo(
    () => selectedFarmerParcelsQuery.data ?? [],
    [selectedFarmerParcelsQuery.data],
  );
  const selectedBatchParcel = useMemo(() => {
    if (!selectedBatch?.parcel_id) return null;
    return selectedFarmerParcels.find((item) => item.id === selectedBatch.parcel_id) ?? null;
  }, [selectedBatch, selectedFarmerParcels]);

  const stepsQuery = usePreHarvestSteps(selectedBatch?.parcel_id ?? null);
  const steps = useMemo(() => stepsQuery.data ?? [], [stepsQuery.data]);
  const completedCount = steps.filter((item) => item.status === "completed").length;
  const progress = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0;
  const latestCompletedStepId = useMemo(() => {
    const completed = steps.filter((item) => item.status === "completed");
    if (completed.length === 0) return null;
    return completed.sort((a, b) => b.step_order - a.step_order)[0]?.id ?? null;
  }, [steps]);

  const lotForm = useForm<LotForm>({
    defaultValues: {
      member_id: "",
      product_id: "",
      surface_ha: 1,
      expected_yield_kg_per_ha: 0,
      expected_losses_kg: 0,
      estimated_charge_fcfa: 0,
    },
  });

  const stepForm = useForm<StepForm>({
    defaultValues: {
      quantity_value: undefined,
      quantity_unit: "",
      operation_cost_fcfa: undefined,
      realization_date: new Date().toISOString().slice(0, 10),
      observations: "",
    },
  });

  const watchedFarmerId = lotForm.watch("member_id");
  useEffect(() => {
    lotForm.setValue("product_id", "");
  }, [watchedFarmerId, lotForm]);

  const modalSelectedFarmer = useMemo(
    () => farmers.find((item) => item.id === watchedFarmerId) ?? null,
    [farmers, watchedFarmerId],
  );
  const farmerProducts = useMemo(() => {
    if (!modalSelectedFarmer) return [];
    const merged = [
      ...(modalSelectedFarmer.products ?? []),
      ...splitTokens(modalSelectedFarmer.main_product),
      ...splitTokens(modalSelectedFarmer.secondary_products),
    ];
    return Array.from(new Set(merged.map((item) => normalizeText(item)).filter(Boolean)));
  }, [modalSelectedFarmer]);

  const filteredProductsForSelectedFarmer = useMemo(() => {
    if (!modalSelectedFarmer) return [];
    if (farmerProducts.length === 0) return [];
    const eligible = products.filter((product) => {
      const productName = normalizeText(product.name);
      if (!farmerProducts.includes(productName)) return false;
      return isValidAgriculturalProductName(product.name);
    });
    const dedupedByName = new Map<string, (typeof eligible)[number]>();
    for (const product of eligible) {
      const key = normalizeText(product.name);
      if (!dedupedByName.has(key)) {
        dedupedByName.set(key, product);
      }
    }
    return Array.from(dedupedByName.values()).sort((a, b) => a.name.localeCompare(b.name, "fr"));
  }, [farmerProducts, modalSelectedFarmer, products]);

  const lotEstimatedQty = useMemo(() => {
    const surface = Number(lotForm.watch("surface_ha") || 0);
    const yieldKgHa = Number(lotForm.watch("expected_yield_kg_per_ha") || 0);
    const losses = Number(lotForm.watch("expected_losses_kg") || 0);
    return Math.max(surface * yieldKgHa - losses, 0);
  }, [lotForm]);

  const openStepModal = (step: PreHarvestStep) => {
    if (selectedLotState !== "preparation") {
      window.alert("Ce lot n’est plus en préparation. Les étapes sont verrouillées.");
      return;
    }
    setActiveStep(step);
    stepForm.reset({
      quantity_value: step.quantity_value ?? undefined,
      quantity_unit: step.quantity_unit ?? "",
      operation_cost_fcfa: step.operation_cost_fcfa ?? undefined,
      realization_date: step.realization_date ?? new Date().toISOString().slice(0, 10),
      observations: step.observations ?? "",
    });
    setStepModalOpen(true);
  };

  const parseWorkflowStep = (value: string, index: number): WorkflowDraftStep => {
    const [rawName, ...rawDetails] = value.split(" — ");
    const name = rawName?.trim() || value.trim();
    const details = rawDetails.join(" — ").trim();
    return {
      id: `${index}-${value}`,
      name,
      details,
    };
  };

  const submitLot = lotForm.handleSubmit(async (values) => {
    if (isCreatingLot) return;
    setIsCreatingLot(true);

    if (!values.member_id) {
      setFormError("Agriculteur requis.");
      setIsCreatingLot(false);
      return;
    }
    if (!values.product_id) {
      setFormError("Produit requis.");
      setIsCreatingLot(false);
      return;
    }

    const selectedProduct = products.find((item) => item.id === values.product_id);
    const proposedSteps = getProductStepTemplate(selectedProduct?.name, "pre_harvest");

    try {
      const now = new Date();
      const isoDate = now.toISOString().slice(0, 10);
      const dateToken = now.toISOString().replace(/-|:|T|Z|\./g, "").slice(0, 14);
      const autoParcelName = `Parcelle auto - ${selectedProduct?.name ?? "culture"} - ${dateToken}`;
      const parcelPayload: ParcelCreate = {
        farmer_id: values.member_id,
        name: autoParcelName,
        surface_ha: Number(values.surface_ha),
        main_culture: selectedProduct?.name ?? "Culture",
        variety: null,
        tree_count: null,
      };
      const createdParcel = await createParcel.mutateAsync(parcelPayload);

      const payload: BatchCreate = {
        product_id: values.product_id,
        member_id: values.member_id,
        parcel_id: createdParcel.id,
        creation_date: isoDate,
        unit: (selectedProduct?.unit as "kg" | "ton") || "kg",
        initial_qty: Math.max(lotEstimatedQty, 1),
        process_steps: proposedSteps,
        surface_ha: Number(values.surface_ha),
        expected_yield_kg_per_ha: Number(values.expected_yield_kg_per_ha),
        expected_losses_kg: Number(values.expected_losses_kg),
        estimated_charge_fcfa: Number(values.estimated_charge_fcfa || 0),
      };
      const created = await createBatch.mutateAsync(payload);
      setSelectedBatchId(created.id);
      setLotModalOpen(false);
      setFormError(null);
      lotForm.reset({
        member_id: "",
        product_id: "",
        surface_ha: 1,
        expected_yield_kg_per_ha: 0,
        expected_losses_kg: 0,
        estimated_charge_fcfa: 0,
      });
    } catch (error) {
      setFormError(getFrenchErrorMessage(error, "Impossible de créer le lot."));
    } finally {
      setIsCreatingLot(false);
    }
  });

  const submitStep = stepForm.handleSubmit(async (values) => {
    if (!selectedBatch?.parcel_id || !activeStep) return;
    setFormError(null);
    try {
      const payload: PreHarvestStepUpdate = {
        quantity_value: values.quantity_value !== undefined ? Number(values.quantity_value) : null,
        quantity_unit: values.quantity_unit.trim() || null,
        operation_cost_fcfa:
          values.operation_cost_fcfa !== undefined ? Number(values.operation_cost_fcfa) : null,
        realization_date: values.realization_date,
        observations: values.observations.trim() || null,
      };
      await updateStep.mutateAsync({ parcelId: selectedBatch.parcel_id, stepId: activeStep.id, payload });
      await completeStep.mutateAsync({ parcelId: selectedBatch.parcel_id, stepId: activeStep.id });
      setStepModalOpen(false);
    } catch (error) {
      setFormError(getFrenchErrorMessage(error, "Impossible d'enregistrer l'étape."));
    }
  });

  const handleApproveLotCharge = async () => {
    if (!selectedBatch) return;
    if (!window.confirm("Approuver la charge estimée et créer Avance Producteur + Trésorerie OUT ?")) return;
    try {
      setPendingAction("approve_charge");
      await approveBatchCharge.mutateAsync(selectedBatch.id);
    } catch (error) {
      setFormError(getFrenchErrorMessage(error, "Impossible d'approuver la charge."));
    } finally {
      setPendingAction(null);
    }
  };

  const handleActivateLot = async () => {
    if (!selectedBatch || selectedLotState !== "preparation") return;
    try {
      setPendingAction("activate");
      await activatePreHarvest.mutateAsync(selectedBatch.id);
    } catch (error) {
      setFormError(getFrenchErrorMessage(error, "Impossible d'activer le lot."));
    } finally {
      setPendingAction(null);
    }
  };

  const handleStopLot = async () => {
    if (!selectedBatch || selectedLotState !== "active") return;
    if (executionStarted) {
      window.alert("Impossible de stopper un lot dont l’exécution a commencé.");
      return;
    }
    if (!window.confirm("Le lot repassera en préparation et pourra être modifié.")) return;
    try {
      setPendingAction("stop");
      await stopPreHarvest.mutateAsync(selectedBatch.id);
    } catch (error) {
      setFormError(getFrenchErrorMessage(error, "Impossible de stopper le lot."));
    } finally {
      setPendingAction(null);
    }
  };

  const handleTryEditWorkflow = () => {
    if (!selectedBatch || !selectedLotState) return;
    if (selectedLotState !== "preparation") {
      window.alert("Ce lot est actif et ne peut plus être modifié.");
      return;
    }
    const source = selectedBatch.ordered_process_steps ?? [];
    const parsed = source.map((item, index) => parseWorkflowStep(item, index));
    setWorkflowStepsDraft(parsed);
    setWorkflowError(null);
    setWorkflowModalOpen(true);
  };

  const handleAddWorkflowStep = () => {
    setWorkflowStepsDraft((current) => [
      ...current,
      { id: `new-${Date.now()}-${current.length}`, name: "", details: "" },
    ]);
  };

  const handleUpdateWorkflowStep = (id: string, key: "name" | "details", value: string) => {
    setWorkflowStepsDraft((current) =>
      current.map((step) => (step.id === id ? { ...step, [key]: value } : step)),
    );
  };

  const handleRemoveWorkflowStep = (id: string) => {
    setWorkflowStepsDraft((current) => current.filter((step) => step.id !== id));
  };

  const handleMoveWorkflowStep = (index: number, direction: -1 | 1) => {
    setWorkflowStepsDraft((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const clone = [...current];
      const [item] = clone.splice(index, 1);
      clone.splice(target, 0, item);
      return clone;
    });
  };

  const handleSaveWorkflowSteps = async () => {
    if (!selectedBatch) return;
    if (selectedLotState !== "preparation") {
      window.alert("Ce lot est actif et ne peut plus être modifié.");
      setWorkflowModalOpen(false);
      return;
    }
    const normalized = workflowStepsDraft
      .map((step) => ({
        name: step.name.trim(),
        details: step.details.trim(),
      }))
      .filter((step) => step.name.length > 0)
      .map((step) => (step.details ? `${step.name} — ${step.details}` : step.name));

    if (workflowStepsDraft.length > 0 && normalized.length !== workflowStepsDraft.length) {
      setWorkflowError("Le nom de l'étape est requis.");
      return;
    }
    if (normalized.length === 0) {
      setWorkflowError("Ajoutez au moins une étape avant d'enregistrer.");
      return;
    }

    try {
      setPendingAction("save_workflow");
      await updateBatch.mutateAsync({
        id: selectedBatch.id,
        payload: { process_steps: normalized },
      });
      setWorkflowModalOpen(false);
      setWorkflowError(null);
    } catch (error) {
      setWorkflowError(getFrenchErrorMessage(error, "Impossible d'enregistrer le workflow."));
    } finally {
      setPendingAction(null);
    }
  };

  const updateExecutionStepStatus = async (stepIndex: number, status: PreHarvestExecutionStatus) => {
    if (!selectedBatch) return;
    const isReadyPostRecolte = Boolean(selectedBatch.preharvest_completed_at && selectedBatch.confirmed_weight_kg);
    if (selectedLotState !== "active" || isReadyPostRecolte) {
      window.alert("Pré-récolte déjà confirmée. Les étapes d’exécution sont verrouillées.");
      return;
    }
    const nextStatuses = activeExecutionSteps.map((step) =>
      step.index === stepIndex
        ? {
            ...step,
            status,
            updated_at: new Date().toISOString(),
          }
        : step,
    );
    try {
      setPendingAction("update_step_status");
      await updatePreHarvestStepStatuses.mutateAsync({
        id: selectedBatch.id,
        payload: { statuses: nextStatuses },
      });
    } catch (error) {
      setFormError(getFrenchErrorMessage(error, "Impossible de mettre à jour le statut d'étape."));
    } finally {
      setPendingAction(null);
    }
  };

  const handleOpenConfirmWeightModal = () => {
    if (!selectedBatch) return;
    if (selectedLotState === "active" && !allExecutionStepsDone) {
      window.alert("Toutes les étapes Pré-récolte doivent être terminées avant de confirmer le poids réel.");
      return;
    }
    setConfirmedWeightInput(selectedBatch.confirmed_weight_kg?.toString() ?? "");
    setConfirmWeightModalOpen(true);
  };

  const handleCompleteLotPreHarvest = async () => {
    if (!selectedBatch) return;
    const confirmed = Number(confirmedWeightInput);
    if (!Number.isFinite(confirmed) || confirmed <= 0) {
      setFormError("Poids confirmé invalide.");
      return;
    }
    if (!window.confirm("Confirmer la clôture pré-récolte et créer Collecte + Stock IN ?")) return;
    try {
      setPendingAction("complete_preharvest");
      await completePreHarvest.mutateAsync({ id: selectedBatch.id, confirmed_weight_kg: confirmed });
      setConfirmWeightModalOpen(false);
    } catch (error) {
      setFormError(getFrenchErrorMessage(error, "Impossible de compléter la pré-récolte."));
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <main>
      <PageIntro title="Parcelles & Culture" />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <StatusBadge label="⚠️ 1 stock(s) bas" tone="warning" />
            <StatusBadge label="🔔 1 commande(s) à traiter" tone="info" />
          </div>
          <div className="flex items-center gap-2">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="wf-input h-10 w-64 px-3 text-sm"
              placeholder="Rechercher lot, agriculteur, produit..."
            />
            <button
              type="button"
              onClick={() => setLotModalOpen(true)}
              className="soft-focus rounded-xl bg-[#168A4A] px-4 py-2 text-sm font-semibold text-white"
            >
              Créer un lot Pré-récolte
            </button>
          </div>
        </div>
      </section>

      <section className="grid min-h-0 gap-4 xl:grid-cols-[340px_1fr]">
        <aside className="space-y-3">
          <article
            className="premium-card reveal h-[calc(100vh-140px)] overflow-y-auto rounded-2xl p-4"
            style={{ ["--delay" as string]: "40ms" }}
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-base font-semibold text-[var(--text)]">Lots Pré-récolte</h3>
              <span className="text-xs text-[var(--muted)]">{preHarvestLots.length} lot(s)</span>
            </div>
            {preHarvestLots.length === 0 ? (
              <p className="text-xs text-[var(--muted)]">Aucun lot Pré-récolte disponible.</p>
            ) : (
              <div className="space-y-2">
                {preHarvestLots.map((lot) => {
                  const isActive = lot.id === selectedBatch?.id;
                  const farmerName = lot.member_id ? farmersById.get(lot.member_id)?.full_name ?? "-" : "-";
                  const productName = productsById.get(lot.product_id)?.name ?? "-";
                  const state = getPreHarvestState(lot);
                  return (
                    <article
                      key={lot.id}
                      className={`rounded-2xl border px-3 py-3 transition-colors ${
                        isActive
                          ? "border-[#168A4A] bg-[#EAF8EE]"
                          : "border-[var(--line)] bg-[var(--surface-soft)]"
                      }`}
                    >
                      <div className="mb-2 flex items-start justify-between gap-2">
                        <button type="button" onClick={() => setSelectedBatchId(lot.id)} className="min-w-0 text-left">
                          <p className="text-sm font-semibold text-[var(--text)]">{lot.code}</p>
                        </button>
                        <StatusBadge label={stateLabel(state)} tone={stateTone(state)} />
                      </div>
                      <button type="button" onClick={() => setSelectedBatchId(lot.id)} className="w-full text-left">
                        <div className="mt-2 grid gap-1">
                          <p className="text-xs text-[var(--muted)]">Agriculteur: {farmerName}</p>
                          <p className="text-xs text-[var(--muted)]">Produit: {productName}</p>
                          <p className="text-xs text-[var(--muted)]">Surface: {(lot.surface_ha ?? 0).toLocaleString("fr-FR")} ha</p>
                          <p className="text-xs text-[var(--muted)]">Quantité estimée: {(lot.estimated_qty_kg ?? 0).toLocaleString("fr-FR")} kg</p>
                          <p className="text-xs text-[var(--muted)]">Charge estimée: {(lot.estimated_charge_fcfa ?? 0).toLocaleString("fr-FR")} FCFA</p>
                          <p className="text-xs text-[var(--muted)]">Charge: {lot.charge_approved_at ? "Approuvée" : "En attente"}</p>
                        </div>
                      </button>
                    </article>
                  );
                })}
              </div>
            )}
          </article>
        </aside>

        <section className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "60ms" }}>
          {!selectedBatch ? (
            <p className="text-sm text-[var(--muted)]">Sélectionnez un lot Pré-récolte ou créez un nouveau lot.</p>
          ) : (
            <>
              <div className="mb-4 rounded-2xl border border-[var(--line)] bg-[var(--surface-soft)] p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-[var(--text)]">Lot {selectedBatch.code}</h3>
                    <p className="text-sm text-[var(--muted)]">
                      Agriculteur: {selectedFarmer?.full_name ?? "-"} · Produit: {productsById.get(selectedBatch.product_id)?.name ?? "-"}
                    </p>
                  </div>
                  <StatusBadge label={stateLabel(selectedLotState ?? "preparation")} tone={stateTone(selectedLotState ?? "preparation")} />
                </div>
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-xl border border-[var(--line)] bg-white px-3 py-2">
                    <p className="text-[11px] text-[var(--muted)]">Surface</p>
                    <p className="text-sm font-semibold text-[var(--text)]">{(selectedBatch.surface_ha ?? 0).toLocaleString("fr-FR")} ha</p>
                  </div>
                  <div className="rounded-xl border border-[var(--line)] bg-white px-3 py-2">
                    <p className="text-[11px] text-[var(--muted)]">Poids estimé</p>
                    <p className="text-sm font-semibold text-[var(--text)]">{(selectedBatch.estimated_qty_kg ?? 0).toLocaleString("fr-FR")} kg</p>
                  </div>
                  <div className="rounded-xl border border-[var(--line)] bg-white px-3 py-2">
                    <p className="text-[11px] text-[var(--muted)]">Charge estimée</p>
                    <p className="text-sm font-semibold text-[var(--text)]">{(selectedBatch.estimated_charge_fcfa ?? 0).toLocaleString("fr-FR")} FCFA</p>
                  </div>
                  <div className="rounded-xl border border-[var(--line)] bg-white px-3 py-2">
                    <p className="text-[11px] text-[var(--muted)]">Parcelle liée</p>
                    <p className="truncate text-sm font-semibold text-[var(--text)]">{selectedBatchParcel?.name ?? selectedBatch.parcel_id ?? "-"}</p>
                  </div>
                </div>
              </div>

              <article className="mb-4 rounded-2xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-[var(--text)]">Actions lot</p>
                  <StatusBadge
                    label={selectedBatch.charge_approved_at ? "Charge approuvée" : "Charge en attente"}
                    tone={selectedBatch.charge_approved_at ? "success" : "warning"}
                  />
                </div>
                <div className="grid gap-2 text-xs text-[var(--muted)] sm:grid-cols-2">
                  <p>Rendement attendu: {(selectedBatch.expected_yield_kg_per_ha ?? 0).toLocaleString("fr-FR")} kg/ha</p>
                  <p>Pertes attendues: {(selectedBatch.expected_losses_kg ?? 0).toLocaleString("fr-FR")} kg</p>
                  <p>Activation: {selectedBatch.preharvest_activated_at ? "Actif" : "Préparation"}</p>
                  <p>Poids réel confirmé: {(selectedBatch.confirmed_weight_kg ?? 0).toLocaleString("fr-FR")} kg</p>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedLotState === "preparation" ? (
                    <button
                      type="button"
                      onClick={handleActivateLot}
                      disabled={pendingAction !== null}
                      className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {pendingAction === "activate" ? "Activation en cours..." : "Activer le lot"}
                    </button>
                  ) : null}
                  {selectedLotState === "active" ? (
                    <button
                      type="button"
                      onClick={handleStopLot}
                      disabled={executionStarted || pendingAction !== null}
                      className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                      title={executionStarted ? "Impossible de stopper un lot dont l’exécution a commencé." : undefined}
                    >
                      {pendingAction === "stop" ? "Arrêt en cours..." : "Stopper le lot"}
                    </button>
                  ) : null}
                  {selectedLotState === "preparation" ? (
                    <button
                      type="button"
                      onClick={handleTryEditWorkflow}
                      disabled={pendingAction !== null}
                      className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Modifier workflow
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={handleApproveLotCharge}
                    disabled={Boolean(selectedBatch.charge_approved_at) || pendingAction !== null}
                    className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {selectedBatch.charge_approved_at
                      ? "Charge approuvée"
                      : pendingAction === "approve_charge"
                        ? "Approbation en cours..."
                        : "Approuver charge"}
                  </button>
                  {selectedLotState !== "ready_post_recolte" ? (
                    <button
                      type="button"
                      onClick={handleOpenConfirmWeightModal}
                      disabled={(selectedLotState === "active" && !allExecutionStepsDone) || pendingAction !== null}
                      className="soft-focus wf-btn-primary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {pendingAction === "complete_preharvest" ? "Clôture en cours..." : "Compléter pré-récolte"}
                    </button>
                  ) : null}
                </div>
                {selectedLotState === "active" && !allExecutionStepsDone ? (
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    Terminez toutes les étapes d&apos;exécution avant de confirmer le poids réel.
                  </p>
                ) : null}
                {selectedLotState === "active" && executionStarted ? (
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    Impossible de stopper un lot dont l’exécution a commencé.
                  </p>
                ) : null}
                {selectedLotState !== "ready_post_recolte" ? (
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    Le stock réel sera créé uniquement après saisie du poids confirmé.
                  </p>
                ) : null}
              </article>

              {selectedLotState === "preparation" ? (
              <article className="mb-4 rounded-2xl border border-[var(--line)] bg-[#FFF9F1] p-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-semibold text-[var(--text)]">Workflow Pré-récolte planifié</p>
                  <StatusBadge label={`${selectedBatch.ordered_process_steps.length} étape(s)`} tone="info" />
                </div>
                {selectedBatch.ordered_process_steps.length === 0 ? (
                  <p className="text-xs text-[var(--muted)]">Aucune étape planifiée.</p>
                ) : (
                  <div className="overflow-hidden pb-1">
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {selectedBatch.ordered_process_steps.map((step, index) => (
                        <div key={`planned-${index}-${step}`} className="relative">
                          <article className="h-full rounded-xl border border-[var(--line)] bg-white p-3">
                            <div className="mb-2 flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                <div className="flex h-8 w-8 items-center justify-center rounded-full border border-[var(--line)] bg-[#F8FBF6] text-sm">
                                  {getWorkflowStepEmoji(step, index)}
                                </div>
                                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                                  Étape {index + 1}
                                </p>
                              </div>
                              <StatusBadge
                                label={selectedLotState === "active" ? "Verrouillé" : "Éditable"}
                                tone={selectedLotState === "active" ? "warning" : "info"}
                              />
                            </div>
                            {(() => {
                              const [name, ...detailsParts] = step.split(" — ");
                              const details = detailsParts.join(" — ").trim();
                              return (
                                <>
                                  <p className="text-sm font-semibold text-[var(--text)]">{name.trim()}</p>
                                  {details ? <p className="mt-1 text-xs text-[var(--muted)]">{details}</p> : null}
                                </>
                              );
                            })()}
                          </article>
                          {index < selectedBatch.ordered_process_steps.length - 1 ? (
                            <>
                              <div className="pointer-events-none absolute -right-2 top-8 hidden h-px w-4 bg-[var(--line)] md:block xl:hidden" />
                              <div className="pointer-events-none absolute -right-2 top-8 hidden h-px w-4 bg-[var(--line)] xl:block" />
                            </>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </article>
              ) : null}

              {selectedLotState === "active" ? (
                <article className="mb-4 rounded-2xl border border-[var(--line)] bg-[#FFF9F1] p-3">
                  <p className="text-sm font-semibold text-[var(--text)]">Exécution terrain — Pré-récolte</p>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    Ces étapes servent à suivre les travaux terrain. Elles ne modifient pas le stock.
                  </p>
                  {activeExecutionSteps.length === 0 ? (
                    <p className="mt-2 text-xs text-[var(--muted)]">Aucune étape prévue pour ce lot.</p>
                  ) : (
                    <>
                      <div className="mb-3 mt-2">
                        <p className="mb-1 text-xs text-[var(--muted)]">
                          {activeExecutionCompletedCount}/{activeExecutionSteps.length} terminées
                        </p>
                        <div className="h-2 w-full rounded-full bg-[#ECEFE8]">
                          <div className="h-2 rounded-full bg-[#168A4A]" style={{ width: `${activeExecutionProgress}%` }} />
                        </div>
                      </div>
                      <div className="space-y-2">
                        {activeExecutionSteps.map((step) => {
                          const statusLabel =
                            step.status === "done" ? "Terminé" : step.status === "in_progress" ? "En cours" : "À faire";
                          const tone =
                            step.status === "done" ? "success" : step.status === "in_progress" ? "info" : "warning";
                          return (
                            <article key={`${step.index}-${step.name}`} className="rounded-xl border border-[var(--line)] bg-white p-3">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="text-sm font-semibold text-[var(--text)]">
                                  {step.index + 1}. {step.name}
                                </p>
                                <div className="flex items-center gap-1.5">
                                  <StatusBadge label="Structure verrouillée" tone="warning" />
                                  <StatusBadge label={statusLabel} tone={tone} />
                                </div>
                              </div>
                              <div className="mt-2 flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  onClick={() => updateExecutionStepStatus(step.index, "todo")}
                                  disabled={pendingAction !== null}
                                  className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  À faire
                                </button>
                                <button
                                  type="button"
                                  onClick={() => updateExecutionStepStatus(step.index, "in_progress")}
                                  disabled={pendingAction !== null}
                                  className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  En cours
                                </button>
                                <button
                                  type="button"
                                  onClick={() => updateExecutionStepStatus(step.index, "done")}
                                  disabled={pendingAction !== null}
                                  className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  Terminé
                                </button>
                              </div>
                            </article>
                          );
                        })}
                      </div>
                    </>
                  )}
                </article>
              ) : null}

              {selectedLotState === "ready_post_recolte" ? (
                <article className="mb-4 rounded-2xl border border-[var(--line)] bg-[#EAF8EE] p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-[var(--text)]">Résumé Pré-récolte terminé</p>
                    <StatusBadge label="Prêt Post-récolte" tone="success" />
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    Workflow verrouillé et finalisé. Ce lot peut continuer en Post-récolte.
                  </p>
                  <div className="mt-2 grid gap-2 text-xs text-[var(--muted)] sm:grid-cols-2">
                    <p>Étapes terminées: {activeExecutionCompletedCount}/{activeExecutionSteps.length || 0}</p>
                    <p>Poids confirmé: {(selectedBatch.confirmed_weight_kg ?? 0).toLocaleString("fr-FR")} kg</p>
                  </div>
                </article>
              ) : null}

              <article className="rounded-2xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-[var(--text)]">Annexe — Suivi agronomique de la parcelle</p>
                    <p className="text-xs text-[var(--muted)]">
                      Information secondaire. Le cycle officiel est géré par le lot Pré-récolte ci-dessus.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAnnexOpen((current) => !current)}
                    className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold"
                  >
                    {annexOpen ? "Masquer l’annexe agronomique" : "Afficher l’annexe agronomique"}
                  </button>
                </div>
                {annexOpen ? (
                  <div className="mt-3">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                      <StatusBadge label={selectedBatch.parcel_id ? "Parcelle liée" : "Sans parcelle"} tone={selectedBatch.parcel_id ? "info" : "warning"} />
                    </div>

                    <article className="rounded-2xl border border-[var(--line)] bg-[#FFF9F1] p-3">
                      <p className="text-sm font-semibold text-[var(--text)]">Suivi pré-récolte (annexe)</p>
                      {selectedBatch.parcel_id ? (
                        <>
                          <div className="mb-3 mt-2">
                            <p className="mb-1 text-xs text-[var(--muted)]">{completedCount}/{steps.length || 0} réalisées</p>
                            <div className="h-2 w-full rounded-full bg-[#ECEFE8]">
                              <div className="h-2 rounded-full bg-[#168A4A]" style={{ width: `${progress}%` }} />
                            </div>
                          </div>
                          {steps.length === 0 ? (
                            <p className="text-xs text-[var(--muted)]">Aucune étape pré-récolte liée à cette parcelle.</p>
                          ) : (
                            <div className="space-y-2">
                              {steps.map((step) => {
                                const canEditStep =
                                  selectedLotState === "preparation" &&
                                  (step.status !== "completed" || step.id === latestCompletedStepId);
                                return (
                                <article key={step.id} className="rounded-xl border border-[var(--line)] bg-white p-3">
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="flex items-center gap-2">
                                      <span className="text-lg">{step.icon}</span>
                                      <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${CATEGORY_TONE[step.category] ?? "bg-[#EEF2F5] text-[#4A5A71]"}`}>
                                        {step.category}
                                      </span>
                                    </div>
                                    <StatusBadge
                                      label={step.status === "completed" ? "Terminé" : "À faire"}
                                      tone={step.status === "completed" ? "success" : "warning"}
                                    />
                                  </div>
                                  <p className="mt-1 text-sm font-semibold text-[var(--text)]">{step.label}</p>
                                  <div className="mt-2 flex items-center justify-end">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        if (!canEditStep) {
                                          window.alert(
                                            selectedLotState === "preparation"
                                              ? "Seule la dernière étape terminée peut être modifiée."
                                              : "Ce lot n’est plus en préparation. Les étapes sont verrouillées.",
                                          );
                                          return;
                                        }
                                        openStepModal(step);
                                      }}
                                      disabled={!canEditStep}
                                      className="soft-focus rounded-xl bg-[#D96A2B] px-3 py-1.5 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                      {!canEditStep ? "Verrouillée" : step.status === "completed" ? "Modifier" : "Saisir données"}
                                    </button>
                                  </div>
                                </article>
                              )})}
                            </div>
                          )}
                        </>
                      ) : (
                        <p className="mt-2 text-xs text-[var(--muted)]">
                          Ce lot n&apos;est pas rattaché à une parcelle. Le workflow principal est porté par le lot.
                        </p>
                      )}
                    </article>
                  </div>
                ) : null}
              </article>
            </>
          )}

          {formError ? <p className="mt-3 text-xs text-[#A53A3A]">{formError}</p> : null}
        </section>
      </section>

      <LiquidGlassModal
        open={confirmWeightModalOpen}
        onClose={() => setConfirmWeightModalOpen(false)}
        title="Confirmer le poids réel"
        subtitle="Le stock réel sera créé uniquement après confirmation du poids réel."
        size="md"
      >
        <div className="space-y-3">
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 text-xs text-[var(--muted)]">
            <p>Lot: {selectedBatch?.code ?? "-"}</p>
            <p>Produit: {selectedBatch ? productsById.get(selectedBatch.product_id)?.name ?? "-" : "-"}</p>
            <p>Poids estimé: {selectedBatch ? (selectedBatch.estimated_qty_kg ?? 0).toLocaleString("fr-FR") : 0} kg</p>
          </div>
          <label className="block text-sm font-medium text-[var(--text)]">
            Poids réel confirmé (kg)
            <input
              type="number"
              min="0"
              step="0.1"
              value={confirmedWeightInput}
              onChange={(event) => setConfirmedWeightInput(event.target.value)}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
              placeholder="ex: 1200"
            />
          </label>
          <p className="text-xs text-[#A53A3A]">
            Cette action créera une Collecte/Input et un mouvement Stock IN.
          </p>
          {formError ? <p className="text-xs text-[#A53A3A]">{formError}</p> : null}
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirmWeightModalOpen(false)}
              className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              disabled={pendingAction !== null}
            >
              Annuler
            </button>
            <button
              type="button"
              onClick={handleCompleteLotPreHarvest}
              className="soft-focus wf-btn-primary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              disabled={pendingAction !== null}
            >
              {pendingAction === "complete_preharvest" ? "Confirmation en cours..." : "Confirmer le poids"}
            </button>
          </div>
        </div>
      </LiquidGlassModal>

      <LiquidGlassModal
        open={stepModalOpen}
        onClose={() => setStepModalOpen(false)}
        title={`Saisir — ${activeStep?.label ?? ""}`}
        subtitle="Enregistrer les données d'exécution de cette étape."
        size="md"
      >
        <form onSubmit={submitStep} className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            {STEP_QUANTITY_LABEL[activeStep?.step_key ?? ""] ?? "Quantité"}
            <input
              type="number"
              min="0"
              step="0.1"
              {...stepForm.register("quantity_value", { valueAsNumber: true })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
              placeholder="ex: 500"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Unité
            <input
              {...stepForm.register("quantity_unit")}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
              placeholder="ex: arbres / kg / L"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Coût de l’opération (FCFA)
            <input
              type="number"
              min="0"
              step="1"
              {...stepForm.register("operation_cost_fcfa", { valueAsNumber: true })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
              placeholder="ex: 25000"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Date de réalisation
            <input
              type="date"
              {...stepForm.register("realization_date", { required: "Date requise." })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Observations
            <textarea
              {...stepForm.register("observations")}
              className="wf-input mt-2 w-full px-3 py-2.5 text-sm"
              placeholder="Notes, remarques..."
            />
          </label>
          {formError ? <p className="text-xs text-[#A53A3A]">{formError}</p> : null}
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setStepModalOpen(false)}
              className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold"
            >
              Annuler
            </button>
            <button
              type="submit"
              className="soft-focus rounded-xl bg-[#168A4A] px-3 py-2 text-sm font-semibold text-white"
            >
              Enregistrer
            </button>
          </div>
        </form>
      </LiquidGlassModal>

      <LiquidGlassModal
        open={lotModalOpen}
        onClose={() => setLotModalOpen(false)}
        title="Créer un lot Pré-récolte"
        subtitle="Le lot est le pilote du workflow. L'estimation n'impacte pas le stock."
        size="md"
      >
        <form onSubmit={submitLot} className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            Agriculteur / membre
            <select
              {...lotForm.register("member_id", { required: "Agriculteur requis." })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
            >
              <option value="">Sélectionner</option>
              {farmers.map((farmer) => (
                <option key={farmer.id} value={farmer.id}>
                  {farmer.full_name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Produit (filtré selon l&apos;agriculteur)
            <select
              {...lotForm.register("product_id", { required: "Produit requis." })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
              disabled={!modalSelectedFarmer}
            >
              <option value="">Sélectionner</option>
              {filteredProductsForSelectedFarmer.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name}
                </option>
              ))}
            </select>
            {modalSelectedFarmer && filteredProductsForSelectedFarmer.length === 0 ? (
              <p className="mt-1 text-xs text-[var(--muted)]">
                Aucun produit valide configuré pour ce producteur.
              </p>
            ) : null}
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Surface (ha)
            <input
              type="number"
              min="0"
              step="0.1"
              {...lotForm.register("surface_ha", { valueAsNumber: true })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Rendement attendu (kg/ha)
            <input
              type="number"
              min="0"
              step="1"
              {...lotForm.register("expected_yield_kg_per_ha", { valueAsNumber: true })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Pertes attendues (kg)
            <input
              type="number"
              min="0"
              step="1"
              {...lotForm.register("expected_losses_kg", { valueAsNumber: true })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Charge estimée (FCFA)
            <input
              type="number"
              min="0"
              step="1"
              {...lotForm.register("estimated_charge_fcfa", { valueAsNumber: true })}
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
            />
          </label>
          <div className="rounded-xl border border-[#BDD6FB] bg-[#EEF5FF] px-3 py-2 text-xs text-[#2F80ED]">
            Quantité estimée = surface × rendement - pertes = {lotEstimatedQty.toLocaleString("fr-FR")} kg.
            <br />
            Quantité prévisionnelle — n&apos;affecte pas le stock.
          </div>
          {formError ? <p className="text-xs text-[#A53A3A]">{formError}</p> : null}
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setLotModalOpen(false)}
              className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold"
              disabled={isCreatingLot}
            >
              Annuler
            </button>
            <button type="submit" className="soft-focus wf-btn-primary px-3 py-2 text-sm font-semibold" disabled={isCreatingLot}>
              {isCreatingLot ? "Création en cours..." : "Créer le lot"}
            </button>
          </div>
        </form>
      </LiquidGlassModal>

      <LiquidGlassModal
        open={workflowModalOpen}
        onClose={() => setWorkflowModalOpen(false)}
        title="Modifier workflow Pré-récolte"
        subtitle="Edition des étapes proposées avant activation."
        size="lg"
      >
        <div className="space-y-4">
          {workflowStepsDraft.length === 0 ? (
            <div className="rounded-2xl border border-[var(--line)] bg-[var(--surface-soft)] px-4 py-4 text-sm text-[var(--muted)]">
              Aucune étape proposée. Ajoutez une étape avant activation.
            </div>
          ) : (
            <div className="space-y-2">
              {workflowStepsDraft.map((step, index) => (
                <article key={step.id} className="rounded-2xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Étape {index + 1}</p>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleMoveWorkflowStep(index, -1)}
                        className="soft-focus wf-btn-secondary px-2.5 py-1 text-xs font-semibold"
                        disabled={index === 0 || pendingAction !== null}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        onClick={() => handleMoveWorkflowStep(index, 1)}
                        className="soft-focus wf-btn-secondary px-2.5 py-1 text-xs font-semibold"
                        disabled={index === workflowStepsDraft.length - 1 || pendingAction !== null}
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemoveWorkflowStep(step.id)}
                        className="soft-focus rounded-xl bg-[#A53A3A] px-2.5 py-1 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={pendingAction !== null}
                      >
                        Supprimer
                      </button>
                    </div>
                  </div>
                  <label className="block text-sm font-medium text-[var(--text)]">
                    Nom de l&apos;étape
                    <input
                      value={step.name}
                      onChange={(event) => handleUpdateWorkflowStep(step.id, "name", event.target.value)}
                      className="wf-input mt-2 h-10 w-full px-3 text-sm"
                      placeholder="Ex: Traitement phytosanitaire"
                      disabled={pendingAction !== null}
                    />
                  </label>
                  <label className="mt-2 block text-sm font-medium text-[var(--text)]">
                    Action / détails
                    <input
                      value={step.details}
                      onChange={(event) => handleUpdateWorkflowStep(step.id, "details", event.target.value)}
                      className="wf-input mt-2 h-10 w-full px-3 text-sm"
                      placeholder="Ex: pulvérisation préventive"
                      disabled={pendingAction !== null}
                    />
                  </label>
                </article>
              ))}
            </div>
          )}
          {workflowError ? <p className="text-xs text-[#A53A3A]">{workflowError}</p> : null}
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--line)] pt-3">
            <button
              type="button"
              onClick={handleAddWorkflowStep}
              className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              disabled={pendingAction !== null}
            >
              + Ajouter étape
            </button>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setWorkflowModalOpen(false)}
                className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                disabled={pendingAction !== null}
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleSaveWorkflowSteps}
                className="soft-focus wf-btn-primary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                disabled={pendingAction !== null}
              >
                {pendingAction === "save_workflow" ? "Enregistrement en cours..." : "Enregistrer"}
              </button>
            </div>
          </div>
        </div>
      </LiquidGlassModal>
    </main>
  );
}
