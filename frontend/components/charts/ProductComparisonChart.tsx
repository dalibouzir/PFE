import { productComparison } from "@/lib/mock-data";

export function ProductComparisonChart() {
  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "180ms" }}>
      <div className="mb-4">
        <h3 className="text-base font-semibold text-[var(--green-900)]">Comparaison par produit</h3>
        <p className="text-xs text-[var(--muted)]">Mangue, arachide, mil</p>
      </div>

      <div className="space-y-4">
        {productComparison.map((item) => (
          <div key={item.produit} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
            <div className="mb-2 flex items-center justify-between text-xs text-[var(--muted)]">
              <span className="font-semibold text-[var(--text)]">{item.produit}</span>
              <span>{item.volume.toFixed(1)} t</span>
            </div>
            <div className="mb-1 text-[11px] text-[var(--muted)]">Efficacité</div>
            <div className="h-2 rounded-full bg-[#deebdd]">
              <div className="h-2 rounded-full bg-[var(--green-700)]" style={{ width: `${item.efficacite}%` }} />
            </div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-[var(--muted)]">
              <span>Perte</span>
              <span className="font-semibold text-[#9a5e3d]">{item.perte.toFixed(1)}%</span>
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}
