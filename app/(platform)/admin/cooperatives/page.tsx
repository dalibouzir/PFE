"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { GlassViewToggle, type DataViewMode } from "@/components/ui/GlassViewToggle";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useCooperatives, useCreateCooperative, useUsers } from "@/hooks/useAdmin";
import type { CooperativeCreate } from "@/lib/api/types";

const statusTone: Record<string, "success" | "info" | "warning"> = {
  active: "success",
  onboarding: "info",
  suspended: "warning",
};

const statusLabel: Record<string, string> = {
  active: "Active",
  onboarding: "En onboarding",
  suspended: "Suspendue",
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("fr-SN", { day: "2-digit", month: "short", year: "numeric" }).format(
    new Date(value),
  );
}

type CooperativeForm = CooperativeCreate;

export default function AdminCooperativesPage() {
  const { data: cooperatives = [] } = useCooperatives();
  const { data: users = [] } = useUsers();
  const createCooperative = useCreateCooperative();

  const [query, setQuery] = useState("");
  const [region, setRegion] = useState<string>("Toutes");
  const [status, setStatus] = useState<string>("Tous");
  const [viewMode, setViewMode] = useState<DataViewMode>("table");
  const [openModal, setOpenModal] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const regionOptions = useMemo(() => {
    const unique = new Set(cooperatives.map((item) => item.region));
    return Array.from(unique);
  }, [cooperatives]);

  const managerCounts = useMemo(() => {
    const counts = new Map<string, number>();
    users
      .filter((user) => user.role === "manager" && user.cooperative_id)
      .forEach((manager) => {
        const key = manager.cooperative_id as string;
        counts.set(key, (counts.get(key) || 0) + 1);
      });
    return counts;
  }, [users]);

  const filtered = useMemo(() => {
    return cooperatives.filter((item) => {
      const byRegion = region === "Toutes" || item.region === region;
      const byStatus = status === "Tous" || item.status === status;
      const byText = `${item.name} ${item.region}`.toLowerCase().includes(query.toLowerCase());
      return byRegion && byStatus && byText;
    });
  }, [cooperatives, query, region, status]);

  const activeCount = filtered.filter((item) => item.status === "active").length;

  const { register, handleSubmit, reset, formState } = useForm<CooperativeForm>({
    defaultValues: {
      name: "",
      region: "",
      address: "",
      phone: "",
      status: "active",
    },
  });

  const openCreateModal = () => {
    reset({ name: "", region: "", address: "", phone: "", status: "active" });
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
      await createCooperative.mutateAsync({
        name: values.name.trim(),
        region: values.region.trim(),
        address: values.address.trim(),
        phone: values.phone.trim(),
        status: values.status || "active",
      });
      closeModal();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Creation impossible.");
    }
  });

  return (
    <main>
      <PageIntro title="Cooperatives" subtitle="Gestion active des cooperatives avec creation via l'API." />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1.2fr_repeat(3,minmax(0,1fr))]">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
            placeholder="Rechercher une cooperative..."
          />
          <select
            value={region}
            onChange={(event) => setRegion(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Toutes</option>
            {regionOptions.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            <option value="active">Active</option>
            <option value="onboarding">En onboarding</option>
            <option value="suspended">Suspendue</option>
          </select>
          <button onClick={openCreateModal} className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]">
            Nouvelle cooperative
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="grid grow gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Cooperatives visibles</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">{filtered.length}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Actives</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">{activeCount}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Managers total</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">
                {filtered.reduce((acc, item) => acc + (managerCounts.get(item.id) || 0), 0)}
              </p>
            </div>
          </div>

          <GlassViewToggle value={viewMode} onChange={setViewMode} className="shrink-0" />
        </div>
      </section>

      {filtered.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucune cooperative ne correspond aux filtres.</p>
        </section>
      ) : viewMode === "table" ? (
        <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "90ms" }}>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
                <tr>
                  <th className="px-4 py-3">Nom</th>
                  <th className="px-4 py-3">Region</th>
                  <th className="px-4 py-3">Telephone</th>
                  <th className="px-4 py-3">Managers</th>
                  <th className="px-4 py-3">Statut</th>
                  <th className="px-4 py-3">Creation</th>
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
                    <td className="px-4 py-3">{managerCounts.get(item.id) || 0}</td>
                    <td className="px-4 py-3">
                      <StatusBadge label={statusLabel[item.status] ?? item.status} tone={statusTone[item.status] ?? "info"} />
                    </td>
                    <td className="px-4 py-3">{formatDate(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((item, index) => (
            <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${90 + index * 30}ms` }}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.name}</p>
                  <p className="text-xs text-[var(--muted)]">{item.region}</p>
                </div>
                <StatusBadge label={statusLabel[item.status] ?? item.status} tone={statusTone[item.status] ?? "info"} />
              </div>

              <div className="mt-3 space-y-1.5 text-xs text-[var(--muted)]">
                <p>Adresse: {item.address}</p>
                <p>Telephone: {item.phone}</p>
                <p>Managers: {managerCounts.get(item.id) || 0}</p>
              </div>

              <p className="mt-2 text-xs text-[var(--muted)]">Creee le {formatDate(item.created_at)}</p>
            </article>
          ))}
        </section>
      )}

      <LiquidGlassModal
        open={openModal}
        onClose={closeModal}
        title="Creer une cooperative"
        subtitle="Les cooperatives sont synchronisees dans la base de donnees."
        size="lg"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <button type="button" onClick={closeModal} className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold text-[var(--green-900)]">
              Annuler
            </button>
            <button type="submit" form="cooperative-form" className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)]" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Creation..." : "Creer"}
            </button>
          </div>
        }
      >
        <form id="cooperative-form" onSubmit={submitForm} className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Nom
            <input
              {...register("name", { required: "Nom requis." })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="Cooperative Deggo Thies"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Region
            <input
              {...register("region", { required: "Region requise." })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="Thies"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)]">
            Telephone
            <input
              {...register("phone", { required: "Telephone requis." })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="+221 77 000 000"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Adresse
            <input
              {...register("address", { required: "Adresse requise." })}
              className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              placeholder="Route de Mbour, Thies"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--green-900)] sm:col-span-2">
            Statut
            <select {...register("status")} className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm">
              <option value="active">Active</option>
              <option value="onboarding">En onboarding</option>
              <option value="suspended">Suspendue</option>
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
