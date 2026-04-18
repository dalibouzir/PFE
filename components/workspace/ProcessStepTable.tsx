"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";
import type { ProcessStep } from "@/lib/api/types";

export function ProcessStepTable({
  steps,
  onEdit,
  onDelete,
}: {
  steps: ProcessStep[];
  onEdit: (step: ProcessStep) => void;
  onDelete: (step: ProcessStep) => void;
}) {
  if (steps.length === 0) {
    return (
      <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "80ms" }}>
        <p className="text-sm text-[var(--muted)]">Aucune etape enregistree pour ce lot.</p>
      </article>
    );
  }

  return (
    <article className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "80ms" }}>
      <div className="overflow-x-auto">
        <table className="wf-table min-w-full text-left text-sm">
          <thead>
            <tr>
              <th className="px-5 py-3.5">Etape</th>
              <th className="px-5 py-3.5">Date</th>
              <th className="px-5 py-3.5">Quantite in</th>
              <th className="px-5 py-3.5">Quantite out</th>
              <th className="px-5 py-3.5">Perte</th>
              <th className="px-5 py-3.5">Statut</th>
              <th className="px-5 py-3.5">Notes / Action</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((step) => (
              <tr key={step.id}>
                <td className="px-5 py-4 font-medium text-[var(--text)]">{step.type}</td>
                <td className="px-5 py-4">{step.date}</td>
                <td className="px-5 py-4">{step.qty_in.toFixed(1)} kg</td>
                <td className="px-5 py-4">{step.qty_out.toFixed(1)} kg</td>
                <td className="px-5 py-4">
                  <span className={step.warning ? "font-semibold text-[var(--danger)]" : "text-[var(--text)]"}>
                    {step.waste_qty.toFixed(1)} kg ({step.loss_pct.toFixed(1)}%)
                  </span>
                </td>
                <td className="px-5 py-4">
                  <StatusBadge label={step.status} tone={step.warning ? "warning" : "success"} />
                </td>
                <td className="px-5 py-4">
                  <p className="text-xs text-[var(--muted)]">{step.notes?.trim() || "Aucune note"}</p>
                  <div className="mt-1 flex items-center gap-2">
                    <button type="button" onClick={() => onEdit(step)} className="text-xs font-semibold text-[var(--primary)] hover:underline">
                      Modifier
                    </button>
                    <button type="button" onClick={() => onDelete(step)} className="text-xs font-semibold text-[var(--danger)] hover:underline">
                      Supprimer
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}
