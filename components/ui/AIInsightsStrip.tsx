"use client";

import Link from "next/link";

export type AIInsightTone = "critical" | "warning" | "success" | "info";

export type AIInsightItem = {
  id: string;
  title: string;
  message: string;
  tone: AIInsightTone;
  actionLabel?: string;
  href?: string;
  meta?: string;
};

const TONE_STYLES: Record<AIInsightTone, { border: string; bg: string; text: string; dot: string }> = {
  critical: {
    border: "border-[#E8B9B9]",
    bg: "bg-[#FFF1F2]",
    text: "text-[#9E2F36]",
    dot: "bg-[#D34B54]",
  },
  warning: {
    border: "border-[#ECD9B5]",
    bg: "bg-[#FFF9EE]",
    text: "text-[#8D5D14]",
    dot: "bg-[#D39D2F]",
  },
  success: {
    border: "border-[#CFE6D5]",
    bg: "bg-[#F1FAF4]",
    text: "text-[#1E6C34]",
    dot: "bg-[#23934A]",
  },
  info: {
    border: "border-[#CFE0F4]",
    bg: "bg-[#F2F7FF]",
    text: "text-[#2F5C90]",
    dot: "bg-[#3D6EA8]",
  },
};

export function AIInsightsStrip({
  title,
  subtitle,
  items,
}: {
  title: string;
  subtitle?: string;
  items: AIInsightItem[];
}) {
  if (items.length === 0) return null;

  return (
    <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "85ms" }}>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-[var(--text)]">{title}</h3>
          {subtitle ? <p className="text-xs text-[var(--muted)]">{subtitle}</p> : null}
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-2">
        {items.map((item) => {
          const tone = TONE_STYLES[item.tone];
          return (
            <div key={item.id} className={`rounded-xl border px-3 py-2 ${tone.border} ${tone.bg}`}>
              <div className="flex items-center justify-between gap-2">
                <p className={`text-sm font-semibold ${tone.text}`}>{item.title}</p>
                <span className={`h-2.5 w-2.5 rounded-full ${tone.dot}`} />
              </div>
              <p className="mt-1 text-xs text-[var(--muted)]">{item.message}</p>
              {item.meta ? <p className="mt-1 text-[11px] text-[var(--muted)]">{item.meta}</p> : null}
              {item.actionLabel && item.href ? (
                <Link href={item.href} className="mt-2 inline-block text-xs font-semibold text-[var(--ai-accent)] hover:underline">
                  {item.actionLabel}
                </Link>
              ) : null}
            </div>
          );
        })}
      </div>
    </article>
  );
}
