"use client";

import { phaseLabel, type WorkflowPhase } from "@/lib/ui/lot-workflow";

export type TimelineStage = {
  key: string;
  label: string;
  icon: string;
  typeTag: string;
  phase: WorkflowPhase;
  status: "done" | "pending" | "warning";
  qtyOut?: number;
  lossKg?: number;
};

function groupByPhase(stages: TimelineStage[]) {
  return {
    pre_harvest: stages.filter((item) => item.phase === "pre_harvest"),
    post_harvest: stages.filter((item) => item.phase === "post_harvest"),
  };
}

export function LotProcessTimeline({ stages }: { stages: TimelineStage[] }) {
  const grouped = groupByPhase(stages);
  const phases: Array<{ key: WorkflowPhase; title: string; items: TimelineStage[] }> = [
    { key: "pre_harvest", title: phaseLabel("pre_harvest"), items: grouped.pre_harvest },
    { key: "post_harvest", title: phaseLabel("post_harvest"), items: grouped.post_harvest },
  ];

  return (
    <section className="min-w-0 space-y-4">
      {phases.map((phase) => (
        <article key={phase.key} className="premium-card reveal min-w-0 rounded-2xl p-4" style={{ ["--delay" as string]: phase.key === "pre_harvest" ? "90ms" : "110ms" }}>
          <h3 className="text-base font-semibold text-[var(--text)]">Phase {phase.title}</h3>
          <div className="scroll-thin mt-3 flex max-w-full items-center gap-2 overflow-x-auto pb-1">
            {phase.items.map((stage, index) => {
              const boxClass =
                stage.status === "done"
                  ? "border-[#2E7D32] bg-[#E8F4EC]"
                  : stage.status === "warning"
                    ? "border-[#D4A017] bg-[#FFF5DC]"
                    : "border-[var(--line)] bg-[var(--surface-soft)]";
              return (
                <div key={stage.key} className="flex items-center gap-2">
                  <div className={`min-w-[170px] rounded-xl border px-3 py-2 ${boxClass}`}>
                    <div className="flex items-center gap-2">
                      <span>{stage.icon}</span>
                      <p className="text-sm font-semibold text-[var(--text)]">{stage.label}</p>
                    </div>
                    <p className="mt-1 text-[11px] text-[var(--muted)]">{stage.typeTag}</p>
                    {stage.status !== "pending" ? (
                      <p className={`mt-1 text-xs font-semibold ${stage.status === "warning" ? "text-[#8B6A00]" : "text-[var(--success)]"}`}>
                        {stage.qtyOut?.toFixed(0)} kg · -{(stage.lossKg ?? 0).toFixed(0)} kg
                      </p>
                    ) : (
                      <p className="mt-1 text-xs text-[var(--muted)]">En attente de saisie</p>
                    )}
                  </div>
                  {index < phase.items.length - 1 ? <span className="text-[var(--muted)]">→</span> : null}
                </div>
              );
            })}
          </div>
        </article>
      ))}
    </section>
  );
}
