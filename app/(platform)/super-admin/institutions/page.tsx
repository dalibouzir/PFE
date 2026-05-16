"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { ConfirmActionModal } from "@/components/ui/ConfirmActionModal";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  useCreateInstitutionAdmin,
  useDisableInstitutionAdmin,
  useEnableInstitutionAdmin,
  useCreateInstitution,
  useDeactivateInstitution,
  useInstitutionAdmins,
  useInstitutions,
  useUpdateInstitution,
} from "@/hooks/useSuperAdmin";
import type { InstitutionAdminCreate, InstitutionCreate, InstitutionUpdate } from "@/lib/api/types";

const toneByStatus: Record<string, "success" | "warning" | "info"> = {
  active: "success",
  inactive: "warning",
  suspended: "warning",
};

type InstitutionForm = InstitutionCreate;

export default function SuperAdminInstitutionsPage() {
  const { data: institutions = [], isLoading, isError, error } = useInstitutions();
  const createInstitution = useCreateInstitution();
  const updateInstitution = useUpdateInstitution();
  const deactivateInstitution = useDeactivateInstitution();
  const createInstitutionAdmin = useCreateInstitutionAdmin();
  const enableInstitutionAdmin = useEnableInstitutionAdmin();
  const disableInstitutionAdmin = useDisableInstitutionAdmin();

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("Tous");
  const [openModal, setOpenModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [openAdminsModal, setOpenAdminsModal] = useState(false);
  const [selectedInstitutionId, setSelectedInstitutionId] = useState<string | null>(null);
  const [adminsError, setAdminsError] = useState<string | null>(null);
  const [pendingDeactivateInstitution, setPendingDeactivateInstitution] = useState<{ id: string; name: string } | null>(null);

  const filtered = useMemo(() => {
    return institutions.filter((item) => {
      const byStatus = status === "Tous" || item.status === status;
      const text = `${item.name} ${item.region || ""} ${item.email || ""}`.toLowerCase();
      return byStatus && text.includes(query.toLowerCase());
    });
  }, [institutions, query, status]);

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
  const {
    register: registerAdmin,
    handleSubmit: handleSubmitAdmin,
    reset: resetAdmin,
    formState: adminFormState,
  } = useForm<InstitutionAdminCreate>({
    defaultValues: {
      full_name: "",
      email: "",
      password: "",
      phone: "",
    },
  });

  const {
    data: institutionAdmins = [],
    isLoading: isAdminsLoading,
    isError: isAdminsError,
    error: adminsQueryError,
  } = useInstitutionAdmins(selectedInstitutionId || "", openAdminsModal && Boolean(selectedInstitutionId));

  const openCreate = () => {
    setEditingId(null);
    reset({
      name: "",
      description: "",
      region: "",
      address: "",
      phone: "",
      email: "",
      status: "active",
    });
    setFormError(null);
    setOpenModal(true);
  };

  const openEdit = (id: string) => {
    const row = institutions.find((item) => item.id === id);
    if (!row) return;
    setEditingId(row.id);
    reset({
      name: row.name,
      description: row.description || "",
      region: row.region || "",
      address: row.address || "",
      phone: row.phone || "",
      email: row.email || "",
      status: row.status || "active",
    });
    setFormError(null);
    setOpenModal(true);
  };

  const closeModal = () => {
    setOpenModal(false);
    setFormError(null);
  };
  const openAdmins = (institutionId: string) => {
    setSelectedInstitutionId(institutionId);
    setAdminsError(null);
    resetAdmin({ full_name: "", email: "", password: "", phone: "" });
    setOpenAdminsModal(true);
  };
  const closeAdminsModal = () => {
    setOpenAdminsModal(false);
    setAdminsError(null);
  };

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      if (editingId) {
        const payload: InstitutionUpdate = {
          name: values.name.trim(),
          description: values.description?.trim() || null,
          region: values.region?.trim() || null,
          address: values.address?.trim() || null,
          phone: values.phone?.trim() || null,
          email: values.email?.trim().toLowerCase() || null,
          status: values.status,
        };
        await updateInstitution.mutateAsync({ id: editingId, payload });
      } else {
        await createInstitution.mutateAsync({
          name: values.name.trim(),
          description: values.description?.trim() || null,
          region: values.region?.trim() || null,
          address: values.address?.trim() || null,
          phone: values.phone?.trim() || null,
          email: values.email?.trim().toLowerCase() || null,
          status: values.status,
        });
      }
      closeModal();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Operation impossible.");
    }
  });

  const openDeactivateInstitution = (id: string) => {
    const institution = institutions.find((item) => item.id === id);
    if (!institution) return;
    setPendingDeactivateInstitution({ id, name: institution.name });
  };

  const deactivate = async () => {
    if (!pendingDeactivateInstitution) return;
    setFormError(null);
    try {
      await deactivateInstitution.mutateAsync(pendingDeactivateInstitution.id);
      setPendingDeactivateInstitution(null);
    } catch (actionError) {
      setFormError(actionError instanceof Error ? actionError.message : "Operation impossible.");
    }
  };
  const onCreateInstitutionAdmin = handleSubmitAdmin(async (values) => {
    if (!selectedInstitutionId) return;
    setAdminsError(null);
    try {
      await createInstitutionAdmin.mutateAsync({
        institutionId: selectedInstitutionId,
        payload: {
          full_name: values.full_name.trim(),
          email: values.email.trim().toLowerCase(),
          password: values.password,
          phone: values.phone?.trim() || null,
        },
      });
      resetAdmin({ full_name: "", email: "", password: "", phone: "" });
    } catch (actionError) {
      setAdminsError(actionError instanceof Error ? actionError.message : "Operation impossible.");
    }
  });

  const onToggleAdminStatus = async (userId: string, userStatus: string) => {
    if (!selectedInstitutionId) return;
    setAdminsError(null);
    try {
      if (userStatus === "active") {
        await disableInstitutionAdmin.mutateAsync({ institutionId: selectedInstitutionId, userId });
      } else {
        await enableInstitutionAdmin.mutateAsync({ institutionId: selectedInstitutionId, userId });
      }
    } catch (actionError) {
      setAdminsError(actionError instanceof Error ? actionError.message : "Operation impossible.");
    }
  };

  return (
    <main>
      <PageIntro title="Institutions" subtitle="Gestion des institutions de la plateforme WeeFarm." />
      {isLoading && (
        <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
          <p className="text-sm text-[var(--muted)]">Chargement des institutions...</p>
        </section>
      )}
      {isError && (
        <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
          <p className="text-sm text-[#8f2f2f]">{error instanceof Error ? error.message : "Impossible de charger les institutions."}</p>
        </section>
      )}
      {formError && !openModal && (
        <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "30ms" }}>
          <p className="text-sm text-[#8f2f2f]">{formError}</p>
        </section>
      )}

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1.5fr_1fr_auto]">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
            placeholder="Rechercher une institution..."
          />
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="suspended">Suspendue</option>
          </select>
          <button onClick={openCreate} className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]">
            Nouvelle institution
          </button>
        </div>
      </section>

      <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "90ms" }}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3">Nom</th>
                <th className="px-4 py-3">Région</th>
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Statut</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id} className="border-t border-[var(--line)] hover:bg-[var(--surface-soft)]/70">
                  <td className="px-4 py-3">
                    <p className="font-medium text-[var(--text)]">{item.name}</p>
                    <p className="text-xs text-[var(--muted)]">{item.description || "-"}</p>
                  </td>
                  <td className="px-4 py-3">{item.region || "-"}</td>
                  <td className="px-4 py-3">
                    <p>{item.email || "-"}</p>
                    <p className="text-xs text-[var(--muted)]">{item.phone || "-"}</p>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge label={item.status} tone={toneByStatus[item.status] ?? "info"} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2 text-xs">
                      <button
                        onClick={() => openAdmins(item.id)}
                        className="rounded-full border border-[#d6ddf0] px-2.5 py-1 text-[#3f4fa2] hover:border-[#b1bdd9]"
                      >
                        Gérer admins
                      </button>
                      <button
                        onClick={() => openEdit(item.id)}
                        className="rounded-full border border-[#cfe3d4] px-2.5 py-1 text-[var(--green-700)] hover:border-[#a8cbb1]"
                      >
                        Modifier
                      </button>
                      {item.status !== "inactive" && (
                        <button
                          onClick={() => openDeactivateInstitution(item.id)}
                          disabled={deactivateInstitution.isPending}
                          className="rounded-full border border-[#f0d6d6] px-2.5 py-1 text-[#a23f3f] hover:border-[#d9b1b1]"
                        >
                          Désactiver
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-[var(--muted)]">
                    Aucune institution trouvée.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <LiquidGlassModal
        open={openAdminsModal}
        onClose={closeAdminsModal}
        title="Gérer admins institution"
        subtitle="Créer, suspendre et réactiver les comptes Institution Admin."
        size="xl"
        footer={
          <div className="flex justify-end">
            <button type="button" onClick={closeAdminsModal} className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--green-900)]">
              Fermer
            </button>
          </div>
        }
      >
        <div className="space-y-4">
          {isAdminsLoading && <p className="text-sm text-[var(--muted)]">Chargement des admins...</p>}
          {(isAdminsError || adminsError) && (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {adminsError || (adminsQueryError instanceof Error ? adminsQueryError.message : "Impossible de charger les admins.")}
            </p>
          )}

          <form onSubmit={onCreateInstitutionAdmin} className="grid gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
              Nom complet
              <input {...registerAdmin("full_name", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--green-900)]">
              Email
              <input {...registerAdmin("email", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--green-900)]">
              Téléphone
              <input {...registerAdmin("phone")} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
              Mot de passe
              <input type="password" {...registerAdmin("password", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white px-3 text-sm" />
            </label>
            <div className="sm:col-span-2 flex justify-end">
              <button
                type="submit"
                disabled={adminFormState.isSubmitting || createInstitutionAdmin.isPending}
                className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)]"
              >
                {adminFormState.isSubmitting || createInstitutionAdmin.isPending ? "Création..." : "Créer admin institution"}
              </button>
            </div>
          </form>

          <div className="overflow-x-auto rounded-xl border border-[var(--line)]">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
                <tr>
                  <th className="px-3 py-2">Nom</th>
                  <th className="px-3 py-2">Email</th>
                  <th className="px-3 py-2">Téléphone</th>
                  <th className="px-3 py-2">Rôle</th>
                  <th className="px-3 py-2">Statut</th>
                  <th className="px-3 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {institutionAdmins.map((adminUser) => (
                  <tr key={adminUser.id} className="border-t border-[var(--line)]">
                    <td className="px-3 py-2 font-medium text-[var(--text)]">{adminUser.full_name}</td>
                    <td className="px-3 py-2">{adminUser.email}</td>
                    <td className="px-3 py-2">{adminUser.phone || "-"}</td>
                    <td className="px-3 py-2">institution_admin</td>
                    <td className="px-3 py-2">
                      <StatusBadge label={adminUser.status} tone={adminUser.status === "active" ? "success" : "warning"} />
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => onToggleAdminStatus(adminUser.id, adminUser.status)}
                        disabled={enableInstitutionAdmin.isPending || disableInstitutionAdmin.isPending}
                        className={`rounded-full border px-2.5 py-1 text-xs ${
                          adminUser.status === "active"
                            ? "border-[#f0d6d6] text-[#a23f3f] hover:border-[#d9b1b1]"
                            : "border-[#cfe3d4] text-[var(--green-700)] hover:border-[#a8cbb1]"
                        }`}
                      >
                        {adminUser.status === "active" ? "Suspendre" : "Réactiver"}
                      </button>
                    </td>
                  </tr>
                ))}
                {institutionAdmins.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center text-sm text-[var(--muted)]">
                      Aucun admin institution pour cette institution.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </LiquidGlassModal>

      <LiquidGlassModal
        open={openModal}
        onClose={closeModal}
        title={editingId ? "Modifier l'institution" : "Créer une institution"}
        subtitle="Les changements sont synchronisés avec la hiérarchie plateforme."
        size="lg"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <button type="button" onClick={closeModal} className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--green-900)]">
              Annuler
            </button>
            <button type="submit" form="institution-form" className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)]" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Enregistrement..." : editingId ? "Mettre à jour" : "Créer"}
            </button>
          </div>
        }
      >
        <form id="institution-form" onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Nom
            <input {...register("name", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Région
            <input {...register("region")} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Téléphone
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

      <ConfirmActionModal
        open={pendingDeactivateInstitution !== null}
        title="Désactiver l'institution"
        message={
          pendingDeactivateInstitution
            ? `Confirmer la désactivation de ${pendingDeactivateInstitution.name} ?`
            : ""
        }
        confirmLabel="Désactiver"
        cancelLabel="Annuler"
        tone="danger"
        loading={deactivateInstitution.isPending}
        onCancel={() => setPendingDeactivateInstitution(null)}
        onConfirm={deactivate}
      />
    </main>
  );
}
