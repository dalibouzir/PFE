"use client";

import Link from "next/link";
import { useMemo } from "react";
import { AlertTriangle, Package, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ContentAreaLoader } from "@/components/ui/ContentAreaLoader";
import { PageIntro } from "@/components/ui/PageIntro";
import { AIInsightsStrip, type AIInsightItem } from "@/components/ui/AIInsightsStrip";
import { useDashboard } from "@/hooks/useDashboard";
import { useCatalogProducts } from "@/hooks/useCommercial";
import { useMembers } from "@/hooks/useMembers";
import { useStocks } from "@/hooks/useStocks";
import {
  buildActionItems,
  buildOperationalInsights,
  buildPriorityStrip,
  buildRecommendationCards,
  buildStageInsights,
} from "@/lib/insights/managerInsights";

const GREEN = "#007E2F";
const GREEN_SOFT = "#5FB87F";
const BLUE = "#3D6EA8";
const AMBER = "#D39D2F";
const ROSE = "#CC5B62";

type LossSegment = {
  label: string;
  value: number;
  color: string;
};

const stageDefinitions = [
  { id: "tri", name: "Tri", keys: ["tri", "sort"], color: ROSE },
  { id: "sechage", name: "Sechage", keys: ["sechage", "sech", "dry"], color: AMBER },
  { id: "nettoyage", name: "Nettoyage", keys: ["nettoyage", "clean"], color: BLUE },
  { id: "conditionnement", name: "Conditionnement", keys: ["conditionnement", "emballage", "pack"], color: GREEN },
] as const;

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
      color: "#7A869A",
    }
  );
}

function statusBadgeClass(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("attente")) return "border-[#EADFC0] bg-[#FFFAEE] text-[#946900]";
  if (normalized.includes("valide") || normalized.includes("ok")) return "border-[#CCE6D6] bg-[#F2FAF6] text-[#0A6D2A]";
  if (normalized.includes("suivi")) return "border-[#D0D9EA] bg-[#F2F6FD] text-[#315A95]";
  return "border-[#DBDEE6] bg-[#F8F9FC] text-[#5D6678]";
}

function toFixed(value: number, decimals = 1) {
  return Number.isFinite(value) ? value.toFixed(decimals) : (0).toFixed(decimals);
}

function computeDelta(current: number, previous: number, invert = false) {
  if (previous <= 0) return 0;
  const raw = ((current - previous) / previous) * 100;
  return invert ? raw * -1 : raw;
}

function flowBarClass(lossPct: number) {
  if (lossPct > 10) return "from-[#E28A92] to-[#CC5B62]";
  if (lossPct >= 5) return "from-[#EBC773] to-[#D39D2F]";
  return "from-[#49A56C] to-[#007E2F]";
}

