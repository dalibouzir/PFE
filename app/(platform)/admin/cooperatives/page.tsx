"use client";

import { FormEvent, useMemo, useState } from "react";
import { GlassViewToggle, type DataViewMode } from "@/components/ui/GlassViewToggle";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { cooperativeRecords, type CooperativeRecord, type CooperativeStatus } from "@/lib/mock-data";

const statusTone: Record<CooperativeStatus, "success" | "info" | "warning"> = {
  Active: "success",
  "En onboarding": "info",
  Suspendue: "warning",
};

const statusCycle: CooperativeStatus[] = ["Active", "En onboarding", "Suspendue"];
const regions: CooperativeRecord["region"][] = ["Thies", "Louga", "Casamance", "Kaolack", "Saint-Louis"];

type CooperativeFormState = {
  name: string;
  region: CooperativeRecord["region"];
  managersCount: string;
  membersCount: string;
  status: CooperativeStatus;
  createdAt: string;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("fr-SN", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value));
}

function toIsoDate(value?: string) {
  if (value) return value;
  return new Date().toISOString().slice(0, 10);
}

function regionCode(region: CooperativeRecord["region"]) {
  if (region === "Thies") return "TH";
  if (region === "Louga") return "LG";
  if (region === "Casamance") return "CS";
  if (region === "Kaolack") return "KL";
  return "SL";
}

