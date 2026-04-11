import { PageIntro } from "@/components/ui/PageIntro";
import {
  analyticsEfficiencyByStep,
  analyticsLotComparison,
  analyticsLossByProduct,
  analyticsOverview,
  analyticsVolumeSeries,
} from "@/lib/mock-data";

export default function AnalytiquePage() {
  return (
    <main>
      <PageIntro title="Analytique" subtitle="Bilan matiere et performance operationnelle." />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {analyticsOverview.map((item, index) => (
          <article key={item.label} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${index * 45}ms` }}>
            <p className="text-xs uppercase tracking-wide text-[var(--muted)]">{item.label}</p>
            <p className="mt-1 text-2xl font-semibold text-[var(--green-900)]">{item.valeur}</p>
            <p className="text-xs text-[var(--green-700)]">{item.tendance}</p>
          </article>
        ))}
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "180ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Pertes par produit</h3>
          <div className="mt-3 space-y-3">
            {analyticsLossByProduct.map((item) => (
              <div key={item.produit}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="font-medium text-[var(--text)]">{item.produit}</span>
                  <span className="text-[#9a5e3d]">{item.perte.toFixed(1)}%</span>
                </div>
                <div className="h-2 rounded-full bg-[#e4eee6]">
                  <div className="h-2 rounded-full bg-[#cc8f6a]" style={{ width: `${item.perte * 6.2}%` }} />
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "220ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Efficacite par etape</h3>
          <div className="mt-3 space-y-2.5">
            {analyticsEfficiencyByStep.map((item) => (
              <div key={item.etape} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
                <div className="mb-1 flex items-center justify-between text-sm">
                  <p className="font-medium text-[var(--text)]">{item.etape}</p>
                  <p className="text-[var(--green-900)]">{item.efficacite.toFixed(1)}%</p>
                </div>
                <div className="h-2 rounded-full bg-[#dfebe1]">
                  <div className="h-2 rounded-full bg-[var(--green-700)]" style={{ width: `${item.efficacite}%` }} />
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "260ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Comparaison des lots</h3>
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-[var(--muted)]">
                <tr>
                  <th className="py-2 pr-4">Lot</th>
                  <th className="py-2 pr-4">Produit</th>
                  <th className="py-2 pr-4">Rendement</th>
                  <th className="py-2">Perte</th>
                </tr>
              </thead>
              <tbody>
                {analyticsLotComparison.map((item) => (
                  <tr key={item.lot} className="border-t border-[var(--line)]">
                    <td className="py-2 pr-4 font-medium text-[var(--text)]">{item.lot}</td>
                    <td className="py-2 pr-4">{item.produit}</td>
                    <td className="py-2 pr-4 text-[var(--green-900)]">{item.rendement.toFixed(1)}%</td>
                    <td className="py-2 text-[#9a5e3d]">{item.perte.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "300ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Volume traite</h3>
          <p className="text-xs text-[var(--muted)]">Tonnes par semaine</p>
          <div className="mt-4 flex h-48 items-end gap-2">
            {analyticsVolumeSeries.map((item) => (
              <div key={item.semaine} className="flex flex-1 flex-col items-center gap-2">
                <div className="w-full rounded-t-md bg-[linear-gradient(180deg,#74b48f_0%,#2f7f53_100%)]" style={{ height: `${item.volume * 6}px` }} />
                <span className="text-[11px] text-[var(--muted)]">{item.semaine}</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
