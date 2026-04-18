"use client";

export type StageMetric = {
  stage: string;
  qtyIn: number;
  qtyOut: number;
  lossPct: number;
  efficiencyPct: number;
  anomalies: number;
};

export function LotAnalyticsPanel({
  stageMetrics,
  totals,
  anomalyCount,
}: {
  stageMetrics: StageMetric[];
  totals: {
    qtyIn: number;
    qtyOut: number;
    lossKg: number;
    efficiencyPct: number;
  };
  anomalyCount: number;
}) {
  return (
    <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
      <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "90ms" }}>
        <h3 className="text-base font-semibold text-[var(--text)]">Analytique par etape</h3>
        {stageMetrics.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--muted)]">Pas assez de donnees pour analyser ce lot.</p>
        ) : (
          <div className="mt-3 space-y-2">
            {stageMetrics.map((item) => (
              <div key={item.stage} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-[var(--text)]">{item.stage}</p>
                  <p className="text-xs font-semibold text-[var(--muted)]">{item.anomalies} anomalie(s)</p>
                </div>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  In {item.qtyIn.toFixed(1)} kg · Out {item.qtyOut.toFixed(1)} kg · Perte {item.lossPct.toFixed(1)}%
                </p>
                <p className="mt-1 text-xs font-semibold text-[var(--info)]">Efficacite {item.efficiencyPct.toFixed(1)}%</p>
              </div>
            ))}
          </div>
        )}
      </article>

      <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "110ms" }}>
        <h3 className="text-base font-semibold text-[var(--text)]">Bilan matiere</h3>
        <div className="mt-3 grid gap-2">
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-[11px] text-[var(--muted)]">Quantite in cumulee</p>
            <p className="text-sm font-semibold text-[var(--text)]">{totals.qtyIn.toFixed(1)} kg</p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-[11px] text-[var(--muted)]">Quantite out cumulee</p>
            <p className="text-sm font-semibold text-[var(--text)]">{totals.qtyOut.toFixed(1)} kg</p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-[11px] text-[var(--muted)]">Perte cumulee</p>
            <p className="text-sm font-semibold text-[var(--danger)]">{totals.lossKg.toFixed(1)} kg</p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-[11px] text-[var(--muted)]">Efficacite globale</p>
            <p className="text-sm font-semibold text-[var(--text)]">{totals.efficiencyPct.toFixed(1)}%</p>
          </div>
          <div className={`rounded-xl border px-3 py-2 ${anomalyCount > 0 ? "border-[#E8B9B9] bg-[#FFEDEE]" : "border-[#BDD6FB] bg-[#EEF5FF]"}`}>
            <p className="text-[11px] text-[var(--muted)]">Anomalies detectees</p>
            <p className={`text-sm font-semibold ${anomalyCount > 0 ? "text-[var(--danger)]" : "text-[var(--info)]"}`}>{anomalyCount}</p>
          </div>
        </div>
      </article>
    </section>
  );
}
