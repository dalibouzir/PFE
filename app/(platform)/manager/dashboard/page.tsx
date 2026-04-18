"use client";

import Link from "next/link";
import { useMemo } from "react";
import { Package } from "lucide-react";
import { Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer } from "recharts";
import { useDashboard } from "@/hooks/useDashboard";
import { PageIntro } from "@/components/ui/PageIntro";
import { useMembers } from "@/hooks/useMembers";
import { useProducts } from "@/hooks/useProducts";
import { useStocks } from "@/hooks/useStocks";

const stageDefinitions = [
  { id: "tri", name: "Tri", keys: ["tri", "sort"], color: "#D64545" },
  { id: "sechage", name: "Sechage", keys: ["sechage", "séchage", "dry"], color: "#D4A017" },
  { id: "nettoyage", name: "Nettoyage", keys: ["nettoyage", "clean"], color: "#2F80ED" },
  { id: "conditionnement", name: "Conditionnement", keys: ["conditionnement", "emballage", "pack"], color: "#007E2F" },
] as const;

type LossSegment = {
  label: string;
  value: number;
  color: string;
};

function compactDate(value: string) {
  return value.length >= 10 ? value.slice(0, 10) : value;
}

function stageFromType(type: string) {
  const normalized = type.toLowerCase();
  return (
    stageDefinitions.find((stage) => stage.keys.some((key) => normalized.includes(key))) ?? {
      id: "autre",
      name: "Autre",
      keys: [],
      color: "#7A7A7A",
    }
  );
}

function padSeries(values: number[], fallback: number) {
  const normalized = values.filter((item) => Number.isFinite(item));
  if (normalized.length === 0) return Array.from({ length: 7 }, () => fallback);
  const result = [...normalized];
  while (result.length < 7) result.unshift(result[0]);
  return result.slice(-7);
}

function computeDelta(series: number[], invert = false) {
  if (series.length < 2) return 0;
  const previous = series[series.length - 2];
  const current = series[series.length - 1];
  if (previous <= 0) return 0;
  const raw = ((current - previous) / previous) * 100;
  return invert ? raw * -1 : raw;
}

function computeMonthDelta(dates: string[]) {
  const now = new Date();
  const currentMonth = now.getMonth();
  const currentYear = now.getFullYear();
  const previousMonth = currentMonth === 0 ? 11 : currentMonth - 1;
  const previousYear = currentMonth === 0 ? currentYear - 1 : currentYear;

  let currentCount = 0;
  let previousCount = 0;

  for (const value of dates) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) continue;
    if (date.getMonth() === currentMonth && date.getFullYear() === currentYear) currentCount += 1;
    if (date.getMonth() === previousMonth && date.getFullYear() === previousYear) previousCount += 1;
  }

  if (previousCount <= 0) return currentCount > 0 ? 100 : 0;
  return ((currentCount - previousCount) / previousCount) * 100;
}

function flowBarClass(lossPct: number) {
  if (lossPct > 10) return "bg-gradient-to-r from-red-400 to-red-600";
  if (lossPct >= 5) return "bg-gradient-to-r from-amber-400 to-amber-600";
  return "bg-gradient-to-r from-green-400 to-green-600";
}

function statusBadgeClass(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("attente")) return "border-[#F3D8A5] bg-[#FFF8E8] text-[#9E6A00]";
  if (normalized.includes("valide")) return "border-[#BFE0CA] bg-[#EEF8F1] text-[#0F7A3B]";
  return "border-[#C9DBF5] bg-[#EFF5FF] text-[#2F80ED]";
}

