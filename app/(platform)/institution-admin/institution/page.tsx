"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useInstitutionAdminInstitution, useInstitutionAdminUpdateInstitution } from "@/hooks/useInstitutionAdmin";
import type { InstitutionUpdate } from "@/lib/api/types";

const toneByStatus: Record<string, "success" | "warning" | "info"> = {
  active: "success",
  inactive: "warning",
  suspended: "warning",
};

type InstitutionForm = {
  name: string;
  description: string;
  region: string;
  address: string;
  phone: string;
  email: string;
  status: string;
};

export default function InstitutionAdminInstitutionPage() {
  const { data: institution, isLoading, isError, error } = useInstitutionAdminInstitution();
  const updateInstitution = useInstitutionAdminUpdateInstitution();

  const [openModal, setOpenModal] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { register, handleSubmit, reset, formState } = useForm<InstitutionForm>({
    defaultValues: {
      name: "",
      description: "",
      region: "",
      address: "",
      phone: "",
      email: "",
      status: "active",
    },
  });

  const openEdit = () => {
    if (!institution) return;
    reset({
      name: institution.name,
      description: institution.description || "",
      region: institution.region || "",
      address: institution.address || "",
      phone: institution.phone || "",
      email: institution.email || "",
      status: institution.status || "active",
    });
    setFormError(null);
    setOpenModal(true);
  };

  const closeModal = () => {
    setOpenModal(false);
    setFormError(null);
  };

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const payload: InstitutionUpdate = {
        name: values.name.trim(),
        description: values.description.trim() || null,
        region: values.region.trim() || null,
        address: values.address.trim() || null,
        phone: values.phone.trim() || null,
        email: values.email.trim().toLowerCase() || null,
        status: values.status,
      };
      await updateInstitution.mutateAsync(payload);
      closeModal();
    } catch (actionError) {
      setFormError(actionError instanceof Error ? actionError.message : "Operation impossible.");
    }
  });

  return (
    <main>
      <PageIntro title="Institution" subtitle="Profil institutionnel et informations de contact." />

      {isLoading && (
        <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "30ms" }}>
          <p className="text-sm text-[var(--muted)]">Chargement de votre institution...</p>
        </section>
      )}

      {isError && (
        <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "30ms" }}>
          <p className="text-sm text-[#8f2f2f]">{error instanceof Error ? error.message : "Impossible de charger votre institution."}</p>
        </section>
      )}

      {!isLoading && !isError && !institution && (
        <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "30ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucune institution disponible pour ce compte.</p>
        </section>
      )}

      {institution && (
        <section className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "60ms" }}>
          <div className="mb-4 flex items-center justify-between gap-2">
            <div>
              <h3 className="text-base font-semibold text-[var(--green-900)]">{institution.name}</h3>
              <p className="text-xs text-[var(--muted)]">Mise à jour du profil institutionnel</p>
            </div>
            <StatusBadge label={institution.status} tone={toneByStatus[institution.status] ?? "info"} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
              <p className="text-xs text-[var(--muted)]">Description</p>
              <p className="text-sm text-[var(--text)]">{institution.description || "-"}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
              <p className="text-xs text-[var(--muted)]">Region</p>
              <p className="text-sm text-[var(--text)]">{institution.region || "-"}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
              <p className="text-xs text-[var(--muted)]">Adresse</p>
              <p className="text-sm text-[var(--text)]">{institution.address || "-"}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
              <p className="text-xs text-[var(--muted)]">Telephone</p>
              <p className="text-sm text-[var(--text)]">{institution.phone || "-"}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5 sm:col-span-2">
              <p className="text-xs text-[var(--muted)]">Email</p>
              <p className="text-sm text-[var(--text)]">{institution.email || "-"}</p>
            </div>
          </div>

          <div className="mt-4 flex justify-end">
            <button
              onClick={openEdit}
              className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]"
            >
              Modifier le profil
            </button>
          </div>
        </section>
      )}

      <LiquidGlassModal
        open={openModal}
        onClose={closeModal}
        title="Modifier l'institution"
        subtitle="Les changements sont synchronises avec votre scope institutionnel."
        size="lg"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <button type="button" onClick={closeModal} className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--green-900)]">
              Annuler
            </button>
            <button type="submit" form="institution-admin-form" className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)]" disabled={formState.isSubmitting || updateInstitution.isPending}>
              {formState.isSubmitting || updateInstitution.isPending ? "Enregistrement..." : "Mettre à jour"}
            </button>
          </div>
        }
      >
        <form id="institution-admin-form" onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Nom
            <input {...register("name", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Region
            <input {...register("region")} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Telephone
            <input {...register("phone")} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Email
            <input {...register("email")} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Adresse
            <input {...register("address")} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Description
            <textarea {...register("description")} className="mt-2 min-h-24 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 py-2 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Statut
            <select {...register("status")} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm">
              <option value="active">active</option>
              <option value="inactive">inactive</option>
              <option value="suspended">suspended</option>
            </select>
          </label>
          {formError && <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f] sm:col-span-2">{formError}</p>}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
