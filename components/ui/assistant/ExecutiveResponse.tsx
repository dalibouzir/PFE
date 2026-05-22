"use client";

import { useEffect, useMemo, useState } from "react";
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

function metricText(metrics: ChatMetricFact[] | undefined, key: string): string {
  const item = metric(metrics, key);
  return String(item?.unit || item?.notes || "").trim();
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

function firstNumber(value: string): number | null {
  const match = String(value || "").match(/-?\d+(?:[.,]\d+)?/);
  if (!match) return null;
  const parsed = Number(match[0].replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function formatFrNumber(value: number): string {
  return value.toLocaleString("fr-FR", { maximumFractionDigits: 1, minimumFractionDigits: Number.isInteger(value) ? 0 : 1 });
}

function firstUpper(value: string): string {
  const clean = String(value || "").trim();
  if (!clean) return clean;
  return `${clean.charAt(0).toUpperCase()}${clean.slice(1)}`;
}

type ParsedTable = {
  block: ChatUIBlock;
  title: string;
  columns: string[];
  rows: string[][];
};

function parseTableBlock(block: ChatUIBlock): ParsedTable | null {
  const payload = blockPayload(block);
  const columns = asArray(payload.columns).map((column) => String(column).toLowerCase());
  const rows = asArray(payload.rows).map((row) => (Array.isArray(row) ? row.map((cell) => String(cell ?? "")) : []));
  if (!rows.length) return null;
  return {
    block,
    title: String(block.title || "").toLowerCase(),
    columns,
    rows,
  };
}

function deriveComparisonSummary(table: ParsedTable): string | null {
  const { columns, rows } = table;
  const idx = (needle: string[]) => columns.findIndex((column) => needle.some((token) => column.includes(token)));
  const batchIdx = idx(["lot", "batch"]);
  const lossIdx = idx(["perte %", "loss %", "loss_pct", "taux de perte"]);
  const effIdx = idx(["efficacité", "efficiency"]);
  if (rows.length >= 2 && batchIdx >= 0 && lossIdx >= 0 && effIdx >= 0) {
    const sorted = [...rows].sort((a, b) => (firstNumber(a[lossIdx] || "") ?? 0) - (firstNumber(b[lossIdx] || "") ?? 0));
    const better = sorted[0];
    const worse = sorted[sorted.length - 1];
    if ((worse[batchIdx] || "") !== (better[batchIdx] || "")) {
      const worseLoss = firstNumber(worse[lossIdx] || "");
      const betterLoss = firstNumber(better[lossIdx] || "");
      const worseEff = firstNumber(worse[effIdx] || "");
      const betterEff = firstNumber(better[effIdx] || "");
      if (worseLoss !== null && betterLoss !== null && worseEff !== null && betterEff !== null) {
        return `${worse[batchIdx]} performe moins bien que ${better[batchIdx]} : ${formatFrNumber(worseLoss)}% de perte contre ${formatFrNumber(betterLoss)}%, avec une efficacité de ${formatFrNumber(worseEff)}% contre ${formatFrNumber(betterEff)}%.`;
      }
    }
  }
  return null;
}

function deriveGapSummary(table: ParsedTable): string | null {
  const { columns, rows } = table;
  const idx = (needle: string[]) => columns.findIndex((column) => needle.some((token) => column.includes(token)));
  const batchIdx = idx(["lot", "batch"]);
  const gapIdx = idx(["écart", "gap", "perte kg", "kg perd", "difference entree sortie", "différence entrée sortie"]);
  if (batchIdx >= 0 && gapIdx >= 0) {
    const sorted = [...rows].sort((a, b) => (firstNumber(b[gapIdx] || "") ?? 0) - (firstNumber(a[gapIdx] || "") ?? 0));
    const lead = sorted[0];
    const batch = lead[batchIdx] || "N/A";
    const gap = firstNumber(lead[gapIdx] || "");
    if (gap !== null) {
      return `${batch} présente le plus grand écart matière : ${formatFrNumber(gap)} kg perdus entre l’entrée et la sortie.`;
    }
  }
  return null;
}

function deriveLossSummary(table: ParsedTable): string | null {
  const { columns, rows } = table;
  const idx = (needle: string[]) => columns.findIndex((column) => needle.some((token) => column.includes(token)));
  const batchIdx = idx(["lot", "batch"]);
  const lossIdx = idx(["perte %", "loss %", "loss_pct", "taux de perte"]);
  const effIdx = idx(["efficacité", "efficiency"]);
  if (batchIdx >= 0 && lossIdx >= 0) {
    const sorted = [...rows].sort((a, b) => (firstNumber(b[lossIdx] || "") ?? 0) - (firstNumber(a[lossIdx] || "") ?? 0));
    const lead = sorted[0];
    const batch = lead[batchIdx] || "N/A";
    const loss = firstNumber(lead[lossIdx] || "");
    const eff = effIdx >= 0 ? firstNumber(lead[effIdx] || "") : null;
    if (loss !== null && eff !== null) {
      return `Le lot le plus critique est ${batch} avec ${formatFrNumber(loss)}% de perte et une efficacité de ${formatFrNumber(eff)}%.`;
    }
  }
  return null;
}

function deriveStageSummary(table: ParsedTable): string | null {
  const { columns, rows } = table;
  const idx = (needle: string[]) => columns.findIndex((column) => needle.some((token) => column.includes(token)));
  const batchIdx = idx(["lot", "batch"]);
  const gapIdx = idx(["écart", "gap", "perte kg", "kg perd"]);
  const stageIdx = idx(["étape", "stage"]);
  const lossIdx = idx(["perte %", "loss %", "loss_pct", "taux de perte"]);
  if (stageIdx >= 0 && lossIdx >= 0) {
    const sorted = [...rows].sort((a, b) => (firstNumber(b[lossIdx] || "") ?? 0) - (firstNumber(a[lossIdx] || "") ?? 0));
    const lead = sorted[0];
    const stage = lead[stageIdx] || "N/A";
    const batch = batchIdx >= 0 ? lead[batchIdx] : "";
    const gap = gapIdx >= 0 ? firstNumber(lead[gapIdx] || "") : null;
    const loss = firstNumber(lead[lossIdx] || "");
    const leadTarget = batch ? `de ${batch}` : "";
    if (gap !== null && loss !== null) {
      return `La perte principale ${leadTarget} se situe à l’étape ${stage}, avec ${formatFrNumber(gap)} kg perdus et ${formatFrNumber(loss)}% de perte.`;
    }
    return `La perte principale ${leadTarget} se situe à l’étape ${stage}.`.replace(/\s+/g, " ").trim();
  }
  return null;
}

function deriveStockSummary(table: ParsedTable): string | null {
  const { columns, rows } = table;
  const idx = (needle: string[]) => columns.findIndex((column) => needle.some((token) => column.includes(token)));
  const productIdx = idx(["produit", "product"]);
  const qtyIdx = idx(["restant", "disponible", "available", "stock"]);
  if (productIdx < 0 || qtyIdx < 0) return null;
  const ranked = [...rows].sort((a, b) => (firstNumber(b[qtyIdx] || "") ?? 0) - (firstNumber(a[qtyIdx] || "") ?? 0));
  if (!ranked.length) return null;
  const lead = ranked[0];
  const total = ranked.reduce((acc, row) => acc + (firstNumber(row[qtyIdx] || "") ?? 0), 0);
  const leadQty = firstNumber(lead[qtyIdx] || "");
  if (leadQty === null) return null;
  return `La coopérative dispose actuellement de ${formatFrNumber(total)} kg de stock disponible répartis sur ${ranked.length} produits. Le produit le plus disponible est ${lead[productIdx]} avec ${formatFrNumber(leadQty)} kg. Le détail par produit et par qualité est présenté ci-dessous.`;
}

function deriveSummaryFromRecommendations(blocks: ChatUIBlock[]): string | null {
  const recommendationBlock = blocks.find((block) => block.type === "recommendation_cards" || block.type === "recommendations");
  if (!recommendationBlock) return null;
  const items = asArray(asObject(recommendationBlock.payload).items).map((item) => asObject(item));
  if (!items.length) return null;
  const first = items[0];
  let action = asString(first.action || first.title, "action prioritaire")
    .replace(/\s+/g, " ")
    .replace(/[.:;,\s]+$/g, "")
    .trim();
  const lot = asString(first.affected_lot || first.related_batch || first.batch_ref, "").trim();
  const cleanLot = lot.replace(/^lot\s+/i, "").trim();
  if (cleanLot) {
    const lotRegex = new RegExp(`\\b(?:lot\\s*)?${cleanLot.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "ig");
    action = action
      .replace(/\bisoler\s+le\s+lot\b/i, "l’isoler")
      .replace(/\bisoler\b/i, "l’isoler")
      .replace(lotRegex, "")
      .replace(/\s{2,}/g, " ")
      .replace(/\s+([,.;:])/g, "$1")
      .trim();
  }
  if (items.length === 1) {
    if (cleanLot) {
      return `Avec les preuves disponibles, une seule action fiable peut être proposée pour ${cleanLot} : ${firstUpper(action)}. Les autres actions ne sont pas générées car le contexte documentaire est limité.`;
    }
    return `Avec les preuves disponibles, une seule action fiable peut être proposée : ${firstUpper(action)}. Les autres actions ne sont pas générées car le contexte documentaire est limité.`;
  }
  const target = cleanLot || asString(first.affected_product || first.target, "la coopérative");
  return `Voici les actions prioritaires proposées pour ${target}, chacune liée à des preuves disponibles.`;
}

function pickExecutiveSummary(response: AssistantChatResponse | undefined, blocks: ChatUIBlock[], fallbackText: string): string {
  const metrics = response?.context_metrics || [];
  const intentFamily = String(metric(metrics, "retrieval_plan.intent_type")?.unit || "").trim().toUpperCase();
  const sqlOperation = String(
    metric(metrics, "orchestration.sql_operation")?.unit ||
      metric(metrics, "sql_dispatch_trace.sql_operation")?.unit ||
      ""
  )
    .trim()
    .toLowerCase();

  const summaryBlock = blocks.find((block) => block.type === "executive_summary");
  const summaryFromBlock = asString(asObject(summaryBlock?.payload).text, "").trim();
  const summaryFromMessage = asString(response?.message, "").trim();
  const genericSummary = /bilan matière global|^stock:\s*\d+\s*produit|^conclusion:|^action prioritaire:/i;

  const recommendationSummary = deriveSummaryFromRecommendations(blocks);
  if (
    recommendationSummary &&
    (intentFamily.includes("RECOMMENDATION") || blocks.some((block) => block.type === "recommendations" || block.type === "recommendation_cards"))
  ) {
    return recommendationSummary;
  }

  const parsedTables = blocks
    .filter((block) => block.type === "comparison_table" || block.type === "table")
    .map(parseTableBlock)
    .filter((value): value is ParsedTable => Boolean(value));

  const comparisonTable = parsedTables.find((table) => table.block.type === "comparison_table" || table.title.includes("compar"));
  if (comparisonTable) {
    const summary = deriveComparisonSummary(comparisonTable);
    if (summary && (intentFamily === "LOT_COMPARISON" || sqlOperation === "get_canonical_material_balance_for_lots")) return summary;
  }

  const gapTable = parsedTables.find((table) => {
    const merged = `${table.title} ${table.columns.join(" ")}`;
    return /écart|gap|kg|entrée|sortie|matière|difference|différence/.test(merged);
  });
  if (gapTable) {
    const summary = deriveGapSummary(gapTable);
    if (
      summary &&
      (intentFamily === "INPUT_OUTPUT_GAP" || sqlOperation === "get_canonical_material_balance" || /écart|gap|kg|entrée|sortie|matière|difference|différence/.test(`${gapTable.title} ${gapTable.columns.join(" ")}`))
    ) {
      return summary;
    }
  }

  const lossTable = parsedTables.find((table) => {
    const merged = `${table.title} ${table.columns.join(" ")}`;
    return /perte|loss|efficacité|efficiency|rendement/.test(merged);
  });
  if (lossTable) {
    const summary = deriveLossSummary(lossTable);
    if (summary) return summary;
  }

  const stageTable = parsedTables.find((table) => {
    const merged = `${table.title} ${table.columns.join(" ")}`;
    return /étape|stage/.test(merged);
  });
  if (stageTable) {
    const summary = deriveStageSummary(stageTable);
    if (summary) return summary;
  }

  const stockTable = parsedTables.find((table) => {
    const merged = `${table.title} ${table.columns.join(" ")}`;
    return /stock|produit|grade|qualité|qualite|disponible|restant/.test(merged);
  });
  if (stockTable) {
    const summary = deriveStockSummary(stockTable);
    if (summary) return summary;
  }

  if (summaryFromBlock && !genericSummary.test(summaryFromBlock)) return summaryFromBlock;

  if (summaryFromMessage && !genericSummary.test(summaryFromMessage)) {
    const firstSentence = summaryFromMessage
      .replace(/Détail qualité\s*:\s*[^.]+\.?/gi, "Le détail par produit et par qualité est présenté ci-dessous.")
      .split(/\n|(?<=[.!?])\s+/)
      .find((line) => line.trim().length > 15);
    if (firstSentence) return firstSentence.trim();
    return summaryFromMessage;
  }
  if (summaryFromBlock) return summaryFromBlock;
  return summaryFromMessage || fallbackText;
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

function extractLimitItems(block?: ChatUIBlock): string[] {
  const payload = asObject(block?.payload);
  const items = asArray(payload.items).map((item) => String(item || "").trim()).filter(Boolean);
  return items;
}

function normalizeWarningText(value: string): string {
  return String(value || "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function isGenericReliabilityText(value: string): boolean {
  const normalized = normalizeWarningText(value);
  return (
    normalized.includes("avertissement de fiabilite") ||
    normalized.includes("avertissement de fiabilité") ||
    normalized.includes("informations partielles ou insuffisantes") ||
    normalized.includes("donnees partielles ou insuffisantes") ||
    normalized.includes("données partielles ou insuffisantes")
  );
}

function responseHasCleanSqlEvidence(response?: AssistantChatResponse): boolean {
  const metrics = response?.context_metrics || [];
  const route = `${response?.mode || ""} ${metricText(metrics, "orchestration.route")}`.toUpperCase();
  const sqlStatus = metricText(metrics, "sql_dispatch_trace.evidence_status") || metricText(metrics, "evidence_status.sql");
  const normalizedStatus = sqlStatus.toUpperCase();
  return (
    route.includes("SQL_ONLY") &&
    ["HAS_EVIDENCE", "PROVEN_NO_DATA"].includes(normalizedStatus)
  );
}

function responseUsesMl(response?: AssistantChatResponse): boolean {
  const metrics = response?.context_metrics || [];
  const route = `${response?.mode || ""} ${metricText(metrics, "orchestration.route")}`.toUpperCase();
  const agents = String(metric(metrics, "agent.agents_count")?.notes || "").toUpperCase();
  const mlStatus = metricText(metrics, "evidence_status.ml").toUpperCase();
  const hasMlSource = (response?.citations || []).some((citation) => String(citation.topic || "").toUpperCase() === "ML");
  return route.includes("ML") || agents.includes("MLLOSSAGENT") || hasMlSource || Boolean(mlStatus);
}

function isUnknownMlKpiItem(item: Generic): boolean {
  const label = `${asString(item.title)} ${asString(item.label)} ${asString(item.metric)}`.toLowerCase();
  if (!label.includes("ml") && !label.includes("signal")) return false;
  const status = `${asString(item.status)} ${String(item.value ?? "")} ${asString(item.unit)}`.toLowerCase();
  return !status.trim() || status.includes("unknown") || status.includes("n/a");
}

function filterKpiBlock(block: ChatUIBlock | undefined, response?: AssistantChatResponse): ChatUIBlock | undefined {
  if (!block) return undefined;
  const payload = asObject(block.payload);
  const items = asArray(payload.items).map((item) => asObject(item));
  if (!items.length) return block;
  const allowMl = responseUsesMl(response);
  const filteredItems = allowMl ? items : items.filter((item) => !isUnknownMlKpiItem(item));
  if (!filteredItems.length) return undefined;
  if (filteredItems.length === items.length) return block;
  return { ...block, payload: { ...payload, items: filteredItems } };
}

function filterLimitsBlock(block: ChatUIBlock | undefined, response?: AssistantChatResponse): ChatUIBlock | undefined {
  if (!block) return undefined;
  const payload = asObject(block.payload);
  const items = asArray(payload.items).map((item) => String(item || "").trim()).filter(Boolean);
  if (!items.length) return block;
  const cleanSqlEvidence = responseHasCleanSqlEvidence(response);
  const filteredItems = cleanSqlEvidence ? items.filter((item) => !isGenericReliabilityText(item)) : items;
  if (!filteredItems.length) return undefined;
  if (filteredItems.length === items.length) return block;
  return { ...block, payload: { ...payload, items: filteredItems } };
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
  const route = metricText(metrics, "orchestration.route") || String(modeMetric?.unit || response.mode || "N/A");
  const intentFamily = metricText(metrics, "retrieval_plan.intent_type") || "N/A";
  const sqlOperation = metricText(metrics, "sql_dispatch_trace.sql_operation") || "N/A";
  const sqlEvidenceStatus = metricText(metrics, "sql_dispatch_trace.evidence_status") || metricText(metrics, "evidence_status.sql") || "N/A";
  const evidenceRows = Number(metric(metrics, "sql_dispatch_trace.evidence_row_count")?.value ?? NaN);
  const finalResponseSource = metricText(metrics, "final_response_source") || "N/A";
  const llmProvider = metricText(metrics, "llm_provider") || "N/A";
  const sqlMs = Number(metric(metrics, "orchestration.sql_duration_ms")?.value || 0);
  const ragMs = Number(metric(metrics, "orchestration.rag_duration_ms")?.value || 0);
  const llmMs = Number(metric(metrics, "orchestration.llm_duration_ms")?.value || 0);
  const totalMs = Number(metric(metrics, "orchestration.total_duration_ms")?.value || 0);
  const warningText = warnings.join(" ").toLowerCase();
  const sqlLayer = ["HAS_EVIDENCE", "PROVEN_NO_DATA"].includes(sqlEvidenceStatus.toUpperCase()) ? "fiables" : sourceCount > 0 ? "fiables" : "limitées";
  const ragLayer = warningText.includes("documentaire") ? "limité" : "disponible";
  const mlLayer = warningText.includes("ml") ? "indicatif/limité" : "indicatif";

  return (
    <details className="group rounded-2xl border border-[var(--line)] bg-white/90 p-4">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
        <span className="text-sm font-semibold text-[#173324]">Détails techniques</span>
        <ChevronDown className="h-4 w-4 text-[var(--muted)] transition-transform group-open:rotate-180" />
      </summary>
      <div className="mt-3 grid gap-2 text-xs text-[#355f4b] sm:grid-cols-2">
        <p>Route: {route}</p>
        <p>Intent: {intentFamily}</p>
        <p>SQL operation: {sqlOperation}</p>
        <p>Evidence SQL: {sqlEvidenceStatus}</p>
        <p>Confiance: {Number.isFinite(confidencePct) ? `${confidencePct}%` : "N/A"}</p>
        <p>Evidence rows: {Number.isFinite(evidenceRows) ? evidenceRows : "N/A"}</p>
        <p>Agents mobilisés: {agentCount || "N/A"}</p>
        <p>Citations: {sourceCount}</p>
        <p>Final source: {finalResponseSource}</p>
        <p>LLM provider: {llmProvider}</p>
        <p>Durée totale: {totalMs > 0 ? `${Math.round(totalMs)} ms` : "N/A"}</p>
        <p>SQL/RAG/LLM: {sqlMs > 0 ? `${Math.round(sqlMs)} ms` : "-"} / {ragMs > 0 ? `${Math.round(ragMs)} ms` : "-"} / {llmMs > 0 ? `${Math.round(llmMs)} ms` : "-"}</p>
        <p className="sm:col-span-2">Lecture par couche: Données SQL {sqlLayer} | RAG documentaire {ragLayer} | ML {mlLayer}</p>
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

function KpiCardsSection({ block }: { block: ChatUIBlock }) {
  const payload = asObject(block.payload);
  const items = asArray(payload.items).map((item) => asObject(item));
  if (!items.length) return null;
  const statusTone = (status: string) => {
    const s = status.toLowerCase();
    if (s.includes("critical") || s.includes("alert")) return "border-[#ef4444]/30 bg-[#fff1f2] text-[#9f1239]";
    if (s.includes("warning")) return "border-[#f59e0b]/25 bg-[#fffbeb] text-[#92400e]";
    return "border-[#16a34a]/25 bg-[#f0fdf4] text-[#166534]";
  };
  return (
    <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
      <h3 className="text-sm font-semibold text-[#173324]">{block.title || "Indicateurs clés"}</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((item, index) => (
          <article key={`kpi-${index}`} className="rounded-xl border border-[#d7e6da] bg-[#f8fcf8] p-3">
            <p className="text-[11px] uppercase tracking-[0.06em] text-[#4f705d]">{asString(item.title || item.label || "Indicateur")}</p>
            <p className="mt-1 text-xl font-semibold text-[#173324]">{String(item.value ?? "-")} {asString(item.unit)}</p>
            {asString(item.explanation) ? <p className="mt-1 text-xs text-[#557a66]">{asString(item.explanation)}</p> : null}
            <span className={`mt-2 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusTone(asString(item.status || "neutral"))}`}>
              {asString(item.status || "neutral")}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}

function LimitsSection({ block }: { block: ChatUIBlock }) {
  const payload = asObject(block.payload);
  const items = asArray(payload.items).map((item) => String(item)).filter(Boolean);
  if (!items.length) return null;
  return (
    <section className="rounded-2xl border border-[#f59e0b]/20 bg-[#fffdf6] p-3">
      <h3 className="text-xs font-semibold uppercase tracking-[0.06em] text-[#92400e]">{block.title || "Limites"}</h3>
      <ul className="mt-1.5 space-y-1 text-xs text-[#7c5c2f]">
        {items.map((item, index) => (
          <li key={`limit-${index}`}>• {item}</li>
        ))}
      </ul>
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
            <div className="wf-mobile-scroll mt-3 overflow-auto">
              <table className="wf-table w-full min-w-[980px] text-left text-sm">
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
                <div className="wf-mobile-scroll mt-2 overflow-auto">
                  <table className="wf-table w-full min-w-[980px] text-left text-xs">
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
  const blocks = response?.ui_blocks || [];

  const kpiBlock = filterKpiBlock(blocks.find((block) => block.type === "kpi_cards"), response);
  const tableBlocks = blocks.filter((block) => block.type === "table" || block.type === "comparison_table");
  const chartBlocks = blocks.filter((block) => block.type === "bar_chart" || block.type === "line_chart" || block.type === "chart");
  const recommendationBlock = blocks.find((block) => block.type === "recommendation_cards" || block.type === "recommendations");
  const bestPracticesBlock = blocks.find((block) => block.type === "best_practices");
  const limitsBlock = filterLimitsBlock(blocks.find((block) => block.type === "limits_block"), response);
  const sourcesBlock = blocks.find((block) => block.type === "sources");
  const warningItemsRaw = extractWarningItems(blocks);
  const limitItems = extractLimitItems(limitsBlock);
  const limitKeySet = new Set(limitItems.map(normalizeWarningText));
  const mode = String(response?.mode || "").toUpperCase();
  const warningItems = warningItemsRaw
    .filter((item) => !limitKeySet.has(normalizeWarningText(item)))
    .filter((item) => {
      const normalized = normalizeWarningText(item);
      if (normalized === normalizeWarningText("Avertissement de fiabilité: informations partielles ou insuffisantes pour cette requête.")) {
        const hasStructuredEvidence = tableBlocks.length > 0 || Boolean(kpiBlock) || chartBlocks.length > 0;
        if (mode.includes("SQL_ONLY") && hasStructuredEvidence) return false;
      }
      if (isGenericReliabilityText(normalized) && responseHasCleanSqlEvidence(response)) return false;
      if (!mode.includes("SQL_ONLY")) return true;
      if (!tableBlocks.length && !kpiBlock) return true;
      if (normalized.includes("partielles") || normalized.includes("insuffisantes")) return false;
      return true;
    });

  const summaryTextRaw = pickExecutiveSummary(response, blocks, fallbackText);
  const summaryText = normalizeSummaryText(summaryTextRaw, tableBlocks.length > 0);
  const sourceCount = response?.citations?.length || 0;
  const summaryWasShortened = summaryText.trim() !== summaryTextRaw.trim();
  const sectionCount = [
    Boolean(kpiBlock),
    tableBlocks.length > 0,
    chartBlocks.length > 0,
    Boolean(recommendationBlock),
    Boolean(bestPracticesBlock),
    Boolean(limitsBlock),
  ].filter(Boolean).length;
  const [visibleSections, setVisibleSections] = useState(0);
  const [typedSummary, setTypedSummary] = useState("");
  const [showMetaSections, setShowMetaSections] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReducedMotion(Boolean(media.matches));
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    if (reducedMotion) {
      setVisibleSections(6);
      setShowMetaSections(true);
      return;
    }
    setVisibleSections(0);
    setShowMetaSections(false);
    const t1 = window.setTimeout(() => setVisibleSections((v) => Math.max(v, 1)), 150);
    const t2 = window.setTimeout(() => setVisibleSections((v) => Math.max(v, 3)), 300);
    const t3 = window.setTimeout(() => setVisibleSections((v) => Math.max(v, 4)), 450);
    const t4 = window.setTimeout(() => setVisibleSections((v) => Math.max(v, 6)), 600);
    const t5 = window.setTimeout(() => setShowMetaSections(true), 700);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
      window.clearTimeout(t3);
      window.clearTimeout(t4);
      window.clearTimeout(t5);
    };
  }, [response?.message, sectionCount, reducedMotion]);

  useEffect(() => {
    const text = String(summaryText || "");
    if (!text) {
      setTypedSummary("");
      return;
    }
    if (reducedMotion) {
      setTypedSummary(text);
      return;
    }
    setTypedSummary("");
    let index = 0;
    const id = window.setInterval(() => {
      index += 3;
      setTypedSummary(text.slice(0, index));
      if (index >= text.length) window.clearInterval(id);
    }, 8);
    return () => window.clearInterval(id);
  }, [summaryText, reducedMotion]);

  const summaryDisplay = useMemo(() => (typedSummary || summaryText), [typedSummary, summaryText]);
  const revealClass = (show: boolean) =>
    `transition-all duration-300 ease-out ${show ? "opacity-100 translate-y-0" : "pointer-events-none opacity-0 translate-y-1"}`;

  if (!response) {
    return <p className="whitespace-pre-wrap text-sm leading-7 text-[#173324]">{fallbackText}</p>;
  }
  if (isNonOperationalMode(response.mode)) {
    return <p className="whitespace-pre-wrap text-sm leading-7 text-[#173324]">{safeNonOperationalText(response.mode, fallbackText)}</p>;
  }
  if (!blocks.length) {
    return <p className="whitespace-pre-wrap text-sm leading-7 text-[#173324]">{fallbackText}</p>;
  }

  return (
    <div className="space-y-3">
      <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-5 shadow-[0_8px_26px_rgba(0,0,0,0.05)]">
        <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-[#3f6b52]">Résumé exécutif</h3>
        <p className="mt-2 whitespace-pre-wrap text-[15px] leading-7 text-[#173324]">{summaryDisplay}</p>
        {summaryWasShortened ? (
          <details className="group mt-2">
            <summary className="cursor-pointer text-xs font-medium text-[#0a8f43] underline-offset-2 hover:underline">
              Voir plus
            </summary>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#355f4b]">{summaryTextRaw}</p>
          </details>
        ) : null}
      </section>

      {kpiBlock ? <div className={revealClass(visibleSections >= 1)}><KpiCardsSection block={kpiBlock} /></div> : null}
      {tableBlocks.length ? <div className={revealClass(visibleSections >= 2)}><TablesSection blocks={tableBlocks} /></div> : null}
      {chartBlocks.length ? <div className={revealClass(visibleSections >= 3)}><ChartsSection blocks={chartBlocks} /></div> : null}
      {recommendationBlock ? <div className={revealClass(visibleSections >= 4)}><RecommendationsSection block={recommendationBlock} /></div> : null}
      {bestPracticesBlock ? <div className={revealClass(visibleSections >= 5)}><BestPracticesSection block={bestPracticesBlock} /></div> : null}
      {limitsBlock ? <div className={revealClass(visibleSections >= 6)}><LimitsSection block={limitsBlock} /></div> : null}

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

      {!hideMetaSections && showMetaSections ? (
        <>
          <SourcesSection block={sourcesBlock} citationsCount={sourceCount} />
          <TechnicalDetailsSection response={response} warnings={warningItems} />
        </>
      ) : null}
    </div>
  );
}
