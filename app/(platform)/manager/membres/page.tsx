"use client";

import { useMemo, useState } from "react";
import { GlassViewToggle, type DataViewMode } from "@/components/ui/GlassViewToggle";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { members, parcels, productFilters, type MemberRecord, type MemberStatus, type ProductName } from "@/lib/mock-data";

const statusTone: Record<MemberStatus, "success" | "warning" | "info"> = {
  Actif: "success",
  Inactif: "warning",
  Saisonnier: "info",
};

type MemberTab = "profil" | "parcelles" | "activite";

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export default function MembersPage() {
  const [records] = useState<MemberRecord[]>(members);
  const [query, setQuery] = useState("");
  const [product, setProduct] = useState<"Tous" | ProductName>("Tous");
  const [status, setStatus] = useState<"Tous" | MemberStatus>("Tous");
  const [viewMode, setViewMode] = useState<DataViewMode>("table");
  const [selectedMember, setSelectedMember] = useState<MemberRecord | null>(null);
  const [activeTab, setActiveTab] = useState<MemberTab>("profil");

  const filtered = useMemo(() => {
    return records.filter((item) => {
      const byProduct = product === "Tous" || item.culturePrincipale === product;
      const byStatus = status === "Tous" || item.statut === status;
      const byText = `${item.nom} ${item.zone} ${item.telephone}`.toLowerCase().includes(query.toLowerCase());
      return byProduct && byStatus && byText;
    });
  }, [records, product, status, query]);

  const totalParcels = filtered.reduce((acc, item) => acc + item.parcelles, 0);
  const totalSurface = filtered.reduce((acc, item) => acc + item.superficieTotaleHa, 0);

  const memberParcels = useMemo(() => {
    if (!selectedMember) return [];
    return parcels.filter((parcel) => parcel.memberId === selectedMember.id);
  }, [selectedMember]);

  const memberActivity = useMemo(() => {
    if (!selectedMember) return [];

    const monthlyProjection = Math.round(selectedMember.superficieTotaleHa * 320);
    const productivity = Math.round((selectedMember.superficieTotaleHa / Math.max(selectedMember.parcelles, 1)) * 100) / 100;

    return [
      {
        id: "ACT-1",
        title: "Projection collecte (30 jours)",
        detail: `${monthlyProjection.toLocaleString("fr-FR")} kg estimes sur ${selectedMember.culturePrincipale}`,
      },
      {
        id: "ACT-2",
        title: "Densite parcellaire",
        detail: `${selectedMember.parcelles} parcelles · ${productivity.toFixed(2)} ha par parcelle`,
      },
      {
        id: "ACT-3",
        title: "Etat du profil",
        detail: `Statut actuel: ${selectedMember.statut} · Zone: ${selectedMember.zone}`,
      },
    ];
  }, [selectedMember]);

  const openMemberDetails = (member: MemberRecord) => {
    setSelectedMember(member);
    setActiveTab("profil");
  };

  return (
    <main>
      <PageIntro title="Membres" subtitle="Suivi adaptatif des producteurs avec vue table/cartes et fiche detaillee." />

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

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="grid grow gap-3 sm:grid-cols-3">
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

          <GlassViewToggle value={viewMode} onChange={setViewMode} className="shrink-0" />
        </div>
      </section>

      {filtered.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucun membre ne correspond aux filtres.</p>
        </section>
      ) : viewMode === "table" ? (
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
                      <button className="text-xs font-semibold text-[var(--green-700)] hover:underline" onClick={() => openMemberDetails(item)}>
                        Voir
                      </button>
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
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.nom}</p>
                  <p className="text-xs text-[var(--muted)]">{item.zone}</p>
                </div>
                <StatusBadge label={item.statut} tone={statusTone[item.statut]} />
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[11px] text-[var(--muted)]">Culture</p>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.culturePrincipale}</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[11px] text-[var(--muted)]">Superficie</p>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.superficieTotaleHa.toFixed(1)} ha</p>
                </div>
              </div>

              <p className="mt-3 text-xs text-[var(--muted)]">{item.telephone}</p>

              <button className="mt-3 rounded-full border border-[var(--line)] px-2.5 py-1 text-xs font-semibold text-[var(--green-700)] hover:border-[var(--green-500)]" onClick={() => openMemberDetails(item)}>
                Ouvrir fiche
              </button>
            </article>
          ))}
        </section>
      )}

      <LiquidGlassModal
        open={Boolean(selectedMember)}
        onClose={() => setSelectedMember(null)}
        title={selectedMember?.nom ?? "Details membre"}
        subtitle={selectedMember ? `${selectedMember.zone} · ${selectedMember.telephone}` : ""}
        size="lg"
        footer={
          <div className="flex justify-end">
            <button className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--green-800)]" onClick={() => setSelectedMember(null)} type="button">
              Fermer la fiche
            </button>
          </div>
        }
      >
        {selectedMember && (
          <div className="space-y-3">
            <div className="inline-flex rounded-full border border-white/80 bg-white/45 p-1">
              {([
                ["profil", "Profil"],
                ["parcelles", "Parcelles"],
                ["activite", "Activite"],
              ] as Array<[MemberTab, string]>).map(([tab, label]) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={cx(
                    "soft-focus rounded-full px-3 py-1.5 text-xs font-semibold transition-all",
                    activeTab === tab ? "bg-[var(--green-900)] text-white" : "text-[var(--green-900)] hover:bg-white/70",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>

            {activeTab === "profil" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-white/75 bg-white/52 p-3">
                  <p className="text-xs text-[var(--muted)]">Culture principale</p>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{selectedMember.culturePrincipale}</p>
                </div>
                <div className="rounded-xl border border-white/75 bg-white/52 p-3">
                  <p className="text-xs text-[var(--muted)]">Superficie</p>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{selectedMember.superficieTotaleHa.toFixed(1)} ha</p>
                </div>
                <div className="rounded-xl border border-white/75 bg-white/52 p-3">
                  <p className="text-xs text-[var(--muted)]">Parcelles</p>
                  <p className="text-sm font-semibold text-[var(--green-900)]">{selectedMember.parcelles}</p>
                </div>
                <div className="rounded-xl border border-white/75 bg-white/52 p-3">
                  <p className="text-xs text-[var(--muted)]">Statut</p>
                  <StatusBadge label={selectedMember.statut} tone={statusTone[selectedMember.statut]} />
                </div>
              </div>
            )}

            {activeTab === "parcelles" && (
              <div className="space-y-2">
                {memberParcels.length === 0 ? (
                  <p className="rounded-xl border border-white/75 bg-white/52 px-3 py-2 text-sm text-[var(--muted)]">Aucune parcelle associee.</p>
                ) : (
                  memberParcels.map((parcel) => (
                    <div key={parcel.id} className="rounded-xl border border-white/75 bg-white/52 px-3 py-2.5">
                      <p className="text-sm font-semibold text-[var(--green-900)]">{parcel.code}</p>
                      <p className="text-xs text-[var(--muted)]">{parcel.localisation}</p>
                      <p className="mt-1 text-xs text-[var(--muted)]">
                        {parcel.superficieHa.toFixed(1)} ha · {parcel.typeSol} · {parcel.statut}
                      </p>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === "activite" && (
              <div className="space-y-2">
                {memberActivity.map((item) => (
                  <div key={item.id} className="rounded-xl border border-white/75 bg-white/52 px-3 py-2.5">
                    <p className="text-sm font-semibold text-[var(--green-900)]">{item.title}</p>
                    <p className="text-xs text-[var(--muted)]">{item.detail}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </LiquidGlassModal>
    </main>
  );
}
