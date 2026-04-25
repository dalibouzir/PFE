"use client";

import type { WorkflowPhase } from "@/lib/ui/lot-workflow";

export type TimelineStage = {
  key: string;
  order: number;
  label: string;
  icon: string;
  typeTag: string;
  phase: WorkflowPhase;
  status: "done" | "pending" | "warning" | "current";
  qtyOut?: number;
  lossKg?: number;
};

function groupByPhase(stages: TimelineStage[]) {
  return {
    post_harvest: stages.filter((item) => item.phase === "post_harvest"),
  };
}

export function LotProcessTimeline({ stages }: { stages: TimelineStage[] }) {
  const grouped = groupByPhase(stages);
  const postHarvestStages = [...grouped.post_harvest].sort((a, b) => a.order - b.order);

  return (
    <section className="min-w-0 space-y-4">
      <article className="premium-card reveal min-w-0 rounded-2xl p-4" style={{ ["--delay" as string]: "110ms" }}>
        <h3 className="text-base font-semibold text-[var(--text)]">Phase Post-recolte</h3>
        {postHarvestStages.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--muted)]">Aucune etape post-recolte configuree.</p>
        ) : (
          <div className="mt-3 space-y-2">
            {postHarvestStages.map((stage, index) => {
              const isLast = index === postHarvestStages.length - 1;
              const isDone = stage.status === "done";
              const boxClass =
                stage.status === "done"
                  ? "border-[#2F80ED] bg-[#EEF5FF]"
                  : stage.status === "warning"
                    ? "border-[#D4A017] bg-[#FFF5DC]"
                    : stage.status === "current"
                      ? "border-[#2F80ED] bg-[#EEF5FF]"
                      : "border-[var(--line)] bg-[var(--surface-soft)]";
              const dotClass = isDone
                ? "bg-[#2F80ED]"
                : stage.status === "warning"
                  ? "bg-[#D4A017]"
                  : stage.status === "current"
                    ? "bg-[#2F80ED]"
                    : "bg-[var(--line)]";
              const lineClass = isDone ? "bg-[#2F80ED]" : "bg-[var(--line)]";
              return (
                <div key={stage.key} className="relative pl-6">
                  <span className={`absolute left-2 top-3 h-2.5 w-2.5 rounded-full ${dotClass}`} />
                  {!isLast ? <span className={`absolute left-2 top-6 h-[calc(100%-1.5rem)] w-px ${lineClass}`} /> : null}
                  <div className={`rounded-xl border px-3 py-2 ${boxClass}`}>
                    <div className="flex items-center gap-2">
                      <span>{stage.icon}</span>
                      <p className="text-sm font-semibold text-[var(--text)]">
                        {stage.order}. {stage.label}
                      </p>
                    </div>
                    <p className="mt-1 text-[11px] text-[var(--muted)]">{stage.typeTag}</p>
                    {stage.status === "done" || stage.status === "warning" ? (
                      <p className={`mt-1 text-xs font-semibold ${stage.status === "warning" ? "text-[#8B6A00]" : "text-[#2F80ED]"}`}>
                        {stage.qtyOut?.toFixed(0)} kg · -{(stage.lossKg ?? 0).toFixed(0)} kg
                      </p>
                    ) : stage.status === "current" ? (
                      <p className="mt-1 text-xs font-semibold text-[#2F80ED]">Etape actuelle a executer</p>
                    ) : (
                      <p className="mt-1 text-xs text-[var(--muted)]">En attente de saisie</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </article>
    </section>
  );
}
