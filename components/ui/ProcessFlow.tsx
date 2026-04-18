import { StatusBadge } from "@/components/ui/StatusBadge";

export type ProcessFlowStage = {
  id: string;
  name: string;
  input: number;
  output: number;
  lossPct: number;
  abnormal: boolean;
};

export function ProcessFlow({ stages }: { stages: ProcessFlowStage[] }) {
  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "220ms" }}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-semibold text-[var(--text)]">Flux matiere</h3>
        <p className="text-xs text-[var(--muted)]">Pre-recolte et post-recolte</p>
      </div>

      <div className="grid gap-3 lg:grid-cols-4">
        {stages.map((stage) => (
          <div
            key={stage.id}
            className={
              "rounded-xl border bg-[var(--surface-soft)] p-3 " + (stage.abnormal ? "border-[#E9B7B7]" : "border-[var(--line)]")
            }
          >
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold text-[var(--text)]">{stage.name}</p>
              <StatusBadge label={stage.abnormal ? "Anormal" : "Stable"} tone={stage.abnormal ? "danger" : "success"} />
            </div>
            <p className="text-xs text-[var(--muted)]">Quantite in: {stage.input.toFixed(1)} kg</p>
            <p className="text-xs text-[var(--muted)]">Quantite out: {stage.output.toFixed(1)} kg</p>
            <p className={`mt-2 text-xs font-semibold ${stage.abnormal ? "text-[var(--danger)]" : "text-[var(--success)]"}`}>Perte: {stage.lossPct.toFixed(1)}%</p>
          </div>
        ))}
      </div>
    </article>
  );
}
