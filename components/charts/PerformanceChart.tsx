type TrendPoint = {
  period: string;
  production: number;
  loss: number;
  efficiency: number;
};

const WIDTH = 640;
const HEIGHT = 280;
const PADDING = 28;

function lineFrom(values: number[], max: number) {
  const step = (WIDTH - PADDING * 2) / (values.length - 1);
  return values
    .map((value, idx) => {
      const x = PADDING + idx * step;
      const y = HEIGHT - PADDING - (value / max) * (HEIGHT - PADDING * 2);
      return `${x},${y}`;
    })
    .join(" ");
}

export function PerformanceChart({ series }: { series?: TrendPoint[] }) {
  const safeSeries = series ?? [];
  const placeholderSeries: TrendPoint[] = [
    { period: "S1", production: 16, loss: 8.5, efficiency: 72 },
    { period: "S2", production: 18, loss: 8.1, efficiency: 74 },
    { period: "S3", production: 17, loss: 7.8, efficiency: 75 },
    { period: "S4", production: 19, loss: 7.2, efficiency: 78 },
  ];
  const displaySeries = safeSeries.length >= 2 ? safeSeries : placeholderSeries;
  const pertes = displaySeries.map((item) => item.loss);
  const efficacite = displaySeries.map((item) => item.efficiency);
  const production = displaySeries.map((item) => item.production);

  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "120ms" }}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-[var(--text)]">Tendance production et pertes</h3>
          <p className="text-xs text-[var(--muted)]">6 dernieres semaines</p>
        </div>
        <div className="flex gap-3 text-[11px] text-[var(--muted)]">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-[var(--info)]" /> Efficacite
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-[var(--warning)]" /> Perte
          </span>
        </div>
      </div>

      <div className={safeSeries.length < 2 ? "rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3" : ""}>
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full">
        <line x1={PADDING} y1={HEIGHT - PADDING} x2={WIDTH - PADDING} y2={HEIGHT - PADDING} stroke="#DCCFBC" />

        {production.map((value, idx) => {
          const barSpace = (WIDTH - PADDING * 2) / production.length;
          const barWidth = barSpace * 0.42;
          const x = PADDING + idx * barSpace + barSpace * 0.28;
          const y = HEIGHT - PADDING - (value / 35) * (HEIGHT - PADDING * 2);
          const h = HEIGHT - PADDING - y;
          return <rect key={idx} x={x} y={y} width={barWidth} height={h} rx="4" fill="#E9E2D5" />;
        })}

        <polyline fill="none" stroke="#2F80ED" strokeWidth="3" points={lineFrom(efficacite, 100)} />
        <polyline fill="none" stroke="#D4A017" strokeWidth="2.5" points={lineFrom(pertes, 20)} />
      </svg>
      </div>

      <div className={`mt-3 grid text-xs text-[var(--muted)] ${displaySeries.length >= 6 ? "grid-cols-6" : "grid-cols-4"}`}>
        {displaySeries.map((item) => (
          <span key={item.period}>{item.period}</span>
        ))}
      </div>
    </article>
  );
}
