import { StatusBadge } from "@/components/ui/StatusBadge";
import { managerRecentActivity } from "@/lib/mock-data";

export function RecentActivity() {
  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "250ms" }}>
      <h3 className="text-base font-semibold text-[var(--green-900)]">Activite recente</h3>
      <div className="mt-3 space-y-2">
        {managerRecentActivity.slice(0, 4).map((item) => (
          <div key={item.id} className="flex items-center justify-between rounded-xl border border-[var(--line)] px-3 py-2 text-sm">
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
        ))}
      </div>
    </article>
  );
}
