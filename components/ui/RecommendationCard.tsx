import { StatusBadge } from "@/components/ui/StatusBadge";

export function RecommendationCard({
  recommendation,
  impact,
  severity,
}: {
  recommendation: string;
  impact: string;
  severity: "danger" | "warning" | "success";
}) {
  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "280ms" }}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-[var(--text)]">Top recommandations IA</h3>
        <StatusBadge label={severity === "danger" ? "Prioritaire" : severity === "warning" ? "Important" : "Optimisation"} tone={severity} />
      </div>
      <p className="mt-3 text-sm text-[var(--text)]">{recommendation}</p>
      <p className="mt-2 text-xs font-semibold text-[var(--ai-accent)]">Impact estime: {impact}</p>
    </article>
  );
}
