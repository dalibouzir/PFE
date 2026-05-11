import { AlertTriangle, BarChart3, ChevronDown, Flame, ShieldCheck, Sparkles } from 'lucide-react';
import { useState } from 'react';

type Generic = Record<string, unknown>;

function tone(level: string) {
  const v = level.toLowerCase();
  if (v.includes('élev') || v.includes('crit')) return 'border-[#ef4444]/30 bg-[#fff5f5] text-[#991b1b]';
  if (v.includes('faible')) return 'border-[#16a34a]/30 bg-[#f0fdf4] text-[#166534]';
  return 'border-[#f59e0b]/30 bg-[#fffbeb] text-[#92400e]';
}

export function PriorityBadge({ value }: { value: string }) {
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${tone(value)}`}>{value}</span>;
}

export function ExecutiveSummaryCard({ text }: { text: string }) {
  return (
    <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-5 shadow-[0_8px_26px_rgba(0,0,0,0.05)]">
      <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-[#3f6b52]">Résumé exécutif</h3>
      <p className="mt-2 text-[15px] leading-7 text-[#173324]">{text}</p>
    </section>
  );
}

export function KpiMiniCard({ label, value, unit, severity }: { label: string; value: string; unit?: string; severity?: string }) {
  return (
    <article className="rounded-xl border border-[var(--line)] bg-[#f8fcf8] p-3">
      <p className="text-[11px] uppercase tracking-wide text-[#557a66]">{label}</p>
      <p className="mt-1 text-xl font-semibold text-[#173324]">{value} <span className="text-sm font-medium">{unit || ''}</span></p>
      {severity ? <div className="mt-2"><PriorityBadge value={severity} /></div> : null}
    </article>
  );
}

export function KPIGrid({ items }: { items: Generic[] }) {
  return (
    <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
      <h3 className="text-sm font-semibold text-[#173324]">Indicateurs opérationnels</h3>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {items.map((item, i) => (
          <KpiMiniCard key={i} label={String(item.label || 'Indicateur')} value={String(item.value ?? '-')} unit={String(item.unit || '')} severity={String(item.severity || '')} />
        ))}
      </div>
    </section>
  );
}

export function RiskBanner({ title, impact, severity }: { title: string; impact: string; severity: string }) {
  return (
    <article className="rounded-xl border border-[#ef4444]/20 bg-white px-3 py-2">
      <div className="flex items-center gap-2"><Flame className="h-4 w-4 text-[#b91c1c]" /><p className="text-sm font-semibold text-[#7f1d1d]">{title}</p><PriorityBadge value={severity} /></div>
      <p className="mt-1 text-sm text-[#4a1f1f]">{impact}</p>
    </article>
  );
}

export function OperationalInsightCard({ text }: { text: string }) {
  return <li className="rounded-lg bg-[#f7fbf8] px-3 py-2 text-sm text-[#173324]">{text}</li>;
}

export function InsightTimeline({ points }: { points: string[] }) {
  return (
    <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
      <h3 className="text-sm font-semibold text-[#173324]">Constats clés</h3>
      <ul className="mt-3 space-y-2">{points.map((p) => <OperationalInsightCard key={p} text={p} />)}</ul>
    </section>
  );
}

export function ActionRecommendationCard({ item, index }: { item: Generic; index: number }) {
  return (
    <li className="rounded-xl border border-[var(--line)] bg-[#f8fcf8] p-3">
      <p className="font-semibold text-[#173324]">{index}. {String(item.action || '')}</p>
      <p className="mt-1 text-[13px] text-[#557a66]">{String(item.impact_attendu || '')}</p>
      <div className="mt-2"><PriorityBadge value={String(item.priorité || 'Priorité moyenne')} /></div>
    </li>
  );
}

export function BenchmarkComparisonCard({ note, citationsCount }: { note: string; citationsCount: number }) {
  return (
    <section className="rounded-2xl border border-[#1d4ed8]/20 bg-[#eff6ff] p-4">
      <div className="flex items-center gap-2"><BarChart3 className="h-4 w-4 text-[#1d4ed8]" /><h3 className="text-sm font-semibold text-[#1e3a8a]">Comparaison de référence</h3></div>
      <p className="mt-2 text-sm text-[#1e3a8a]">{note}</p>
      <p className="mt-2 text-xs text-[#3658a2]">Sources mobilisées : {citationsCount}</p>
    </section>
  );
}

export function ConfidenceMeter({ label, score, explanation }: { label: string; score: number; explanation: string }) {
  const width = Math.max(6, Math.min(100, score));
  return (
    <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
      <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-[#1f6b3f]" /><h3 className="text-sm font-semibold text-[#173324]">Niveau de confiance</h3></div>
      <div className="mt-3 flex items-center justify-between"><PriorityBadge value={label} /><span className="font-semibold text-[#173324]">{Math.round(width)}%</span></div>
      <div className="mt-2 h-2 rounded-full bg-[#e8f2eb]"><div className="h-2 rounded-full bg-[#0a8f43]" style={{ width: `${width}%` }} /></div>
      <p className="mt-2 text-xs text-[#557a66]">{explanation}</p>
    </section>
  );
}

export function SourceReferenceChip({ label }: { label: string }) {
  return <span className="inline-flex rounded-full border border-[#c7dfcf] bg-[#f2faf5] px-2.5 py-1 text-[11px] font-medium text-[#24523b]">{label}</span>;
}

export function CompactStatsFooter({ left, right }: { left: string; right: string }) {
  return <div className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[#f8fcf8] px-3 py-2 text-xs text-[#557a66]"><span>{left}</span><span>{right}</span></div>;
}

export function TechnicalDrawer({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
      <button type="button" onClick={() => setOpen((v) => !v)} className="flex w-full items-center justify-between text-left">
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-[#173324]"><Sparkles className="h-4 w-4 text-[#355f4b]" />{title}</span>
        <ChevronDown className={`h-4 w-4 text-[#557a66] transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open ? <div className="mt-3">{children}</div> : null}
    </section>
  );
}

export function AlertPanel({ issue, impact, actions }: { issue: string; impact: string; actions: string[] }) {
  return (
    <section className="rounded-2xl border border-[#ef4444]/30 bg-[#fff1f2] p-4 shadow-[0_8px_24px_rgba(239,68,68,0.12)]">
      <div className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-[#b91c1c]" /><h3 className="text-sm font-semibold text-[#881337]">Alerte critique</h3></div>
      <p className="mt-2 text-sm font-semibold text-[#9f1239]">{issue}</p>
      <p className="mt-1 text-sm text-[#7f1d1d]">Impact : {impact}</p>
      <ul className="mt-2 space-y-1 text-sm text-[#7f1d1d]">{actions.map((a) => <li key={a}>• {a}</li>)}</ul>
    </section>
  );
}
