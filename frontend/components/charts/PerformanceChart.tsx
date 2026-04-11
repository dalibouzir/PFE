import { managerTrendSeries } from "@/lib/mock-data";

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

export function PerformanceChart() {
  const pertes = managerTrendSeries.map((item) => item.perte);
  const efficacite = managerTrendSeries.map((item) => item.efficacite);
  const production = managerTrendSeries.map((item) => item.production);

  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "120ms" }}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Tendance production et pertes</h3>
          <p className="text-xs text-[var(--muted)]">6 dernieres semaines</p>
        </div>
        <div className="flex gap-3 text-[11px] text-[var(--muted)]">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-[#2f7f53]" /> Efficacite
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-[#cc8f6a]" /> Perte
          </span>
        </div>
      </div>

      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full">
        <line x1={PADDING} y1={HEIGHT - PADDING} x2={WIDTH - PADDING} y2={HEIGHT - PADDING} stroke="#d8e3d8" />

        {production.map((value, idx) => {
          const barSpace = (WIDTH - PADDING * 2) / production.length;
          const barWidth = barSpace * 0.42;
          const x = PADDING + idx * barSpace + barSpace * 0.28;
          const y = HEIGHT - PADDING - (value / 35) * (HEIGHT - PADDING * 2);
          const h = HEIGHT - PADDING - y;
          return <rect key={idx} x={x} y={y} width={barWidth} height={h} rx="4" fill="#dfece0" />;
        })}

        <polyline fill="none" stroke="#2f7f53" strokeWidth="3" points={lineFrom(efficacite, 100)} />
        <polyline fill="none" stroke="#cc8f6a" strokeWidth="2.5" points={lineFrom(pertes, 20)} />
      </svg>

      <div className="mt-3 grid grid-cols-6 text-xs text-[var(--muted)]">
        {managerTrendSeries.map((item) => (
          <span key={item.periode}>{item.periode}</span>
        ))}
      </div>
    </article>
  );
}
