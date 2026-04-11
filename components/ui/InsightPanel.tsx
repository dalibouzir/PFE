import { StatusBadge } from "@/components/ui/StatusBadge";
import { criticalStocks, lotsToWatch } from "@/lib/mock-data";

export function InsightPanel() {
  const stockAlerts = criticalStocks.slice(0, 2).map((item) => ({
    id: item.id,
    title: `${item.produit} Grade ${item.grade}`,
    detail: `${item.quantiteTonnes.toFixed(1)} t / seuil ${item.seuilTonnes.toFixed(1)} t`,
    tone: "danger" as const,
  }));

  const lotAlerts = lotsToWatch.slice(0, 2).map((item) => ({
    id: item.code,
    title: `${item.code} · ${item.produit}`,
    detail: `${item.etape} · perte ${item.pertePct.toFixed(1)}%`,
    tone: item.pertePct >= 13 ? ("warning" as const) : ("info" as const),
  }));

  const alerts = [...stockAlerts, ...lotAlerts];

  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "220ms" }}>
      <h3 className="text-base font-semibold text-[var(--green-900)]">Alertes operationnelles</h3>
      <p className="mt-1 text-xs text-[var(--muted)]">Lots a surveiller et seuils de stock</p>

      <div className="mt-4 space-y-3">
        {alerts.map((alert) => (
          <div key={alert.id} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
            <div className="mb-1 flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-[var(--text)]">{alert.title}</p>
              <StatusBadge label={alert.tone === "danger" ? "Critique" : alert.tone === "warning" ? "A suivre" : "Info"} tone={alert.tone} />
            </div>
            <p className="text-xs text-[var(--muted)]">{alert.detail}</p>
          </div>
        ))}
      </div>
    </article>
  );
}
