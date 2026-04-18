import { StatusBadge } from "@/components/ui/StatusBadge";

type InsightAlert = {
  id: string;
  title: string;
  detail: string;
  tone: "danger" | "warning" | "info";
};

export function InsightPanel({ alerts }: { alerts?: InsightAlert[] }) {
  const resolvedAlerts = alerts ?? [];

  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "220ms" }}>
      <h3 className="text-base font-semibold text-[var(--text)]">Alertes operationnelles</h3>
      <p className="mt-1 text-xs text-[var(--muted)]">Lots a surveiller et seuils de stock</p>

      <div className="mt-4 space-y-3">
        {resolvedAlerts.length === 0 ? (
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3 text-sm text-[var(--muted)]">
            Aucune alerte active.
          </div>
        ) : (
          resolvedAlerts.map((alert) => (
            <div key={alert.id} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <div className="mb-1 flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-[var(--text)]">{alert.title}</p>
                <StatusBadge label={alert.tone === "danger" ? "Critique" : alert.tone === "warning" ? "A suivre" : "Info"} tone={alert.tone} />
              </div>
              <p className="text-xs text-[var(--muted)]">{alert.detail}</p>
            </div>
          ))
        )}
      </div>
    </article>
  );
}
