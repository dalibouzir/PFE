"use client";

import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { ConfirmActionModal } from "@/components/ui/ConfirmActionModal";
import { ContentAreaLoader } from "@/components/ui/ContentAreaLoader";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ExportActions } from "@/components/ui/table/ExportActions";
import { TableToolbar } from "@/components/ui/table/TableToolbar";
import {
  useActivatePreHarvest,
  useApproveBatchCharge,
  useBatches,
  useCompletePreHarvest,
  useCreateBatch,
  useDeleteBatch,
  useStopPreHarvest,
  useUpdatePreHarvestStepStatuses,
  useUpdateBatch,
} from "@/hooks/useBatches";
import { useProducts } from "@/hooks/useProducts";
import {
  useCreateParcel,
  useFarmers,
  useParcels,
} from "@/hooks/useParcellesCulture";
import type { Batch, BatchCreate, ParcelCreate } from "@/lib/api/types";
import { exportRowsToCsv, exportRowsToExcel, exportRowsToPdf, type ExportColumn } from "@/lib/export/client";
import { useTableControls } from "@/lib/table/useTableControls";
import { getProductStepTemplate } from "@/lib/workflow/productStepTemplates";

type LotForm = {
  member_id: string;
  product_id: string;
  surface_ha: number;
  expected_yield_kg_per_ha: number;
  expected_losses_kg: number;
};

type WorkflowDraftStep = {
  id: string;
  name: string;
  details: string;
};

type PreHarvestExecutionStatus = "todo" | "in_progress" | "done";
type PreHarvestExecutionStep = {
  index: number;
  name: string;
  status: PreHarvestExecutionStatus;
  updated_at?: string | null;
  execution_date?: string | null;
  duration_minutes?: number | null;
  summary?: string | null;
};

const MINUTES_PER_DAY = 60 * 24;

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

function getPreHarvestState(batch: Batch): "preparation" | "active" | "ready_collecte" | "ready_post_recolte" {
  if (batch.preharvest_completed_at && (batch.collecte_created || batch.stock_in_created || batch.confirmed_weight_kg)) {
    return "ready_post_recolte";
  }
  if (batch.preharvest_completed_at) return "ready_collecte";
  if (batch.preharvest_activated_at && !batch.preharvest_completed_at) return "active";
  return "preparation";
}

function stateLabel(state: "preparation" | "active" | "ready_collecte" | "ready_post_recolte") {
  if (state === "ready_post_recolte") return "Collecté · Prêt Post-récolte";
  if (state === "ready_collecte") return "Prêt pour Collecte";
  if (state === "active") return "Actif";
  return "Préparation";
}

