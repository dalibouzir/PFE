"use client";

import { useMemo, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { members, parcels, productFilters, type MemberRecord, type MemberStatus, type ProductName } from "@/lib/mock-data";

const statusTone: Record<MemberStatus, "success" | "warning" | "info"> = {
  Actif: "success",
  Inactif: "warning",
  Saisonnier: "info",
};

export default function MembersPage() {
  const [query, setQuery] = useState("");
  const [product, setProduct] = useState<"Tous" | ProductName>("Tous");
  const [status, setStatus] = useState<"Tous" | MemberStatus>("Tous");
  const [selectedMember, setSelectedMember] = useState<MemberRecord | null>(null);

  const filtered = useMemo(() => {
    return members.filter((item) => {
      const byProduct = product === "Tous" || item.culturePrincipale === product;
      const byStatus = status === "Tous" || item.statut === status;
      const byText = `${item.nom} ${item.zone} ${item.telephone}`.toLowerCase().includes(query.toLowerCase());
      return byProduct && byStatus && byText;
    });
  }, [product, status, query]);

  const totalParcels = filtered.reduce((acc, item) => acc + item.parcelles, 0);
  const totalSurface = filtered.reduce((acc, item) => acc + item.superficieTotaleHa, 0);

  return (
    <main>
      <PageIntro title="Membres" subtitle="Suivi des producteurs et contexte agricole local." />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1.3fr_1fr_1fr]">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
            placeholder="Rechercher un membre..."
          />
          <select
            value={product}
            onChange={(event) => setProduct(event.target.value as "Tous" | ProductName)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            {productFilters.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as "Tous" | MemberStatus)}
            className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            <option>Actif</option>
            <option>Saisonnier</option>
            <option>Inactif</option>
          </select>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-xs text-[var(--muted)]">Membres visibles</p>
            <p className="text-lg font-semibold text-[var(--green-900)]">{filtered.length}</p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-xs text-[var(--muted)]">Parcelles</p>
            <p className="text-lg font-semibold text-[var(--green-900)]">{totalParcels}</p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-xs text-[var(--muted)]">Superficie totale</p>
            <p className="text-lg font-semibold text-[var(--green-900)]">{totalSurface.toFixed(1)} ha</p>
          </div>
        </div>
      </section>

      <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "90ms" }}>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3">Nom</th>
                <th className="px-4 py-3">Telephone</th>
                <th className="px-4 py-3">Zone</th>
                <th className="px-4 py-3">Culture principale</th>
                <th className="px-4 py-3">Parcelles</th>
                <th className="px-4 py-3">Statut</th>
                <th className="px-4 py-3">Details</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id} className="border-t border-[var(--line)] hover:bg-[var(--surface-soft)]/65">
                  <td className="px-4 py-3 font-medium text-[var(--text)]">{item.nom}</td>
                  <td className="px-4 py-3">{item.telephone}</td>
                  <td className="px-4 py-3">{item.zone}</td>
                  <td className="px-4 py-3">{item.culturePrincipale}</td>
                  <td className="px-4 py-3">{item.parcelles}</td>
                  <td className="px-4 py-3">
                    <StatusBadge label={item.statut} tone={statusTone[item.statut]} />
                  </td>
                  <td className="px-4 py-3">
                    <button className="text-xs font-semibold text-[var(--green-700)] hover:underline" onClick={() => setSelectedMember(item)}>
                      Voir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selectedMember && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#103126]/45 px-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-xl rounded-2xl border border-[var(--line)] bg-white p-5 shadow-[0_30px_50px_rgba(15,47,34,0.24)]">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[var(--green-900)]">{selectedMember.nom}</h3>
                <p className="text-sm text-[var(--muted)]">{selectedMember.zone} · {selectedMember.telephone}</p>
              </div>
              <button className="text-[var(--muted)] hover:text-[var(--green-800)]" onClick={() => setSelectedMember(null)}>
                Fermer
              </button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
                <p className="text-xs text-[var(--muted)]">Culture principale</p>
                <p className="text-sm font-semibold text-[var(--text)]">{selectedMember.culturePrincipale}</p>
              </div>
              <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
                <p className="text-xs text-[var(--muted)]">Superficie</p>
                <p className="text-sm font-semibold text-[var(--text)]">{selectedMember.superficieTotaleHa.toFixed(1)} ha</p>
              </div>
            </div>

            <div className="mt-4">
              <h4 className="text-sm font-semibold text-[var(--green-900)]">Parcelles associees</h4>
              <div className="mt-2 space-y-2">
                {parcels
                  .filter((parcel) => parcel.memberId === selectedMember.id)
                  .map((parcel) => (
                    <div key={parcel.id} className="rounded-xl border border-[var(--line)] px-3 py-2.5 text-sm">
                      <p className="font-medium text-[var(--text)]">{parcel.code}</p>
                      <p className="text-xs text-[var(--muted)]">{parcel.localisation} · {parcel.superficieHa.toFixed(1)} ha · {parcel.typeSol}</p>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