function buildForm(record?: CooperativeRecord): CooperativeFormState {
  if (!record) {
    return {
      name: "",
      region: "Thies",
      managersCount: "1",
      membersCount: "40",
      status: "Active",
      createdAt: toIsoDate(),
    };
  }

  return {
    name: record.name,
    region: record.region,
    managersCount: String(record.managersCount),
    membersCount: String(record.membersCount),
    status: record.status,
    createdAt: record.createdAt,
  };
}

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export default function AdminCooperativesPage() {
  const [records, setRecords] = useState<CooperativeRecord[]>(cooperativeRecords);
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState<"Toutes" | CooperativeRecord["region"]>("Toutes");
  const [status, setStatus] = useState<"Tous" | CooperativeStatus>("Tous");
  const [viewMode, setViewMode] = useState<DataViewMode>("table");
  const [openModal, setOpenModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<CooperativeFormState>(buildForm());
  const [formError, setFormError] = useState("");

  const filtered = useMemo(() => {
    return records.filter((item) => {
      const byRegion = region === "Toutes" || item.region === region;
      const byStatus = status === "Tous" || item.status === status;
      const byText = `${item.name} ${item.id} ${item.region}`.toLowerCase().includes(query.toLowerCase());
      return byRegion && byStatus && byText;
    });
  }, [records, query, region, status]);

  const activeCount = filtered.filter((item) => item.status === "Active").length;

  const modalTitle = editingId ? "Modifier cooperative" : "Creer cooperative";

  const openCreateModal = () => {
    setEditingId(null);
    setForm(buildForm());
    setFormError("");
    setOpenModal(true);
  };

  const openEditModal = (item: CooperativeRecord) => {
    setEditingId(item.id);
    setForm(buildForm(item));
    setFormError("");
    setOpenModal(true);
  };

  const closeModal = () => {
    setOpenModal(false);
    setFormError("");
  };

  const cycleCooperativeStatus = (id: string) => {
    setRecords((prev) =>
      prev.map((item) => {
        if (item.id !== id) return item;
        const currentIndex = statusCycle.indexOf(item.status);
        const next = statusCycle[(currentIndex + 1) % statusCycle.length];
        return { ...item, status: next };
      }),
    );
  };

  const submitForm = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!form.name.trim()) {
      setFormError("Le nom de la cooperative est requis.");
      return;
    }

    const managersCount = Number(form.managersCount);
    const membersCount = Number(form.membersCount);

    if (!Number.isFinite(managersCount) || managersCount < 0 || !Number.isFinite(membersCount) || membersCount < 1) {
      setFormError("Verifiez les nombres de managers et membres.");
      return;
    }

    setRecords((prev) => {
      if (editingId) {
        return prev.map((item) =>
          item.id === editingId
            ? {
                ...item,
                name: form.name.trim(),
                region: form.region,
                managersCount,
                membersCount,
                status: form.status,
                createdAt: form.createdAt,
              }
            : item,
        );
      }

      const created: CooperativeRecord = {
        id: `COOP-${regionCode(form.region)}-${String(prev.length + 1).padStart(3, "0")}`,
        name: form.name.trim(),
        region: form.region,
        managersCount,
        membersCount,
        status: form.status,
        createdAt: form.createdAt,
      };

      return [created, ...prev];
    });

    closeModal();
  };

  return (
    <main>
      <PageIntro title="Cooperatives" subtitle="Gestion active, edition locale et vues adaptatives des cooperatives." />

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
            onChange={(event) => setRegion(event.target.value as "Toutes" | CooperativeRecord["region"])}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Toutes</option>
            {regions.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as "Tous" | CooperativeStatus)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            <option>Active</option>
            <option>En onboarding</option>
            <option>Suspendue</option>
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
              <p className="text-lg font-semibold text-[var(--green-900)]">{filtered.reduce((acc, item) => acc + item.managersCount, 0)}</p>
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
                  <th className="px-4 py-3">Creation</th>
                  <th className="px-4 py-3">Managers</th>
                  <th className="px-4 py-3">Statut</th>
                  <th className="px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} className="border-t border-[var(--line)] hover:bg-[var(--surface-soft)]/70">
                    <td className="px-4 py-3">
                      <p className="font-medium text-[var(--text)]">{item.name}</p>
                      <p className="text-xs text-[var(--muted)]">{item.id} · {item.membersCount} membres</p>
                    </td>
                    <td className="px-4 py-3">{item.region}</td>
                    <td className="px-4 py-3">{formatDate(item.createdAt)}</td>
                    <td className="px-4 py-3">{item.managersCount}</td>
                    <td className="px-4 py-3">
                      <StatusBadge label={item.status} tone={statusTone[item.status]} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2 text-xs">
                        <button onClick={() => openEditModal(item)} className="rounded-full border border-[var(--line)] px-2.5 py-1 font-semibold text-[var(--green-700)] hover:border-[var(--green-500)]">
                          Modifier
                        </button>
                        <button onClick={() => cycleCooperativeStatus(item.id)} className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--muted)] hover:text-[var(--green-700)]">
                          Changer statut
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
            <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${90 + index * 35}ms` }}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.name}</p>
                  <p className="text-xs text-[var(--muted)]">{item.id} · {item.region}</p>
                </div>
                <StatusBadge label={item.status} tone={statusTone[item.status]} />
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[11px] text-[var(--muted)]">Managers</p>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.managersCount}</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[11px] text-[var(--muted)]">Membres</p>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.membersCount}</p>
                </div>
              </div>

              <p className="mt-3 text-xs text-[var(--muted)]">Creation: {formatDate(item.createdAt)}</p>

              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <button onClick={() => openEditModal(item)} className="rounded-full border border-[var(--line)] px-2.5 py-1 font-semibold text-[var(--green-700)] hover:border-[var(--green-500)]">
                  Modifier
                </button>
                <button onClick={() => cycleCooperativeStatus(item.id)} className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--muted)] hover:text-[var(--green-700)]">
                  Changer statut
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      <LiquidGlassModal
        open={openModal}
        onClose={closeModal}
        title={modalTitle}
        subtitle="Mode local uniquement: les changements restent dans cette session."
        size="lg"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <button className="soft-focus w-full rounded-xl border border-white/85 bg-white/55 px-4 py-2 text-sm text-[var(--green-900)] hover:bg-white/75 sm:w-auto" onClick={closeModal} type="button">
              Annuler
            </button>
            <button className="soft-focus w-full rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)] sm:w-auto" form="cooperative-form" type="submit">
              {editingId ? "Mettre a jour" : "Creer"}
            </button>
          </div>
        }
      >
        <form id="cooperative-form" onSubmit={submitForm} className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm text-[var(--muted)] sm:col-span-2">
            Nom
            <input
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
              placeholder="Ex: Cooperative Delta"
            />
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

          <label className="text-sm text-[var(--muted)]">
            Date creation
            <input
              type="date"
              value={form.createdAt}
              onChange={(event) => setForm((prev) => ({ ...prev, createdAt: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            />
          </label>

          <label className="text-sm text-[var(--muted)]">
            Managers
            <input
              type="number"
              min={0}
              value={form.managersCount}
              onChange={(event) => setForm((prev) => ({ ...prev, managersCount: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            />
          </label>

          <label className="text-sm text-[var(--muted)]">
            Membres
            <input
              type="number"
              min={1}
              value={form.membersCount}
              onChange={(event) => setForm((prev) => ({ ...prev, membersCount: event.target.value }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            />
          </label>

          <label className="text-sm text-[var(--muted)] sm:col-span-2">
            Statut
            <select
              value={form.status}
              onChange={(event) => setForm((prev) => ({ ...prev, status: event.target.value as CooperativeStatus }))}
              className="soft-focus mt-1 w-full rounded-xl border border-white/85 bg-white/65 px-3 py-2.5 text-sm"
            >
              <option>Active</option>
              <option>En onboarding</option>
              <option>Suspendue</option>
            </select>
          </label>

          {formError && <p className="sm:col-span-2 rounded-xl border border-[#ecc9c9] bg-[#fff1f1]/90 px-3 py-2 text-xs text-[#8d3d3d]">{formError}</p>}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
