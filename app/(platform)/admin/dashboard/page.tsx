"use client";

import { useMemo } from "react";
import { KpiCard } from "@/components/ui/KpiCard";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useCooperatives, useUsers } from "@/hooks/useAdmin";

function isWithinDays(isoDate: string, days: number) {
  const value = new Date(isoDate).getTime();
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return value >= cutoff;
}

export default function AdminDashboardPage() {
  const { data: cooperatives = [] } = useCooperatives();
  const { data: users = [] } = useUsers();

  const managers = users.filter((user) => user.role === "manager");
  const activeManagers = managers.filter((user) => user.status === "active");
  const disabledUsers = users.filter((user) => user.status === "disabled");
  const newCoops = cooperatives.filter((coop) => isWithinDays(coop.created_at, 30));

  const regionOverview = useMemo(() => {
    const regionMap = new Map<string, { cooperatives: number; managers: number }>();
    const coopById = new Map(cooperatives.map((coop) => [coop.id, coop]));

    cooperatives.forEach((coop) => {
      const entry = regionMap.get(coop.region) || { cooperatives: 0, managers: 0 };
      entry.cooperatives += 1;
      regionMap.set(coop.region, entry);
    });

    managers.forEach((manager) => {
      if (!manager.cooperative_id) return;
      const coop = coopById.get(manager.cooperative_id);
      if (!coop) return;
      const entry = regionMap.get(coop.region) || { cooperatives: 0, managers: 0 };
      entry.managers += 1;
      regionMap.set(coop.region, entry);
    });

    return Array.from(regionMap.entries()).map(([region, counts]) => ({
      region,
      cooperatives: counts.cooperatives,
      managers: counts.managers,
    }));
  }, [cooperatives, managers]);

  const maxCoops = Math.max(1, ...regionOverview.map((item) => item.cooperatives));

  const statusOverview = useMemo(() => {
    const active = cooperatives.filter((coop) => coop.status === "active").length;
    const onboarding = cooperatives.filter((coop) => coop.status === "onboarding").length;
    const suspended = cooperatives.filter((coop) => coop.status === "suspended").length;
    return [
      { label: "Cooperatives actives", value: active, tone: "success" as const },
      { label: "Onboarding en cours", value: onboarding, tone: "info" as const },
      { label: "Cooperatives suspendues", value: suspended, tone: "warning" as const },
    ];
  }, [cooperatives]);

  const recentActivity = useMemo(() => {
    const coopEvents = cooperatives.map((coop) => ({
      id: `coop-${coop.id}`,
      title: "Cooperative creee",
      detail: `${coop.name} (${coop.region})`,
      date: coop.created_at,
      tone: "success" as const,
    }));

    const managerEvents = managers.map((manager) => ({
      id: `mgr-${manager.id}`,
      title: "Manager cree",
      detail: `${manager.full_name} (${manager.email})`,
      date: manager.created_at,
      tone: manager.status === "disabled" ? ("warning" as const) : ("info" as const),
    }));

    return [...coopEvents, ...managerEvents]
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
      .slice(0, 6);
  }, [cooperatives, managers]);

  return (
    <main>
      <PageIntro title="Tableau de bord" subtitle="Vue plateforme des cooperatives et des comptes managers." />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Total cooperatives" value={cooperatives.length} suffix="" delta={4.5} status="good" delay="0ms" />
        <KpiCard label="Managers actifs" value={activeManagers.length} suffix="" delta={2.8} status="good" delay="45ms" />
        <KpiCard label="Nouvelles cooperatives" value={newCoops.length} suffix="" delta={1.7} status="warning" delay="90ms" />
        <KpiCard label="Comptes desactives" value={disabledUsers.length} suffix="" delta={-1.4} status="critical" delay="135ms" />
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "180ms" }}>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-base font-semibold text-[var(--green-900)]">Cooperatives par region</h3>
            <p className="text-xs text-[var(--muted)]">Synthese active</p>
          </div>

          {regionOverview.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">Aucune cooperative enregistree.</p>
          ) : (
            <div className="space-y-3">
              {regionOverview.map((region) => (
                <div key={region.region}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="font-medium text-[var(--text)]">{region.region}</span>
                    <span className="text-[var(--muted)]">{region.cooperatives} coops · {region.managers} managers</span>
                  </div>
                  <div className="h-2 rounded-full bg-[#e2ede4]">
                    <div className="h-2 rounded-full bg-[var(--green-700)]" style={{ width: `${(region.cooperatives / maxCoops) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "220ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Etat plateforme</h3>
          <div className="mt-3 space-y-2">
            {statusOverview.map((item) => (
              <div key={item.label} className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium text-[var(--text)]">{item.label}</p>
                </div>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.value}</p>
                  <StatusBadge label={item.tone === "warning" ? "Suivi" : item.tone === "success" ? "Stable" : "Info"} tone={item.tone} />
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="premium-card reveal mt-4 rounded-2xl p-5" style={{ ["--delay" as string]: "260ms" }}>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-semibold text-[var(--green-900)]">Activite recente</h3>
          <span className="text-xs text-[var(--muted)]">Dernieres operations</span>
        </div>

        {recentActivity.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">Aucune activite recente.</p>
        ) : (
          <div className="space-y-2.5">
            {recentActivity.map((item) => (
              <div key={item.id} className="flex items-start justify-between gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium text-[var(--text)]">{item.title}</p>
                  <p className="text-xs text-[var(--muted)]">{item.detail}</p>
                </div>
                <div className="flex items-center gap-2">
                  <p className="text-xs text-[var(--muted)]">{new Date(item.date).toLocaleDateString("fr-FR")}</p>
                  <StatusBadge
                    label={item.tone === "success" ? "OK" : item.tone === "warning" ? "A suivre" : "Info"}
                    tone={item.tone}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
