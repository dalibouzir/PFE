"use client";

import { useMemo, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { cooperativeRecords, type CooperativeRecord, type CooperativeStatus } from "@/lib/mock-data";

const statusTone: Record<CooperativeStatus, "success" | "info" | "warning"> = {
  Active: "success",
  "En onboarding": "info",
  Suspendue: "warning",
};

const regions: CooperativeRecord["region"][] = ["Thies", "Louga", "Casamance", "Kaolack", "Saint-Louis"];

function formatDate(value: string) {
  return new Intl.DateTimeFormat("fr-SN", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value));
}

export default function AdminCooperativesPage() {
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState<"Toutes" | CooperativeRecord["region"]>("Toutes");
  const [status, setStatus] = useState<"Tous" | CooperativeStatus>("Tous");
  const [openModal, setOpenModal] = useState(false);
  const [editing, setEditing] = useState<CooperativeRecord | null>(null);

  const filtered = useMemo(() => {
    return cooperativeRecords.filter((item) => {
      const byRegion = region === "Toutes" || item.region === region;
      const byStatus = status === "Tous" || item.status === status;
      const byText = `${item.name} ${item.id} ${item.region}`.toLowerCase().includes(query.toLowerCase());
      return byRegion && byStatus && byText;
    });
  }, [query, region, status]);

  const activeCount = filtered.filter((item) => item.status === "Active").length;

  return (
    <main>
      <PageIntro title="Cooperatives" subtitle="Gestion des cooperatives et suivi de leur statut." />

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
          <button
            className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]"
            onClick={() => {
              setEditing(null);
              setOpenModal(true);
            }}
          >
            Nouvelle cooperative
          </button>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
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
      </section>

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
                    <button
                      onClick={() => {
                        setEditing(item);
                        setOpenModal(true);
                      }}
                      className="text-xs font-semibold text-[var(--green-700)] hover:underline"
                    >
                      Modifier
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {openModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#103126]/45 px-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-lg rounded-2xl border border-[var(--line)] bg-white p-5 shadow-[0_30px_50px_rgba(15,47,34,0.24)]">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[var(--green-900)]">{editing ? "Modifier cooperative" : "Creer cooperative"}</h3>
                <p className="text-sm text-[var(--muted)]">Gestion locale demo</p>
              </div>
              <button className="text-[var(--muted)] hover:text-[var(--green-800)]" onClick={() => setOpenModal(false)}>
                Fermer
              </button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm text-[var(--muted)]">
                Nom
                <input defaultValue={editing?.name} className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm" />
              </label>
              <label className="text-sm text-[var(--muted)]">
                Region
                <select defaultValue={editing?.region ?? "Thies"} className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm">
                  {regions.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label className="text-sm text-[var(--muted)]">
                Nombre managers
                <input defaultValue={editing?.managersCount ?? 1} type="number" className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm" />
              </label>
              <label className="text-sm text-[var(--muted)]">
                Statut
                <select defaultValue={editing?.status ?? "Active"} className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm">
                  <option>Active</option>
                  <option>En onboarding</option>
                  <option>Suspendue</option>
                </select>
              </label>
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <button className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm" onClick={() => setOpenModal(false)}>
                Annuler
              </button>
              <button className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)]" onClick={() => setOpenModal(false)}>
                Enregistrer
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
