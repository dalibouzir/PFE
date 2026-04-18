import Link from "next/link";
import type { QuickAction } from "@/lib/ui/types";

export function QuickActions() {
  const actions: QuickAction[] = [
    { label: "Ajouter membre", href: "/manager/membres", tone: "accent" },
    { label: "Nouvelle parcelle", href: "/manager/parcelles" },
    { label: "Nouvel input", href: "/manager/inputs" },
    { label: "Suivi stocks", href: "/manager/stocks" },
  ];

  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "280ms" }}>
      <h3 className="text-base font-semibold text-[var(--text)]">Actions rapides</h3>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {actions.map((action) => (
          <Link
            key={action.label}
            href={action.href}
            className={
              "soft-focus rounded-xl border px-3 py-2.5 text-left text-sm transition " +
              (action.tone === "accent"
                ? "border-[var(--primary)] bg-[var(--primary-light)] text-[var(--text)] hover:bg-[#dff0e6]"
                : "border-[var(--line)] bg-[var(--surface-soft)] text-[var(--text)] hover:border-[var(--primary)] hover:bg-[#f2f8f2]")
            }
          >
            {action.label}
          </Link>
        ))}
      </div>
    </article>
  );
}
