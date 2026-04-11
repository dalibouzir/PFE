import { PageIntro } from "@/components/ui/PageIntro";
import { productOverview } from "@/lib/mock-data";

export default function ProduitsPage() {
  return (
    <main>
      <PageIntro title="Produits" subtitle="Vue compacte sur mangue, arachide et mil." />

      <section className="grid gap-4 lg:grid-cols-3">
        {productOverview.map((item, index) => (
          <article key={item.produit} className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: `${index * 60}ms` }}>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-[var(--green-900)]">{item.produit}</h3>
              <span className="rounded-full bg-[var(--green-200)] px-2 py-1 text-[11px] font-semibold text-[var(--green-800)]">{item.lotsActifs} lots</span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="rounded-xl bg-[var(--surface-soft)] p-3">
                <p className="text-[11px] text-[var(--muted)]">Volume collecte</p>
                <p className="font-semibold text-[var(--text)]">{item.volumeCollecteTonnes.toFixed(1)} t</p>
              </div>
              <div className="rounded-xl bg-[var(--surface-soft)] p-3">
                <p className="text-[11px] text-[var(--muted)]">Stock actuel</p>
                <p className="font-semibold text-[var(--text)]">{item.stockActuelTonnes.toFixed(1)} t</p>
              </div>
              <div className="rounded-xl bg-[var(--surface-soft)] p-3">
                <p className="text-[11px] text-[var(--muted)]">Perte moyenne</p>
                <p className="font-semibold text-[#9a5e3d]">{item.perteMoyennePct.toFixed(1)}%</p>
              </div>
              <div className="rounded-xl bg-[var(--surface-soft)] p-3">
                <p className="text-[11px] text-[var(--muted)]">Rendement</p>
                <p className="font-semibold text-[var(--green-900)]">{(100 - item.perteMoyennePct).toFixed(1)}%</p>
              </div>
            </div>

            <div className="mt-4">
              <p className="mb-2 text-xs text-[var(--muted)]">Repartition grades</p>
              <div className="h-2 overflow-hidden rounded-full bg-[#e3eee5]">
                <div className="h-full bg-[#2f7f53]" style={{ width: `${item.gradeA}%` }} />
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-[var(--muted)]">
                <span>A: {item.gradeA}%</span>
                <span>B: {item.gradeB}%</span>
                <span>C: {item.gradeC}%</span>
              </div>
            </div>
          </article>
        ))}
      </section>

      <section className="premium-card reveal mt-4 rounded-2xl p-5" style={{ ["--delay" as string]: "220ms" }}>
        <h3 className="text-base font-semibold text-[var(--green-900)]">Synthese produits</h3>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-[var(--muted)]">
              <tr>
                <th className="py-2 pr-4">Produit</th>
                <th className="py-2 pr-4">Collecte</th>
                <th className="py-2 pr-4">Stock</th>
                <th className="py-2 pr-4">Lots actifs</th>
                <th className="py-2">Perte moyenne</th>
              </tr>
            </thead>
            <tbody>
              {productOverview.map((item) => (
                <tr key={item.produit} className="border-t border-[var(--line)]">
                  <td className="py-2 pr-4 font-medium text-[var(--text)]">{item.produit}</td>
                  <td className="py-2 pr-4">{item.volumeCollecteTonnes.toFixed(1)} t</td>
                  <td className="py-2 pr-4">{item.stockActuelTonnes.toFixed(1)} t</td>
                  <td className="py-2 pr-4">{item.lotsActifs}</td>
                  <td className="py-2 text-[#9a5e3d]">{item.perteMoyennePct.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
