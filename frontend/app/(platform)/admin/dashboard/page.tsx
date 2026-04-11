import { KpiCard } from "@/components/ui/KpiCard";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { adminDashboardKpis, adminRecentActivity, adminRegionOverview, adminStatusOverview } from "@/lib/mock-data";

export default function AdminDashboardPage() {
  const maxCoops = Math.max(...adminRegionOverview.map((item) => item.cooperatives));

  return (
    <main>
      <PageIntro title="Tableau de bord" subtitle="Vue plateforme des cooperatives et des comptes managers." />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {adminDashboardKpis.map((kpi, index) => (
          <KpiCard key={kpi.id} label={kpi.label} value={kpi.value} suffix={kpi.suffix ?? ""} trend={kpi.trend} delay={`${index * 45}ms`} />
        ))}
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "180ms" }}>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-base font-semibold text-[var(--green-900)]">Cooperatives par region</h3>
            <p className="text-xs text-[var(--muted)]">Widget plateforme</p>
          </div>

          <div className="space-y-3">
            {adminRegionOverview.map((region) => (
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
        </article>

        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "220ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Etat plateforme</h3>
          <div className="mt-3 space-y-2">
            {adminStatusOverview.map((item) => (
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
          <span className="text-xs text-[var(--muted)]">7 derniers jours</span>
        </div>

        <div className="space-y-2.5">
          {adminRecentActivity.map((item) => (
            <div key={item.id} className="flex items-start justify-between gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
              <div>
                <p className="text-sm font-medium text-[var(--text)]">{item.title}</p>
                <p className="text-xs text-[var(--muted)]">{item.detail}</p>
              </div>
              <div className="flex items-center gap-2">
                <p className="text-xs text-[var(--muted)]">{item.date}</p>
                <StatusBadge
                  label={item.tone === "success" ? "OK" : item.tone === "warning" ? "A suivre" : item.tone === "danger" ? "Critique" : "Info"}
                  tone={item.tone}
                />
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
