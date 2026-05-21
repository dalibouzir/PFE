"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";
import type { ProcessStep } from "@/lib/api/types";
import type { WorkflowPhase } from "@/lib/ui/lot-workflow";

const MINUTES_PER_DAY = 60 * 24;

function formatDurationDays(minutes?: number | null): string {
  if (minutes === null || minutes === undefined) return "-";
  const days = minutes / MINUTES_PER_DAY;
  const formatted = Number.isInteger(days) ? String(days) : String(Number(days.toFixed(2)));
  return `${formatted} j`;
}

export type ProcessTableRow = {
  key: string;
  order: number;
  label: string;
  icon: string;
  typeTag: string;
  phase: WorkflowPhase;
  status: "done" | "pending" | "warning" | "current";
  isExecutable?: boolean;
  step?: ProcessStep;
};

export function LotProcessTable({
  rows,
  onEnterStage,
  onEditStep,
}: {
  rows: ProcessTableRow[];
  onEnterStage: (row: ProcessTableRow) => void;
  onEditStep: (step: ProcessStep) => void;
}) {
  if (rows.length === 0) {
    return (
      <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "130ms" }}>
        <p className="text-sm text-[var(--muted)]">Aucune etape configuree.</p>
      </article>
    );
  }

  return (
    <article className="premium-card reveal min-w-0 overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "130ms" }}>
      <div className="thin-scrollbar max-w-full overflow-x-auto">
        <table className="wf-table w-full min-w-[980px] text-left text-sm">
          <thead>
            <tr>
              <th className="px-5 py-3.5">Etape</th>
              <th className="px-5 py-3.5">Type</th>
              <th className="px-5 py-3.5">Quantite entrante</th>
              <th className="px-5 py-3.5">Pertes</th>
              <th className="px-5 py-3.5">Quantite sortante</th>
              <th className="px-5 py-3.5">Date</th>
              <th className="px-5 py-3.5">Durée</th>
              <th className="px-5 py-3.5">Notes</th>
              <th className="px-5 py-3.5">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const step = row.step;
              const lossKg = step ? step.normalized_loss_value : null;
              const actionLabel = step
                ? step.stage_status === "pending"
                  ? "Completer"
                  : "Modifier"
                : row.isExecutable
                  ? "Demarrer"
                  : "En attente";
              const actionClass = step
                ? step.stage_status === "pending"
                  ? "rounded-xl border border-[var(--warning)] bg-[#FFF7E6] px-3 py-1.5 text-xs font-semibold text-[#A36A00] hover:brightness-95"
                  : "rounded-xl border border-[var(--info)] bg-[#EEF5FF] px-3 py-1.5 text-xs font-semibold text-[var(--info)] hover:brightness-95"
                : row.isExecutable
                  ? "rounded-xl border border-[var(--primary)] bg-[var(--primary)] px-3 py-1.5 text-xs font-semibold text-white hover:brightness-95"
                  : "cursor-not-allowed rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--muted)]";

              return (
                <tr key={row.key}>
                  <td className="px-5 py-3.5 whitespace-nowrap">
                    <p className="font-semibold text-[var(--text)]">
                      {row.order}. {row.icon} {row.label}
                    </p>
                  </td>
                  <td className="px-5 py-3.5">
                    <StatusBadge
                      label={row.typeTag}
                      tone={
                        row.status === "warning"
                          ? "warning"
                          : row.status === "done"
                            ? row.phase === "post_harvest"
                              ? "success"
                              : "info"
                            : "neutral"
                      }
                    />
                  </td>
                  <td className="px-5 py-3.5">{step ? `${step.qty_in.toFixed(2)} kg` : "-"}</td>
                  <td className={`px-5 py-3.5 ${step && row.status === "warning" ? "font-semibold text-[var(--danger)]" : ""}`}>
                    {step && lossKg !== null ? `-${lossKg.toFixed(2)} kg` : "-"}
                  </td>
                  <td className="px-5 py-3.5 font-semibold text-[var(--text)]">{step ? `${step.qty_out.toFixed(2)} kg` : "-"}</td>
                  <td className="px-5 py-3.5">{step ? step.date : "-"}</td>
                  <td className="px-5 py-3.5">{formatDurationDays(step?.duration_minutes)}</td>
                  <td className="px-5 py-3.5 text-xs text-[var(--muted)]">{step?.notes?.trim() || "-"}</td>
                  <td className="px-5 py-3.5">
                    <button
                      type="button"
                      onClick={() => (step ? onEditStep(step) : row.isExecutable ? onEnterStage(row) : null)}
                      className={actionClass}
                      disabled={!step && !row.isExecutable}
                    >
                      {actionLabel}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </article>
  );
}
