"use client";

import { useMemo } from "react";
import { KpiCard } from "@/components/ui/KpiCard";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useInstitutionAdminCooperatives, useInstitutionAdminInstitution } from "@/hooks/useInstitutionAdmin";

const toneByStatus: Record<string, "success" | "warning" | "info"> = {
  active: "success",
  onboarding: "info",
  suspended: "warning",
  inactive: "warning",
};

export default function InstitutionAdminDashboardPage() {
  const { data: institution, isLoading: isInstitutionLoading, isError: isInstitutionError, error: institutionError } = useInstitutionAdminInstitution();
  const { data: cooperatives = [], isLoading: isCoopsLoading, isError: isCoopsError, error: coopsError } = useInstitutionAdminCooperatives();

  const activeCooperatives = cooperatives.filter((item) => item.status === "active").length;
  const suspendedCooperatives = cooperatives.filter((item) => item.status === "suspended").length;

  const statusOverview = useMemo(() => {
    const active = cooperatives.filter((item) => item.status === "active").length;
    const onboarding = cooperatives.filter((item) => item.status === "onboarding").length;
    const suspended = cooperatives.filter((item) => item.status === "suspended").length;
    return [
      { label: "Cooperatives actives", value: active, tone: "success" as const },
      { label: "Onboarding", value: onboarding, tone: "info" as const },
      { label: "Cooperatives suspendues", value: suspended, tone: "warning" as const },
    ];
  }, [cooperatives]);

  const recentCoops = useMemo(() => {
    return [...cooperatives]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 5);
  }, [cooperatives]);

  return (
    <main>
      <PageIntro title="Tableau de bord institution" subtitle="Pilotage des cooperatives rattachées à votre institution." />

      {(isInstitutionLoading || isCoopsLoading) && (
        <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "30ms" }}>
          <p className="text-sm text-[var(--muted)]">Chargement des donnees institution...</p>
        </section>
      )}

      {(isInstitutionError || isCoopsError) && (
        <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "30ms" }}>
          <p className="text-sm text-[#8f2f2f]">{(institutionError as Error)?.message || (coopsError as Error)?.message || "Impossible de charger les donnees."}</p>
        </section>
      )}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Institution chargee" value={institution ? 1 : 0} suffix="" delta={0} status="good" delay="0ms" />
        <KpiCard label="Total cooperatives" value={cooperatives.length} suffix="" delta={0} status="good" delay="45ms" />
        <KpiCard label="Cooperatives actives" value={activeCooperatives} suffix="" delta={0} status="good" delay="90ms" />
        <KpiCard label="Cooperatives suspendues" value={suspendedCooperatives} suffix="" delta={0} status="warning" delay="135ms" />
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "180ms" }}>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-base font-semibold text-[var(--green-900)]">Profil institution</h3>
            <StatusBadge label={institution?.status || "-"} tone={toneByStatus[institution?.status || ""] ?? "info"} />
          </div>
          <div className="space-y-2 text-sm text-[var(--text)]">
            <p><span className="text-[var(--muted)]">Nom:</span> {institution?.name || "-"}</p>
            <p><span className="text-[var(--muted)]">Region:</span> {institution?.region || "-"}</p>
            <p><span className="text-[var(--muted)]">Email:</span> {institution?.email || "-"}</p>
            <p><span className="text-[var(--muted)]">Telephone:</span> {institution?.phone || "-"}</p>
          </div>
        </article>

        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "220ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Etat des cooperatives</h3>
          <div className="mt-3 space-y-2">
            {statusOverview.map((item) => (
              <div key={item.label} className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
                <p className="text-sm font-medium text-[var(--text)]">{item.label}</p>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-[var(--green-900)]">{item.value}</p>
                  <StatusBadge label={item.tone === "warning" ? "A suivre" : item.tone === "success" ? "Stable" : "Info"} tone={item.tone} />
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="premium-card reveal mt-4 rounded-2xl p-5" style={{ ["--delay" as string]: "260ms" }}>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-semibold text-[var(--green-900)]">Apercu recent</h3>
          <span className="text-xs text-[var(--muted)]">Dernieres cooperatives</span>
        </div>

        {recentCoops.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">Aucune cooperative disponible.</p>
        ) : (
          <div className="space-y-2.5">
            {recentCoops.map((item) => (
              <div key={item.id} className="flex items-start justify-between gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium text-[var(--text)]">{item.name}</p>
                  <p className="text-xs text-[var(--muted)]">{item.region}</p>
                </div>
                <StatusBadge label={item.status} tone={toneByStatus[item.status] ?? "info"} />
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
