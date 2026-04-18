"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";

export function LotSummaryHero({
  lotCode,
  productName,
  statusLabel,
  statusTone,
  initialQty,
  currentQty,
  cumulativeLossKg,
  efficiencyPct,
  latestStage,
  onCreateLot,
  onEditLot,
  onCreateStep,
}: {
  lotCode: string;
  productName: string;
  statusLabel: string;
  statusTone: "success" | "warning" | "danger" | "info";
  initialQty: number;
  currentQty: number;
  cumulativeLossKg: number;
  efficiencyPct: number;
  latestStage: string;
  onCreateLot: () => void;
  onEditLot: () => void;
  onCreateStep: () => void;
}) {
  return (
    <section className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "40ms" }}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Lot selectionne</p>
          <h2 className="mt-1 text-xl font-semibold text-[var(--text)]">{lotCode}</h2>
          <p className="text-sm text-[var(--muted)]">{productName}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge label={statusLabel} tone={statusTone} />
          <button type="button" onClick={onCreateStep} className="soft-focus wf-btn-primary px-3 py-1.5 text-xs font-semibold">
            Ajouter etape
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
        <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
          <p className="text-[11px] text-[var(--muted)]">Quantite initiale</p>
          <p className="text-sm font-semibold text-[var(--text)]">{initialQty.toFixed(1)} kg</p>
        </div>
        <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
          <p className="text-[11px] text-[var(--muted)]">Quantite actuelle</p>
          <p className="text-sm font-semibold text-[var(--text)]">{currentQty.toFixed(1)} kg</p>
        </div>
        <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
          <p className="text-[11px] text-[var(--muted)]">Perte cumulee</p>
          <p className="text-sm font-semibold text-[var(--danger)]">{cumulativeLossKg.toFixed(1)} kg</p>
        </div>
        <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
          <p className="text-[11px] text-[var(--muted)]">Efficacite</p>
          <p className="text-sm font-semibold text-[var(--text)]">{efficiencyPct.toFixed(1)}%</p>
        </div>
        <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
          <p className="text-[11px] text-[var(--muted)]">Stade actuel</p>
          <p className="text-sm font-semibold text-[var(--text)]">{latestStage}</p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" onClick={onEditLot} className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold">
          Modifier lot
        </button>
        <button type="button" onClick={onCreateLot} className="soft-focus wf-btn-secondary px-3 py-1.5 text-xs font-semibold">
          Nouveau lot
        </button>
      </div>
    </section>
  );
}