export default function ManagerDashboardPage() {
  const { data, isLoading, isError, refetch } = useDashboard();
  const { data: members = [] } = useMembers();
  const { data: products = [] } = useProducts();
  const { data: stocks = [] } = useStocks();

  const inputs = useMemo(() => data?.recent_inputs ?? [], [data?.recent_inputs]);
  const steps = useMemo(() => data?.recent_process_steps ?? [], [data?.recent_process_steps]);
  const stocksCritiques = useMemo(() => data?.stock_alerts ?? [], [data?.stock_alerts]);

  const totalStock = stocks.reduce((sum, item) => sum + item.quantity, 0);

  const stockSeries = padSeries(stocks.map((item) => item.quantity), totalStock || 0);
  const membersSeries = padSeries([members.length], members.length || 0);
  const productsSeries = padSeries([products.length], products.length || 0);
  const perteSeries = padSeries(steps.map((item) => item.loss_pct), data?.loss_rate ?? 0);
  const efficaciteSeries = padSeries(steps.map((item) => item.efficiency_pct), data?.efficiency_rate ?? 0);
  const membersDelta = computeMonthDelta(members.map((item) => item.created_at));
  const productsDelta = computeMonthDelta(products.map((item) => item.created_at));

  const kpis = [
    {
      id: "stock-total",
      href: "/manager/stocks",
      label: "Stock disponible",
      value: totalStock,
      suffix: " kg",
      decimals: 1,
      dotClass: "bg-[var(--success)]",
      delta: computeDelta(stockSeries),
      deltaClass: computeDelta(stockSeries) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
      series: stockSeries,
    },
    {
      id: "membres",
      href: "/manager/membres",
      label: "Membres",
      value: members.length,
      suffix: "",
      decimals: 0,
      dotClass: "bg-[var(--success)]",
      delta: membersDelta,
      deltaClass: membersDelta >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
      series: membersSeries,
    },
    {
      id: "produits",
      href: "/manager/stocks",
      label: "Produits suivis",
      value: products.length,
      suffix: "",
      decimals: 0,
      dotClass: "bg-[#2F80ED]",
      delta: productsDelta,
      deltaClass: productsDelta >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
      series: productsSeries,
    },
    {
      id: "perte",
      href: "/manager/lots",
      label: "Taux de perte",
      value: data?.loss_rate ?? 0,
      suffix: "%",
      decimals: 1,
      dotClass: (data?.loss_rate ?? 0) > 10 ? "bg-[var(--danger)]" : "bg-[var(--warning)]",
      delta: computeDelta(perteSeries, true),
      deltaClass: computeDelta(perteSeries, true) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
      series: perteSeries,
    },
    {
      id: "efficacite",
      href: "/manager/lots",
      label: "Rendement moyen",
      value: data?.efficiency_rate ?? 0,
      suffix: "%",
      decimals: 1,
      dotClass: (data?.efficiency_rate ?? 0) >= 80 ? "bg-[var(--success)]" : "bg-[var(--warning)]",
      delta: computeDelta(efficaciteSeries),
      deltaClass: computeDelta(efficaciteSeries) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
      series: efficaciteSeries,
    },
  ] as const;

  const recentRows = useMemo(() => {
    const inputRows = inputs.map((item) => ({
      id: `input-${item.id}`,
      date: compactDate(item.date),
      operation: `Collecte ${item.product_id.slice(0, 8).toUpperCase()}`,
      quantite: `${item.quantity.toFixed(1)} kg`,
      statut: item.status.toLowerCase().includes("pending") ? "En attente" : "Valide",
    }));

    const stepRows = steps.map((item) => ({
      id: `step-${item.id}`,
      date: compactDate(item.date),
      operation: `Etape ${stageFromType(item.type).name}`,
      quantite: `${item.qty_out.toFixed(1)} kg`,
      statut: item.warning ? "Suivi" : "OK",
    }));

    return [...stepRows, ...inputRows]
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
      .slice(0, 6);
  }, [inputs, steps]);

  const lossSegments = useMemo<LossSegment[]>(() => {
    const grouped = new Map<string, { value: number; color: string }>();
    for (const step of steps) {
      const stage = stageFromType(step.type);
      const loss = Math.max(step.waste_qty, step.qty_in - step.qty_out, 0);
      const current = grouped.get(stage.name);
      grouped.set(stage.name, { value: (current?.value ?? 0) + loss, color: stage.color });
    }

    return Array.from(grouped.entries())
      .map(([label, entry]) => ({ label, value: entry.value, color: entry.color }))
      .filter((item) => item.value > 0)
      .sort((a, b) => b.value - a.value);
  }, [steps]);

  const totalLoss = lossSegments.reduce((sum, item) => sum + item.value, 0);

  const flowRows = useMemo(() => {
    const raw = stageDefinitions.map((stage) => {
      const matched = steps.filter((step) => stage.keys.some((key) => step.type.toLowerCase().includes(key)));
      const output = matched.reduce((sum, step) => sum + step.qty_out, 0);
      const avgLoss = matched.length ? matched.reduce((sum, step) => sum + step.loss_pct, 0) / matched.length : 0;
      return { id: stage.id, label: stage.name, output, avgLoss };
    });
    const maxOutput = Math.max(...raw.map((item) => item.output), 1);
    return raw.map((item) => ({ ...item, progress: (item.output / maxOutput) * 100 }));
  }, [steps]);

  if (isError) {
    return (
      <main>
        <section className="premium-card rounded-2xl p-6">
          <p className="text-sm text-[var(--danger)]">Erreur de chargement du dashboard.</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-3 rounded-xl bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white"
          >
            Reessayer
          </button>
        </section>
      </main>
    );
  }

  return (
    <main>
      <PageIntro title="Dashboard" subtitle="Vue simple des operations: collecte, pertes, activite recente et stocks." />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {(isLoading && !data ? Array.from({ length: 5 }).map((_, i) => ({ id: `s-${i}` })) : kpis).map((kpi) =>
          "label" in kpi ? (
            <Link key={kpi.id} href={kpi.href} className="block">
              <article className="premium-card rounded-2xl p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">{kpi.label}</p>
                  <span className={`h-2.5 w-2.5 rounded-full ${kpi.dotClass}`} />
                </div>
                <p className="mt-2 text-[38px] font-semibold leading-none text-[var(--text)]">
                  {kpi.value.toFixed(kpi.decimals)}
                  {kpi.suffix}
                </p>
                <p className={`mt-2 text-xs font-semibold ${kpi.deltaClass}`}>
                  {kpi.delta >= 0 ? "↗" : "↘"} {kpi.delta >= 0 ? "+" : "-"}
                  {Math.abs(kpi.delta).toFixed(1)}% vs mois dernier
                </p>
                <div className="mt-3 h-[34px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={kpi.series.map((value, index) => ({ x: index, y: value }))}>
                      <Line type="monotone" dataKey="y" stroke="#72736D" strokeWidth={2} dot={false} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </article>
            </Link>
          ) : (
            <article key={kpi.id} className="premium-card rounded-2xl p-4">
              <div className="h-3 w-28 animate-pulse rounded bg-[var(--line)]" />
              <div className="mt-3 h-8 w-24 animate-pulse rounded bg-[var(--line)]" />
              <div className="mt-2 h-3 w-32 animate-pulse rounded bg-[var(--line)]" />
              <div className="mt-3 h-7 animate-pulse rounded bg-[var(--surface-soft)]" />
            </article>
          ),
        )}
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
        <article className="premium-card rounded-2xl p-5">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-base font-semibold text-[var(--text)]">Activite recente</h3>
            <p className="text-xs text-[var(--muted)]">{recentRows.length} elements</p>
          </div>
          <div className="mt-3 max-h-[420px] overflow-auto rounded-xl border border-[var(--line)]">
            <table className="min-w-full text-left text-sm">
              <thead className="sticky top-0 border-b border-[var(--line)] bg-[var(--surface)] text-[11px] uppercase tracking-[0.12em] text-[var(--muted)]">
                <tr>
                  <th className="px-3 py-3 font-semibold">Date</th>
                  <th className="px-3 py-3 font-semibold">Operation</th>
                  <th className="px-3 py-3 font-semibold">Quantite</th>
                  <th className="px-3 py-3 font-semibold">Statut</th>
                </tr>
              </thead>
              <tbody>
                {recentRows.map((row) => (
                  <tr key={row.id} className="border-b border-[var(--line)] last:border-b-0">
                    <td className="px-3 py-3 text-[var(--muted)]">{row.date}</td>
                    <td className="px-3 py-3 font-medium text-[var(--text)]">{row.operation}</td>
                    <td className="px-3 py-3 text-[var(--text)]">{row.quantite}</td>
                    <td className="px-3 py-3">
                      <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${statusBadgeClass(row.statut)}`}>
                        {row.statut}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <div className="grid gap-4">
          <article className="premium-card rounded-2xl p-5">
            <h3 className="text-base font-semibold text-[var(--text)]">Repartition des pertes</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">Par etape de transformation</p>
            {lossSegments.length === 0 ? (
              <p className="mt-4 text-sm text-[var(--muted)]">Aucune perte recente detectee.</p>
            ) : (
              <div className="mt-3 grid gap-3 sm:grid-cols-[180px_1fr] xl:grid-cols-1">
                <div className="relative h-[180px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={lossSegments}
                        dataKey="value"
                        nameKey="label"
                        innerRadius={50}
                        outerRadius={78}
                        paddingAngle={2}
                        isAnimationActive={false}
                      >
                        {lossSegments.map((entry) => (
                          <Cell key={entry.label} fill={entry.color} />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">Pertes</p>
                    <p className="text-xl font-semibold text-[var(--text)]">{totalLoss.toFixed(1)} kg</p>
                  </div>
                </div>
                <div className="space-y-2">
                  {lossSegments.map((item) => {
                    const pct = totalLoss > 0 ? (item.value / totalLoss) * 100 : 0;
                    return (
                      <div key={item.label} className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                        <p className="flex items-center gap-2 text-sm font-medium text-[var(--text)]">
                          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                          {item.label}
                        </p>
                        <p className="text-xs font-semibold text-[var(--muted)]">
                          {item.value.toFixed(1)} kg ({pct.toFixed(0)}%)
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </article>
        </div>
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <article className="premium-card rounded-2xl p-5">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-base font-semibold text-[var(--text)]">Flux matiere actifs</h3>
            <p className="text-xs text-[var(--muted)]">Progression par etape</p>
          </div>
          <div className="mt-4 space-y-3">
            {flowRows.map((row) => (
              <div key={row.id}>
                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-[var(--text)]">{row.label}</p>
                  <p className="text-xs text-[var(--muted)]">
                    {row.output.toFixed(1)} kg · perte {row.avgLoss.toFixed(1)}%
                  </p>
                </div>
                <div className="h-2.5 rounded-full bg-[#E8E3DB]">
                  <div className={`h-2.5 rounded-full ${flowBarClass(row.avgLoss)}`} style={{ width: `${Math.max(6, row.progress)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="premium-card rounded-2xl p-5">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-base font-semibold text-[var(--text)]">Etat stocks critiques</h3>
            <p className="text-xs text-[var(--muted)]">{stocksCritiques.length} alerte(s)</p>
          </div>
          {stocksCritiques.length === 0 ? (
            <div className="mt-4 flex min-h-[164px] flex-col items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--surface-soft)]">
              <Package className="h-8 w-8 text-[var(--muted)]" />
              <p className="mt-3 text-lg font-semibold text-[var(--text)]">Tout est sous controle</p>
              <p className="text-sm text-[var(--muted)]">Aucun stock critique detecte</p>
            </div>
          ) : (
            <div className="mt-4 space-y-2">
              {stocksCritiques.map((item) => (
                <div key={item.stock_id} className="rounded-xl border border-[#F1CECE] bg-[#FFF4F4] px-3 py-2.5">
                  <p className="text-sm font-semibold text-[var(--text)]">Produit {item.product_id.slice(0, 8)}</p>
                  <p className="text-xs text-[var(--muted)]">
                    Quantite {item.quantity.toFixed(1)} {item.unit} · seuil {item.threshold.toFixed(1)} {item.unit}
                  </p>
                  <p className="mt-1 text-xs font-semibold text-[var(--danger)]">Deficit: {item.deficit.toFixed(1)} {item.unit}</p>
                </div>
              ))}
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
