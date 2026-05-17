"use client";

export type StageMetric = {
  key: string;
  stage: string;
  status: "pending" | "done" | "cancelled";
  qtyIn: number;
  qtyOut: number;
  lossKg: number;
  lossPct: number;
  efficiencyPct: number;
  anomalies: number;
};

export function LotAnalyticsPanel({
  stageMetrics,
  initialQty,
  currentQty,
  finalQty,
  totalLossKg,
  totalLossPct,
  totalEfficiencyPct,
  interpretation,
  fallbackReason,
}: {
  stageMetrics: StageMetric[];
  initialQty: number;
  currentQty: number;
  finalQty: number | null;
  totalLossKg: number;
  totalLossPct: number;
  totalEfficiencyPct: number;
  interpretation: {
    bestStage: string | null;
    weakestStage: string | null;
    mainLossSource: string | null;
    verdict: string;
  };
  fallbackReason: string | null;
}) {
  if (fallbackReason) {
    return (
      <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "90ms" }}>
        <h3 className="text-base font-semibold text-[var(--text)]">Bilan matière</h3>
        <p className="mt-3 text-sm text-[var(--muted)]">Données insuffisantes pour calculer le bilan matière.</p>
        <p className="mt-1 text-xs text-[var(--muted)]">{fallbackReason}</p>
      </article>
    );
  }

  const flowLabels = ["Quantité initiale", ...stageMetrics.map((item) => item.stage), "Sortie finale"];

  return (
    <section className="space-y-4">
      <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "90ms" }}>
        <h3 className="text-base font-semibold text-[var(--text)]">Bilan matière post-récolte</h3>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-[11px] text-[var(--muted)]">Quantité initiale confirmée</p>
            <p className="text-sm font-semibold text-[var(--text)]">{initialQty.toFixed(1)} kg</p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-[11px] text-[var(--muted)]">Quantité actuelle</p>
            <p className="text-sm font-semibold text-[var(--text)]">{currentQty.toFixed(1)} kg</p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-[11px] text-[var(--muted)]">Quantité finale</p>
            <p className="text-sm font-semibold text-[var(--text)]">{finalQty === null ? "—" : `${finalQty.toFixed(1)} kg`}</p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-[11px] text-[var(--muted)]">Perte cumulée</p>
            <p className="text-sm font-semibold text-[var(--danger)]">{totalLossKg.toFixed(1)} kg</p>
            <p className="text-[11px] text-[var(--muted)]">{totalLossPct.toFixed(1)}%</p>
          </div>
          <div className="rounded-xl border border-[#CFE6D5] bg-[#F1FAF4] px-3 py-2">
            <p className="text-[11px] text-[var(--muted)]">Efficacité globale</p>
            <p className="text-sm font-semibold text-[#1E6C34]">{totalEfficiencyPct.toFixed(1)}%</p>
          </div>
        </div>
      </article>

      <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "100ms" }}>
        <h3 className="text-base font-semibold text-[var(--text)]">Flux matière par étape</h3>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {flowLabels.map((label, index) => (
            <div key={`${label}-${index}`} className="flex items-center gap-2">
              <span className="rounded-full border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-1 text-xs font-medium text-[var(--text)]">
                {label}
              </span>
              {index < flowLabels.length - 1 ? <span className="text-xs text-[var(--muted)]">→</span> : null}
            </div>
          ))}
        </div>
      </article>

      <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "110ms" }}>
        <h3 className="text-base font-semibold text-[var(--text)]">Performance par étape</h3>
        <div className="mt-3 space-y-2">
          {stageMetrics.map((item) => {
            const riskLabel = item.lossPct >= 12 ? "Critique" : item.lossPct >= 8 ? "À surveiller" : "Normal";
            const riskClass =
              item.lossPct >= 12
                ? "border-[#E8B9B9] bg-[#FFF1F2] text-[#9E2F36]"
                : item.lossPct >= 8
                  ? "border-[#ECD9B5] bg-[#FFF9EE] text-[#8D5D14]"
                  : "border-[#CFE6D5] bg-[#F1FAF4] text-[#1E6C34]";
            const statusLabel = item.status === "done" ? "Terminé" : item.status === "pending" ? "En cours" : "Annulé";
            return (
              <div key={item.key} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-[var(--text)]">{item.stage}</p>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-[var(--line)] bg-white px-2 py-0.5 text-[11px] font-semibold text-[var(--muted)]">{statusLabel}</span>
                    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${riskClass}`}>{riskLabel}</span>
                  </div>
                </div>
                <div className="mt-2 grid gap-1 text-xs text-[var(--muted)] sm:grid-cols-3">
                  <p>Entrée: <span className="font-semibold text-[var(--text)]">{item.qtyIn.toFixed(1)} kg</span></p>
                  <p>Sortie: <span className="font-semibold text-[var(--text)]">{item.qtyOut.toFixed(1)} kg</span></p>
                  <p>Perte: <span className="font-semibold text-[var(--danger)]">{item.lossKg.toFixed(1)} kg</span></p>
                </div>
                <div className="mt-1 grid gap-1 text-xs text-[var(--muted)] sm:grid-cols-3">
                  <p>Perte: <span className="font-semibold text-[var(--text)]">{item.lossPct.toFixed(1)}%</span></p>
                  <p>Efficacité: <span className="font-semibold text-[var(--info)]">{item.efficiencyPct.toFixed(1)}%</span></p>
                  <p>Anomalies: <span className="font-semibold text-[var(--text)]">{item.anomalies}</span></p>
                </div>
              </div>
            );
          })}
        </div>
      </article>

      <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "120ms" }}>
        <h3 className="text-base font-semibold text-[var(--text)]">Interprétation opérationnelle</h3>
        <div className="mt-3 grid gap-2 text-xs text-[var(--muted)] sm:grid-cols-2">
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p>Meilleure étape</p>
            <p className="text-sm font-semibold text-[var(--text)]">{interpretation.bestStage ?? "—"}</p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p>Étape la plus faible</p>
            <p className="text-sm font-semibold text-[var(--text)]">{interpretation.weakestStage ?? "—"}</p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 sm:col-span-2">
            <p>Source principale de perte</p>
            <p className="text-sm font-semibold text-[var(--text)]">{interpretation.mainLossSource ?? "—"}</p>
          </div>
          <div className="rounded-xl border border-[#CFE0F4] bg-[#F2F7FF] px-3 py-2 text-[#2F5C90] sm:col-span-2">
            <p className="text-[11px] uppercase tracking-wide">Lecture managériale</p>
            <p className="mt-1 text-sm font-semibold">{interpretation.verdict}</p>
          </div>
        </div>
      </article>
    </section>
  );
}
