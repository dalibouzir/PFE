"use client";

import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { AIInsightsStrip, type AIInsightItem } from "@/components/ui/AIInsightsStrip";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  useCompletePreHarvestStep,
  useCreateGlobalCharge,
  useCreateParcel,
  useFarmerCharges,
  useFarmers,
  useParcels,
  usePreHarvestSteps,
  useUpdatePreHarvestStep,
} from "@/hooks/useParcellesCulture";
import type { GlobalChargeCreate, ParcelCreate, PreHarvestStep, PreHarvestStepUpdate } from "@/lib/api/types";

type ParcelForm = {
  name: string;
  surface_ha: number;
  main_culture: string;
  variety: string;
  tree_count?: number;
};

type StepForm = {
  quantity_value?: number;
  quantity_unit: string;
  operation_cost_fcfa?: number;
  realization_date: string;
  observations: string;
};

type ChargeForm = {
  charge_type: string;
  label: string;
  amount_fcfa: number;
  date: string;
  parcel_id: string;
  notes: string;
};

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

function splitTokens(raw?: string | null) {
  if (!raw) return [];
  return raw
    .split(/[;,/|]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function ParcellesCulturePage() {
  const farmersQuery = useFarmers();
  const [search, setSearch] = useState("");
  const [selectedFarmerId, setSelectedFarmerId] = useState<string | null>(null);
  const [selectedParcelId, setSelectedParcelId] = useState<string | null>(null);
  const [parcelModalOpen, setParcelModalOpen] = useState(false);
  const [stepModalOpen, setStepModalOpen] = useState(false);
  const [chargeModalOpen, setChargeModalOpen] = useState(false);
  const [aiModalOpen, setAiModalOpen] = useState(false);
  const [activeStep, setActiveStep] = useState<PreHarvestStep | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const filteredFarmers = useMemo(() => {
    const farmers = farmersQuery.data ?? [];
    const needle = search.toLowerCase();
    return farmers.filter((item) => `${item.full_name} ${item.village ?? ""}`.toLowerCase().includes(needle));
  }, [farmersQuery.data, search]);

  useEffect(() => {
    if (!selectedFarmerId && filteredFarmers.length > 0) {
      setSelectedFarmerId(filteredFarmers[0].id);
    }
  }, [filteredFarmers, selectedFarmerId]);

  const selectedFarmer = useMemo(
    () => filteredFarmers.find((item) => item.id === selectedFarmerId) ?? null,
    [filteredFarmers, selectedFarmerId],
  );

  const parcelsQuery = useParcels(selectedFarmer?.id ?? null);
  useEffect(() => {
    const parcels = parcelsQuery.data ?? [];
    if (!selectedParcelId && parcels.length > 0) {
      setSelectedParcelId(parcels[0].id);
      return;
    }
    if (selectedParcelId && !parcels.find((item) => item.id === selectedParcelId)) {
      setSelectedParcelId(parcels[0]?.id ?? null);
    }
  }, [parcelsQuery.data, selectedParcelId]);

  const selectedParcel = useMemo(() => {
    const parcels = parcelsQuery.data ?? [];
    return parcels.find((item) => item.id === selectedParcelId) ?? null;
  }, [parcelsQuery.data, selectedParcelId]);
  const stepsQuery = usePreHarvestSteps(selectedParcel?.id ?? null);
  const steps = useMemo(() => stepsQuery.data ?? [], [stepsQuery.data]);
  const chargesQuery = useFarmerCharges(selectedFarmer?.id ?? null);
  const charges = chargesQuery.data;

  const createParcel = useCreateParcel();
  const updateStep = useUpdatePreHarvestStep();
  const completeStep = useCompletePreHarvestStep();
  const createCharge = useCreateGlobalCharge();

  const parcelForm = useForm<ParcelForm>({
    defaultValues: {
      name: "",
      surface_ha: 1,
      main_culture: "",
      variety: "",
      tree_count: undefined,
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

  const chargeForm = useForm<ChargeForm>({
    defaultValues: {
      charge_type: "Engrais",
      label: "",
      amount_fcfa: 0,
      date: new Date().toISOString().slice(0, 10),
      parcel_id: "",
      notes: "",
    },
  });

  const completedCount = steps.filter((item) => item.status === "completed").length;
  const progress = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0;

  const farmerProducts = useMemo(() => {
    if (!selectedFarmer) return [];
    const merged = [
      ...(selectedFarmer.products ?? []),
      ...splitTokens(selectedFarmer.main_product),
      ...splitTokens(selectedFarmer.secondary_products),
    ];
    return Array.from(new Set(merged));
  }, [selectedFarmer]);

  const openStepModal = (step: PreHarvestStep) => {
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

  const submitParcel = parcelForm.handleSubmit(async (values) => {
    if (!selectedFarmer) {
      setFormError("Veuillez sélectionner un agriculteur.");
      return;
    }
    setFormError(null);
    try {
      const payload: ParcelCreate = {
        farmer_id: selectedFarmer.id,
        name: values.name.trim(),
        surface_ha: Number(values.surface_ha),
        main_culture: values.main_culture.trim(),
        variety: values.variety.trim() || null,
        tree_count: values.tree_count ?? null,
      };
      const created = await createParcel.mutateAsync(payload);
      setSelectedParcelId(created.id);
      setParcelModalOpen(false);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'ajouter la parcelle.");
    }
  });

  const submitStep = stepForm.handleSubmit(async (values) => {
    if (!selectedParcel || !activeStep) return;
    setFormError(null);
    try {
      const payload: PreHarvestStepUpdate = {
        quantity_value: values.quantity_value !== undefined ? Number(values.quantity_value) : null,
        quantity_unit: values.quantity_unit.trim() || null,
        operation_cost_fcfa: values.operation_cost_fcfa !== undefined ? Number(values.operation_cost_fcfa) : null,
        realization_date: values.realization_date,
        observations: values.observations.trim() || null,
      };
      await updateStep.mutateAsync({ parcelId: selectedParcel.id, stepId: activeStep.id, payload });
      await completeStep.mutateAsync({ parcelId: selectedParcel.id, stepId: activeStep.id });
      setStepModalOpen(false);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer l'étape.");
    }
  });

  const submitCharge = chargeForm.handleSubmit(async (values) => {
    if (!selectedFarmer) return;
    setFormError(null);
    try {
      const payload: GlobalChargeCreate = {
        farmer_id: selectedFarmer.id,
        parcel_id: values.parcel_id || null,
        charge_type: values.charge_type,
        label: values.label.trim(),
        amount_fcfa: Number(values.amount_fcfa),
        date: values.date,
        notes: values.notes.trim() || null,
      };
      await createCharge.mutateAsync(payload);
      setChargeModalOpen(false);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer la charge.");
    }
  });

  const aiAdvice = useMemo(() => {
    if (!selectedFarmer || !selectedParcel) {
      return "Sélectionnez un agriculteur et une parcelle pour générer un conseil contextualisé.";
    }
    if (steps.length === 0) {
      return `Conseil IA basé sur la parcelle ${selectedParcel.name} : aucune opération pré-récolte n'est encore initialisée.`;
    }
    if (completedCount === 0) {
      return `Conseil IA basé sur la parcelle ${selectedParcel.name} : aucune opération enregistrée pour le moment. Commencez par taille, traitement et fertilisation.`;
    }
    return `Conseil IA basé sur ${selectedFarmer.full_name} / ${selectedParcel.name} : ${completedCount}/${steps.length} étapes réalisées. Priorisez les étapes restantes avant récolte.`;
  }, [selectedFarmer, selectedParcel, steps.length, completedCount]);

  const preHarvestInsights = useMemo<AIInsightItem[]>(() => {
    if (!selectedFarmer || !selectedParcel) {
      return [
        {
          id: "select-context",
          title: "Contexte requis",
          message: "Selectionnez un agriculteur et une parcelle pour obtenir un conseil IA contextualise.",
          tone: "info",
        },
      ];
    }

    const pending = steps.filter((item) => item.status !== "completed");
    const doneRatio = steps.length > 0 ? completedCount / steps.length : 0;
    const riskyPending = pending.filter((item) =>
      ["phytosanitary_treatment", "fertilization", "irrigation"].includes(item.step_key),
    );
    const recentCharges = charges?.items.slice(0, 5) ?? [];
    const recentChargeAmount = recentCharges.reduce((sum, item) => sum + item.amount_fcfa, 0);

    const items: AIInsightItem[] = [
      {
        id: "cycle-progress",
        title: doneRatio < 0.5 ? "Cycle pre-recolte en retard" : "Cycle pre-recolte en bonne voie",
        message: `${completedCount}/${steps.length || 0} etapes realisees pour ${selectedParcel.name}.`,
        tone: doneRatio < 0.5 ? "warning" : "success",
        meta: doneRatio < 0.5 ? "Planifier les etapes restantes cette semaine." : "Maintenir la cadence actuelle.",
      },
    ];

    if (riskyPending.length > 0) {
      items.push({
        id: "critical-remaining",
        title: "Etapes sensibles non realisees",
        message: `${riskyPending.length} etape(s) critique(s) en attente: ${riskyPending
          .slice(0, 2)
          .map((item) => item.label)
          .join(", ")}${riskyPending.length > 2 ? "..." : ""}.`,
        tone: "critical",
        meta: "Prioriser avant la fenetre de recolte pour limiter le risque terrain.",
      });
    }

    items.push({
      id: "charge-signal",
      title: "Signal cout pre-recolte",
      message: `Charges recentes: ${recentChargeAmount.toLocaleString("fr-FR")} FCFA.`,
      tone: recentChargeAmount > 200000 ? "warning" : "info",
      meta:
        recentChargeAmount > 200000
          ? "Verifier l'impact des charges sur le rendement attendu."
          : "Cout sous controle, continuer le suivi des justificatifs.",
    });

    return items.slice(0, 4);
  }, [selectedFarmer, selectedParcel, steps, completedCount, charges?.items]);

  return (
    <main>
      <PageIntro title="Parcelles & Culture" />

      <section className="premium-card mb-4 rounded-2xl p-4">
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
              placeholder="Rechercher agriculteur..."
            />
            <button type="button" onClick={() => setAiModalOpen(true)} className="soft-focus rounded-xl bg-[#5F4AB8] px-4 py-2 text-sm font-semibold text-white">
              🤖 IA
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <aside className="space-y-3">
          <article className="premium-card rounded-2xl p-4">
            <h3 className="text-base font-semibold text-[var(--text)]">👥 Agriculteurs</h3>
            <div className="mt-3 space-y-2">
              {filteredFarmers.map((farmer) => {
                const active = farmer.id === selectedFarmer?.id;
                return (
                  <button
                    type="button"
                    key={farmer.id}
                    onClick={() => {
                      setSelectedFarmerId(farmer.id);
                      setSelectedParcelId(null);
                    }}
                    className={`w-full rounded-xl border px-3 py-2 text-left transition-colors ${
                      active ? "border-[#168A4A] bg-[#EAF8EE]" : "border-[var(--line)] bg-[var(--surface-soft)]"
                    }`}
                  >
                    <p className="text-sm font-semibold text-[var(--text)]">{farmer.full_name}</p>
                    <p className="text-xs text-[var(--muted)]">
                      {farmer.village ?? "Zone non renseignée"} · {farmer.parcel_count} parcelle(s)
                    </p>
                  </button>
                );
              })}
            </div>
          </article>

          <article className="premium-card rounded-2xl p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-base font-semibold text-[var(--text)]">🗺️ Parcelles</h3>
              <button type="button" onClick={() => setParcelModalOpen(true)} className="text-xs font-semibold text-[#C44D17] hover:underline">
                + Ajouter parcelle
              </button>
            </div>
            {(parcelsQuery.data ?? []).length === 0 ? (
              <p className="text-xs text-[var(--muted)]">Aucune parcelle enregistrée pour cet agriculteur.</p>
            ) : (
              <div className="space-y-2">
                {(parcelsQuery.data ?? []).map((parcel) => {
                  const active = parcel.id === selectedParcel?.id;
                  return (
                    <button
                      key={parcel.id}
                      type="button"
                      onClick={() => setSelectedParcelId(parcel.id)}
                      className={`w-full rounded-xl border px-3 py-2 text-left transition-colors ${
                        active ? "border-[#D1622A] bg-[#FFF0E7]" : "border-[var(--line)] bg-[var(--surface-soft)]"
                      }`}
                    >
                      <span className="inline-flex rounded-full bg-[#FFE8D8] px-2 py-0.5 text-[11px] font-semibold text-[#BA5B19]">
                        {parcel.main_culture}
                      </span>
                      <p className="mt-1 text-sm font-semibold text-[var(--text)]">{parcel.name}</p>
                      <p className="text-xs text-[var(--muted)]">
                        {parcel.surface_ha.toFixed(1)} ha{parcel.tree_count ? ` · ${parcel.tree_count} arbres` : ""}
                        {parcel.variety ? ` · var. ${parcel.variety}` : ""}
                      </p>
                    </button>
                  );
                })}
              </div>
            )}
          </article>

          <article className="premium-card rounded-2xl p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-base font-semibold text-[var(--text)]">🧾 Charges globales</h3>
              <button type="button" onClick={() => setChargeModalOpen(true)} className="text-xs font-semibold text-[#168A4A] hover:underline">
                + Nouvelle charge
              </button>
            </div>
            <p className="text-lg font-semibold text-[var(--text)]">
              {(charges?.total_amount_fcfa ?? 0).toLocaleString("fr-FR")} FCFA
            </p>
            {(charges?.items.length ?? 0) === 0 ? (
              <p className="mt-1 text-xs text-[var(--muted)]">Aucune charge enregistrée</p>
            ) : (
              <div className="mt-2 space-y-1">
                {charges?.items.slice(0, 4).map((charge) => (
                  <p key={charge.id} className="text-xs text-[var(--muted)]">
                    {charge.label} · {charge.amount_fcfa.toLocaleString("fr-FR")} FCFA
                  </p>
                ))}
              </div>
            )}
          </article>
        </aside>

        <section className="premium-card rounded-2xl p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-[var(--text)]">
                {selectedFarmer && selectedParcel ? `${selectedFarmer.full_name} — ${selectedParcel.name}` : "Sélection"}
              </h3>
              <p className="text-sm text-[var(--muted)]">
                {selectedParcel
                  ? `${selectedParcel.main_culture} · ${selectedParcel.surface_ha.toFixed(1)} ha${selectedParcel.variety ? ` · var. ${selectedParcel.variety}` : ""}${selectedParcel.tree_count ? ` · ${selectedParcel.tree_count} arbres` : ""}`
                  : "Sélectionnez une parcelle pour suivre les phases pré-récolte."}
              </p>
            </div>
            <button type="button" onClick={() => setAiModalOpen(true)} className="soft-focus rounded-xl bg-[#5F4AB8] px-4 py-2 text-sm font-semibold text-white">
              🤖 Conseils IA
            </button>
          </div>

          <div className="mb-4">
            <p className="mb-1 text-xs text-[var(--muted)]">
              {completedCount}/{steps.length || 0} réalisées
            </p>
            <div className="h-2 w-full rounded-full bg-[#ECEFE8]">
              <div className="h-2 rounded-full bg-[#168A4A]" style={{ width: `${progress}%` }} />
            </div>
          </div>

          <AIInsightsStrip
            title="Conseils IA pre-recolte"
            subtitle="Lecture operationnelle pour la parcelle selectionnee."
            items={preHarvestInsights}
          />

          <h4 className="mb-3 text-base font-semibold text-[var(--text)]">
            🌱 Phases pré-récolte — {selectedParcel?.main_culture ?? "-"}
          </h4>
          {steps.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">Sélectionnez une parcelle pour afficher le cycle pré-récolte.</p>
          ) : (
            <div className="space-y-3">
              {steps.map((step) => (
                <article key={step.id} className="rounded-2xl border border-[var(--line)] bg-[#FFF9F1] p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{step.icon}</span>
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${CATEGORY_TONE[step.category] ?? "bg-[#EEF2F5] text-[#4A5A71]"}`}>
                        {step.category}
                      </span>
                    </div>
                    <StatusBadge
                      label={step.status === "completed" ? `Réalisé${step.realization_date ? ` le ${step.realization_date}` : ""}` : "Pas encore réalisé"}
                      tone={step.status === "completed" ? "success" : "warning"}
                    />
                  </div>
                  <p className="mt-2 text-sm font-semibold text-[var(--text)]">{step.label}</p>
                  <div className="mt-3 flex items-center justify-end">
                    <button type="button" onClick={() => openStepModal(step)} className="soft-focus rounded-xl bg-[#D96A2B] px-3 py-1.5 text-xs font-semibold text-white">
                      {step.status === "completed" ? "Modifier" : "Saisir données"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>

      <LiquidGlassModal
        open={parcelModalOpen}
        onClose={() => setParcelModalOpen(false)}
        title="Nouvelle parcelle"
        subtitle="Créer une parcelle liée à l'agriculteur sélectionné."
        size="md"
      >
        <form onSubmit={submitParcel} className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            Nom de la parcelle
            <input {...parcelForm.register("name", { required: "Nom requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="ex: Champ Nord" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Surface (ha)
            <input type="number" step="0.1" min="0.1" {...parcelForm.register("surface_ha", { required: "Surface requise.", valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Culture principale
            <select {...parcelForm.register("main_culture", { required: "Culture requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
              <option value="">Sélectionner</option>
              {farmerProducts.map((product) => (
                <option key={product} value={product}>
                  {product}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Variété
            <input {...parcelForm.register("variety")} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="ex: Kent" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Nb arbres (optionnel)
            <input type="number" min="0" {...parcelForm.register("tree_count", { valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>
          {formError ? <p className="text-xs text-[#A53A3A]">{formError}</p> : null}
          <div className="flex items-center justify-end gap-2">
            <button type="button" onClick={() => setParcelModalOpen(false)} className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold">
              Annuler
            </button>
            <button type="submit" className="soft-focus wf-btn-primary px-3 py-2 text-sm font-semibold">
              💾 Ajouter la parcelle
            </button>
          </div>
        </form>
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
            <input type="number" min="0" step="0.1" {...stepForm.register("quantity_value", { valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="ex: 500" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Unité
            <input {...stepForm.register("quantity_unit")} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="ex: arbres / kg / L" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Coût de l’opération (FCFA)
            <input type="number" min="0" step="1" {...stepForm.register("operation_cost_fcfa", { valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="ex: 25000" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Date de réalisation
            <input type="date" {...stepForm.register("realization_date", { required: "Date requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Observations
            <textarea {...stepForm.register("observations")} className="wf-input mt-2 w-full px-3 py-2.5 text-sm" placeholder="Notes, remarques..." />
          </label>
          {formError ? <p className="text-xs text-[#A53A3A]">{formError}</p> : null}
          <div className="flex items-center justify-end gap-2">
            <button type="button" onClick={() => setStepModalOpen(false)} className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold">
              Annuler
            </button>
            <button type="submit" className="soft-focus rounded-xl bg-[#168A4A] px-3 py-2 text-sm font-semibold text-white">
              💾 Enregistrer
            </button>
          </div>
        </form>
      </LiquidGlassModal>

      <LiquidGlassModal
        open={chargeModalOpen}
        onClose={() => setChargeModalOpen(false)}
        title={`Nouvelle charge — ${selectedFarmer?.full_name ?? ""}`}
        subtitle="Ajouter une charge globale liée à l'agriculteur."
        size="md"
      >
        <form onSubmit={submitCharge} className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            Type de charge
            <select {...chargeForm.register("charge_type", { required: "Type requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
              <option>Semences/Plants</option>
              <option>Engrais</option>
              <option>Main d’œuvre</option>
              <option>Transport</option>
              <option>Irrigation</option>
              <option>Traitement</option>
              <option>Autre</option>
            </select>
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Libellé
            <input {...chargeForm.register("label", { required: "Libellé requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="ex: Achat engrais NPK 50kg" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Montant (FCFA)
            <input type="number" min="1" step="1" {...chargeForm.register("amount_fcfa", { required: "Montant requis.", valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Date
            <input type="date" {...chargeForm.register("date", { required: "Date requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Parcelle concernée (optionnel)
            <select {...chargeForm.register("parcel_id")} className="wf-input mt-2 h-11 w-full px-3 text-sm">
              <option value="">— Générale —</option>
              {(parcelsQuery.data ?? []).map((parcel) => (
                <option key={parcel.id} value={parcel.id}>
                  {parcel.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Notes
            <textarea {...chargeForm.register("notes")} className="wf-input mt-2 w-full px-3 py-2.5 text-sm" />
          </label>
          {formError ? <p className="text-xs text-[#A53A3A]">{formError}</p> : null}
          <div className="flex items-center justify-end gap-2">
            <button type="button" onClick={() => setChargeModalOpen(false)} className="soft-focus wf-btn-secondary px-3 py-2 text-sm font-semibold">
              Annuler
            </button>
            <button type="submit" className="soft-focus wf-btn-primary px-3 py-2 text-sm font-semibold">
              💾 Enregistrer
            </button>
          </div>
        </form>
      </LiquidGlassModal>

      <LiquidGlassModal open={aiModalOpen} onClose={() => setAiModalOpen(false)} title="🤖 Conseils IA" subtitle="Conseil contextuel basé sur les données disponibles." size="md">
        <p className="text-sm text-[var(--text)]">{aiAdvice}</p>
        <div className="mt-3 space-y-2">
          {preHarvestInsights.map((item) => (
            <div key={item.id} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs font-semibold text-[var(--text)]">{item.title}</p>
              <p className="text-xs text-[var(--muted)]">{item.message}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-[var(--muted)]">
          Note: ce conseil reste une aide a la decision et doit etre confirme par verification terrain.
        </p>
      </LiquidGlassModal>
    </main>
  );
}
