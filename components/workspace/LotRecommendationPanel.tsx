"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";

export type LotRecommendationItem = {
  id: string;
  title: string;
  priority: "critical" | "high" | "medium" | "low";
  decisionStatus: "Stable" | "À surveiller" | "Prioritaire" | "Critique";
  mainReason: string;
  recommendedAction: string;
  focusStage: string;
  evidence: string[];
  confidence: string;
  caveat: string;
};

export function LotRecommendationPanel({ items, fallbackReason }: { items: LotRecommendationItem[]; fallbackReason?: string | null }) {
  if (items.length === 0) {
    return (
      <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "100ms" }}>
        <p className="text-sm text-[var(--muted)]">Données insuffisantes pour générer des recommandations exploitables.</p>
        {fallbackReason ? <p className="mt-1 text-xs text-[var(--muted)]">{fallbackReason}</p> : null}
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
              <p className="mt-1 text-xs text-[var(--muted)]">Étape à vérifier: {item.focusStage}</p>
            </div>
            <StatusBadge
              label={
                item.priority === "critical"
                  ? "Priorité critique"
                  : item.priority === "high"
                    ? "Priorité élevée"
                    : item.priority === "medium"
                      ? "Priorité moyenne"
                      : "Priorité faible"
              }
              tone={item.priority === "critical" ? "danger" : item.priority === "high" ? "warning" : "ai"}
            />
          </div>

          <div className="mt-3 grid gap-2 text-xs text-[var(--muted)] sm:grid-cols-2">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 sm:col-span-2">
              <p className="font-semibold text-[var(--text)]">Situation du lot</p>
              <p className="mt-1">{item.mainReason}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 sm:col-span-2">
              <p className="font-semibold text-[var(--text)]">Priorité</p>
              <p className="mt-1">{item.decisionStatus}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 sm:col-span-2">
              <p className="font-semibold text-[var(--text)]">Action recommandée</p>
              <p className="mt-1">{item.recommendedAction}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 sm:col-span-2">
              <p className="font-semibold text-[var(--text)]">Éléments de preuve</p>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {item.evidence.map((entry) => (
                  <li key={entry}>{entry}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-xl border border-[#CFE0F4] bg-[#F2F7FF] px-3 py-2">
              <p className="font-semibold text-[#2F5C90]">Réserve / confiance</p>
              <p className="mt-1 text-[var(--text)]">{item.confidence}</p>
            </div>
            <div className="rounded-xl border border-[#E6E0F7] bg-[#F8F5FF] px-3 py-2 sm:col-span-2">
              <p className="font-semibold text-[var(--text)]">Réserve</p>
              <p className="mt-1">{item.caveat}</p>
            </div>
          </div>
        </article>
      ))}
    </section>
  );
}
