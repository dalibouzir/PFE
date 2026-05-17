"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";

export type LotRecommendationItem = {
  id: string;
  title: string;
  priority: "critical" | "high" | "medium" | "low";
  problem: string;
  evidence: string;
  action: string;
  expectedImpact: string;
  confidence: string;
  caveat: string;
  impactedStep: string;
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
              <p className="mt-1 text-xs text-[var(--muted)]">Étape impactée: {item.impactedStep}</p>
            </div>
            <StatusBadge
              label={
                item.priority === "critical"
                  ? "Critique"
                  : item.priority === "high"
                    ? "Haute"
                    : item.priority === "medium"
                      ? "Moyenne"
                      : "Faible"
              }
              tone={item.priority === "critical" ? "danger" : item.priority === "high" ? "warning" : "ai"}
            />
          </div>

          <div className="mt-3 grid gap-2 text-xs text-[var(--muted)] sm:grid-cols-2">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 sm:col-span-2">
              <p className="font-semibold text-[var(--text)]">Problème détecté</p>
              <p className="mt-1">{item.problem}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 sm:col-span-2">
              <p className="font-semibold text-[var(--text)]">Éléments de preuve</p>
              <p className="mt-1">{item.evidence}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 sm:col-span-2">
              <p className="font-semibold text-[var(--text)]">Action recommandée</p>
              <p className="mt-1">{item.action}</p>
            </div>
            <div className="rounded-xl border border-[#CFE6D5] bg-[#F1FAF4] px-3 py-2">
              <p className="font-semibold text-[#1E6C34]">Impact attendu</p>
              <p className="mt-1 text-[var(--text)]">{item.expectedImpact}</p>
            </div>
            <div className="rounded-xl border border-[#CFE0F4] bg-[#F2F7FF] px-3 py-2">
              <p className="font-semibold text-[#2F5C90]">Confiance et réserve</p>
              <p className="mt-1 text-[var(--text)]">{item.confidence}</p>
            </div>
            <div className="rounded-xl border border-[#E6E0F7] bg-[#F8F5FF] px-3 py-2 sm:col-span-2">
              <p className="font-semibold text-[var(--text)]">Caveat</p>
              <p className="mt-1">{item.caveat}</p>
            </div>
          </div>
        </article>
      ))}
    </section>
  );
}