function stateTone(state: "preparation" | "active" | "ready_collecte" | "ready_post_recolte"): "warning" | "info" | "success" {
  if (state === "ready_post_recolte") return "success";
  if (state === "ready_collecte") return "info";
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

function normalizeStepName(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function formatDurationDaysFromMinutes(minutes?: number | null): string {
  if (minutes === null || minutes === undefined) return "";
  const days = minutes / MINUTES_PER_DAY;
  if (!Number.isFinite(days) || days < 0) return "";
  return Number.isInteger(days) ? String(days) : String(Number(days.toFixed(2)));
}

function parseDurationDaysToMinutes(raw: string): number | null {
  if (!raw.trim()) return null;
  const parsed = Number(raw.replace(",", "."));
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  // Backend persists `duration_minutes`; UI captures days and maps to minutes.
  return Math.round(parsed * MINUTES_PER_DAY);
}

export default function ParcellesCulturePage() {
  const [search, setSearch] = useState("");
  const [productFilterId, setProductFilterId] = useState("all");
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [lotModalOpen, setLotModalOpen] = useState(false);
  const [workflowModalOpen, setWorkflowModalOpen] = useState(false);
  const [completePreHarvestModalOpen, setCompletePreHarvestModalOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [workflowStepsDraft, setWorkflowStepsDraft] = useState<WorkflowDraftStep[]>([]);
  const [workflowStepToAdd, setWorkflowStepToAdd] = useState("");
  const [workflowCustomStep, setWorkflowCustomStep] = useState("");
  const [executionDetailsDraft, setExecutionDetailsDraft] = useState<Record<number, { execution_date: string; duration_days: string; summary: string }>>({});
  const [editingExecutionStepIndex, setEditingExecutionStepIndex] = useState<number | null>(null);
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
  const [pendingApproveCharge, setPendingApproveCharge] = useState(false);
  const [approveChargeDraft, setApproveChargeDraft] = useState("");
  const [pendingStopLot, setPendingStopLot] = useState(false);
  const [pendingDeleteLot, setPendingDeleteLot] = useState(false);
  const [listPage, setListPage] = useState(1);
  const [listPageSize, setListPageSize] = useState(10);
  const tableControls = useTableControls(
    [
      {
        key: "state",
        label: "État",
        options: [
          { value: "all", label: "Tous états" },
          { value: "preparation", label: "Préparation" },
          { value: "active", label: "Actif" },
          { value: "ready_collecte", label: "Prêt collecte" },
          { value: "ready_post_recolte", label: "Prêt post-récolte" },
        ],
        initialValue: "all",
      },
    ],
    "desc",
  );

  const farmersQuery = useFarmers();
  const productsQuery = useProducts();
  const batchesQuery = useBatches();
  const products = productsQuery.data ?? [];
  const batches = batchesQuery.data ?? [];

  const createBatch = useCreateBatch();
  const updateBatch = useUpdateBatch();
  const approveBatchCharge = useApproveBatchCharge();
  const activatePreHarvest = useActivatePreHarvest();
  const stopPreHarvest = useStopPreHarvest();
  const deleteBatch = useDeleteBatch();
  const updatePreHarvestStepStatuses = useUpdatePreHarvestStepStatuses();
  const completePreHarvest = useCompletePreHarvest();
  const createParcel = useCreateParcel();

  const farmers = useMemo(() => farmersQuery.data ?? [], [farmersQuery.data]);
  const farmersById = useMemo(() => new Map(farmers.map((item) => [item.id, item])), [farmers]);
  const productsById = useMemo(() => new Map(products.map((item) => [item.id, item])), [products]);

  const preHarvestLots = useMemo(() => {
    const rows = [...batches].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    const needle = search.trim().toLowerCase();
    if (!needle) return rows;

    return rows.filter((item) => {
      const farmerName = item.member_id ? farmersById.get(item.member_id)?.full_name ?? "" : "";
      const productName = productsById.get(item.product_id)?.name ?? "";
      const text = `${item.code} ${farmerName} ${productName}`.toLowerCase();
      return text.includes(needle);
    });
  }, [batches, farmersById, productsById, search]);

  const visiblePreHarvestLots = useMemo(() => {
    const stateValue = tableControls.filters.state;
    const filtered = preHarvestLots.filter((item) => {
      const stateMatches = stateValue === "all" || getPreHarvestState(item) === stateValue;
      const productMatches = productFilterId === "all" || item.product_id === productFilterId;
      return stateMatches && productMatches;
    });
    const sorted = filtered.slice().sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    return tableControls.sortOrder === "asc" ? sorted : sorted.reverse();
  }, [preHarvestLots, productFilterId, tableControls.filters.state, tableControls.sortOrder]);
  const pagedPreHarvestLots = useMemo(() => {
    const start = (listPage - 1) * listPageSize;
    return visiblePreHarvestLots.slice(start, start + listPageSize);
  }, [visiblePreHarvestLots, listPage, listPageSize]);
  const totalPages = Math.max(Math.ceil(visiblePreHarvestLots.length / listPageSize), 1);
  useEffect(() => {
    setListPage(1);
  }, [search, productFilterId, tableControls.filters.state, tableControls.sortOrder, listPageSize]);

  const preHarvestProductFilterOptions = useMemo(() => {
    const ids = Array.from(new Set(preHarvestLots.map((lot) => lot.product_id)));
    return ids
      .map((id) => ({ id, name: productsById.get(id)?.name ?? id }))
      .sort((a, b) => a.name.localeCompare(b.name, "fr"));
  }, [preHarvestLots, productsById]);

  const selectedBatch = useMemo(() => {
    if (!selectedBatchId) return visiblePreHarvestLots[0] ?? null;
    return visiblePreHarvestLots.find((item) => item.id === selectedBatchId) ?? visiblePreHarvestLots[0] ?? null;
  }, [selectedBatchId, visiblePreHarvestLots]);

  useEffect(() => {
    if (!selectedBatch && visiblePreHarvestLots.length > 0) {
      setSelectedBatchId(visiblePreHarvestLots[0].id);
      return;
    }
    if (selectedBatchId && !visiblePreHarvestLots.find((item) => item.id === selectedBatchId)) {
      setSelectedBatchId(visiblePreHarvestLots[0]?.id ?? null);
    }
  }, [selectedBatch, selectedBatchId, visiblePreHarvestLots]);

  const preHarvestExportColumns: ExportColumn<Batch>[] = [
    { key: "code", header: "Lot" },
    { key: "farmer", header: "Agriculteur", format: (_, row) => (row.member_id ? farmersById.get(row.member_id)?.full_name ?? "-" : "-") },
    { key: "product", header: "Produit", format: (_, row) => productsById.get(row.product_id)?.name ?? "-" },
    { key: "surface_ha", header: "Surface (ha)", format: (_, row) => (row.surface_ha ?? 0).toLocaleString("fr-FR") },
    { key: "estimated_qty_kg", header: "Quantité estimée (kg)", format: (_, row) => (row.estimated_qty_kg ?? 0).toLocaleString("fr-FR") },
    { key: "estimated_charge_fcfa", header: "Charge estimée (FCFA)", format: (_, row) => (row.estimated_charge_fcfa ?? 0).toLocaleString("fr-FR") },
    { key: "state", header: "État", format: (_, row) => stateLabel(getPreHarvestState(row)) },
  ];

  const selectedLotState = useMemo(
    () => (selectedBatch ? getPreHarvestState(selectedBatch) : null),
    [selectedBatch],
  );
  const requiredLoading = farmersQuery.isLoading || productsQuery.isLoading || batchesQuery.isLoading;
  const requiredError = farmersQuery.isError || productsQuery.isError || batchesQuery.isError;

  const activeExecutionSteps = useMemo<PreHarvestExecutionStep[]>(() => {
    if (!selectedBatch) return [];
    const persisted = selectedBatch.preharvest_step_statuses ?? [];
    if (persisted.length > 0) {
      return persisted.map((step) => ({
        index: step.index,
        name: step.name,
        status: step.status,
        updated_at: step.updated_at ?? null,
        execution_date: step.execution_date ?? null,
        duration_minutes: step.duration_minutes ?? null,
        summary: step.summary ?? null,
      }));
    }
    return (selectedBatch.ordered_process_steps ?? []).map((label, index) => ({
      index,
      name: label,
      status: "todo" as PreHarvestExecutionStatus,
      updated_at: null,
      execution_date: null,
      duration_minutes: null,
      summary: null,
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

  useEffect(() => {
    const draft: Record<number, { execution_date: string; duration_days: string; summary: string }> = {};
    for (const step of activeExecutionSteps) {
      draft[step.index] = {
        execution_date: step.execution_date ?? "",
        duration_days: formatDurationDaysFromMinutes(step.duration_minutes),
        summary: step.summary ?? "",
      };
    }
    setExecutionDetailsDraft(draft);
  }, [selectedBatch?.id, activeExecutionSteps]);

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

  const lotForm = useForm<LotForm>({
    defaultValues: {
      member_id: "",
      product_id: "",
      surface_ha: 1,
      expected_yield_kg_per_ha: 0,
      expected_losses_kg: 0,
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
  const lotEstimatedChargeFcfa = useMemo(() => Math.round(Math.max(lotEstimatedQty, 0)), [lotEstimatedQty]);

  const preHarvestTemplateSteps = useMemo(() => {
    if (!selectedBatch) return [];
    const productName = productsById.get(selectedBatch.product_id)?.name ?? null;
    return getProductStepTemplate(productName, "pre_harvest");
  }, [productsById, selectedBatch]);


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
        estimated_charge_fcfa: lotEstimatedChargeFcfa,
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
      });
    } catch (error) {
      setFormError(getFrenchErrorMessage(error, "Impossible de créer le lot."));
    } finally {
      setIsCreatingLot(false);
    }
  });

  const handleApproveLotCharge = async () => {
    if (!selectedBatch) return;
    const parsedCharge = Number(approveChargeDraft.replace(",", "."));
    if (!Number.isFinite(parsedCharge) || parsedCharge <= 0) {
      setFormError("Le montant de charge doit être supérieur à 0.");
      return;
    }
    try {
      setPendingAction("approve_charge");
      if ((selectedBatch.estimated_charge_fcfa ?? 0) !== parsedCharge) {
        await updateBatch.mutateAsync({
          id: selectedBatch.id,
          payload: { estimated_charge_fcfa: parsedCharge },
        });
      }
      await approveBatchCharge.mutateAsync(selectedBatch.id);
      setPendingApproveCharge(false);
      setFormError(null);
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
    try {
      setPendingAction("stop");
      await stopPreHarvest.mutateAsync(selectedBatch.id);
    } catch (error) {
      setFormError(getFrenchErrorMessage(error, "Impossible de stopper le lot."));
    } finally {
      setPendingAction(null);
    }
  };

  const handleDeleteLot = async () => {
    if (!selectedBatch) return;
    try {
      await deleteBatch.mutateAsync(selectedBatch.id);
      setPendingDeleteLot(false);
      setSelectedBatchId(null);
      setFormError(null);
    } catch (error) {
      setFormError(getFrenchErrorMessage(error, "Impossible de supprimer le lot."));
    }
  };

  const handleTryEditWorkflow = () => {
    if (!selectedBatch || !selectedLotState) return;
    if (selectedBatch.preharvest_completed_at) {
      window.alert("La Pré-récolte est terminée. Le workflow ne peut plus être modifié.");
      return;
    }
    const source = selectedBatch.ordered_process_steps ?? [];
    const parsed = source.map((item, index) => parseWorkflowStep(item, index));
    setWorkflowStepsDraft(parsed);
    setWorkflowStepToAdd("");
    setWorkflowCustomStep("");
    setWorkflowError(null);
    setWorkflowModalOpen(true);
  };

  const handleAddWorkflowStep = () => {
    const action = workflowStepToAdd.trim();
    if (!action) return;
    const exists = workflowStepsDraft.some((step) => step.name.trim().toLowerCase() === action.toLowerCase());
    if (exists) {
      setWorkflowError("Cette action est déjà dans le workflow.");
      return;
    }
    setWorkflowStepsDraft((current) => [
      ...current,
      { id: `new-${Date.now()}-${current.length}`, name: action, details: "" },
    ]);
    setWorkflowStepToAdd("");
    setWorkflowError(null);
  };

  const handleAddCustomWorkflowStep = () => {
    const action = workflowCustomStep.trim();
    if (!action) return;
    const exists = workflowStepsDraft.some((step) => step.name.trim().toLowerCase() === action.toLowerCase());
    if (exists) {
      setWorkflowError("Cette action est déjà dans le workflow.");
      return;
    }
    setWorkflowStepsDraft((current) => [
      ...current,
      { id: `custom-${Date.now()}-${current.length}`, name: action, details: "" },
    ]);
    setWorkflowCustomStep("");
    setWorkflowError(null);
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
    if (selectedBatch.preharvest_completed_at) {
      window.alert("La Pré-récolte est terminée. Le workflow ne peut plus être modifié.");
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
      if (selectedLotState === "active") {
        const existing = selectedBatch.preharvest_step_statuses ?? [];
        const grouped = new Map<string, PreHarvestExecutionStep[]>();
        for (const step of existing) {
          const key = normalizeStepName(step.name);
          const current = grouped.get(key) ?? [];
          current.push(step);
          grouped.set(key, current);
        }
        const rebuilt = normalized.map((name, index) => {
          const key = normalizeStepName(name);
          const bucket = grouped.get(key) ?? [];
          const preserved = bucket.shift();
          grouped.set(key, bucket);
          if (preserved) {
            return {
              ...preserved,
              index,
              name,
            };
          }
          return {
            index,
            name,
            status: "todo" as const,
            updated_at: null,
            execution_date: null,
            duration_minutes: null,
            summary: null,
          };
        });
        await updatePreHarvestStepStatuses.mutateAsync({
          id: selectedBatch.id,
          payload: { statuses: rebuilt },
        });
      }
      setWorkflowModalOpen(false);
      setWorkflowError(null);
    } catch (error) {
      setWorkflowError(getFrenchErrorMessage(error, "Impossible d'enregistrer le workflow."));
    } finally {
      setPendingAction(null);
    }
  };

  const updateExecutionStep = async (
    stepIndex: number,
    updates: Partial<Pick<PreHarvestExecutionStep, "status" | "execution_date" | "duration_minutes" | "summary">>,
  ) => {
    if (!selectedBatch) return;
    const isReadyPostRecolte = Boolean(
      selectedBatch.preharvest_completed_at && (selectedBatch.collecte_created || selectedBatch.stock_in_created || selectedBatch.confirmed_weight_kg),
    );
    if (selectedLotState !== "active" || isReadyPostRecolte) {
      window.alert("Pré-récolte déjà confirmée. Les étapes d’exécution sont verrouillées.");
      return;
    }
    const nextStatuses = activeExecutionSteps.map((step) => {
      if (step.index !== stepIndex) return step;
      return {
        ...step,
        ...updates,
        status: updates.status ?? step.status,
        updated_at: new Date().toISOString(),
      };
    });
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

  const handleOpenCompletePreHarvestModal = () => {
    if (!selectedBatch) return;
    if ((selectedLotState === "active" || selectedLotState === "preparation") && !allExecutionStepsDone) {
      window.alert("Toutes les étapes Pré-récolte doivent être terminées avant de terminer la pré-récolte.");
      return;
    }
    setCompletePreHarvestModalOpen(true);
  };

  const saveExecutionDetails = async (stepIndex: number) => {
    const draft = executionDetailsDraft[stepIndex] ?? { execution_date: "", duration_days: "", summary: "" };
    await updateExecutionStep(stepIndex, {
      execution_date: draft.execution_date || null,
      duration_minutes: parseDurationDaysToMinutes(draft.duration_days),
      summary: draft.summary || null,
    });
  };

  const completeExecutionStepWithDetails = async (stepIndex: number) => {
    const draft = executionDetailsDraft[stepIndex] ?? { execution_date: "", duration_days: "", summary: "" };
    await updateExecutionStep(stepIndex, {
      status: "done",
      execution_date: draft.execution_date || null,
      duration_minutes: parseDurationDaysToMinutes(draft.duration_days),
      summary: draft.summary || null,
    });
    setEditingExecutionStepIndex(null);
  };

  const handleCompleteLotPreHarvest = async () => {
    if (!selectedBatch) return;
    try {
      setPendingAction("complete_preharvest");
      await completePreHarvest.mutateAsync({ id: selectedBatch.id });
      setCompletePreHarvestModalOpen(false);
    } catch (error) {
      setFormError(getFrenchErrorMessage(error, "Impossible de compléter la pré-récolte."));
    } finally {
      setPendingAction(null);
    }
  };

  if (requiredLoading) {
    return (
      <main className="relative min-h-[60vh]">
        <PageIntro title="Parcelles & Culture" />
        <ContentAreaLoader
          title="Chargement Parcelles & Culture"
          subtitle="Synchronisation des lots, membres et produits..."
        />
      </main>
    );
  }

  if (requiredError) {
    return (
      <main>
        <PageIntro title="Parcelles & Culture" />
        <section className="premium-card reveal mt-4 rounded-2xl p-4">
          <p className="text-sm text-[var(--danger)]">Impossible de charger les données requises de la page Parcelles & Culture.</p>
        </section>
      </main>
    );
  }

  return (
    <main>
      <PageIntro title="Parcelles & Culture" />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <StatusBadge label="⚠️ 1 stock(s) bas" tone="warning" />
            <StatusBadge label="🔔 1 commande(s) à traiter" tone="info" />
          </div>
          <div className="w-full">
            <TableToolbar
              search={search}
              onSearchChange={setSearch}
              searchPlaceholder="Rechercher lot, agriculteur, produit..."
              filters={tableControls.filterDefinitions}
              onFilterChange={tableControls.setFilterValue}
              sortOrder={tableControls.sortOrder}
              onSortOrderChange={tableControls.setSortOrder}
              sortAscLabel="Date asc"
              sortDescLabel="Date desc"
              rightActions={
                <ExportActions
                  onCsv={() => exportRowsToCsv({ filename: "lots-pre-recolte", title: "Lots Pré-récolte", columns: preHarvestExportColumns, rows: visiblePreHarvestLots })}
                  onExcel={() => exportRowsToExcel({ filename: "lots-pre-recolte", title: "Lots Pré-récolte", columns: preHarvestExportColumns, rows: visiblePreHarvestLots })}
                  onPdf={() => exportRowsToPdf({ filename: "lots-pre-recolte", title: "Lots Pré-récolte", columns: preHarvestExportColumns, rows: visiblePreHarvestLots })}
                />
              }
            />
          </div>
          <div className="flex items-center gap-2">
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
            className="premium-card reveal max-h-[calc(100dvh-190px)] overflow-y-auto no-scrollbar rounded-2xl p-4"
            style={{ ["--delay" as string]: "40ms" }}
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-base font-semibold text-[var(--text)]">Lots Pré-récolte</h3>
              <span className="text-xs text-[var(--muted)]">{visiblePreHarvestLots.length} lot(s)</span>
            </div>
            <label className="mb-3 block text-xs font-medium text-[var(--text)]">
              Filtrer par produit
              <select
                value={productFilterId}
                onChange={(event) => setProductFilterId(event.target.value)}
                className="wf-input mt-1 h-9 w-full px-2.5 text-xs"
              >
                <option value="all">Tous les produits</option>
                {preHarvestProductFilterOptions.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                  </option>
                ))}
              </select>
            </label>
            {visiblePreHarvestLots.length === 0 ? (
              <p className="text-xs text-[var(--muted)]">Aucun lot Pré-récolte disponible.</p>
            ) : (
              <div className="space-y-2">
                {pagedPreHarvestLots.map((lot) => {
                  const isActive = lot.id === selectedBatch?.id;
                  const farmerName = lot.member_id ? farmersById.get(lot.member_id)?.full_name ?? "-" : "-";
                  const productName = productsById.get(lot.product_id)?.name ?? "-";
                  const state = getPreHarvestState(lot);
                  const executedStepsCount = (lot.preharvest_step_statuses ?? []).filter((step) => step.status === "done").length;
                  const totalStepsCount = lot.ordered_process_steps?.length ?? 0;
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
                          <p className="mt-0.5 text-[11px] text-[var(--muted)]">
                            Créé le: {new Date(lot.created_at).toLocaleString("fr-FR")}
                          </p>
                        </button>
                        <StatusBadge label={stateLabel(state)} tone={stateTone(state)} />
                      </div>
                      <button type="button" onClick={() => setSelectedBatchId(lot.id)} className="w-full text-left">
                        <div className="mt-3 grid gap-1">
                          <p className="text-xs text-[var(--muted)]">Agriculteur: {farmerName}</p>
                          <p className="text-xs text-[var(--muted)]">Produit: {productName}</p>
                          <p className="text-xs text-[var(--muted)]">Étapes exécutées: {executedStepsCount}/{totalStepsCount}</p>
                          <p className="text-xs text-[var(--muted)]">Surface: {(lot.surface_ha ?? 0).toLocaleString("fr-FR")} ha</p>
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
                  <p>
                    Collecte liée: {selectedBatch.collecte_created ? "Créée" : selectedBatch.preharvest_completed_at ? "En attente" : "Non disponible"}
                  </p>
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
                      onClick={() => setPendingStopLot(true)}
                      disabled={executionStarted || pendingAction !== null}
                      className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                      title={executionStarted ? "Impossible de stopper un lot dont l’exécution a commencé." : undefined}
                    >
                      {pendingAction === "stop" ? "Arrêt en cours..." : "Stopper le lot"}
                    </button>
                  ) : null}
                  {!selectedBatch.preharvest_completed_at ? (
                    <button
                      type="button"
                      onClick={handleTryEditWorkflow}
                      disabled={pendingAction !== null}
                      className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Modifier workflow
                    </button>
                  ) : null}
                  {selectedLotState === "preparation" ? (
                    <button
                      type="button"
                      onClick={() => setPendingDeleteLot(true)}
                      disabled={pendingAction !== null || deleteBatch.isPending}
                      className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold text-[var(--danger)] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Supprimer lot
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => {
                      setApproveChargeDraft(String(selectedBatch.estimated_charge_fcfa ?? 0));
                      setPendingApproveCharge(true);
                      setFormError(null);
                    }}
                    disabled={Boolean(selectedBatch.charge_approved_at) || pendingAction !== null}
                    className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {selectedBatch.charge_approved_at
                      ? "Charge approuvée"
                      : pendingAction === "approve_charge"
                        ? "Approbation en cours..."
                        : "Approuver charge"}
                  </button>
                  {selectedLotState === "active" ? (
                    <button
                      type="button"
                      onClick={handleOpenCompletePreHarvestModal}
                      disabled={!allExecutionStepsDone || pendingAction !== null}
                      className="soft-focus wf-btn-primary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {pendingAction === "complete_preharvest" ? "Clôture en cours..." : "Terminer Pré-récolte"}
                    </button>
                  ) : null}
                </div>
                {selectedLotState === "active" && !allExecutionStepsDone ? (
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    Terminez toutes les étapes d&apos;exécution avant de terminer la pré-récolte.
                  </p>
                ) : null}
                {selectedLotState === "active" && executionStarted ? (
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    Impossible de stopper un lot dont l’exécution a commencé.
                  </p>
                ) : null}
                {selectedLotState !== "ready_post_recolte" ? (
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    Le stock réel sera créé uniquement après la Collecte liée à ce lot.
                  </p>
                ) : null}
                {selectedBatch.preharvest_completed_at ? (
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    La Pré-récolte est terminée. Le workflow ne peut plus être modifié.
                  </p>
                ) : null}
              </article>

              {!selectedBatch.preharvest_completed_at ? (
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
                                label="Éditable"
                                tone="info"
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
                          const draft = executionDetailsDraft[step.index] ?? {
                            execution_date: "",
                            duration_days: "",
                            summary: "",
                          };
                          const statusLabel = step.status === "done" ? "Terminé" : "En cours";
                          const tone = step.status === "done" ? "success" : "info";
                          const isDone = step.status === "done";
                          const isEditing = editingExecutionStepIndex === step.index || !isDone;
                          return (
                            <article
                              key={`${step.index}-${step.name}`}
                              className={`rounded-xl border p-3 ${
                                isDone ? "border-[#9FD6B2] bg-[#F1FBF4]" : "border-[var(--line)] bg-white"
                              }`}
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="text-sm font-semibold text-[var(--text)]">
                                  {step.index + 1}. {step.name}
                                </p>
                                <div className="flex items-center gap-1.5">
                                  <StatusBadge label="Structure verrouillée" tone="warning" />
                                  <StatusBadge label={statusLabel} tone={tone} />
                                </div>
                              </div>
                              {isDone && !isEditing ? (
                                <div className="mt-3 space-y-2 rounded-xl border border-[#CFE7D8] bg-white px-3 py-2 text-xs text-[var(--muted)]">
                                  <p>
                                    <span className="font-semibold text-[var(--text)]">Date:</span>{" "}
                                    {step.execution_date || "Non renseignée"}
                                  </p>
                                  <p>
                                    <span className="font-semibold text-[var(--text)]">Durée (jours):</span>{" "}
                                    {step.duration_minutes != null ? formatDurationDaysFromMinutes(step.duration_minutes) : "Non renseignée"}
                                  </p>
                                  <p>
                                    <span className="font-semibold text-[var(--text)]">Résumé:</span>{" "}
                                    {step.summary?.trim() ? step.summary : "Aucun résumé"}
                                  </p>
                                  <div className="flex justify-end">
                                    <button
                                      type="button"
                                      onClick={() => setEditingExecutionStepIndex(step.index)}
                                      disabled={pendingAction !== null}
                                      className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                      Modifier
                                    </button>
                                  </div>
                                </div>
                              ) : (
                                <>
                                  <div className="mt-3 grid gap-2 sm:grid-cols-3">
                                <label className="block text-xs font-medium text-[var(--text)]">
                                  Date d&apos;exécution
                                  <input
                                    type="date"
                                    value={draft.execution_date}
                                    onChange={(event) =>
                                      setExecutionDetailsDraft((current) => ({
                                        ...current,
                                        [step.index]: {
                                          ...(current[step.index] ?? { execution_date: "", duration_days: "", summary: "" }),
                                          execution_date: event.target.value,
                                        },
                                      }))
                                    }
                                    className="wf-input mt-1 h-10 w-full px-2.5 text-xs"
                                    disabled={pendingAction !== null}
                                  />
                                </label>
                                <label className="block text-xs font-medium text-[var(--text)]">
                                  Durée (jours)
                                  <input
                                    type="number"
                                    min="0"
                                    step="0.1"
                                    value={draft.duration_days}
                                    onChange={(event) =>
                                      setExecutionDetailsDraft((current) => ({
                                        ...current,
                                        [step.index]: {
                                          ...(current[step.index] ?? { execution_date: "", duration_days: "", summary: "" }),
                                          duration_days: event.target.value,
                                        },
                                      }))
                                    }
                                    className="wf-input mt-1 h-10 w-full px-2.5 text-xs"
                                    disabled={pendingAction !== null}
                                  />
                                </label>
                                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2 text-[11px] text-[var(--muted)]">
                                  Suivi terrain uniquement
                                  <br />
                                  Aucun impact stock
                                  </div>
                                  </div>
                                  <label className="mt-2 block text-xs font-medium text-[var(--text)]">
                                    Résumé / notes
                                    <textarea
                                      value={draft.summary}
                                      onChange={(event) =>
                                        setExecutionDetailsDraft((current) => ({
                                          ...current,
                                          [step.index]: {
                                            ...(current[step.index] ?? { execution_date: "", duration_days: "", summary: "" }),
                                            summary: event.target.value,
                                          },
                                        }))
                                      }
                                      className="wf-input mt-1 min-h-[68px] w-full px-2.5 py-2 text-xs"
                                      placeholder="Saisir un résumé de l&apos;intervention terrain..."
                                      disabled={pendingAction !== null}
                                    />
                                  </label>
                                  <div className="mt-2 flex justify-end gap-2">
                                    {isDone ? (
                                      <button
                                        type="button"
                                        onClick={() => setEditingExecutionStepIndex(null)}
                                        disabled={pendingAction !== null}
                                        className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                                      >
                                        Annuler
                                      </button>
                                    ) : null}
                                    <button
                                      type="button"
                                      onClick={() =>
                                        isDone ? saveExecutionDetails(step.index) : completeExecutionStepWithDetails(step.index)
                                      }
                                      disabled={pendingAction !== null}
                                      className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                      {pendingAction === "update_step_status"
                                        ? "Enregistrement..."
                                        : isDone
                                          ? "Enregistrer modifications"
                                          : "Enregistrer suivi"}
                                    </button>
                                  </div>
                                </>
                              )}
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
                    <StatusBadge label="Collecté · Prêt Post-récolte" tone="success" />
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    Workflow verrouillé et finalisé. Ce lot peut continuer en Post-récolte.
                  </p>
                  <div className="mt-2 grid gap-2 text-xs text-[var(--muted)] sm:grid-cols-2">
                    <p>Étapes terminées: {activeExecutionCompletedCount}/{activeExecutionSteps.length || 0}</p>
                    <p>Poids confirmé: {(selectedBatch.confirmed_weight_kg ?? 0).toLocaleString("fr-FR")} kg</p>
                  </div>
                  <div className="mt-3 rounded-xl border border-[var(--line)] bg-white p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                        Détail des étapes exécutées
                      </p>
                      <StatusBadge
                        label={`${activeExecutionCompletedCount}/${activeExecutionSteps.length || 0} terminées`}
                        tone="success"
                      />
                    </div>
                    {activeExecutionSteps.length === 0 ? (
                      <p className="text-xs text-[var(--muted)]">Aucune étape d&apos;exécution enregistrée.</p>
                    ) : (
                      <div className="space-y-2">
                        {activeExecutionSteps.map((step) => (
                          <article key={`ready-post-${step.index}`} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-2.5">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                <div className="flex h-7 w-7 items-center justify-center rounded-full border border-[var(--line)] bg-white text-sm">
                                  {getWorkflowStepEmoji(step.name, step.index)}
                                </div>
                                <p className="text-sm font-semibold text-[var(--text)]">
                                  {step.index + 1}. {step.name}
                                </p>
                              </div>
                              <StatusBadge label={step.status === "done" ? "Terminé" : "En cours"} tone={step.status === "done" ? "success" : "info"} />
                            </div>
                            <div className="mt-2 grid gap-1 text-xs text-[var(--muted)] sm:grid-cols-2">
                              <p>Date: {step.execution_date || "Non renseignée"}</p>
                              <p>Durée (jours): {step.duration_minutes != null ? formatDurationDaysFromMinutes(step.duration_minutes) : "Non renseignée"}</p>
                            </div>
                            <p className="mt-1 text-xs text-[var(--muted)]">Résumé: {step.summary?.trim() ? step.summary : "Aucun résumé"}</p>
                          </article>
                        ))}
                      </div>
                    )}
              </div>
              {visiblePreHarvestLots.length > 0 ? (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-[var(--muted)]">
                    {Math.min((listPage - 1) * listPageSize + 1, visiblePreHarvestLots.length)}–{Math.min(listPage * listPageSize, visiblePreHarvestLots.length)} sur {visiblePreHarvestLots.length}
                  </p>
                  <div className="flex items-center gap-2">
                    <select value={listPageSize} onChange={(event) => setListPageSize(Number(event.target.value))} className="wf-input h-8 w-[88px] px-2 text-xs">
                      <option value={10}>10</option><option value={20}>20</option><option value={50}>50</option>
                    </select>
                    <button type="button" className="soft-focus rounded-lg border border-[var(--line)] px-2 py-1 text-xs font-semibold disabled:opacity-50" disabled={listPage <= 1} onClick={() => setListPage((prev) => Math.max(1, prev - 1))}>Précédent</button>
                    <span className="text-xs text-[var(--muted)]">{listPage}/{totalPages}</span>
                    <button type="button" className="soft-focus rounded-lg border border-[var(--line)] px-2 py-1 text-xs font-semibold disabled:opacity-50" disabled={listPage >= totalPages} onClick={() => setListPage((prev) => Math.min(totalPages, prev + 1))}>Suivant</button>
                  </div>
                </div>
              ) : null}
            </article>
              ) : null}

              {selectedLotState === "ready_collecte" ? (
                <article className="mb-4 rounded-2xl border border-[var(--line)] bg-[#EEF5FF] p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-[var(--text)]">Pré-récolte terminée</p>
                    <StatusBadge label="Prêt pour Collecte" tone="info" />
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    Le lot est prêt pour la Collecte liée. Le stock réel sera créé après enregistrement de cette collecte dans le module Collecte.
                  </p>
                  <div className="mt-3 rounded-xl border border-[var(--line)] bg-white p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                        Résumé des étapes exécutées
                      </p>
                      <StatusBadge
                        label={`${activeExecutionCompletedCount}/${activeExecutionSteps.length || 0} terminées`}
                        tone="success"
                      />
                    </div>
                    {activeExecutionSteps.length === 0 ? (
                      <p className="text-xs text-[var(--muted)]">Aucune étape d&apos;exécution enregistrée.</p>
                    ) : (
                      <div className="space-y-2">
                        {activeExecutionSteps.map((step) => (
                          <article key={`ready-collecte-${step.index}`} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-2.5">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                <div className="flex h-7 w-7 items-center justify-center rounded-full border border-[var(--line)] bg-white text-sm">
                                  {getWorkflowStepEmoji(step.name, step.index)}
                                </div>
                                <p className="text-sm font-semibold text-[var(--text)]">
                                  {step.index + 1}. {step.name}
                                </p>
                              </div>
                              <StatusBadge label={step.status === "done" ? "Terminé" : "Incomplet"} tone={step.status === "done" ? "success" : "warning"} />
                            </div>
                            <div className="mt-2 grid gap-1 text-xs text-[var(--muted)] sm:grid-cols-3">
                              <p>📅 Date: {step.execution_date || "Non renseignée"}</p>
                              <p>⏱️ Durée (jours): {step.duration_minutes != null ? formatDurationDaysFromMinutes(step.duration_minutes) : "Non renseignée"}</p>
                              <p>📝 Résumé: {step.summary?.trim() ? step.summary : "Aucun résumé"}</p>
                            </div>
                          </article>
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              ) : null}

            </>
          )}

          {formError ? <p className="mt-3 text-xs text-[#A53A3A]">{formError}</p> : null}
        </section>
      </section>

      <LiquidGlassModal
        open={completePreHarvestModalOpen}
        onClose={() => setCompletePreHarvestModalOpen(false)}
        title="Terminer Pré-récolte"
        subtitle="Le lot passera en statut prêt pour Collecte."
        size="md"
      >
        <div className="space-y-3">
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 text-xs text-[var(--muted)]">
            <p>Lot: {selectedBatch?.code ?? "-"}</p>
            <p>Produit: {selectedBatch ? productsById.get(selectedBatch.product_id)?.name ?? "-" : "-"}</p>
            <p>Quantité estimée: {selectedBatch ? (selectedBatch.estimated_qty_kg ?? 0).toLocaleString("fr-FR") : 0} kg</p>
          </div>
          <p className="text-xs text-[var(--muted)]">
            Le lot sera prêt pour la Collecte. Le stock réel sera créé uniquement après la Collecte liée à ce lot.
          </p>
          {formError ? <p className="text-xs text-[#A53A3A]">{formError}</p> : null}
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setCompletePreHarvestModalOpen(false)}
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
              {pendingAction === "complete_preharvest" ? "Clôture en cours..." : "Terminer Pré-récolte"}
            </button>
          </div>
        </div>
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
          <div className="rounded-xl border border-[#BDD6FB] bg-[#EEF5FF] px-3 py-2 text-xs text-[#2F80ED]">
            Quantité estimée = surface × rendement - pertes = {lotEstimatedQty.toLocaleString("fr-FR")} kg.
            <br />
            Charge estimée automatique = {lotEstimatedChargeFcfa.toLocaleString("fr-FR")} FCFA.
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
        subtitle="Sélection des actions terrain prévues avant clôture Pré-récolte."
        size="lg"
      >
        <div className="space-y-4">
          <div className="rounded-xl border border-[#BDD6FB] bg-[#EEF5FF] px-3 py-2 text-xs text-[#2F80ED]">
            Sélectionnez les actions terrain prévues pour ce lot. Pendant l&apos;activité, vous pouvez encore ajouter, retirer et réordonner les étapes.
          </div>
          <div className="space-y-2 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
            <p className="text-sm font-semibold text-[var(--text)]">Actions Pré-récolte disponibles</p>
            <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
              <select
                value={workflowStepToAdd}
                onChange={(event) => setWorkflowStepToAdd(event.target.value)}
                className="wf-input h-10 w-full px-3 text-sm"
                disabled={pendingAction !== null}
              >
                <option value="">Choisir une action standard</option>
                {preHarvestTemplateSteps.map((step) => {
                  const exists = workflowStepsDraft.some(
                    (draftStep) => normalizeStepName(draftStep.name) === normalizeStepName(step),
                  );
                  return (
                    <option key={step} value={step}>
                      {exists ? `${step} (déjà ajoutée)` : step}
                    </option>
                  );
                })}
              </select>
              <button
                type="button"
                onClick={handleAddWorkflowStep}
                className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!workflowStepToAdd || pendingAction !== null}
              >
                Ajouter
              </button>
            </div>
            <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
              <input
                value={workflowCustomStep}
                onChange={(event) => setWorkflowCustomStep(event.target.value)}
                className="wf-input h-10 w-full px-3 text-sm"
                placeholder="Ajouter une action personnalisée"
                disabled={pendingAction !== null}
              />
              <button
                type="button"
                onClick={handleAddCustomWorkflowStep}
                className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!workflowCustomStep.trim() || pendingAction !== null}
              >
                Ajouter perso
              </button>
            </div>
          </div>
          {workflowStepsDraft.length === 0 ? (
            <div className="rounded-2xl border border-[var(--line)] bg-[var(--surface-soft)] px-4 py-4 text-sm text-[var(--muted)]">
              Aucune étape proposée. Ajoutez une étape avant activation.
            </div>
          ) : (
            <div className="space-y-2">
              {workflowStepsDraft.map((step, index) => (
                <article key={step.id} className="rounded-2xl border border-[var(--line)] bg-white p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-full border border-[var(--line)] bg-[#F8FBF6] text-xs">
                        {getWorkflowStepEmoji(step.name || step.details, index)}
                      </div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Étape {index + 1}</p>
                    </div>
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
                  <p className="text-sm font-semibold text-[var(--text)]">{step.name || "Action sans nom"}</p>
                  <label className="mt-2 block text-sm font-medium text-[var(--text)]">
                    Détails / action terrain (optionnel)
                    <input
                      value={step.details}
                      onChange={(event) => handleUpdateWorkflowStep(step.id, "details", event.target.value)}
                      className="wf-input mt-2 h-10 w-full px-3 text-sm"
                      placeholder="Ex: équipe A, parcelle nord, matériel prévu..."
                      disabled={pendingAction !== null}
                    />
                  </label>
                </article>
              ))}
            </div>
          )}
          {workflowError ? <p className="text-xs text-[#A53A3A]">{workflowError}</p> : null}
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--line)] pt-3">
            <span className="text-xs text-[var(--muted)]">Étapes du modèle produit + action personnalisée.</span>
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
      <LiquidGlassModal
        open={pendingApproveCharge}
        onClose={() => setPendingApproveCharge(false)}
        title="Approuver la charge estimée"
        subtitle="Vous pouvez ajuster la charge avant validation."
        size="sm"
      >
        <div className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            Montant charge (FCFA)
            <input
              type="number"
              min="0"
              step="1"
              value={approveChargeDraft}
              onChange={(event) => setApproveChargeDraft(event.target.value)}
              className="wf-input mt-2 h-10 w-full px-3 text-sm"
              disabled={pendingAction === "approve_charge"}
            />
          </label>
          <p className="text-xs text-[var(--muted)]">Cette validation crée Avance Producteur + Trésorerie OUT.</p>
          {formError ? <p className="text-xs text-[#A53A3A]">{formError}</p> : null}
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setPendingApproveCharge(false)}
              className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold"
              disabled={pendingAction === "approve_charge"}
            >
              Annuler
            </button>
            <button
              type="button"
              onClick={() => {
                void handleApproveLotCharge();
              }}
              className="soft-focus wf-btn-primary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              disabled={pendingAction === "approve_charge"}
            >
              {pendingAction === "approve_charge" ? "Approbation en cours..." : "Enregistrer et approuver"}
            </button>
          </div>
        </div>
      </LiquidGlassModal>
      <ConfirmActionModal
        open={pendingStopLot}
        title="Stopper le lot"
        message="Le lot repassera en préparation et pourra être modifié."
        confirmLabel="Stopper"
        loading={pendingAction === "stop"}
        onCancel={() => setPendingStopLot(false)}
        onConfirm={() => {
          void handleStopLot();
          setPendingStopLot(false);
        }}
      />
      <ConfirmActionModal
        open={pendingDeleteLot}
        title="Supprimer le lot"
        message="Cette action supprimera définitivement ce lot pré-récolte."
        confirmLabel="Supprimer"
        loading={deleteBatch.isPending}
        onCancel={() => setPendingDeleteLot(false)}
        onConfirm={() => {
          void handleDeleteLot();
        }}
      />
    </main>
  );
}
