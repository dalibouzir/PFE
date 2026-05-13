"use client";

import { useState } from "react";
import type { AssistantChatResponse, ChatMetricFact, ChatUIBlock } from "@/lib/api/types";
import { BarChart3, ChevronDown, Database, FileText, FlaskConical, TriangleAlert } from "lucide-react";

type Props = {
  response?: AssistantChatResponse;
  fallbackText: string;
  hideMetaSections?: boolean;
};

type Generic = Record<string, unknown>;

function asObject(value: unknown): Generic {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Generic) : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function blockPayload(block: ChatUIBlock): Generic {
  const payload = asObject(block.payload);
  if (Object.keys(payload).length) return payload;
  return asObject(block as unknown);
}

function formatPriority(value: unknown): string {
  const raw = String(value || "").trim().toUpperCase();
  if (raw === "HIGH") return "Haute";
  if (raw === "MEDIUM") return "Moyenne";
  if (raw === "LOW") return "Faible";
  return raw || "Moyenne";
}

function priorityClass(value: unknown): string {
  const raw = String(value || "").trim().toUpperCase();
  if (raw === "HIGH") return "border-[#ef4444]/30 bg-[#fff1f2] text-[#9f1239]";
  if (raw === "LOW") return "border-[#16a34a]/25 bg-[#f0fdf4] text-[#166534]";
  return "border-[#f59e0b]/25 bg-[#fffbeb] text-[#92400e]";
}

function isNonOperationalMode(mode?: string | null): boolean {
  const current = String(mode || "").toLowerCase();
  return current === "small_talk" || current === "clarification_needed" || current === "unsupported";
}

function safeNonOperationalText(mode: string | undefined, fallbackText: string): string {
  const normalized = String(mode || "").toLowerCase();
  if (normalized === "clarification_needed") {
    return "Pouvez-vous préciser votre demande ? Je peux vous aider sur les stocks, lots, pertes, risques et recommandations.";
  }
  if (normalized === "unsupported") {
    return "Cette question sort du périmètre. Je peux répondre aux questions opérationnelles de la coopérative.";
  }
  return fallbackText;
}

function metric(metrics: ChatMetricFact[] | undefined, key: string): ChatMetricFact | undefined {
  return (metrics || []).find((item) => item.metric === key);
}

function normalizeSummaryText(text: string, hasTable: boolean): string {
  const clean = String(text || "").trim();
  if (!clean) return "";
  if (!hasTable) return clean;

  // Evite de répéter une longue liste textuelle quand un tableau structuré est déjà affiché.
  const firstBullet = clean.indexOf("\n- ");
  if (firstBullet > 0) {
    return clean.slice(0, firstBullet).trim();
  }
  if (clean.length > 260) {
    const firstSentence = clean.split(/[.!?]/).find((part) => part.trim().length > 20);
    if (firstSentence) return `${firstSentence.trim()}.`;
  }
  return clean;
}

function toReadableBullets(input: string): string[] {
  const compact = String(input || "").replace(/\s+/g, " ").trim();
  if (!compact) return [];
  const sentenceParts = compact
    .split(/(?:\.\s+|;\s+|\n+)/)
    .map((part) => part.trim())
    .filter((part) => part.length >= 18);
  if (sentenceParts.length >= 2) return sentenceParts.slice(0, 8);
  const commaParts = compact
    .split(/\s*,\s*/)
    .map((part) => part.trim())
    .filter((part) => part.length >= 18);
  if (commaParts.length >= 2) return commaParts.slice(0, 8);
  return [compact];
}

