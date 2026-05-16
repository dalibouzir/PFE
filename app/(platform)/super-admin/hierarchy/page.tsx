"use client";

import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useHierarchyOverview } from "@/hooks/useSuperAdmin";

const toneByStatus: Record<string, "success" | "warning" | "info"> = {
  active: "success",
  onboarding: "info",
  suspended: "warning",
  inactive: "warning",
};

export default function SuperAdminHierarchyPage() {
  const { data, isLoading, isError } = useHierarchyOverview();

  if (isLoading) {
    return (
      <main>
        <PageIntro title="Hiérarchie" subtitle="Chargement de la hiérarchie plateforme..." />
      </main>
    );
  }

  if (isError || !data) {
    return (
      <main>
        <PageIntro title="Hiérarchie" subtitle="Impossible de charger la hiérarchie pour le moment." />
      </main>
    );
  }

  return (
    <main>
      <PageIntro title="Hiérarchie plateforme" subtitle="Institutions, cooperatives rattachées et cooperatives independantes." />

      <section className="space-y-4">
        {data.institutions.map((institution, index) => (
          <article key={institution.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${40 + index * 25}ms` }}>
            <div className="mb-3 flex items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-[var(--green-900)]">{institution.name}</p>
                <p className="text-xs text-[var(--muted)]">{institution.region || "Région non renseignée"}</p>
              </div>
              <StatusBadge label={institution.status} tone={toneByStatus[institution.status] ?? "info"} />
            </div>
            <div className="overflow-hidden rounded-xl border border-[var(--line)]">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
                  <tr>
                    <th className="px-3 py-2">Coopérative</th>
                    <th className="px-3 py-2">Région</th>
                    <th className="px-3 py-2">Téléphone</th>
                    <th className="px-3 py-2">Statut</th>
                  </tr>
                </thead>
                <tbody>
                  {institution.cooperatives.map((coop) => (
                    <tr key={coop.id} className="border-t border-[var(--line)]">
                      <td className="px-3 py-2">{coop.name}</td>
                      <td className="px-3 py-2">{coop.region}</td>
                      <td className="px-3 py-2">{coop.phone}</td>
                      <td className="px-3 py-2">
                        <StatusBadge label={coop.status} tone={toneByStatus[coop.status] ?? "info"} />
                      </td>
                    </tr>
                  ))}
                  {institution.cooperatives.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-3 py-4 text-center text-xs text-[var(--muted)]">
                        Aucune coopérative rattachée.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </article>
        ))}
      </section>

      <section className="premium-card reveal mt-4 rounded-2xl p-4" style={{ ["--delay" as string]: "200ms" }}>
        <h3 className="text-base font-semibold text-[var(--green-900)]">Coopératives indépendantes</h3>
        <div className="mt-3 overflow-hidden rounded-xl border border-[var(--line)]">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
              <tr>
                <th className="px-3 py-2">Coopérative</th>
                <th className="px-3 py-2">Région</th>
                <th className="px-3 py-2">Téléphone</th>
                <th className="px-3 py-2">Statut</th>
              </tr>
            </thead>
            <tbody>
              {data.independent_cooperatives.map((coop) => (
                <tr key={coop.id} className="border-t border-[var(--line)]">
                  <td className="px-3 py-2">{coop.name}</td>
                  <td className="px-3 py-2">{coop.region}</td>
                  <td className="px-3 py-2">{coop.phone}</td>
                  <td className="px-3 py-2">
                    <StatusBadge label={coop.status} tone={toneByStatus[coop.status] ?? "info"} />
                  </td>
                </tr>
              ))}
              {data.independent_cooperatives.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-3 py-4 text-center text-xs text-[var(--muted)]">
                    Aucune coopérative indépendante.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
