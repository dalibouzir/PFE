"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";

export type ActiveLotItem = {
  id: string;
  code: string;
  productName: string;
  seasonLabel: string;
  phaseLabel: string;
  stepsDone: number;
  stepsTotal: number;
  currentQty: number;
  unit: string;
  progressPct: number;
  statusLabel: string;
  statusTone: "success" | "warning" | "danger" | "info";
};

export function LotActiveSidebar({
  items,
  selectedId,
  onSelect,
}: {
  items: ActiveLotItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <aside
      className="premium-card reveal flex max-h-[70svh] flex-col overflow-hidden rounded-2xl p-4 xl:max-h-[calc(100svh-10rem)]"
      style={{ ["--delay" as string]: "40ms" }}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xl font-semibold text-[var(--text)]">Lots actifs</h3>
        <p className="text-xs text-[var(--muted)]">{items.length}</p>
      </div>

      <div className="scroll-thin no-scrollbar mt-3 flex-1 space-y-2.5 overflow-y-auto pr-1">
        {items.length === 0 ? (
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-3 text-sm text-[var(--muted)]">
            Aucun lot actif.
          </div>
        ) : (
          items.map((item) => {
            const selected = selectedId === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelect(item.id)}
                className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                  selected
                    ? "border-[var(--info)] bg-[#EEF5FF]"
                    : "border-[var(--line)] bg-[var(--surface-soft)] hover:border-[var(--primary)]"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <StatusBadge label={item.phaseLabel} tone={item.phaseLabel.toLowerCase().includes("post") ? "success" : "warning"} />
                  <p className="text-sm font-semibold text-[var(--text)]">{item.productName}</p>
                </div>
                <p className="mt-2 text-xs text-[var(--muted)]">
                  {item.code} · {item.seasonLabel || "Saison N/A"}
                </p>
                <div className="mt-2 h-2 rounded-full bg-[#e1d8c7]">
                  <div className="h-2 rounded-full bg-[var(--info)]" style={{ width: `${Math.max(0, Math.min(100, item.progressPct))}%` }} />
                </div>
                <div className="mt-1.5 flex items-center justify-between text-[11px] text-[var(--muted)]">
                  <span>
                    {item.stepsDone}/{item.stepsTotal} etapes
                  </span>
                  <span>{item.currentQty.toFixed(2)} {item.unit}</span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
