import { AnimatedNumber } from "@/components/ui/AnimatedNumber";

export function KpiCard({
  label,
  value,
  suffix,
  delta,
  status,
  subtitle,
  emptyLabel,
  delay,
}: {
  label: string;
  value: number;
  suffix: string;
  delta: number;
  status: "good" | "warning" | "critical";
  subtitle?: string;
  emptyLabel?: string;
  delay?: string;
}) {
  const isEmpty = typeof emptyLabel === "string" && value === 0;
  const isPositive = delta >= 0;
  const trendSymbol = isPositive ? "↑" : "↓";
  const deltaClass = status === "good" ? "text-[var(--success)]" : status === "warning" ? "text-[var(--warning)]" : "text-[var(--danger)]";
  const dotClass = status === "good" ? "bg-[var(--success)]" : status === "warning" ? "bg-[var(--warning)]" : "bg-[var(--danger)]";

  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: delay ?? "0ms" }}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs uppercase tracking-wide text-[var(--muted)]">{label}</p>
        <span className={`h-2.5 w-2.5 rounded-full ${dotClass}`} aria-hidden />
      </div>
      <p className="mt-2 text-3xl font-semibold text-[var(--text)]">
        {isEmpty ? emptyLabel : <AnimatedNumber value={value} suffix={suffix} />}
      </p>
      {isEmpty ? (
        <p className="mt-2 text-xs text-[var(--muted)]">{subtitle ?? "Donnees recentes indisponibles."}</p>
      ) : (
        <p className={`mt-2 text-xs font-semibold ${deltaClass}`}>
          {trendSymbol} {Math.abs(delta).toFixed(1)}% vs periode precedente
        </p>
      )}
      {!isEmpty && subtitle ? <p className="mt-1 text-xs text-[var(--muted)]">{subtitle}</p> : null}
    </article>
  );
}
