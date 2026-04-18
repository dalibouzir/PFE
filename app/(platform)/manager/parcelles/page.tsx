"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useCreateField, useDeleteField, useFields, useUpdateField } from "@/hooks/useFields";
import { useMembers } from "@/hooks/useMembers";
import type { Field, FieldCreate } from "@/lib/api/types";

export default function ParcellesPage() {
  const { data: fields = [] } = useFields();
  const { data: members = [] } = useMembers();
  const createField = useCreateField();
  const updateField = useUpdateField();
  const deleteField = useDeleteField();
  const [query, setQuery] = useState("");
  const [soilType, setSoilType] = useState<string>("Tous");
  const [formOpen, setFormOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<Field | null>(null);

  const { register, handleSubmit, reset, formState } = useForm<FieldCreate>({
    defaultValues: {
      member_id: "",
      location: "",
      area: 0,
      soil_type: "",
      irrigation_type: "",
    },
  });

  const memberLookup = useMemo(() => new Map(members.map((m) => [m.id, m.full_name])), [members]);

  const soilOptions = useMemo(() => {
    const unique = new Set(fields.map((field) => field.soil_type).filter(Boolean));
    return Array.from(unique) as string[];
  }, [fields]);

  const openCreateForm = () => {
    setEditingField(null);
    reset({ member_id: members[0]?.id ?? "", location: "", area: 0, soil_type: "", irrigation_type: "" });
    setFormError(null);
    setFormOpen(true);
  };

  const openEditForm = (field: Field) => {
    setEditingField(field);
    reset({
      member_id: field.member_id,
      location: field.location,
      area: field.area,
      soil_type: field.soil_type ?? "",
      irrigation_type: field.irrigation_type ?? "",
    });
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setFormError(null);
  };

  const submitField = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const payload: FieldCreate = {
        member_id: values.member_id,
        location: values.location.trim(),
        area: Number(values.area),
        soil_type: values.soil_type?.trim() || null,
        irrigation_type: values.irrigation_type?.trim() || null,
      };

      if (editingField) {
        await updateField.mutateAsync({ id: editingField.id, payload });
      } else {
        await createField.mutateAsync(payload);
      }
      closeForm();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer la parcelle.");
    }
  });

  const handleDeleteField = async (field: Field) => {
    if (!window.confirm("Supprimer cette parcelle ?")) return;
    try {
      await deleteField.mutateAsync(field.id);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de supprimer la parcelle.");
    }
  };

  const filtered = useMemo(() => {
    return fields.filter((item) => {
      const bySoil = soilType === "Tous" || item.soil_type === soilType;
      const text = `${item.location} ${memberLookup.get(item.member_id) ?? ""}`.toLowerCase();
      return bySoil && text.includes(query.toLowerCase());
    });
  }, [fields, soilType, query, memberLookup]);

  return (
    <main>
      <PageIntro title="Parcelles" subtitle="Suivi des parcelles et sols enregistres." />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
            placeholder="Localisation ou agriculteur..."
          />
          <select
            value={soilType}
            onChange={(event) => setSoilType(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option value="Tous">Tous types de sol</option>
            {soilOptions.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={openCreateForm}
            className="soft-focus rounded-xl bg-[var(--primary)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]"
          >
            Nouvelle parcelle
          </button>
        </div>
      </section>

      {filtered.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucune parcelle enregistree.</p>
        </section>
      ) : (
        <section className="grid gap-4 xl:grid-cols-[1.4fr_0.6fr]">
          <div className="grid gap-3 md:grid-cols-2">
            {filtered.map((item, index) => (
              <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${80 + index * 30}ms` }}>
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-semibold text-[var(--text)]">{item.location}</p>
                  <StatusBadge label="Active" tone="success" />
                </div>
                <p className="text-sm text-[var(--text)]">{memberLookup.get(item.member_id) ?? "Agriculteur"}</p>
                <p className="mt-1 text-xs text-[var(--muted)]">{item.area.toFixed(1)} ha</p>

                <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-xl bg-[var(--surface-soft)] p-2.5">
                    <p className="text-[11px] text-[var(--muted)]">Type sol</p>
                    <p className="font-semibold text-[var(--text)]">{item.soil_type ?? "-"}</p>
                  </div>
                  <div className="rounded-xl bg-[var(--surface-soft)] p-2.5">
                    <p className="text-[11px] text-[var(--muted)]">Irrigation</p>
                    <p className="font-semibold text-[var(--text)]">{item.irrigation_type ?? "-"}</p>
                  </div>
                </div>

                <div className="mt-3 flex items-center gap-2">
                  <button
                    type="button"
                    className="text-xs font-semibold text-[var(--green-700)] hover:underline"
                    onClick={() => openEditForm(item)}
                  >
                    Modifier
                  </button>
                  <button
                    type="button"
                    className="text-xs font-semibold text-[#a34141] hover:underline"
                    onClick={() => handleDeleteField(item)}
                  >
                    Supprimer
                  </button>
                </div>
              </article>
            ))}
          </div>

          <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "160ms" }}>
            <h3 className="text-base font-semibold text-[var(--text)]">Vue zone</h3>
            <p className="mt-1 text-xs text-[var(--muted)]">Apercu parcelles disponibles</p>

            <div className="mt-3 rounded-2xl border border-[var(--line)] bg-[linear-gradient(180deg,#f1f6f2_0%,#e7f0ea_100%)] p-3">
              <div className="h-52 rounded-xl border border-dashed border-[#bcd3be] bg-[radial-gradient(circle_at_30%_30%,rgba(112,170,128,0.18),transparent_42%),radial-gradient(circle_at_70%_60%,rgba(84,161,115,0.2),transparent_45%)]" />
              <p className="mt-2 text-[11px] text-[var(--muted)]">Carte disponible apres integration SIG.</p>
            </div>

            <div className="mt-3 space-y-2 text-sm">
              <div className="rounded-xl bg-[var(--surface-soft)] px-3 py-2">Parcelles: {filtered.length}</div>
              <div className="rounded-xl bg-[var(--surface-soft)] px-3 py-2">Superficie totale: {filtered.reduce((acc, item) => acc + item.area, 0).toFixed(1)} ha</div>
            </div>
          </article>
        </section>
      )}

      <LiquidGlassModal
        open={formOpen}
        onClose={closeForm}
        title={editingField ? "Modifier parcelle" : "Nouvelle parcelle"}
        subtitle="Les parcelles sont rattachees aux agriculteurs."
        size="md"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--text)]" onClick={closeForm}>
              Annuler
            </button>
            <button type="submit" form="field-form" className="soft-focus rounded-xl bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        }
      >
        <form id="field-form" onSubmit={submitField} className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            Agriculteur
            <select {...register("member_id", { required: "Agriculteur requis." })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm">
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
            Localisation
            <input
              {...register("location", { required: "Localisation requise." })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="Parcelle Sud - Pout"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Superficie (ha)
            <input
              type="number"
              step="0.1"
              min="0"
              {...register("area", { required: "Superficie requise.", valueAsNumber: true })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Type de sol
            <input
              {...register("soil_type")}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="Argileux"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--text)]">
            Irrigation
            <input
              {...register("irrigation_type")}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="Goutte-a-goutte"
            />
          </label>
          {formError && (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {formError}
            </p>
          )}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
