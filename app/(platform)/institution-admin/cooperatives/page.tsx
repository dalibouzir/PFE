"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  useInstitutionAdminCooperativeUsers,
  useInstitutionAdminCooperatives,
  useInstitutionAdminCreateCooperative,
  useInstitutionAdminCreateCooperativeUser,
  useInstitutionAdminDisableCooperativeUser,
  useInstitutionAdminEnableCooperativeUser,
  useInstitutionAdminUpdateCooperative,
} from "@/hooks/useInstitutionAdmin";
import type { CooperativeCreate, CooperativeUpdate, CooperativeUserCreate } from "@/lib/api/types";

const toneByStatus: Record<string, "success" | "warning" | "info"> = {
  active: "success",
  onboarding: "info",
  suspended: "warning",
};

type CooperativeForm = CooperativeCreate;
type CooperativeUserForm = CooperativeUserCreate;

export default function InstitutionAdminCooperativesPage() {
  const { data: cooperatives = [], isLoading, isError, error } = useInstitutionAdminCooperatives();
  const createCooperative = useInstitutionAdminCreateCooperative();
  const updateCooperative = useInstitutionAdminUpdateCooperative();

  const createCooperativeUser = useInstitutionAdminCreateCooperativeUser();
  const enableCooperativeUser = useInstitutionAdminEnableCooperativeUser();
  const disableCooperativeUser = useInstitutionAdminDisableCooperativeUser();

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("Tous");
  const [openModal, setOpenModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const [openUsersModal, setOpenUsersModal] = useState(false);
  const [selectedCooperativeId, setSelectedCooperativeId] = useState<string | null>(null);
  const [usersError, setUsersError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    return cooperatives.filter((item) => {
      const byStatus = status === "Tous" || item.status === status;
      const text = `${item.name} ${item.region} ${item.address}`.toLowerCase();
      return byStatus && text.includes(query.toLowerCase());
    });
  }, [cooperatives, query, status]);

  const { register, handleSubmit, reset, formState } = useForm<CooperativeForm>({
    defaultValues: {
      name: "",
      region: "",
      address: "",
      phone: "",
      status: "active",
    },
  });

  const {
    register: registerUser,
    handleSubmit: handleSubmitUser,
    reset: resetUser,
    formState: userFormState,
  } = useForm<CooperativeUserForm>({
    defaultValues: {
      full_name: "",
      email: "",
      password: "",
      phone: "",
      role: "manager",
    },
  });

  const { data: cooperativeUsers = [], isLoading: isUsersLoading, isError: isUsersError, error: usersQueryError } =
    useInstitutionAdminCooperativeUsers(selectedCooperativeId || "", openUsersModal && Boolean(selectedCooperativeId));

  const openCreate = () => {
    setEditingId(null);
    reset({ name: "", region: "", address: "", phone: "", status: "active" });
    setFormError(null);
    setOpenModal(true);
  };

  const openEdit = (id: string) => {
    const row = cooperatives.find((item) => item.id === id);
    if (!row) return;
    setEditingId(row.id);
    reset({
      name: row.name,
      region: row.region,
      address: row.address,
      phone: row.phone,
      status: row.status,
    });
    setFormError(null);
    setOpenModal(true);
  };

  const openUsers = (cooperativeId: string) => {
    setSelectedCooperativeId(cooperativeId);
    setUsersError(null);
    resetUser({ full_name: "", email: "", password: "", phone: "", role: "manager" });
    setOpenUsersModal(true);
  };

  const closeModal = () => {
    setOpenModal(false);
    setFormError(null);
  };

  const closeUsersModal = () => {
    setOpenUsersModal(false);
    setUsersError(null);
  };

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const payload: CooperativeUpdate = {
        name: values.name.trim(),
        region: values.region.trim(),
        address: values.address.trim(),
        phone: values.phone.trim(),
        status: values.status,
      };
      if (editingId) {
        await updateCooperative.mutateAsync({ id: editingId, payload });
      } else {
        await createCooperative.mutateAsync(payload as CooperativeCreate);
      }
      closeModal();
    } catch (actionError) {
      setFormError(actionError instanceof Error ? actionError.message : "Operation impossible.");
    }
  });

  const onCreateUser = handleSubmitUser(async (values) => {
    if (!selectedCooperativeId) return;
    setUsersError(null);
    try {
      await createCooperativeUser.mutateAsync({
        cooperativeId: selectedCooperativeId,
        payload: {
          full_name: values.full_name.trim(),
          email: values.email.trim().toLowerCase(),
          password: values.password,
          phone: values.phone?.trim() || null,
          role: values.role,
        },
      });
      resetUser({ full_name: "", email: "", password: "", phone: "", role: "manager" });
    } catch (actionError) {
      setUsersError(actionError instanceof Error ? actionError.message : "Operation impossible.");
    }
  });

  const onToggleUserStatus = async (userId: string, userStatus: string) => {
    if (!selectedCooperativeId) return;
    setUsersError(null);
    try {
      if (userStatus === "active") {
        await disableCooperativeUser.mutateAsync({ cooperativeId: selectedCooperativeId, userId });
      } else {
        await enableCooperativeUser.mutateAsync({ cooperativeId: selectedCooperativeId, userId });
      }
    } catch (actionError) {
      setUsersError(actionError instanceof Error ? actionError.message : "Operation impossible.");
    }
  };

  return (
    <main>
      <PageIntro title="Cooperatives" subtitle="Gestion des cooperatives rattachées à votre institution." />

      {isLoading && (
        <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
          <p className="text-sm text-[var(--muted)]">Chargement des cooperatives...</p>
        </section>
      )}
      {isError && (
        <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
          <p className="text-sm text-[#8f2f2f]">{error instanceof Error ? error.message : "Impossible de charger les cooperatives."}</p>
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
            placeholder="Rechercher une cooperative..."
          />
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            <option value="active">Active</option>
            <option value="onboarding">Onboarding</option>
            <option value="suspended">Suspendue</option>
          </select>
          <button onClick={openCreate} className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]">
            Nouvelle cooperative
          </button>
        </div>
      </section>

      <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "90ms" }}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3">Nom</th>
                <th className="px-4 py-3">Region</th>
                <th className="px-4 py-3">Telephone</th>
                <th className="px-4 py-3">Statut</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id} className="border-t border-[var(--line)] hover:bg-[var(--surface-soft)]/70">
                  <td className="px-4 py-3">
                    <p className="font-medium text-[var(--text)]">{item.name}</p>
                    <p className="text-xs text-[var(--muted)]">{item.address}</p>
                  </td>
                  <td className="px-4 py-3">{item.region}</td>
                  <td className="px-4 py-3">{item.phone}</td>
                  <td className="px-4 py-3">
                    <StatusBadge label={item.status} tone={toneByStatus[item.status] ?? "info"} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2 text-xs">
                      <button
                        onClick={() => openUsers(item.id)}
                        className="rounded-full border border-[#d6ddf0] px-2.5 py-1 text-[#3f4fa2] hover:border-[#b1bdd9]"
                      >
                        Gérer utilisateurs
                      </button>
                      <button
                        onClick={() => openEdit(item.id)}
                        className="rounded-full border border-[#cfe3d4] px-2.5 py-1 text-[var(--green-700)] hover:border-[#a8cbb1]"
                        disabled={updateCooperative.isPending || createCooperative.isPending}
                      >
                        Modifier
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-[var(--muted)]">
                    Aucune cooperative trouvée.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <LiquidGlassModal
        open={openUsersModal}
        onClose={closeUsersModal}
        title="Gérer utilisateurs"
        subtitle="Créer et gérer les comptes manager et lecture seule de la coopérative sélectionnée."
        size="xl"
        footer={
          <div className="flex justify-end">
            <button type="button" onClick={closeUsersModal} className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--green-900)]">
              Fermer
            </button>
          </div>
        }
      >
        <div className="space-y-4">
          {isUsersLoading && <p className="text-sm text-[var(--muted)]">Chargement des utilisateurs...</p>}
          {(isUsersError || usersError) && (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {usersError || (usersQueryError instanceof Error ? usersQueryError.message : "Impossible de charger les utilisateurs.")}
            </p>
          )}

          <form onSubmit={onCreateUser} className="grid gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
              Nom complet
              <input {...registerUser("full_name", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--green-900)]">
              Email
              <input {...registerUser("email", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--green-900)]">
              Téléphone
              <input {...registerUser("phone")} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--green-900)]">
              Mot de passe
              <input type="password" {...registerUser("password", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--green-900)]">
              Rôle
              <select {...registerUser("role")} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white px-3 text-sm">
                <option value="manager">Manager</option>
                <option value="viewer">Lecture seule</option>
              </select>
            </label>
            <div className="sm:col-span-2 flex justify-end">
              <button
                type="submit"
                disabled={userFormState.isSubmitting || createCooperativeUser.isPending}
                className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)]"
              >
                {userFormState.isSubmitting || createCooperativeUser.isPending ? "Création..." : "Créer utilisateur"}
              </button>
            </div>
          </form>

          <div className="overflow-x-auto rounded-xl border border-[var(--line)]">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
                <tr>
                  <th className="px-3 py-2">Nom</th>
                  <th className="px-3 py-2">Email</th>
                  <th className="px-3 py-2">Rôle</th>
                  <th className="px-3 py-2">Statut</th>
                  <th className="px-3 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {cooperativeUsers.map((user) => (
                  <tr key={user.id} className="border-t border-[var(--line)]">
                    <td className="px-3 py-2">{user.full_name}</td>
                    <td className="px-3 py-2">{user.email}</td>
                    <td className="px-3 py-2">{user.role === "viewer" ? "Lecture seule" : "Manager"}</td>
                    <td className="px-3 py-2">
                      <StatusBadge label={user.status === "active" ? "Actif" : "Suspendu"} tone={user.status === "active" ? "success" : "warning"} />
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => onToggleUserStatus(user.id, user.status)}
                        disabled={enableCooperativeUser.isPending || disableCooperativeUser.isPending}
                        className="rounded-full border border-[#cfe3d4] px-2.5 py-1 text-xs text-[var(--green-700)] hover:border-[#a8cbb1]"
                      >
                        {user.status === "active" ? "Désactiver" : "Réactiver"}
                      </button>
                    </td>
                  </tr>
                ))}
                {cooperativeUsers.length === 0 && !isUsersLoading && (
                  <tr>
                    <td colSpan={5} className="px-3 py-4 text-center text-xs text-[var(--muted)]">
                      Aucun utilisateur sur cette coopérative.
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
        title={editingId ? "Modifier la cooperative" : "Créer une cooperative"}
        subtitle="Toutes les creations restent dans votre institution."
        size="lg"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <button type="button" onClick={closeModal} className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--green-900)]">
              Annuler
            </button>
            <button type="submit" form="institution-coop-form" className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)]" disabled={formState.isSubmitting || updateCooperative.isPending || createCooperative.isPending}>
              {formState.isSubmitting || updateCooperative.isPending || createCooperative.isPending ? "Enregistrement..." : editingId ? "Mettre à jour" : "Créer"}
            </button>
          </div>
        }
      >
        <form id="institution-coop-form" onSubmit={onSubmit} className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Nom
            <input {...register("name", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Region
            <input {...register("region", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Telephone
            <input {...register("phone", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Adresse
            <input {...register("address", { required: true })} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm" />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Statut
            <select {...register("status")} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm">
              <option value="active">active</option>
              <option value="onboarding">onboarding</option>
              <option value="suspended">suspended</option>
            </select>
          </label>
          {formError && <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f] sm:col-span-2">{formError}</p>}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
