"use client";

import { useMemo, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { managerAccounts, type ManagerStatus } from "@/lib/mock-data";

const toneByStatus: Record<ManagerStatus, "success" | "warning" | "info"> = {
  Actif: "success",
  Suspendu: "warning",
  "Invitation envoyee": "info",
};

export default function AdminManagersPage() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"Tous" | ManagerStatus>("Tous");
  const [openModal, setOpenModal] = useState(false);

  const filtered = useMemo(() => {
    return managerAccounts.filter((item) => {
      const byStatus = status === "Tous" || item.status === status;
      const text = `${item.name} ${item.email} ${item.cooperative} ${item.phone}`.toLowerCase();
      return byStatus && text.includes(query.toLowerCase());
    });
  }, [query, status]);

  const actives = filtered.filter((item) => item.status === "Actif").length;
  const suspended = filtered.filter((item) => item.status === "Suspendu").length;

  return (
    <main>
      <PageIntro title="Managers" subtitle="Gestion des comptes managers lies aux cooperatives." />

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
          <button
            onClick={() => setOpenModal(true)}
            className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]"
          >
            Creer manager
          </button>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
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
      </section>

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
                    <p className="text-xs text-[var(--muted)]">{item.region}</p>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge label={item.status} tone={toneByStatus[item.status]} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2 text-xs">
                      <button className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--green-700)] hover:border-[var(--green-500)]">
                        Basculer statut
                      </button>
                      <button className="rounded-full border border-[var(--line)] px-2.5 py-1 text-[var(--muted)] hover:text-[var(--green-700)]">
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

      {openModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#103126]/45 px-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-lg rounded-2xl border border-[var(--line)] bg-white p-5 shadow-[0_30px_50px_rgba(15,47,34,0.24)]">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[var(--green-900)]">Creer un compte manager</h3>
                <p className="text-sm text-[var(--muted)]">Creation locale pour la demo</p>
              </div>
              <button className="text-[var(--muted)] hover:text-[var(--green-800)]" onClick={() => setOpenModal(false)}>
                Fermer
              </button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm text-[var(--muted)]">
                Nom complet
                <input className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm" placeholder="Ex: Ousmane Diallo" />
              </label>
              <label className="text-sm text-[var(--muted)]">
                Telephone
                <input className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm" placeholder="+221 ..." />
              </label>
              <label className="text-sm text-[var(--muted)] sm:col-span-2">
                Email
                <input type="email" className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm" placeholder="nom@cooperative.sn" />
              </label>
              <label className="text-sm text-[var(--muted)] sm:col-span-2">
                Cooperative
                <select className="soft-focus mt-1 w-full rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm">
                  {Array.from(new Set(managerAccounts.map((item) => item.cooperative))).map((cooperative) => (
                    <option key={cooperative}>{cooperative}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <button className="soft-focus rounded-xl border border-[var(--line)] px-4 py-2 text-sm" onClick={() => setOpenModal(false)}>
                Annuler
              </button>
              <button className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)]" onClick={() => setOpenModal(false)}>
                Creer
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
