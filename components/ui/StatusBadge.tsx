import type { BadgeTone } from "@/lib/ui/types";

const toneClass: Record<BadgeTone, string> = {
  success: "border border-[#C7E3D2] bg-[#E8F4EC] text-[#007E2F]",
  warning: "border border-[#E8D39A] bg-[#FFF5DC] text-[#8B6A00]",
  danger: "border border-[#E8B9B9] bg-[#FFEDEE] text-[#B23B3B]",
  info: "border border-[#BDD6FB] bg-[#EEF5FF] text-[#2F80ED]",
  ai: "border border-[#D0C4FF] bg-[#F3EEFF] text-[#6A4DE0]",
  neutral: "border border-[var(--line)] bg-[var(--surface-soft)] text-[var(--muted)]",
};

export function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: BadgeTone }) {
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${toneClass[tone]}`}>{label}</span>;
}