export default function ManagerDashboardPage() {
  const dashboardQuery = useDashboard();
  const catalogQuery = useCatalogProducts();
  const membersQuery = useMembers();
  const stocksQuery = useStocks();
  const data = dashboardQuery.data;
  const catalogProducts = catalogQuery.data ?? [];
  const members = membersQuery.data ?? [];
  const stocks = stocksQuery.data ?? [];

  const inputs = useMemo(() => data?.recent_inputs ?? [], [data?.recent_inputs]);
  const steps = useMemo(() => data?.recent_process_steps ?? [], [data?.recent_process_steps]);
  const stocksCritiques = useMemo(() => data?.stock_alerts ?? [], [data?.stock_alerts]);
  const totalStock = useMemo(() => stocks.reduce((sum, item) => sum + item.available_stock_kg, 0), [stocks]);

  const trendData = useMemo(() => {
    const grouped = new Map<string, { loss: number[]; efficiency: number[]; output: number }>();
    for (const step of steps) {
      const day = compactDate(step.date);
      const current = grouped.get(day) ?? { loss: [], efficiency: [], output: 0 };
      current.loss.push(step.loss_pct);
      current.efficiency.push(step.efficiency_pct);
      current.output += step.qty_out;
      grouped.set(day, current);
    }

    const series = Array.from(grouped.entries())
      .sort(([a], [b]) => new Date(a).getTime() - new Date(b).getTime())
      .map(([date, values]) => ({
        date,
        label: date.slice(5),
        loss: values.loss.length ? values.loss.reduce((sum, item) => sum + item, 0) / values.loss.length : 0,
        efficiency: values.efficiency.length
          ? values.efficiency.reduce((sum, item) => sum + item, 0) / values.efficiency.length
          : 0,
        output: values.output,
      }));

    const safeSeries = series.length ? series : [{ date: "", label: "--", loss: data?.loss_rate ?? 0, efficiency: data?.efficiency_rate ?? 0, output: totalStock }];
    while (safeSeries.length < 7) {
      safeSeries.unshift({ ...safeSeries[0], label: safeSeries[0].label === "--" ? "--" : "..." });
    }
    return safeSeries.slice(-7);
  }, [steps, data?.loss_rate, data?.efficiency_rate, totalStock]);

  const currentPoint = trendData[trendData.length - 1];
  const previousPoint = trendData[trendData.length - 2] ?? currentPoint;
  const lossDelta = computeDelta(currentPoint?.loss ?? 0, previousPoint?.loss ?? 0, true);
  const efficiencyDelta = computeDelta(currentPoint?.efficiency ?? 0, previousPoint?.efficiency ?? 0);

  const recentRows = useMemo(() => {
    const inputRows = inputs.map((item) => ({
      id: `input-${item.id}`,
      date: compactDate(item.date),
      operation: `Collecte ${item.product_id.slice(0, 8).toUpperCase()}`,
      quantite: `${toFixed(item.quantity, 1)} kg`,
      statut: item.status.toLowerCase().includes("pending") ? "En attente" : "Valide",
    }));

    const stepRows = steps.map((item) => ({
      id: `step-${item.id}`,
      date: compactDate(item.date),
      operation: `Etape ${stageFromType(item.type).name}`,
      quantite: `${toFixed(item.qty_out, 1)} kg`,
      statut: item.warning ? "Suivi" : "OK",
    }));

    return [...stepRows, ...inputRows]
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
      .slice(0, 7);
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

  const totalLoss = useMemo(() => lossSegments.reduce((sum, item) => sum + item.value, 0), [lossSegments]);

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

  const kpiCards = [
    {
      id: "active-batches",
      href: "/manager/lots",
      label: "Lots actifs",
      value: data?.number_of_active_batches ?? 0,
      suffix: "",
      trend: trendData.map((item) => item.output),
      tone: "neutral",
    },
    {
      id: "stock",
      href: "/manager/stocks",
      label: "Stock disponible",
      value: totalStock,
      suffix: " kg",
      trend: trendData.map((item) => item.output),
      tone: "positive",
    },
    {
      id: "members",
      href: "/manager/membres",
      label: "Membres",
      value: members.length,
      suffix: "",
      trend: trendData.map((item) => item.efficiency),
      tone: "positive",
    },
    {
      id: "products",
      href: "/manager/commercialisation",
      label: "Produits vendables",
      value: catalogProducts.length,
      suffix: "",
      trend: trendData.map((item) => item.loss),
      tone: "neutral",
    },
  ] as const;

  const mlInsights = useMemo<AIInsightItem[]>(() => {
    if (!data) return [];

    const stageInsights = buildStageInsights(data);
    const recommendationCards = buildRecommendationCards(data);
    const actions = buildActionItems(recommendationCards, stageInsights, data.stock_alerts);
    const priority = buildPriorityStrip(data, actions);
    const operationalCards = buildOperationalInsights(data, stageInsights, actions);

    const priorityTone: AIInsightItem["tone"] =
      priority.severity === "critical" ? "critical" : priority.severity === "warning" ? "warning" : "success";

    const mappedCards: AIInsightItem[] = operationalCards.map((card) => ({
      id: card.id,
      title: card.title,
      message: card.message,
      tone:
        card.severity === "critical"
          ? "critical"
          : card.severity === "warning"
            ? "warning"
            : card.severity === "healthy"
              ? "success"
              : "info",
      actionLabel: "Voir les recommandations",
      href: "/manager/lots?tab=recommendations",
      meta: card.action,
    }));

    return [
      {
        id: "priority-strip",
        title: priority.headline,
        message: priority.message,
        tone: priorityTone,
        actionLabel: "Action recommandee",
        href: "/manager/lots?tab=recommendations",
        meta: priority.recommendation,
      },
      ...mappedCards,
    ].slice(0, 4);
  }, [data]);

  const primaryInsight = (data?.loss_rate ?? 0) > 9 ? "Drop detecte sur les etapes aval" : "Tendance stable sur la semaine";
  const secondaryInsight = (data?.efficiency_rate ?? 0) >= 80 ? "Trend increasing sur le rendement" : "Efficacite sous cible, suivi recommande";

  const requiredLoading =
    dashboardQuery.isLoading || catalogQuery.isLoading || membersQuery.isLoading || stocksQuery.isLoading;
  const requiredError =
    dashboardQuery.isError || catalogQuery.isError || membersQuery.isError || stocksQuery.isError;

  if (requiredLoading) {
    return (
      <main className="relative min-h-[60vh]">
        <PageIntro title="Dashboard" />
        <ContentAreaLoader
          title="Chargement Dashboard"
          subtitle="Synchronisation des indicateurs, stocks, membres et produits..."
        />
      </main>
    );
  }

  if (requiredError) {
    return (
      <main>
        <PageIntro title="Dashboard" />
        <section className="premium-card rounded-xl p-6">
          <p className="text-sm text-[var(--danger)]">Erreur de chargement du dashboard.</p>
          <button
            type="button"
            onClick={() => {
              void dashboardQuery.refetch();
              void catalogQuery.refetch();
              void membersQuery.refetch();
              void stocksQuery.refetch();
            }}
            className="mt-3 rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white"
          >
            Reessayer
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="space-y-5">
      <PageIntro title="Dashboard" />

      <section className="grid gap-4 xl:grid-cols-[1.55fr_0.45fr]">
          <article className="rounded-xl border border-[#d3dfeb] bg-white p-4 shadow-[0_8px_20px_rgba(18,46,78,0.08)] sm:p-5">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#5c7088]">Monitoring performance</p>
                <h2 className="mt-1 text-xl font-semibold text-[#10283f]">Vue tendance pertes vs rendement</h2>
              </div>
              <span className="inline-flex items-center gap-1 rounded-full border border-[#c8e4d2] bg-[#f1faf5] px-3 py-1 text-xs font-semibold text-[#0e6b2b]">
                <Sparkles className="h-3.5 w-3.5" />
                {primaryInsight}
              </span>
            </div>

            <div className="h-[250px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData} margin={{ top: 10, right: 6, left: -16, bottom: 0 }}>
                  <defs>
                    <linearGradient id="effGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={GREEN} stopOpacity={0.22} />
                      <stop offset="100%" stopColor={GREEN} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#e8eef5" strokeDasharray="3 4" vertical={false} />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#6d7f95", fontSize: 11 }} />
                  <YAxis tickLine={false} axisLine={false} tick={{ fill: "#6d7f95", fontSize: 11 }} width={36} />
                  <Tooltip
                    contentStyle={{ borderRadius: 10, border: "1px solid #d5e0ec", background: "#ffffff" }}
                    labelStyle={{ color: "#27435e", fontWeight: 600 }}
                  />
                  <Area type="monotone" dataKey="efficiency" stroke="none" fill="url(#effGradient)" />
                  <Line type="monotone" dataKey="efficiency" stroke={GREEN} strokeWidth={2.4} dot={false} name="Rendement %" />
                  <Line type="monotone" dataKey="loss" stroke={ROSE} strokeWidth={2.1} dot={false} name="Perte %" />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <div className="rounded-lg border border-[#d6e9de] bg-[#f4fbf7] px-3 py-2">
                <p className="text-[11px] uppercase tracking-[0.1em] text-[#47745a]">AI insight</p>
                <p className="mt-1 text-sm font-semibold text-[#134730]">{secondaryInsight}</p>
              </div>
              <div className="rounded-lg border border-[#ebd8d8] bg-[#fff6f6] px-3 py-2">
                <p className="text-[11px] uppercase tracking-[0.1em] text-[#7f5157]">Signal</p>
                <p className="mt-1 text-sm font-semibold text-[#5e2f36]">{(data?.loss_rate ?? 0) > 9 ? "Loss spike sur un segment" : "Aucun spike critique detecte"}</p>
              </div>
            </div>
          </article>

          <div className="grid gap-4">
            <article className="rounded-xl border border-[#d6e8dc] bg-white p-4 shadow-[0_8px_20px_rgba(18,46,78,0.08)]">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#56706f]">Rendement moyen</p>
              <p className="mt-2 text-4xl font-semibold text-[#0e2f2a]">{toFixed(data?.efficiency_rate ?? 0, 1)}%</p>
              <p className={`mt-2 inline-flex items-center gap-1 text-xs font-semibold ${efficiencyDelta >= 0 ? "text-[#0b6f2f]" : "text-[#b44650]"}`}>
                {efficiencyDelta >= 0 ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
                {efficiencyDelta >= 0 ? "+" : "-"}
                {toFixed(Math.abs(efficiencyDelta), 1)}% vs point precedent
              </p>
            </article>

            <article className="rounded-xl border border-[#ebdcdc] bg-white p-4 shadow-[0_8px_20px_rgba(18,46,78,0.08)]">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#6f5959]">Taux de perte</p>
              <p className="mt-2 text-4xl font-semibold text-[#2a333f]">{toFixed(data?.loss_rate ?? 0, 1)}%</p>
              <p className={`mt-2 inline-flex items-center gap-1 text-xs font-semibold ${lossDelta >= 0 ? "text-[#0b6f2f]" : "text-[#b44650]"}`}>
                {lossDelta >= 0 ? <TrendingDown className="h-3.5 w-3.5" /> : <TrendingUp className="h-3.5 w-3.5" />}
                {lossDelta >= 0 ? "-" : "+"}
                {toFixed(Math.abs(lossDelta), 1)}% vs point precedent
              </p>
            </article>
          </div>
      </section>

      <AIInsightsStrip
        title="Pilotage IA multi-pages"
        subtitle="Synthese actionnable pour lots, stocks et suivi terrain."
        items={mlInsights}
      />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {kpiCards.map((kpi) => (
          <Link key={kpi.id} href={kpi.href} className="block">
            <article className="rounded-xl border border-[#d8e2ee] bg-white p-4 shadow-[0_7px_18px_rgba(15,46,80,0.06)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_14px_28px_rgba(15,46,80,0.1)]">
              <p className="text-[11px] uppercase tracking-[0.14em] text-[#688099]">{kpi.label}</p>
              <p className="mt-2 text-3xl font-semibold text-[#132f47]">
                {kpi.value.toFixed(kpi.suffix ? 1 : 0)}
                {kpi.suffix}
              </p>
              <div className="mt-3 h-[42px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={kpi.trend.map((value, index) => ({ x: index, y: value }))}>
                    <Line
                      type="monotone"
                      dataKey="y"
                      stroke={kpi.tone === "positive" ? GREEN : GREEN_SOFT}
                      strokeWidth={2.1}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </article>
          </Link>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <article className="rounded-xl border border-[#d8e2ee] bg-white p-5 shadow-[0_8px_20px_rgba(18,46,78,0.08)]">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-base font-semibold text-[#122d44]">Operations recentes</h3>
            <p className="text-xs text-[#6f8398]">{recentRows.length} lignes</p>
          </div>
          <div className="scroll-thin overflow-x-auto rounded-lg border border-[#dce4ef]">
            <table className="wf-table w-full min-w-[980px] text-left text-sm">
              <thead>
                <tr>
                  <th className="px-3 py-3 font-semibold">Date</th>
                  <th className="px-3 py-3 font-semibold">Operation</th>
                  <th className="px-3 py-3 font-semibold">Quantite</th>
                  <th className="px-3 py-3 font-semibold">Statut</th>
                </tr>
              </thead>
              <tbody>
                {recentRows.length === 0 ? (
                  <tr>
                    <td className="px-3 py-5 text-sm text-[#6f8398]" colSpan={4}>
                      Aucune activite recente.
                    </td>
                  </tr>
                ) : (
                  recentRows.map((row) => (
                    <tr key={row.id}>
                      <td className="px-3 py-3 text-[#6f8398]">{row.date}</td>
                      <td className="px-3 py-3 font-medium text-[#162f45]">{row.operation}</td>
                      <td className="px-3 py-3 text-[#1b3a54]">{row.quantite}</td>
                      <td className="px-3 py-3">
                        <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${statusBadgeClass(row.statut)}`}>
                          {row.statut}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </article>

        <div className="grid gap-4">
          <article className="rounded-xl border border-[#d8e2ee] bg-white p-5 shadow-[0_8px_20px_rgba(18,46,78,0.08)]">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-base font-semibold text-[#122d44]">Repartition des pertes</h3>
              <span className="rounded-full bg-[#eff8f2] px-2.5 py-1 text-[11px] font-semibold text-[#0f6a2b]">AI tracked</span>
            </div>
            {lossSegments.length === 0 ? (
              <p className="mt-3 text-sm text-[#6f8398]">Aucune perte recente detectee.</p>
            ) : (
              <div className="mt-3 grid gap-3 sm:grid-cols-[170px_1fr]">
                <div className="relative h-[170px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={lossSegments} dataKey="value" nameKey="label" innerRadius={45} outerRadius={72} paddingAngle={2} isAnimationActive={false}>
                        {lossSegments.map((entry) => (
                          <Cell key={entry.label} fill={entry.color} />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.11em] text-[#5f7288]">Pertes</p>
                    <p className="text-lg font-semibold text-[#13314a]">{toFixed(totalLoss, 1)} kg</p>
                  </div>
                </div>

                <div className="space-y-2">
                  {lossSegments.map((item) => (
                    <div key={item.label} className="flex items-center justify-between rounded-lg border border-[#dde6f0] bg-[#f9fbfe] px-3 py-2">
                      <p className="flex items-center gap-2 text-sm font-medium text-[#173850]">
                        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                        {item.label}
                      </p>
                      <p className="text-xs font-semibold text-[#5d7289]">{toFixed(item.value, 1)} kg</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </article>

          <article className="rounded-xl border border-[#d8e2ee] bg-white p-5 shadow-[0_8px_20px_rgba(18,46,78,0.08)]">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-base font-semibold text-[#122d44]">Flux matiere</h3>
              <p className="text-xs text-[#6f8398]">Sortie nette par etape</p>
            </div>

            <div className="h-[170px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={flowRows} margin={{ top: 8, right: 0, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke="#edf2f8" vertical={false} />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#6c8198", fontSize: 11 }} />
                  <YAxis tickLine={false} axisLine={false} tick={{ fill: "#6c8198", fontSize: 11 }} width={34} />
                  <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #d8e2ee", background: "#fff" }} />
                  <Bar dataKey="output" radius={[8, 8, 0, 0]}>
                    {flowRows.map((row) => (
                      <Cell key={row.id} fill={row.avgLoss > 10 ? ROSE : GREEN} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="mt-3 space-y-2">
              {flowRows.map((row) => (
                <div key={row.id}>
                  <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                    <p className="font-medium text-[#1f3f59]">{row.label}</p>
                    <p className="text-[#63788f]">{toFixed(row.output, 1)} kg · perte {toFixed(row.avgLoss, 1)}%</p>
                  </div>
                  <div className="h-2.5 rounded-full bg-[#e9eff7]">
                    <div className={`h-2.5 rounded-full bg-gradient-to-r ${flowBarClass(row.avgLoss)}`} style={{ width: `${Math.max(7, row.progress)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </article>
        </div>
      </section>

      <section className="rounded-xl border border-[#dbe5f0] bg-white p-4 shadow-[0_10px_24px_rgba(15,48,87,0.07)]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-[#13314a]">Alertes critiques de stock</h3>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#355a84]">{stocksCritiques.length} alerte(s)</span>
        </div>

        {stocksCritiques.length === 0 ? (
          <div className="mt-3 flex min-h-[120px] items-center justify-center rounded-lg border border-[#d5e1ee] bg-white">
            <div className="text-center">
              <Package className="mx-auto h-7 w-7 text-[#67829f]" />
              <p className="mt-2 text-sm font-semibold text-[#1d3f5d]">Aucune rupture imminente</p>
              <p className="text-xs text-[#6e8298]">Le niveau de stock est actuellement stable.</p>
            </div>
          </div>
        ) : (
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {stocksCritiques.map((item) => (
              <div key={item.stock_id} className="rounded-lg border border-[#e8d6d7] bg-white px-3 py-2.5">
                <p className="flex items-center gap-1.5 text-sm font-semibold text-[#21415f]">
                  <AlertTriangle className="h-4 w-4 text-[#c55a62]" />
                  Produit {item.product_id.slice(0, 8)}
                </p>
                <p className="mt-1 text-xs text-[#687e95]">
                  Quantite {toFixed(item.quantity, 1)} {item.unit} · seuil {toFixed(item.threshold, 1)} {item.unit}
                </p>
                <p className="mt-1 text-xs font-semibold text-[#bb4d56]">Deficit: {toFixed(item.deficit, 1)} {item.unit}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
