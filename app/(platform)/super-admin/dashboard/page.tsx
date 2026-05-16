"use client";

import { useMemo } from "react";
import { KpiCard } from "@/components/ui/KpiCard";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useCooperativesGlobal, useInstitutions } from "@/hooks/useSuperAdmin";

export default function SuperAdminDashboardPage() {
  const { data: institutions = [] } = useInstitutions();
  const { data: cooperatives = [] } = useCooperativesGlobal();

  const inactiveInstitutions = institutions.filter((item) => item.status === "inactive").length;
  const suspendedCooperatives = cooperatives.filter((item) => item.status === "suspended").length;
  const independentCooperatives = cooperatives.filter((item) => !item.institution_id).length;

  const regionOverview = useMemo(() => {
    const regionMap = new Map<string, { institutions: number; cooperatives: number }>();
    institutions.forEach((item) => {
      const key = item.region || "Non renseignée";
      const row = regionMap.get(key) || { institutions: 0, cooperatives: 0 };
      row.institutions += 1;
      regionMap.set(key, row);
    });
    cooperatives.forEach((item) => {
      const key = item.region || "Non renseignée";
      const row = regionMap.get(key) || { institutions: 0, cooperatives: 0 };
      row.cooperatives += 1;
      regionMap.set(key, row);
    });
    return Array.from(regionMap.entries()).map(([region, values]) => ({ region, ...values }));
  }, [institutions, cooperatives]);

  return (
    <main>
      <PageIntro title="Super Admin Dashboard" subtitle="Pilotage global des institutions et des cooperatives WeeFarm." />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Total institutions" value={institutions.length} suffix="" delta={0} status="good" delay="0ms" />
        <KpiCard label="Total cooperatives" value={cooperatives.length} suffix="" delta={0} status="good" delay="45ms" />
        <KpiCard label="Cooperatives independantes" value={independentCooperatives} suffix="" delta={0} status="warning" delay="90ms" />
        <KpiCard label="Entites inactives/suspendues" value={inactiveInstitutions + suspendedCooperatives} suffix="" delta={0} status="critical" delay="135ms" />
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "180ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Répartition par région</h3>
          <div className="mt-3 space-y-2.5">
            {regionOverview.length === 0 ? (
              <p className="text-sm text-[var(--muted)]">Aucune donnée disponible.</p>
            ) : (
              regionOverview.map((item) => (
                <div key={item.region} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
                  <p className="text-sm font-medium text-[var(--text)]">{item.region}</p>
                  <p className="text-xs text-[var(--muted)]">
                    {item.institutions} institutions · {item.cooperatives} cooperatives
                  </p>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "220ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Etat des entités</h3>
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
              <p className="text-sm font-medium text-[var(--text)]">Institutions inactives</p>
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-[var(--green-900)]">{inactiveInstitutions}</p>
                <StatusBadge label="A suivre" tone="warning" />
              </div>
            </div>
            <div className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
              <p className="text-sm font-medium text-[var(--text)]">Cooperatives suspendues</p>
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-[var(--green-900)]">{suspendedCooperatives}</p>
                <StatusBadge label="A suivre" tone="warning" />
              </div>
            </div>
            <div className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
              <p className="text-sm font-medium text-[var(--text)]">Cooperatives independantes</p>
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-[var(--green-900)]">{independentCooperatives}</p>
                <StatusBadge label="Info" tone="info" />
              </div>
            </div>
          </div>
        </article>
      </section>
    </main>
  );
}
