import { AnimatedNumber } from "@/components/ui/AnimatedNumber";

export function KpiCard({
  label,
  value,
  suffix,
  trend,
  delay,
}: {
  label: string;
  value: number;
  suffix: string;
  trend: string;
  delay?: string;
}) {
  return (
    <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: delay ?? "0ms" }}>
      <p className="text-xs uppercase tracking-wide text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-[var(--green-900)]">
        <AnimatedNumber value={value} suffix={suffix} />
      </p>
      <p className="mt-2 text-xs font-medium text-[var(--green-700)]">{trend}</p>
    </article>
  );
}
