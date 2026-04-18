import { StatusBadge } from "@/components/ui/StatusBadge";

export type AIInsightItem = {
  id: string;
  issue: string;
  severity: "danger" | "warning" | "success";
};

export function AIInsightStrip({ items }: { items: AIInsightItem[] }) {
  const visibleItems = items.slice(0, 3);

  return (
    <section className="mt-4 grid gap-3 md:grid-cols-3">
      {visibleItems.map((item, index) => (
        <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${130 + index * 40}ms` }}>
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Signal operationnel</p>
            <StatusBadge label={item.severity === "danger" ? "Critique" : item.severity === "warning" ? "A suivre" : "Action recommandee"} tone={item.severity} />
          </div>
          <p className="mt-2 text-sm font-semibold text-[var(--text)]">{item.issue}</p>
        </article>
      ))}
    </section>
  );
}
