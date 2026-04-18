type ProductComparisonItem = {
  product: string;
  volume: number;
  efficiency: number;
  loss: number;
};

export function ProductComparisonChart({ items }: { items?: ProductComparisonItem[] }) {
  const rows = items ?? [];
  const displayRows =
    rows.length > 0
      ? rows
      : [
          { product: "Mango", volume: 1.8, efficiency: 76, loss: 8.1 },
          { product: "Arachide", volume: 1.3, efficiency: 73, loss: 9.4 },
          { product: "Mil", volume: 1.0, efficiency: 79, loss: 6.7 },
        ];

  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "180ms" }}>
      <div className="mb-4">
        <h3 className="text-base font-semibold text-[var(--text)]">Comparaison par produit</h3>
        <p className="text-xs text-[var(--muted)]">Mangue, arachide, mil</p>
      </div>

      <div className={rows.length === 0 ? "space-y-4 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3" : "space-y-4"}>
        {displayRows.map((item) => (
            <div key={item.product} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <div className="mb-2 flex items-center justify-between text-xs text-[var(--muted)]">
                <span className="font-semibold text-[var(--text)]">{item.product}</span>
                <span>{item.volume.toFixed(1)} t</span>
              </div>
              <div className="mb-1 text-[11px] text-[var(--muted)]">Efficacite</div>
              <div className="h-2 rounded-full bg-[#DFEBF5]">
                <div className="h-2 rounded-full bg-[var(--info)]" style={{ width: `${item.efficiency}%` }} />
              </div>
              <div className="mt-2 flex items-center justify-between text-[11px] text-[var(--muted)]">
                <span>Perte</span>
                <span className="font-semibold text-[var(--warning)]">{item.loss.toFixed(1)}%</span>
              </div>
            </div>
          ))}
      </div>
    </article>
  );
}