function ExpandableText({
  text,
  collapsedChars = 280,
  className = "text-sm text-[#173324]",
}: {
  text: string;
  collapsedChars?: number;
  className?: string;
}) {
  const clean = String(text || "").trim();
  const [expanded, setExpanded] = useState(false);
  const needsToggle = clean.length > collapsedChars;
  const visible = !needsToggle || expanded ? clean : `${clean.slice(0, Math.max(0, collapsedChars)).trimEnd()}…`;

  return (
    <div>
      <p className={className}>{visible}</p>
      {needsToggle ? (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-1 text-xs font-medium text-[#0a8f43] underline-offset-2 hover:underline"
        >
          {expanded ? "Voir moins" : "Voir plus"}
        </button>
      ) : null}
    </div>
  );
}

function extractWarningItems(blocks: ChatUIBlock[]): string[] {
  const warningBlocks = blocks.filter((block) => block.type === "warnings" || block.type === "analysis_section");
  const items: string[] = [];
  for (const block of warningBlocks) {
    const payload = asObject(block.payload);
    for (const item of asArray(payload.items)) {
      items.push(String(item));
    }
    for (const point of asArray(payload.points)) {
      const pointObj = asObject(point);
      const text = asString(pointObj.text || pointObj.value || Object.values(pointObj)[0]);
      if (text) items.push(text);
    }
  }
  return items.filter(Boolean);
}

function sourceIcon(role: string) {
  const normalized = role.toLowerCase();
  if (normalized.includes("sql")) return Database;
  if (normalized.includes("rag")) return FileText;
  if (normalized.includes("ml")) return FlaskConical;
  return FileText;
}

function SourcesSection({ block, citationsCount }: { block?: ChatUIBlock; citationsCount: number }) {
  const payload = asObject(block?.payload);
  const rawItems = asArray(payload.items);
  const items = rawItems
    .map((item) => {
      if (typeof item === "string") return { source: item, role: "SOURCE" };
      const row = asObject(item);
      return {
        source: asString(row.source || row.title || row.label || "Source"),
        role: asString(row.role || row.type || "SOURCE"),
      };
    })
    .filter((item) => item.source);

  return (
    <details className="group rounded-2xl border border-[var(--line)] bg-white/90 p-4">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
        <span className="text-sm font-semibold text-[#173324]">Sources utilisées ({items.length || citationsCount})</span>
        <ChevronDown className="h-4 w-4 text-[var(--muted)] transition-transform group-open:rotate-180" />
      </summary>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.length ? (
          items.map((item, index) => {
            const Icon = sourceIcon(item.role);
            return (
              <span
                key={`${item.source}-${index}`}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#c7dfcf] bg-[#f2faf5] px-2.5 py-1 text-[11px] font-medium text-[#24523b]"
              >
                <Icon className="h-3.5 w-3.5" />
                {item.role}: {item.source}
              </span>
            );
          })
        ) : (
          <p className="text-xs text-[var(--muted)]">Aucune source structurée disponible.</p>
        )}
      </div>
    </details>
  );
}

function TechnicalDetailsSection({
  response,
  warnings,
}: {
  response: AssistantChatResponse;
  warnings: string[];
}) {
  const metrics = response.context_metrics || [];
  const modeMetric = metric(metrics, "retrieval_plan.intent_type");
  const confidenceMetric = metric(metrics, "orchestration.confidence_score");
  const sourceCount = response.citations?.length || 0;
  const agentCount = Number(metric(metrics, "agent.agents_count")?.value || 0);
  const confidencePct = Math.round(Math.max(0, Math.min(100, Number(confidenceMetric?.value || 0) * 100)));

  return (
    <details className="group rounded-2xl border border-[var(--line)] bg-white/90 p-4">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
        <span className="text-sm font-semibold text-[#173324]">Détails techniques</span>
        <ChevronDown className="h-4 w-4 text-[var(--muted)] transition-transform group-open:rotate-180" />
      </summary>
      <div className="mt-3 grid gap-2 text-xs text-[#355f4b] sm:grid-cols-2">
        <p>Mode de réponse: {String(modeMetric?.unit || response.mode || "N/A")}</p>
        <p>Confiance: {Number.isFinite(confidencePct) ? `${confidencePct}%` : "N/A"}</p>
        <p>Agents mobilisés: {agentCount || "N/A"}</p>
        <p>Citations: {sourceCount}</p>
        <p className="sm:col-span-2">Avertissements: {warnings.length ? warnings.join(" | ") : "Aucun"}</p>
      </div>
    </details>
  );
}

