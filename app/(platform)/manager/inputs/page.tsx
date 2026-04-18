"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { GlassViewToggle, type DataViewMode } from "@/components/ui/GlassViewToggle";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useCreateInput, useDeleteInput, useInputs, useUpdateInput } from "@/hooks/useInputs";
import { useFields } from "@/hooks/useFields";
import { useMembers } from "@/hooks/useMembers";
import { useProducts } from "@/hooks/useProducts";
import type { Input, InputCreate } from "@/lib/api/types";

const statusTone: Record<string, "success" | "warning" | "info"> = {
  validated: "success",
  quality_control: "warning",
  pending: "info",
};
const statusLabel: Record<string, string> = {
  validated: "Valide",
  quality_control: "Controle qualite",
  pending: "En attente",
};
const gradeTone: Record<string, "success" | "info" | "warning"> = {
  A: "success",
  B: "info",
  C: "warning",
};

export default function InputsPage() {
  const { data: inputs = [] } = useInputs();
  const { data: members = [] } = useMembers();
  const { data: products = [] } = useProducts();
  const { data: fields = [] } = useFields();
  const createInput = useCreateInput();
  const updateInput = useUpdateInput();
  const deleteInput = useDeleteInput();

  const [productId, setProductId] = useState<string>("Tous");
  const [fromDate, setFromDate] = useState("");
  const [viewMode, setViewMode] = useState<DataViewMode>("table");
  const [formOpen, setFormOpen] = useState(false);
  const [editingInput, setEditingInput] = useState<Input | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const { register, handleSubmit, reset, watch, formState } = useForm<InputCreate>({
    defaultValues: {
      member_id: "",
      product_id: "",
      field_id: "",
      date: "",
      quantity: 0,
      grade: "",
      status: "pending",
      estimated_value: undefined,
    },
  });

  const memberLookup = useMemo(() => new Map(members.map((m) => [m.id, m.full_name])), [members]);
  const productLookup = useMemo(() => new Map(products.map((p) => [p.id, p.name])), [products]);

  const filtered = useMemo(() => {
    return inputs.filter((item) => {
      const byProduct = productId === "Tous" || item.product_id === productId;
      const byDate = fromDate ? item.date >= fromDate : true;
      return byProduct && byDate;
    });
  }, [inputs, productId, fromDate]);

  const totalKg = filtered.reduce((sum, item) => sum + item.quantity, 0);
  const pendingCount = filtered.filter((item) => item.status !== "validated").length;
  const validatedCount = filtered.filter((item) => item.status === "validated").length;
  const gradeA = filtered.filter((item) => item.grade.toUpperCase() === "A").length;

  const selectedMemberId = watch("member_id");
  const availableFields = useMemo(() => {
    if (!selectedMemberId) return [];
    return fields.filter((field) => field.member_id === selectedMemberId);
  }, [fields, selectedMemberId]);

  const openCreateForm = () => {
    setEditingInput(null);
    reset({
      member_id: members[0]?.id ?? "",
      product_id: products[0]?.id ?? "",
      field_id: "",
      date: "",
      quantity: 0,
      grade: "",
      status: "pending",
      estimated_value: undefined,
    });
    setFormError(null);
    setFormOpen(true);
  };

  const openEditForm = (item: Input) => {
    setEditingInput(item);
    reset({
      member_id: item.member_id,
      product_id: item.product_id,
      field_id: item.field_id ?? "",
      date: item.date,
      quantity: item.quantity,
      grade: item.grade,
      status: item.status,
      estimated_value: item.estimated_value ?? undefined,
    });
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setFormError(null);
  };

  const submitInput = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const payload: InputCreate = {
        member_id: values.member_id,
        product_id: values.product_id,
        field_id: values.field_id || null,
        date: values.date,
        quantity: Number(values.quantity),
        grade: values.grade.trim(),
        status: values.status || "pending",
        estimated_value: values.estimated_value ? Number(values.estimated_value) : null,
      };

      if (editingInput) {
        await updateInput.mutateAsync({ id: editingInput.id, payload });
      } else {
        await createInput.mutateAsync(payload);
      }
      closeForm();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer la collecte.");
    }
  });

  const handleDeleteInput = async (item: Input) => {
    if (!window.confirm("Supprimer cette collecte ?")) return;
    try {
      await deleteInput.mutateAsync(item.id);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de supprimer la collecte.");
    }
  };

  return (
    <main>
      <PageIntro title="Collecte" subtitle="Suivi des apports membres avec validation qualite et statut operationnel." />

      <section className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Volume collecte</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{totalKg.toLocaleString("fr-FR")} kg</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Collectes validees</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{validatedCount}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "60ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">A traiter</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{pendingCount}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "80ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Qualite A</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{gradeA}</p>
        </article>
      </section>

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto_auto]">
          <select
            value={productId}
            onChange={(event) => setProductId(event.target.value)}
            className="soft-focus wf-input px-3 py-2.5 text-sm"
          >
            <option value="Tous">Tous produits</option>
            {products.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={fromDate}
            onChange={(event) => setFromDate(event.target.value)}
            className="soft-focus wf-input px-3 py-2.5 text-sm"
          />
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5 text-sm text-[var(--muted)]">
            {filtered.length} enregistrements
          </div>
          <button
            type="button"
            onClick={openCreateForm}
            className="soft-focus wf-btn-primary px-4 py-2.5 text-sm font-semibold"
          >
            Nouvelle collecte
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="grid grow gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Volume visible</p>
              <p className="text-lg font-semibold text-[var(--text)]">{totalKg.toLocaleString("fr-FR")} kg</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">A traiter</p>
              <p className="text-lg font-semibold text-[var(--text)]">{pendingCount}</p>
            </div>
          </div>

          <GlassViewToggle value={viewMode} onChange={setViewMode} className="shrink-0" />
        </div>
      </section>

      {filtered.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "100ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucune collecte ne correspond aux filtres.</p>
        </section>
      ) : viewMode === "table" ? (
        <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "100ms" }}>
          <div className="overflow-x-auto">
            <table className="wf-table min-w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="px-5 py-3.5">Date</th>
                  <th className="px-5 py-3.5">Agriculteur</th>
                  <th className="px-5 py-3.5">Produit</th>
                  <th className="px-5 py-3.5">Quantite</th>
                  <th className="px-5 py-3.5">Grade</th>
                  <th className="px-5 py-3.5">Statut</th>
                  <th className="px-5 py-3.5">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id}>
                    <td className="px-5 py-4">{item.date}</td>
                    <td className="px-5 py-4 font-medium text-[var(--text)]">{memberLookup.get(item.member_id) ?? item.member_id.slice(0, 8)}</td>
                    <td className="px-5 py-4">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</td>
                    <td className="px-5 py-4">{item.quantity.toLocaleString("fr-FR")} kg</td>
                    <td className="px-5 py-4">
                      <StatusBadge label={item.grade.toUpperCase()} tone={gradeTone[item.grade.toUpperCase()] ?? "info"} />
                    </td>
                    <td className="px-5 py-4">
                      <StatusBadge label={statusLabel[item.status] ?? item.status} tone={statusTone[item.status] ?? "info"} />
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <button className="text-xs font-semibold text-[var(--primary)] hover:underline" onClick={() => openEditForm(item)}>
                          Modifier
                        </button>
                        <button className="text-xs font-semibold text-[var(--danger)] hover:underline" onClick={() => handleDeleteInput(item)}>
                          Supprimer
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((item, index) => (
            <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${100 + index * 30}ms` }}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-[var(--text)]">{memberLookup.get(item.member_id) ?? item.member_id.slice(0, 8)}</p>
                  <p className="text-xs text-[var(--muted)]">{item.date}</p>
                </div>
                <StatusBadge label={item.status} tone={statusTone[item.status] ?? "info"} />
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[11px] text-[var(--muted)]">Produit</p>
                  <p className="text-sm font-semibold text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[11px] text-[var(--muted)]">Quantite</p>
                  <p className="text-sm font-semibold text-[var(--text)]">{item.quantity.toFixed(1)} kg</p>
                </div>
              </div>

              <p className="mt-3 text-xs text-[var(--muted)]">Grade {item.grade}</p>

              <div className="mt-3 flex items-center gap-2">
                <button className="text-xs font-semibold text-[var(--primary)] hover:underline" onClick={() => openEditForm(item)}>
                  Modifier
                </button>
                <button className="text-xs font-semibold text-[var(--danger)] hover:underline" onClick={() => handleDeleteInput(item)}>
                  Supprimer
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      <LiquidGlassModal
        open={formOpen}
        onClose={closeForm}
        title={editingInput ? "Modifier collecte" : "Nouvelle collecte"}
        subtitle="Les collectes actualisent automatiquement les stocks."
        size="lg"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={closeForm}>
              Annuler
            </button>
            <button type="submit" form="input-form" className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        }
      >
        <form id="input-form" onSubmit={submitInput} className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm font-medium text-[var(--text)]">
            Agriculteur
            <select {...register("member_id", { required: "Agriculteur requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
              <option value="" disabled>
                Selectionner un agriculteur
              </option>
              {members.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.full_name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Produit
            <select {...register("product_id", { required: "Produit requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
              <option value="" disabled>
                Selectionner un produit
              </option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Parcelle (optionnel)
            <select {...register("field_id")} className="wf-input mt-2 h-11 w-full px-3 text-sm">
              <option value="">Aucune</option>
              {availableFields.map((field) => (
                <option key={field.id} value={field.id}>
                  {field.location}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Date
            <input type="date" {...register("date", { required: "Date requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Quantite (kg)
            <input type="number" step="0.1" min="0" {...register("quantity", { required: "Quantite requise.", valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Grade
            <input {...register("grade", { required: "Grade requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="A" />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Statut
            <select {...register("status")} className="wf-input mt-2 h-11 w-full px-3 text-sm">
              <option value="pending">En attente</option>
              <option value="quality_control">Controle qualite</option>
              <option value="validated">Valide</option>
            </select>
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Valeur estimee (optionnel)
            <input type="number" step="0.1" min="0" {...register("estimated_value", { valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>
          {formError && (
            <p className="sm:col-span-2 rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {formError}
            </p>
          )}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
