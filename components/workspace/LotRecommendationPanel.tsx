"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";

export type LotRecommendationItem = {
  id: string;
  title: string;
  priority: "critical" | "warning" | "optimization";
  rationale: string;
  impactedStep: string;
  expectedEffect: string;
  action: string;
};

export function LotRecommendationPanel({ items }: { items: LotRecommendationItem[] }) {
  if (items.length === 0) {
    return (
      <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "100ms" }}>
        <p className="text-sm text-[var(--muted)]">Aucune recommandation IA disponible pour ce lot.</p>
      </article>
    );
  }

  return (
    <section className="grid gap-3">
      {items.map((item, index) => (
        <article key={item.id} className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: `${100 + index * 40}ms` }}>
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="text-base font-semibold text-[var(--text)]">{item.title}</h3>
              <p className="mt-1 text-xs text-[var(--muted)]">Etape impactee: {item.impactedStep}</p>
            </div>
            <StatusBadge
              label={item.priority === "critical" ? "Prioritaire" : item.priority === "warning" ? "Important" : "Optimisation"}
              tone={item.priority === "critical" ? "danger" : item.priority === "warning" ? "warning" : "ai"}
            />
          </div>

          <p className="mt-3 text-sm text-[var(--text)]">{item.rationale}</p>
          <p className="mt-2 text-xs text-[var(--ai-accent)]">Effet attendu: {item.expectedEffect}</p>

          <div className="mt-3 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
            <p className="text-xs font-semibold text-[var(--text)]">Action suggeree</p>
            <p className="mt-1 text-xs text-[var(--muted)]">{item.action}</p>
          </div>
        </article>
      ))}
    </section>
  );
}
