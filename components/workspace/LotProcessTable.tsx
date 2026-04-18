"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";
import type { ProcessStep } from "@/lib/api/types";
import type { WorkflowPhase } from "@/lib/ui/lot-workflow";

export type ProcessTableRow = {
  key: string;
  label: string;
  icon: string;
  typeTag: string;
  phase: WorkflowPhase;
  status: "done" | "pending" | "warning";
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
      <div className="max-w-full overflow-x-auto">
        <table className="wf-table min-w-full text-left text-sm">
          <thead>
            <tr>
              <th className="px-5 py-3.5">Etape</th>
              <th className="px-5 py-3.5">Type</th>
              <th className="px-5 py-3.5">Quantite entrante</th>
              <th className="px-5 py-3.5">Pertes</th>
              <th className="px-5 py-3.5">Quantite sortante</th>
              <th className="px-5 py-3.5">Date</th>
              <th className="px-5 py-3.5">Notes</th>
              <th className="px-5 py-3.5">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const step = row.step;
              const lossKg = step ? Math.max(step.waste_qty, step.qty_in - step.qty_out, 0) : null;
              const actionLabel = step ? "Modifier" : "Saisir";
              const actionClass = step
                ? "rounded-xl border border-[var(--info)] bg-[#EEF5FF] px-3 py-1.5 text-xs font-semibold text-[var(--info)] hover:brightness-95"
                : "rounded-xl border border-[var(--primary)] bg-[var(--primary)] px-3 py-1.5 text-xs font-semibold text-white hover:brightness-95";

              return (
                <tr key={row.key}>
                  <td className="px-5 py-3.5">
                    <p className="font-semibold text-[var(--text)]">
                      {row.icon} {row.label}
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
                  <td className="px-5 py-3.5">{step ? `${step.qty_in.toFixed(0)} kg` : "-"}</td>
                  <td className={`px-5 py-3.5 ${step && row.status === "warning" ? "font-semibold text-[var(--danger)]" : ""}`}>
                    {step && lossKg !== null ? `-${lossKg.toFixed(0)} kg` : "-"}
                  </td>
                  <td className="px-5 py-3.5 font-semibold text-[var(--text)]">{step ? `${step.qty_out.toFixed(0)} kg` : "-"}</td>
                  <td className="px-5 py-3.5">{step ? step.date : "-"}</td>
                  <td className="px-5 py-3.5 text-xs text-[var(--muted)]">{step?.notes?.trim() || "-"}</td>
                  <td className="px-5 py-3.5">
                    <button
                      type="button"
                      onClick={() => (step ? onEditStep(step) : onEnterStage(row))}
                      className={actionClass}
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
