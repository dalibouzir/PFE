"use client";

import { FormEvent, useMemo, useState } from "react";
import { GlassViewToggle, type DataViewMode } from "@/components/ui/GlassViewToggle";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { managerAccounts, type CooperativeRecord, type ManagerAccount, type ManagerStatus } from "@/lib/mock-data";

const toneByStatus: Record<ManagerStatus, "success" | "warning" | "info"> = {
  Actif: "success",
  Suspendu: "warning",
  "Invitation envoyee": "info",
};

const statusCycle: ManagerStatus[] = ["Actif", "Suspendu", "Invitation envoyee"];
const regions: CooperativeRecord["region"][] = ["Thies", "Louga", "Casamance", "Kaolack", "Saint-Louis"];

type ManagerFormState = {
  name: string;
  email: string;
  phone: string;
  cooperative: string;
  region: CooperativeRecord["region"];
  status: ManagerStatus;
};

function buildForm(cooperativeOptions: string[]): ManagerFormState {
  return {
    name: "",
    email: "",
    phone: "",
    cooperative: cooperativeOptions[0] ?? "Cooperative Deggo Thies",
    region: "Thies",
    status: "Invitation envoyee",
  };
}

function formatActivityStamp() {
  return new Intl.DateTimeFormat("fr-SN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date());
}

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export default function AdminManagersPage() {
  const [records, setRecords] = useState<ManagerAccount[]>(managerAccounts);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"Tous" | ManagerStatus>("Tous");
  const [viewMode, setViewMode] = useState<DataViewMode>("table");
  const [openModal, setOpenModal] = useState(false);
  const [formError, setFormError] = useState("");

  const cooperativeOptions = useMemo(() => Array.from(new Set(records.map((item) => item.cooperative))), [records]);

  const [form, setForm] = useState<ManagerFormState>(() => buildForm(Array.from(new Set(managerAccounts.map((item) => item.cooperative)))));

  const filtered = useMemo(() => {
    return records.filter((item) => {
      const byStatus = status === "Tous" || item.status === status;
      const text = `${item.name} ${item.email} ${item.cooperative} ${item.phone}`.toLowerCase();
      return byStatus && text.includes(query.toLowerCase());
    });
  }, [records, query, status]);

  const actives = filtered.filter((item) => item.status === "Actif").length;
  const suspended = filtered.filter((item) => item.status === "Suspendu").length;

  const openCreateModal = () => {
    setForm(buildForm(cooperativeOptions));
    setFormError("");
    setOpenModal(true);
  };

  const closeModal = () => {
    setOpenModal(false);
    setFormError("");
  };

  const cycleManagerStatus = (id: string) => {
    setRecords((prev) =>
      prev.map((item) => {
        if (item.id !== id) return item;
        const currentIndex = statusCycle.indexOf(item.status);
        const next = statusCycle[(currentIndex + 1) % statusCycle.length];
        return { ...item, status: next };
      }),
    );
  };

  const resetManager = (id: string) => {
    const stamp = formatActivityStamp();
    setRecords((prev) => prev.map((item) => (item.id === id ? { ...item, status: "Invitation envoyee", lastActive: `Reset ${stamp}` } : item)));
  };

  const submitForm = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!form.name.trim() || !form.email.trim() || !form.phone.trim()) {
      setFormError("Nom, email et telephone sont requis.");
      return;
    }

    if (!form.email.includes("@")) {
      setFormError("Entrez un email valide.");
      return;
    }

    const created: ManagerAccount = {
      id: `MGR-${String(records.length + 1).padStart(3, "0")}`,
      name: form.name.trim(),
      email: form.email.trim().toLowerCase(),
      phone: form.phone.trim(),
      cooperative: form.cooperative,
      region: form.region,
      status: form.status,
      lastActive: "-",
    };

    setRecords((prev) => [created, ...prev]);
    closeModal();
  };

  return (
    <main>
      <PageIntro title="Managers" subtitle="Gestion locale des comptes, statuts et cycles d'activation." />

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
            onChange={(event) => setStatus(event.target.value as "Tous" | ManagerStatus)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            <option>Actif</option>
            <option>Suspendu</option>
            <option>Invitation envoyee</option>
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
              <p className="text-lg font-semibold text-[var(--green-900)]">{actives}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Suspendus</p>
              <p className="text-lg font-semibold text-[var(--green-900)]">{suspended}</p>
            </div>
          </div>

          <GlassViewToggle value={viewMode} onChange={setViewMode} className="shrink-0" />
        </div>
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
                {filtered.map((item) => (
                  <tr key={item.id} className="border-t border-[var(--line)] hover:bg-[var(--surface-soft)]/70">
                    <td className="px-4 py-3 font-medium text-[var(--text)]">{item.name}</td>
                    <td className="px-4 py-3">{item.email}</td>
                    <td className="px-4 py-3">{item.phone}</td>
                    <td className="px-4 py-3">
                      <p>{item.cooperative}</p>
                      <p className="text-xs text-[var(--muted)]">{item.region} · Derniere activite: {item.lastActive}</p>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge label={item.status} tone={toneByStatus[item.status]} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2 text-xs">
                        <button onClick={() => cycleManagerStatus(item.id)} className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--green-700)] hover:border-[var(--green-500)]">
                          Basculer statut
                        </button>
                        <button onClick={() => resetManager(item.id)} className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--muted)] hover:text-[var(--green-700)]">
                          Reinitialiser
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
            <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${90 + index * 30}ms` }}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.name}</p>
                  <p className="text-xs text-[var(--muted)]">{item.email}</p>
                </div>
                <StatusBadge label={item.status} tone={toneByStatus[item.status]} />
              </div>

              <div className="mt-3 space-y-1.5 text-xs text-[var(--muted)]">
                <p>Tel: {item.phone}</p>
                <p>Cooperative: {item.cooperative}</p>
                <p>Region: {item.region}</p>
                <p>Derniere activite: {item.lastActive}</p>
              </div>

              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <button onClick={() => cycleManagerStatus(item.id)} className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--green-700)] hover:border-[var(--green-500)]">
                  Basculer statut
                </button>
                <button onClick={() => resetManager(item.id)} className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--muted)] hover:text-[var(--green-700)]">
                  Reinitialiser
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      <LiquidGlassModal
        open={openModal}
        onClose={closeModal}
        title="Creer un compte manager"
        subtitle="Creation locale pour la demo (sans backend)."
        size="lg"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <button className="soft-focus w-full rounded-xl border border-white/85 bg-white/55 px-4 py-2 text-sm text-[var(--green-900)] hover:bg-white/75 sm:w-auto" onClick={closeModal} type="button">
              Annuler
            </button>
            <button className="soft-focus w-full rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)] sm:w-auto" form="manager-form" type="submit">
              Creer
            </button>
          </div>
        }
      >
        <form id="manager-form" onSubmit={submitForm} className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm text-[var(--muted)]">
            Nom complet
            <input
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
              placeholder="Ex: Ousmane Diallo"
            />
          </label>

          <label className="text-sm text-[var(--muted)]">
            Telephone
            <input
              value={form.phone}
              onChange={(event) => setForm((prev) => ({ ...prev, phone: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
              placeholder="+221 ..."
            />
          </label>

          <label className="text-sm text-[var(--muted)] sm:col-span-2">
            Email
            <input
              type="email"
              value={form.email}
              onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
              placeholder="nom@cooperative.sn"
            />
          </label>

          <label className="text-sm text-[var(--muted)]">
            Cooperative
            <select
              value={form.cooperative}
              onChange={(event) => setForm((prev) => ({ ...prev, cooperative: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            >
              {cooperativeOptions.map((cooperative) => (
                <option key={cooperative}>{cooperative}</option>
              ))}
            </select>
          </label>

          <label className="text-sm text-[var(--muted)]">
            Region
            <select
              value={form.region}
              onChange={(event) => setForm((prev) => ({ ...prev, region: event.target.value as CooperativeRecord["region"] }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            >
              {regions.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>

          <label className="text-sm text-[var(--muted)] sm:col-span-2">
            Statut initial
            <select
              value={form.status}
              onChange={(event) => setForm((prev) => ({ ...prev, status: event.target.value as ManagerStatus }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            >
              <option>Actif</option>
              <option>Suspendu</option>
              <option>Invitation envoyee</option>
            </select>
          </label>

          {formError && <p className="sm:col-span-2 rounded-xl border border-[#ecc9c9] bg-[#fff1f1]/90 px-3 py-2 text-xs text-[#8d3d3d]">{formError}</p>}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
