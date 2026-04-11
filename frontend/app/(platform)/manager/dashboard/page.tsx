import dynamic from "next/dynamic";
import { KpiCard } from "@/components/ui/KpiCard";
import { InsightPanel } from "@/components/ui/InsightPanel";
import { PageIntro } from "@/components/ui/PageIntro";
import { QuickActions } from "@/components/ui/QuickActions";
import { RecentActivity } from "@/components/ui/RecentActivity";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { criticalStocks, lotsToWatch, managerDashboardKpis } from "@/lib/mock-data";

const PerformanceChart = dynamic(
  () => import("@/components/charts/PerformanceChart").then((mod) => mod.PerformanceChart),
  { loading: () => <div className="premium-card h-[340px] animate-pulse rounded-2xl" /> },
);

const ProductComparisonChart = dynamic(
  () => import("@/components/charts/ProductComparisonChart").then((mod) => mod.ProductComparisonChart),
  { loading: () => <div className="premium-card h-[260px] animate-pulse rounded-2xl" /> },
);

const dashboardFilters = ["Periode: 7 jours", "Produit: Tous", "Zone: Thies-Louga"];

export default function ManagerDashboardPage() {
  return (
    <main>
      <PageIntro title="Tableau de bord" subtitle="Suivi operationnel des collectes, lots et transformations." />

      <section className="mb-4 flex flex-wrap gap-2">
        {dashboardFilters.map((item) => (
          <button
            key={item}
            className="soft-focus rounded-full border border-[var(--line)] bg-[var(--surface)] px-3 py-1.5 text-xs text-[var(--muted)] hover:border-[var(--green-500)] hover:text-[var(--green-800)]"
          >
            {item}
          </button>
        ))}
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {managerDashboardKpis.map((kpi, index) => (
          <KpiCard key={kpi.id} label={kpi.label} value={kpi.value} suffix={kpi.suffix ?? ""} trend={kpi.trend} delay={`${index * 50}ms`} />
        ))}
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[1.3fr_0.9fr]">
        <PerformanceChart />
        <ProductComparisonChart />
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <InsightPanel />
        <RecentActivity />
        <QuickActions />
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "330ms" }}>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-base font-semibold text-[var(--green-900)]">Lots a surveiller</h3>
            <a href="/manager/lots" className="text-xs font-semibold text-[var(--green-700)] hover:underline">
              Ouvrir lots
            </a>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-[var(--muted)]">
                <tr>
                  <th className="py-2 pr-4">Lot</th>
                  <th className="py-2 pr-4">Produit</th>
                  <th className="py-2 pr-4">Etape</th>
                  <th className="py-2 pr-4">Perte</th>
                  <th className="py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {lotsToWatch.map((item) => (
                  <tr key={item.code} className="border-t border-[var(--line)]">
                    <td className="py-2 pr-4 font-medium text-[var(--text)]">{item.code}</td>
                    <td className="py-2 pr-4">{item.produit}</td>
                    <td className="py-2 pr-4">{item.etape}</td>
                    <td className="py-2 pr-4 text-[#9a5e3d]">{item.pertePct.toFixed(1)}%</td>
                    <td className="py-2">
                      <span className="text-xs text-[var(--green-700)]">{item.action}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "360ms" }}>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-base font-semibold text-[var(--green-900)]">Stocks critiques</h3>
            <a href="/manager/stocks" className="text-xs font-semibold text-[var(--green-700)] hover:underline">
              Ouvrir stocks
            </a>
          </div>

          <div className="space-y-2.5">
            {criticalStocks.map((item) => (
              <div key={item.id} className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium text-[var(--text)]">
                    {item.produit} Grade {item.grade}
                  </p>
                  <p className="text-xs text-[var(--muted)]">
                    {item.entrepot} · MAJ {item.derniereMiseAJour}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-[var(--green-900)]">
                    {item.quantiteTonnes.toFixed(1)} t / {item.seuilTonnes.toFixed(1)} t
                  </p>
                  <StatusBadge label={item.statut} tone={item.statut === "Critique" ? "danger" : "warning"} />
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
