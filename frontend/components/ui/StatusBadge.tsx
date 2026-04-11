import type { BadgeTone } from "@/lib/mock-data";

const toneClass: Record<BadgeTone, string> = {
  success: "bg-[#e8f4ec] text-[#2f7a4d]",
  warning: "bg-[#f7edd8] text-[#946727]",
  danger: "bg-[#f9e2df] text-[#9f463e]",
  info: "bg-[#e6eef9] text-[#3a5f93]",
  neutral: "bg-[var(--surface-soft)] text-[var(--muted)]",
};

export function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: BadgeTone }) {
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${toneClass[tone]}`}>{label}</span>;
}
