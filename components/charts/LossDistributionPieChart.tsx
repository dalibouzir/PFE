"use client";

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

type LossSegmentTone = "success" | "warning" | "danger" | "info";

export type LossSegment = {
  id: string;
  label: string;
  value: number;
  tone: LossSegmentTone;
};

const toneColor: Record<LossSegmentTone, string> = {
  success: "var(--success)",
  warning: "var(--warning)",
  danger: "var(--danger)",
  info: "var(--info)",
};

export function LossDistributionPieChart({
  title,
  subtitle,
  segments,
}: {
  title: string;
  subtitle?: string;
  segments: LossSegment[];
}) {
  const safeSegments = segments.filter((segment) => segment.value > 0);
  const total = safeSegments.reduce((sum, segment) => sum + segment.value, 0);

  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "120ms" }}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-[var(--text)]">{title}</h3>
          {subtitle ? <p className="text-xs text-[var(--muted)]">{subtitle}</p> : null}
        </div>
      </div>

      {total <= 0 ? (
        <div className="mt-4 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-4 text-sm text-[var(--muted)]">
          Pas assez de donnees pour afficher la repartition des pertes.
        </div>
      ) : (
        <div className="mt-4 grid gap-4 md:grid-cols-[168px_1fr] md:items-center">
          <div className="mx-auto grid h-[168px] w-[168px] place-items-center rounded-full border border-[var(--line)] bg-[var(--surface-soft)] p-2">
            <div className="relative h-[152px] w-[152px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={safeSegments}
                    dataKey="value"
                    nameKey="label"
                    cx="50%"
                    cy="50%"
                    innerRadius={42}
                    outerRadius={68}
                    paddingAngle={2}
                    stroke="none"
                    isAnimationActive={true}
                    animationBegin={200}
                    animationDuration={800}
                  >
                    {safeSegments.map((segment) => (
                      <Cell key={segment.id} fill={toneColor[segment.tone]} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>

              <div className="pointer-events-none absolute inset-0 grid place-items-center">
                <div className="grid h-[86px] w-[86px] place-items-center rounded-full border border-[var(--line)] bg-[var(--surface)] text-center">
                  <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">Pertes</p>
                  <p className="text-sm font-semibold text-[var(--text)]">{total.toFixed(1)} kg</p>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            {safeSegments.map((segment) => {
              const percent = total > 0 ? (segment.value / total) * 100 : 0;
              return (
                <div key={segment.id} className="flex items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: toneColor[segment.tone] }} />
                    <p className="text-sm font-medium text-[var(--text)]">{segment.label}</p>
                  </div>
                  <p className="text-xs font-semibold text-[var(--muted)]">
                    {segment.value.toFixed(1)} kg ({percent.toFixed(0)}%)
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </article>
  );
}
