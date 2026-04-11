export function KpiCard({ title, value }: { title: string; value: string }) {
  return (
    <article className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-black/5">
      <p className="text-sm text-slate-600">{title}</p>
      <p className="text-2xl font-semibold text-brand-800">{value}</p>
    </article>
  );
}
