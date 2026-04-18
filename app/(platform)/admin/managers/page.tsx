"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { GlassViewToggle, type DataViewMode } from "@/components/ui/GlassViewToggle";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useCooperatives, useCreateManager, useDeleteUser, useDisableUser, useEnableUser, useUsers } from "@/hooks/useAdmin";
import type { ManagerCreate } from "@/lib/api/types";

const toneByStatus: Record<string, "success" | "warning" | "info"> = {
  active: "success",
  disabled: "warning",
};

const statusLabel: Record<string, string> = {
  active: "Actif",
  disabled: "Suspendu",
};

type ManagerForm = ManagerCreate;

export default function AdminManagersPage() {
  const { data: cooperatives = [] } = useCooperatives();
  const { data: users = [] } = useUsers();
  const createManager = useCreateManager();
  const disableUser = useDisableUser();
  const enableUser = useEnableUser();
  const deleteUser = useDeleteUser();

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string>("Tous");
  const [viewMode, setViewMode] = useState<DataViewMode>("table");
  const [openModal, setOpenModal] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const managers = useMemo(() => users.filter((user) => user.role === "manager"), [users]);

  const filtered = useMemo(() => {
    return managers.filter((item) => {
      const byStatus = status === "Tous" || item.status === status;
      const text = `${item.full_name} ${item.email} ${item.phone ?? ""}`.toLowerCase();
      return byStatus && text.includes(query.toLowerCase());
    });
  }, [managers, query, status]);

  const activeCount = filtered.filter((item) => item.status === "active").length;
  const suspended = filtered.filter((item) => item.status === "disabled").length;

  const cooperativeLookup = useMemo(() => {
    return new Map(cooperatives.map((coop) => [coop.id, coop]));
  }, [cooperatives]);

  const { register, handleSubmit, reset, formState } = useForm<ManagerForm>({
    defaultValues: {
      full_name: "",
      email: "",
      phone: "",
      password: "",
      cooperative_id: cooperatives[0]?.id ?? "",
    },
  });

  const openCreateModal = () => {
    reset({
      full_name: "",
      email: "",
      phone: "",
      password: "",
      cooperative_id: cooperatives[0]?.id ?? "",
    });
    setFormError(null);
    setOpenModal(true);
  };

  const closeModal = () => {
    setOpenModal(false);
    setFormError(null);
  };

  const submitForm = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await createManager.mutateAsync({
        full_name: values.full_name.trim(),
        email: values.email.trim().toLowerCase(),
        phone: values.phone?.trim() || undefined,
        password: values.password,
        cooperative_id: values.cooperative_id,
      });
      closeModal();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Creation impossible.");
    }
  });

  const disableAccount = async (userId: string) => {
    setActionError(null);
    try {
      await disableUser.mutateAsync(userId);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Impossible de desactiver le compte.");
    }
  };

  const enableAccount = async (userId: string) => {
    setActionError(null);
    try {
      await enableUser.mutateAsync(userId);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Impossible de reactiver le compte.");
    }
  };

  const deleteAccount = async (userId: string) => {
    if (!window.confirm("Supprimer ce compte ? Cette action est irreversible.")) return;
    setActionError(null);
    try {
      await deleteUser.mutateAsync(userId);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Impossible de supprimer le compte.");
    }
  };

  return (
    <main>
      <PageIntro title="Managers" subtitle="Gestion des comptes managers via l'API." />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1.4fr_1fr_auto]">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
            placeholder="Rechercher un manager..."
          />
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            <option value="active">Actif</option>
            <option value="disabled">Suspendu</option>
          </select>
          <button onClick={openCreateModal} className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]">
            Creer manager
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="grid grow gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Managers visibles</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">{filtered.length}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Actifs</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">{activeCount}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Suspendus</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">{suspended}</p>
            </div>
          </div>

          <GlassViewToggle value={viewMode} onChange={setViewMode} className="shrink-0" />
        </div>
        {actionError && (
          <p className="mt-4 rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
            {actionError}
          </p>
        )}
      </section>

      {filtered.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucun manager ne correspond aux filtres.</p>
        </section>
      ) : viewMode === "table" ? (
        <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "90ms" }}>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
                <tr>
                  <th className="px-4 py-3">Nom</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Telephone</th>
                  <th className="px-4 py-3">Cooperative</th>
                  <th className="px-4 py-3">Statut</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => {
                  const coop = item.cooperative_id ? cooperativeLookup.get(item.cooperative_id) : undefined;
                  return (
                    <tr key={item.id} className="border-t border-[var(--line)] hover:bg-[var(--surface-soft)]/70">
                      <td className="px-4 py-3 font-medium text-[var(--text)]">{item.full_name}</td>
                      <td className="px-4 py-3">{item.email}</td>
                      <td className="px-4 py-3">{item.phone ?? "-"}</td>
                      <td className="px-4 py-3">
                        <p>{coop?.name ?? "Non assigne"}</p>
                        <p className="text-xs text-[var(--muted)]">{coop?.region ?? ""}</p>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge label={statusLabel[item.status] ?? item.status} tone={toneByStatus[item.status] ?? "info"} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2 text-xs">
                          {item.status === "active" ? (
                            <button
                              onClick={() => disableAccount(item.id)}
                              className="rounded-full border border-[#f0d6d6] px-2.5 py-1 text-[#a23f3f] hover:border-[#d9b1b1]"
                            >
                              Desactiver
                            </button>
                          ) : (
                            <button
                              onClick={() => enableAccount(item.id)}
                              className="rounded-full border border-[#cfe3d4] px-2.5 py-1 text-[var(--green-700)] hover:border-[#a8cbb1]"
                            >
                              Reactiver
                            </button>
                          )}
                          <button
                            onClick={() => deleteAccount(item.id)}
                            className="rounded-full border border-[#f0d6d6] px-2.5 py-1 text-[#a23f3f] hover:border-[#d9b1b1]"
                          >
                            Supprimer
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((item, index) => {
            const coop = item.cooperative_id ? cooperativeLookup.get(item.cooperative_id) : undefined;
            return (
              <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${90 + index * 30}ms` }}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-[var(--green-900)]">{item.full_name}</p>
                    <p className="text-xs text-[var(--muted)]">{item.email}</p>
                  </div>
                  <StatusBadge label={statusLabel[item.status] ?? item.status} tone={toneByStatus[item.status] ?? "info"} />
                </div>

                <div className="mt-3 space-y-1.5 text-xs text-[var(--muted)]">
                  <p>Tel: {item.phone ?? "-"}</p>
                  <p>Cooperative: {coop?.name ?? "Non assignee"}</p>
                  <p>Region: {coop?.region ?? "-"}</p>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  {item.status === "active" ? (
                    <button
                      onClick={() => disableAccount(item.id)}
                      className="rounded-full border border-[#f0d6d6] px-2.5 py-1 text-xs text-[#a23f3f] hover:border-[#d9b1b1]"
                    >
                      Desactiver
                    </button>
                  ) : (
                    <button
                      onClick={() => enableAccount(item.id)}
                      className="rounded-full border border-[#cfe3d4] px-2.5 py-1 text-xs text-[var(--green-700)] hover:border-[#a8cbb1]"
                    >
                      Reactiver
                    </button>
                  )}
                  <button
                    onClick={() => deleteAccount(item.id)}
                    className="rounded-full border border-[#f0d6d6] px-2.5 py-1 text-xs text-[#a23f3f] hover:border-[#d9b1b1]"
                  >
                    Supprimer
                  </button>
                </div>
              </article>
            );
          })}
        </section>
      )}

      <LiquidGlassModal
        open={openModal}
        onClose={closeModal}
        title="Creer un compte manager"
        subtitle="Les managers sont liees aux cooperatives selectionnees."
        size="lg"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <button type="button" onClick={closeModal} className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--green-900)]">
              Annuler
            </button>
            <button type="submit" form="manager-form" className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)]" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Creation..." : "Creer"}
            </button>
          </div>
        }
      >
        <form id="manager-form" onSubmit={submitForm} className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Nom complet
            <input
              {...register("full_name", { required: "Nom requis." })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="Aissatou Ndiaye"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Email
            <input
              {...register("email", { required: "Email requis." })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="manager@cooperative.sn"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Telephone
            <input
              {...register("phone")}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="+221 77 000 000"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Mot de passe
            <input
              type="password"
              {...register("password", { required: "Mot de passe requis." })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="********"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Cooperative
            <select {...register("cooperative_id", { required: "Cooperative requise." })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm">
              {cooperatives.length === 0 ? (
                <option value="">Aucune cooperative</option>
              ) : (
                cooperatives.map((coop) => (
                  <option key={coop.id} value={coop.id}>
                    {coop.name}
                  </option>
                ))
              )}
            </select>
          </label>
          {formError && (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f] sm:col-span-2">
              {formError}
            </p>
          )}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
