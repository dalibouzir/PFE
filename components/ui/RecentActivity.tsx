import { StatusBadge } from "@/components/ui/StatusBadge";
import type { ActivityItem } from "@/lib/ui/types";

export function RecentActivity({ items }: { items?: ActivityItem[] }) {
  const activityItems = items ?? [];

  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "250ms" }}>
      <h3 className="text-base font-semibold text-[var(--text)]">Activite recente</h3>
      <div className="mt-3 space-y-2">
        {activityItems.length === 0 ? (
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-3 text-sm text-[var(--muted)]">
            Aucune activite recente.
          </div>
        ) : (
          activityItems.slice(0, 3).map((item) => (
          <div key={item.id} className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-3 text-sm">
            <div>
              <p className="font-medium text-[var(--text)]">{item.title}</p>
              <p className="text-xs text-[var(--muted)]">{item.detail}</p>
              <p className="text-[11px] text-[var(--muted)]">{item.date}</p>
            </div>
            <StatusBadge
              label={item.tone === "danger" ? "Critique" : item.tone === "warning" ? "Suivi" : item.tone === "success" ? "OK" : "Info"}
              tone={item.tone}
            />
          </div>
          ))
        )}
      </div>
    </article>
  );
}
