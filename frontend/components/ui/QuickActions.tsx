import Link from "next/link";
import { managerQuickActions } from "@/lib/mock-data";

export function QuickActions() {
  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "280ms" }}>
      <h3 className="text-base font-semibold text-[var(--green-900)]">Actions rapides</h3>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {managerQuickActions.map((action) => (
          <Link
            key={action.label}
            href={action.href}
            className={
              "soft-focus rounded-xl border px-3 py-2 text-left text-sm transition " +
              (action.tone === "accent"
                ? "border-[var(--green-500)] bg-[#ebf6ee] text-[var(--green-900)] hover:bg-[#e2f2e7]"
                : "border-[var(--line)] bg-[var(--surface-soft)] text-[var(--green-800)] hover:border-[var(--green-500)] hover:bg-[#eff7ef]")
            }
          >
            {action.label}
          </Link>
        ))}
      </div>
    </article>
  );
}