function RecommendationsSection({ block }: { block: ChatUIBlock }) {
  const payload = asObject(block.payload);
  const items = asArray(payload.items).map((item) => asObject(item));
  if (!items.length) return null;

  return (
    <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
      <h3 className="text-sm font-semibold text-[#173324]">{block.title || "Actions recommandées"}</h3>
      <div className="mt-3 grid gap-4">
        {items.map((item, index) => {
          const evidence = asArray(item.evidence_details || item.evidence).map((part) => String(part)).filter(Boolean);
          const targetTokens = [item.affected_lot, item.affected_product, item.affected_stage].map((token) => String(token || "").trim()).filter(Boolean);
          return (
            <article key={`recommendation-${index}`} className="rounded-xl border border-[#d7e6da] bg-[#f8fcf8] p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${priorityClass(item.priority)}`}>
                  Priorité {formatPriority(item.priority)}
                </span>
                {targetTokens.length ? (
                  <span className="rounded-full border border-[#c7dfcf] bg-white px-2 py-0.5 text-[10px] font-medium text-[#355f4b]">
                    Cible: {targetTokens.join(" / ")}
                  </span>
                ) : null}
              </div>
              <p className="mt-3 text-[13px] font-medium uppercase tracking-[0.06em] text-[#4f705d]">Action</p>
              <p className="mt-1 text-sm font-semibold text-[#173324]">{asString(item.action || item.title || "Action recommandée")}</p>
              {asString(item.reason) ? (
                <>
                  <p className="mt-3 text-[13px] font-medium uppercase tracking-[0.06em] text-[#4f705d]">Raison</p>
                  <p className="mt-1 text-xs leading-5 text-[#4f705d]">{asString(item.reason)}</p>
                </>
              ) : null}
              {evidence.length ? (
                <div className="mt-3">
                  <p className="text-[13px] font-medium uppercase tracking-[0.06em] text-[#4f705d]">Preuves</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {evidence.map((value, evidenceIndex) => (
                    <span key={`${index}-evidence-${evidenceIndex}`} className="inline-flex rounded-full border border-[#d8e6dc] bg-white px-2 py-0.5 text-[10px] text-[#355f4b]">
                      {value}
                    </span>
                  ))}
                  </div>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function BestPracticesSection({ block }: { block: ChatUIBlock }) {
  const payload = asObject(block.payload);
  const items = asArray(payload.items).map((item) => String(item)).filter(Boolean);
  if (!items.length) return null;

  const readableItems = items.flatMap((item) => toReadableBullets(item)).filter(Boolean);

  return (
    <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
      <h3 className="text-sm font-semibold text-[#173324]">{block.title || "Bonnes pratiques"}</h3>
      <div className="mt-3 grid gap-2">
        {readableItems.map((item, index) => (
          <article key={`practice-${index}`} className="rounded-xl border border-[#d8e6dc] bg-[#f8fcf8] px-3 py-2.5 text-sm text-[#173324]">
            <div className="flex items-start gap-2">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[#0a8f43]" />
              <ExpandableText text={item} collapsedChars={260} className="text-sm leading-6 text-[#173324]" />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function TablesSection({ blocks }: { blocks: ChatUIBlock[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        const payload = blockPayload(block);
        const columns = asArray(payload.columns).map((column) => String(column));
        const rows = asArray(payload.rows).map((row) =>
          Array.isArray(row) ? row.map((cell) => (typeof cell === "number" || typeof cell === "string" ? cell : String(cell ?? ""))) : []
        );

        return (
          <section key={`table-${index}`} className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
            <h3 className="text-sm font-semibold text-[#173324]">{block.title || "Tableau"}</h3>
            <div className="mt-3 overflow-auto">
              <table className="wf-table min-w-full text-left text-sm">
                <thead>
                  <tr>
                    {columns.map((column) => (
                      <th key={`${block.title}-${column}`}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.length ? (
                    rows.map((row, rowIndex) => (
                      <tr key={`${block.title || "table"}-${rowIndex}`}>
                        {row.map((cell, cellIndex) => (
                          <td key={`${rowIndex}-${cellIndex}`}>{String(cell)}</td>
                        ))}
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={Math.max(columns.length, 1)} className="text-[var(--muted)]">
                        Aucune donnée disponible.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </>
  );
}

type ChartDatum = {
  label: string;
  value: number;
};

function getChartData(block: ChatUIBlock): ChartDatum[] {
  const payload = blockPayload(block);
  const xKey = asString(payload.x_key, "");
  const yKey = asString(payload.y_key, "");
  const rawData = asArray(payload.data);
  const pointsFromData: ChartDatum[] = rawData
    .map((row) => asObject(row))
    .map((row) => {
      const labelValue =
        (xKey ? row[xKey] : undefined) ??
        row.stage ??
        row.product ??
        row.batch_ref ??
        row.x ??
        "";
      const numericValue =
        (yKey ? row[yKey] : undefined) ??
        row.loss_pct ??
        row.available_stock_kg ??
        row.y ??
        null;
      const label = String(labelValue || "").trim();
      const value = asNumber(numericValue);
      return label && value !== null ? { label, value } : null;
    })
    .filter((item): item is ChartDatum => Boolean(item));
  if (pointsFromData.length) return pointsFromData;

  const labels = asArray(payload.labels).map((item) => String(item || "").trim());
  const series = asArray(payload.series).map((item) => asObject(item));
  const firstSeries = series[0];
  const values = asArray(firstSeries?.data);
  const pointsFromSeries: ChartDatum[] = labels
    .map((label, index) => {
      const value = asNumber(values[index]);
      return label && value !== null ? { label, value } : null;
    })
    .filter((item): item is ChartDatum => Boolean(item));
  return pointsFromSeries;
}

function ChartsSection({ blocks }: { blocks: ChatUIBlock[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        const payload = blockPayload(block);
        const xKey = asString(payload.x_key, "");
        const yKey = asString(payload.y_key, "");
        const rawData = asArray(payload.data).map((row) => asObject(row));
        const chartData = getChartData(block);
        const hasData = chartData.length > 0;
        const maxValue = hasData ? Math.max(...chartData.map((item) => item.value), 0) : 0;
        const fallbackRows = rawData
          .map((row) => {
            const label = String(
              (xKey ? row[xKey] : undefined) ??
                row.stage ??
                row.product ??
                row.batch_ref ??
                row.x ??
                "",
            ).trim();
            const value = String(
              (yKey ? row[yKey] : undefined) ??
                row.loss_pct ??
                row.available_stock_kg ??
                row.y ??
                "",
            ).trim();
            return label || value ? [label || "-", value || "-"] : null;
          })
          .filter((row): row is [string, string] => Boolean(row));
        return (
          <section key={`chart-${index}`} className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-[#173324]">
              <BarChart3 className="h-4 w-4 text-[#0a8f43]" />
              {block.title || "Graphique"}
            </h3>
            {hasData ? (
              <div className="mt-4 grid gap-2">
                {chartData.map((item, itemIndex) => {
                  const widthPct = maxValue > 0 ? Math.max((item.value / maxValue) * 100, 4) : 0;
                  return (
                    <div key={`chart-row-${index}-${itemIndex}-${item.label}-${item.value}`} className="grid gap-1">
                      <div className="flex items-center justify-between gap-3 text-xs">
                        <span className="truncate text-[#355f4b]">{item.label}</span>
                        <span className="font-semibold text-[#173324]">{item.value.toLocaleString("fr-FR")}</span>
                      </div>
                      <div className="h-2.5 rounded-full bg-[#e8f2eb]">
                        <div
                          className="h-2.5 rounded-full bg-gradient-to-r from-[#66b973] to-[#0a8f43]"
                          style={{ width: `${widthPct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="mt-3 rounded-xl border border-[#e3eadf] bg-[#f9fcf9] p-3">
                <p className="text-xs text-[#4f705d]">Données graphiques incomplètes. Affichage tabulaire de secours.</p>
                <div className="mt-2 overflow-auto">
                  <table className="wf-table min-w-full text-left text-xs">
                    <thead>
                      <tr>
                        <th>Libellé</th>
                        <th>Valeur</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fallbackRows.length ? (
                        fallbackRows.map((row, rowIndex) => (
                          <tr key={`fallback-${index}-${rowIndex}`}>
                            <td>{row[0]}</td>
                            <td>{row[1]}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={2} className="text-[var(--muted)]">
                            Aucune donnée exploitable.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        );
      })}
    </>
  );
}

export function ExecutiveResponse({ response, fallbackText, hideMetaSections = false }: Props) {
  if (!response) {
    return <p className="whitespace-pre-wrap text-sm leading-7 text-[#173324]">{fallbackText}</p>;
  }

  if (isNonOperationalMode(response.mode)) {
    return <p className="whitespace-pre-wrap text-sm leading-7 text-[#173324]">{safeNonOperationalText(response.mode, fallbackText)}</p>;
  }

  const blocks = response.ui_blocks || [];
  if (!blocks.length) {
    return <p className="whitespace-pre-wrap text-sm leading-7 text-[#173324]">{fallbackText}</p>;
  }

  const summaryBlock = blocks.find((block) => block.type === "executive_summary");
  const tableBlocks = blocks.filter((block) => block.type === "table");
  const chartBlocks = blocks.filter((block) => block.type === "bar_chart" || block.type === "line_chart" || block.type === "chart");
  const recommendationBlock = blocks.find((block) => block.type === "recommendation_cards" || block.type === "recommendations");
  const bestPracticesBlock = blocks.find((block) => block.type === "best_practices");
  const sourcesBlock = blocks.find((block) => block.type === "sources");
  const warningItems = extractWarningItems(blocks);

  const summaryTextRaw = asString(asObject(summaryBlock?.payload).text, response.message || fallbackText);
  const summaryText = normalizeSummaryText(summaryTextRaw, tableBlocks.length > 0);
  const sourceCount = response.citations?.length || 0;
  const summaryWasShortened = summaryText.trim() !== summaryTextRaw.trim();

  return (
    <div className="space-y-3">
      <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-5 shadow-[0_8px_26px_rgba(0,0,0,0.05)]">
        <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-[#3f6b52]">Résumé exécutif</h3>
        <p className="mt-2 whitespace-pre-wrap text-[15px] leading-7 text-[#173324]">{summaryText}</p>
        {summaryWasShortened ? (
          <details className="group mt-2">
            <summary className="cursor-pointer text-xs font-medium text-[#0a8f43] underline-offset-2 hover:underline">
              Voir plus
            </summary>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#355f4b]">{summaryTextRaw}</p>
          </details>
        ) : null}
      </section>

      {tableBlocks.length ? <TablesSection blocks={tableBlocks} /> : null}
      {chartBlocks.length ? <ChartsSection blocks={chartBlocks} /> : null}
      {recommendationBlock ? <RecommendationsSection block={recommendationBlock} /> : null}
      {bestPracticesBlock ? <BestPracticesSection block={bestPracticesBlock} /> : null}

      {warningItems.length ? (
        <section className="rounded-2xl border border-[#f59e0b]/20 bg-[#fffdf6] p-3">
          <div className="flex items-start gap-2">
            <TriangleAlert className="mt-0.5 h-4 w-4 text-[#b45309]" />
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-[0.06em] text-[#92400e]">Avertissements</h3>
              <ul className="mt-1.5 space-y-1 text-xs text-[#7c5c2f]">
                {warningItems.map((item, index) => (
                  <li key={`warning-${index}`}>• {item}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      ) : null}

      {!hideMetaSections ? (
        <>
          <SourcesSection block={sourcesBlock} citationsCount={sourceCount} />
          <TechnicalDetailsSection response={response} warnings={warningItems} />
        </>
      ) : null}
    </div>
  );
}
