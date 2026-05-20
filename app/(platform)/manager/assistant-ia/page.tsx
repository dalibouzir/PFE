"use client";
/* eslint-disable @typescript-eslint/no-unused-vars */

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import type { LucideIcon } from "lucide-react";
import {
  ArrowDown,
  Bot,
  CalendarRange,
  Check,
  CheckCheck,
  ChevronDown,
  Copy,
  Lightbulb,
  MessageSquare,
  Paperclip,
  Plus,
  Send,
  Tag,
  Trash2,
  ThumbsDown,
  ThumbsUp,
  Workflow,
  X,
} from "lucide-react";
import { PageIntro } from "@/components/ui/PageIntro";
import { ExecutiveResponse } from "@/components/ui/assistant/ExecutiveResponse";
import { ApiError, apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { AgentChatResponse, AssistantChatResponse, ChatMessage, ChatSession, ChatUIBlock } from "@/lib/api/types";

type Tone = "normal" | "critical";

type StageDatum = {
  label: string;
  value: number;
  tone?: Tone;
};

type SourceChipItem = {
  id: string;
  label: string;
  icon: LucideIcon;
};

type RequestAnchorItem = {
  id: string;
  anchorId: string;
  preview: string;
  time: string;
};

type PreviousChatSummary = {
  id: string;
  title: string;
  time: string;
  messageCount: number;
};

type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  time: string;
  response?: AssistantChatResponse;
};

const SAFE_INVALID_RESPONSE_MESSAGE = "Je n’ai pas pu traiter cette demande. Veuillez reformuler votre question.";

type ChatMessageUserProps = {
  id: string;
  text: string;
  time: string;
};

type ChatMessageAIProps = {
  id: string;
  text: string;
  time: string;
  response?: AssistantChatResponse;
};

type MetricsCardSectionProps = {
  lossPct: number;
  efficiencyPct: number;
  qtyIn: number;
  qtyOut: number;
};

type StageComparisonChartProps = {
  data: StageDatum[];
};

type RecommendationCardSectionProps = {
  text: string;
};

type SourceChipsProps = {
  items: SourceChipItem[];
};

type RequestAnchorRailProps = {
  items: RequestAnchorItem[];
  activeId: string;
  onSelect: (item: RequestAnchorItem) => void;
};

type ChatComposerProps = {
  value: string;
  pending: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
};

type PreviousChatsMenuProps = {
  items: PreviousChatSummary[];
  activeId: string | null;
  pendingCreate: boolean;
  deletingSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onCreate: () => void;
  onDelete: (sessionId: string) => Promise<void> | void;
};

const STAGE_DATA: StageDatum[] = [
  { label: "Nettoyage", value: 8 },
  { label: "Séchage", value: 18, tone: "critical" },
  { label: "Tri", value: 9 },
  { label: "Emballage", value: 4 },
];

function getNowTime() {
  return new Intl.DateTimeFormat("fr-SN", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date());
}

function formatStoredTime(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return getNowTime();
  return new Intl.DateTimeFormat("fr-SN", { hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}

function formatSessionTime(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "N/A";
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function trimText(input: string, limit: number) {
  if (input.length <= limit) return input;
  return `${input.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}

function stripAssistantMetaSections(input: string) {
  const lines = input.split("\n");
  const output: string[] = [];
  let skipMode: "confidence" | "sources" | null = null;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    const lower = line.toLowerCase();

    if (lower === "niveau de confiance") {
      skipMode = "confidence";
      continue;
    }
    if (lower === "sources utilisées") {
      skipMode = "sources";
      continue;
    }
    if (lower === "afficher les détails techniques") {
      skipMode = null;
      continue;
    }

    if (skipMode === "confidence") {
      if (line === "") {
        skipMode = null;
      }
      continue;
    }

    if (skipMode === "sources") {
      if (line === "") {
        skipMode = null;
      }
      continue;
    }

    if (lower === "source métier") continue;
    if (/^source\s*:/i.test(line)) continue;
    if (/^processus\s*:/i.test(line)) continue;

    output.push(rawLine);
  }

  return output.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function buildRecommendation(message: string) {
  const clean = message.replace(/\s+/g, " ").trim();
  if (!clean) {
    return "Vérifier le lot concerné puis comparer les étapes avec la base coopérative pour corriger la perte.";
  }
  const firstSentence = clean.split(/[.!?]/).find((part) => part.trim().length > 20)?.trim();
  return firstSentence ? `${firstSentence}.` : trimText(clean, 160);
}

function buildSourceChips(response?: AssistantChatResponse): SourceChipItem[] {
  if (!response?.citations?.length) return [];
  return response.citations.slice(0, 4).map((citation, index) => {
    if (index === 0) {
      return { id: `source-lot-${index}`, label: `Source: ${citation.source_id}`, icon: Tag };
    }
    if (index === 1) {
      return { id: `source-topic-${index}`, label: `Processus: ${citation.topic}`, icon: Workflow };
    }
    if (index === 2) {
      return { id: `source-region-${index}`, label: `Région: ${citation.region}`, icon: CalendarRange };
    }
    return { id: `source-crop-${index}`, label: `Culture: ${citation.crop}`, icon: Plus };
  });
}

function isNonOperationalMode(mode?: string | null) {
  const current = String(mode || "").toLowerCase();
  return current === "small_talk" || current === "clarification_needed" || current === "unsupported";
}

function normalizeAssistantResponse(response?: AssistantChatResponse | null): AssistantChatResponse | null {
  if (!response || typeof response !== "object") return null;
  const message = typeof response.message === "string" ? response.message.trim() : "";
  if (!message) return null;

  return {
    success: Boolean(response.success),
    session_id: String(response.session_id || ""),
    user_message_id: response.user_message_id ?? null,
    assistant_message_id: response.assistant_message_id ?? null,
    message,
    grounded: Boolean(response.grounded),
    mode: typeof response.mode === "string" ? response.mode : "fallback",
    llm_provider: null,
    llm_model: null,
    citations: Array.isArray(response.citations) ? [...response.citations] : [],
    context_metrics: Array.isArray(response.context_metrics) ? [...response.context_metrics] : [],
    dashboard: response.dashboard ?? null,
    ui_blocks: Array.isArray(response.ui_blocks) ? [...response.ui_blocks] : [],
  };
}

function mapAgentBlocksToUIBlocks(response: AgentChatResponse): ChatUIBlock[] {
  const blocks = Array.isArray(response.response_blocks) ? response.response_blocks : [];
  const mapped: ChatUIBlock[] = [];
  for (const block of blocks) {
    if (!block || typeof block !== "object") continue;
    const type = String(block.type || "");
    const title = String(block.title || "");
    if (type === "summary") {
      mapped.push({ type: "executive_summary", title: title || "Résumé", payload: { text: String(block.content || "") } });
      continue;
    }
    if (type === "recommendations") {
      mapped.push({ type: "recommendation_cards", title: title || "Actions recommandées", payload: { items: Array.isArray(block.items) ? block.items : [] } });
      continue;
    }
    if (type === "chart") {
      const data = Array.isArray(block.data) ? block.data : [];
      const xKey = String(block.x_key || "x");
      const yKey = String(block.y_key || "y");
      const labels = data.map((row) => {
        const record = row as Record<string, unknown>;
        const value = record[xKey] ?? record.stage ?? record.product ?? record.batch_ref ?? record.x ?? "";
        return String(value);
      });
      const seriesValues = data.map((row) => {
        const record = row as Record<string, unknown>;
        const value = record[yKey] ?? record.loss_pct ?? record.available_stock_kg ?? record.y ?? 0;
        const numeric = Number(value);
        return Number.isFinite(numeric) ? numeric : 0;
      });
      mapped.push({
        type: String(block.chart_type || "bar") === "line" ? "line_chart" : "bar_chart",
        title: title || "Graphique",
        payload: {
          x_key: xKey,
          y_key: yKey,
          data,
          labels,
          series: [{ name: yKey || "Valeur", data: seriesValues }],
        },
      });
      continue;
    }
    if (type === "warnings") {
      const warningItems = Array.isArray(block.items) ? block.items : [];
      mapped.push({
        type: "warnings",
        title: title || "Avertissements",
        payload: { items: warningItems.map((item) => String(item)) },
      });
      continue;
    }
    if (type === "best_practices") {
      const practiceItems = Array.isArray(block.items) ? block.items : [];
      mapped.push({
        type: "best_practices",
        title: title || "Bonnes pratiques",
        payload: { items: practiceItems.map((item) => String(item)) },
      });
      continue;
    }
    if (type === "sources") {
      const sourceItems = Array.isArray(block.items) ? block.items : [];
      mapped.push({
        type: "sources",
        title: title || "Sources utilisées",
        payload: { items: sourceItems },
      });
      continue;
    }
    if (type === "table") {
      mapped.push({
        type: "table",
        title: title || "Tableau",
        payload: {
          columns: Array.isArray(block.columns) ? block.columns : [],
          rows: Array.isArray(block.rows) ? block.rows : [],
        },
      });
      continue;
    }
    mapped.push({
      type,
      title: title || "Bloc",
      payload: block as Record<string, unknown>,
    });
  }
  return mapped;
}

function adaptAgentResponseToAssistant(response: AgentChatResponse): AssistantChatResponse {
  const conversationId = String(response.metadata?.conversation_id || "");
  const warnings = Array.isArray(response.warnings) ? response.warnings : [];
  const citations = (Array.isArray(response.sources) ? response.sources : []).map((source, index) => ({
    source_id: String(source.title || source.table || source.model || `source-${index + 1}`),
    source_url: "",
    region: "cooperative",
    crop: String(source.related_product || "multi"),
    topic: String(source.type || "source"),
    excerpt: String(source.label || source.title || source.model || "Source opérationnelle"),
  }));

  return {
    success: true,
    session_id: conversationId,
    user_message_id: null,
    assistant_message_id: null,
    message: response.answer,
    grounded: citations.length > 0,
    mode: `agent:${response.route}`,
    llm_provider: null,
    llm_model: null,
    citations,
    context_metrics: [
      {
        source_id: "agent",
        region: "cooperative",
        crop: "multi",
        metric: "retrieval_plan.intent_type",
        period: "current",
        value: 1,
        unit: response.route,
        notes: response.route,
      },
      {
        source_id: "agent",
        region: "cooperative",
        crop: "multi",
        metric: "orchestration.confidence_score",
        period: "current",
        value: Number(response.confidence || 0),
        unit: "score",
        notes: "",
      },
      {
        source_id: "agent",
        region: "cooperative",
        crop: "multi",
        metric: "orchestration.warning_count",
        period: "current",
        value: warnings.length,
        unit: "count",
        notes: warnings.length ? warnings.join(" | ") : "none",
      },
      {
        source_id: "agent",
        region: "cooperative",
        crop: "multi",
        metric: "agent.agents_count",
        period: "current",
        value: Array.isArray(response.agents_used) ? response.agents_used.length : 0,
        unit: "count",
        notes: Array.isArray(response.agents_used) ? response.agents_used.join(" | ") : "",
      },
    ],
    dashboard: null,
    ui_blocks: mapAgentBlocksToUIBlocks(response),
  };
}

function createWelcomeMessage(): ConversationMessage {
  return {
    id: "assistant-welcome",
    role: "assistant",
    text: "Conversation test prête. Posez votre question opérationnelle, je réponds avec le contexte de votre coopérative.",
    time: getNowTime(),
  };
}

function fromStoredMessage(message: ChatMessage): ConversationMessage | null {
  if (message.role !== "user" && message.role !== "assistant") return null;
  const normalizedResponse =
    message.role === "assistant"
      ? normalizeAssistantResponse({
          success: true,
          session_id: message.session_id,
          message: message.content,
          grounded: message.citations.length > 0,
          mode: message.mode ?? "fallback",
          llm_provider: null,
          llm_model: null,
          citations: message.citations,
          context_metrics: message.context_metrics,
          dashboard: message.dashboard,
          ui_blocks: message.ui_blocks,
        })
      : null;
  return {
    id: message.id,
    role: message.role,
    text: message.content,
    time: formatStoredTime(message.created_at),
    response: normalizedResponse ?? undefined,
  };
}

function ChatMessageUser({ id, text, time }: ChatMessageUserProps) {
  return (
    <div id={id} className="flex justify-end scroll-mt-28">
      <article className="relative w-full max-w-[760px] rounded-[22px] border border-[#D5E6CF] bg-[#EEF7E6] px-5 py-4 text-sm text-[var(--text)] shadow-[0_5px_14px_rgba(35,30,21,0.05)]">
        <p className="pr-16 text-sm text-[var(--text)]">{text}</p>
        <div className="mt-2 flex items-center justify-end gap-1.5 text-xs text-[var(--muted)]">
          <span>{time}</span>
          <CheckCheck className="h-3.5 w-3.5 text-[var(--success)]" />
        </div>
      </article>
    </div>
  );
}

function MetricsCardSection({ lossPct, efficiencyPct, qtyIn, qtyOut }: MetricsCardSectionProps) {
  return (
    <section className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
      <h3 className="text-sm font-semibold text-[var(--text)]">Métriques clés</h3>
      <dl className="mt-3 space-y-2.5 text-xs">
        <div className="flex items-center justify-between gap-3">
          <dt className="text-[var(--muted)]">Pertes</dt>
          <dd className="font-semibold text-[var(--danger)]">{lossPct.toFixed(1)}%</dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt className="text-[var(--muted)]">Efficacité</dt>
          <dd className="font-semibold text-[var(--success)]">{efficiencyPct.toFixed(1)}%</dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt className="text-[var(--muted)]">Quantité entrée</dt>
          <dd className="font-semibold text-[var(--text)]">{qtyIn.toLocaleString("fr-FR")} kg</dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt className="text-[var(--muted)]">Quantité sortie</dt>
          <dd className="font-semibold text-[var(--text)]">{qtyOut.toLocaleString("fr-FR")} kg</dd>
        </div>
      </dl>
    </section>
  );
}

function StageComparisonChart({ data }: StageComparisonChartProps) {
  const max = useMemo(() => Math.max(...data.map((item) => item.value), 1), [data]);

  return (
    <section className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
      <h3 className="text-sm font-semibold text-[var(--text)]">Comparaison par étape</h3>
      <div className="mt-3 grid grid-cols-[38px_1fr] gap-2">
        <div className="flex h-32 flex-col justify-between text-[11px] text-[var(--muted)]">
          <span>30%</span>
          <span>20%</span>
          <span>10%</span>
          <span>0%</span>
        </div>

        <div className="grid h-32 grid-cols-4 items-end gap-3 rounded-xl border border-[rgba(19,40,31,0.06)] bg-[rgba(255,255,255,0.55)] px-3 pb-2.5 pt-2">
          {data.map((stage) => {
            const heightPct = Math.max((stage.value / max) * 100, 14);
            const barClass = stage.tone === "critical" ? "bg-gradient-to-b from-[#F27772] to-[#D64545]" : "bg-gradient-to-b from-[#95D092] to-[#64B26B]";

            return (
              <div key={stage.label} className="flex h-full flex-col items-center justify-end gap-1">
                <span className="text-[11px] font-semibold text-[var(--text)]">{stage.value}%</span>
                <div className="flex h-[92px] items-end">
                  <div className={`w-7 rounded-md ${barClass}`} style={{ height: `${heightPct}%` }} />
                </div>
                <span className="text-[11px] text-[var(--text)]">{stage.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function RecommendationCardSection({ text }: RecommendationCardSectionProps) {
  return (
    <section className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
      <div className="flex items-center gap-2">
        <Lightbulb className="h-4 w-4 text-[var(--success)]" />
        <h3 className="text-sm font-semibold text-[var(--text)]">Recommandation</h3>
      </div>
      <p className="mt-3 text-sm leading-6 text-[var(--text)]">{text}</p>
    </section>
  );
}

function SourceChips({ items }: SourceChipsProps) {
  return (
    <div className="mt-4">
      <p className="text-xs font-medium text-[var(--text)]">Sources utilisées</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-1.5 text-xs text-[var(--text)] transition-colors hover:bg-[var(--surface-soft)]"
            >
              <Icon className="h-3.5 w-3.5 text-[var(--success)]" />
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function StructuredBlocks({ blocks }: { blocks: ChatUIBlock[] }) {
  if (!blocks.length) return null;

  return (
    <div className="mt-4 grid gap-3">
      {blocks.map((block, index) => {
        const payload = block.payload as Record<string, unknown>;
        if (block.type === "table") {
          const columns = Array.isArray(payload.columns) ? (payload.columns as string[]) : [];
          const rows = Array.isArray(payload.rows) ? (payload.rows as Array<Array<string | number>>) : [];
          return (
            <section key={`${block.type}-${index}`} className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
              <h3 className="text-sm font-semibold text-[var(--text)]">{block.title}</h3>
              <div className="mt-3 overflow-auto">
                <table className="min-w-full text-xs">
                  <thead>
                    <tr className="text-left text-[var(--muted)]">
                      {columns.map((column) => (
                        <th key={column} className="px-2 py-1.5 font-medium">{column}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, rowIndex) => (
                      <tr key={`${block.title}-${rowIndex}`} className="border-t border-[rgba(19,40,31,0.08)] text-[var(--text)]">
                        {row.map((cell, cellIndex) => (
                          <td key={`${rowIndex}-${cellIndex}`} className="px-2 py-1.5">{String(cell)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          );
        }

        if (block.type === "kpi") {
          return (
            <section key={`${block.type}-${index}`} className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
              <h3 className="text-sm font-semibold text-[var(--text)]">{block.title}</h3>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(payload).map(([key, value]) => (
                  <div key={key} className="rounded-xl border border-[rgba(19,40,31,0.08)] px-3 py-2">
                    <p className="text-[11px] uppercase tracking-wide text-[var(--muted)]">{key.replaceAll("_", " ")}</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--text)]">{String(value)}</p>
                  </div>
                ))}
              </div>
            </section>
          );
        }

        if (block.type === "bar_chart" || block.type === "line_chart") {
          const labels = Array.isArray(payload.labels) ? (payload.labels as string[]) : [];
          const series = Array.isArray(payload.series) ? (payload.series as Array<{ name?: string; data?: number[] }>) : [];
          const firstSeries = series[0];
          const data = Array.isArray(firstSeries?.data) ? firstSeries.data : [];
          return (
            <section key={`${block.type}-${index}`} className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
              <h3 className="text-sm font-semibold text-[var(--text)]">{block.title}</h3>
              <div className="mt-3 space-y-1.5">
                {labels.map((label, i) => (
                  <div key={`${label}-${i}`} className="flex items-center justify-between gap-3 text-xs">
                    <span className="text-[var(--muted)]">{label}</span>
                    <span className="font-semibold text-[var(--text)]">{typeof data[i] === "number" ? data[i] : "-"}</span>
                  </div>
                ))}
              </div>
            </section>
          );
        }

        return (
          <section key={`${block.type}-${index}`} className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-4">
            <h3 className="text-sm font-semibold text-[var(--text)]">{block.title}</h3>
            <pre className="mt-3 overflow-auto rounded-xl bg-[var(--surface-soft)] p-3 text-xs text-[var(--text)]">
              {JSON.stringify(payload, null, 2)}
            </pre>
          </section>
        );
      })}
    </div>
  );
}

function ChatMessageAI({ id, text, time, response }: ChatMessageAIProps) {
  const [copied, setCopied] = useState(false);
  const hasStructuredResponse = Boolean(response) && !isNonOperationalMode(response?.mode);
  const cleanedText = stripAssistantMetaSections(response?.message || text) || text;
  const confidenceMetric = response?.context_metrics?.find((metric) => metric.metric === "orchestration.confidence_score");
  const confidencePct = confidenceMetric ? Math.round(Math.max(0, Math.min(100, (confidenceMetric.value || 0) * 100))) : null;
  const intentMetric = response?.context_metrics?.find((metric) => metric.metric === "retrieval_plan.intent_type");
  const responseMode = String(intentMetric?.unit || response?.mode || "HYBRID");
  const agentsMetric = response?.context_metrics?.find((metric) => metric.metric === "agent.agents_count");
  const agentCount = Number(agentsMetric?.value || 0);

  const copyResponse = async () => {
    const payload = cleanedText;
    try {
      await navigator.clipboard.writeText(payload);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="flex scroll-mt-28 gap-3" id={id}>
      <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-white shadow-[0_8px_18px_rgba(0,126,47,0.22)]">
        <Bot className="h-5 w-5" />
      </div>

      <div className="w-full">
        <div className="mb-2 flex items-center justify-between gap-3">
          <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#2e5b41]">Assistant coopérative</span>
          <span className="text-xs text-[var(--muted)]">{time}</span>
        </div>

        {hasStructuredResponse ? (
          <ExecutiveResponse response={response} fallbackText={cleanedText} />
        ) : (
          <p className="max-w-4xl whitespace-pre-wrap text-sm leading-7 text-[var(--text)]">{cleanedText}</p>
        )}

        {hasStructuredResponse ? (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
            <span className="rounded-full border border-[#c7dfcf] bg-[#f2faf5] px-2.5 py-1 font-semibold text-[#24523b]">
              Route: {responseMode}
            </span>
            <span className="rounded-full border border-[#c7dfcf] bg-[#f2faf5] px-2.5 py-1 font-semibold text-[#24523b]">
              Agents: {agentCount || "N/A"}
            </span>
            <span className="rounded-full border border-[#c7dfcf] bg-[#f2faf5] px-2.5 py-1 font-semibold text-[#24523b]">
              Confiance: {confidencePct !== null ? `${confidencePct}%` : "N/A"}
            </span>
          </div>
        ) : null}

        <div className="mt-4 flex items-center gap-2 border-t border-[rgba(19,40,31,0.08)] pt-3">
          <button
            type="button"
            onClick={copyResponse}
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--line)] bg-[var(--surface)] px-2.5 py-1 text-xs font-medium text-[var(--muted)] transition-colors hover:bg-[var(--surface-soft)] hover:text-[var(--text)]"
            aria-label="Copier la réponse"
          >
            <Copy className="h-3.5 w-3.5" />
            {copied ? "Copié" : "Copier"}
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--line)] bg-[var(--surface)] px-2.5 py-1 text-xs font-medium text-[var(--muted)] transition-colors hover:bg-[var(--surface-soft)] hover:text-[var(--text)]"
            aria-label="Réponse utile"
          >
            <ThumbsUp className="h-3.5 w-3.5" />
            Utile
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--line)] bg-[var(--surface)] px-2.5 py-1 text-xs font-medium text-[var(--muted)] transition-colors hover:bg-[var(--surface-soft)] hover:text-[var(--text)]"
            aria-label="Réponse peu utile"
          >
            <ThumbsDown className="h-3.5 w-3.5" />
            Peu utile
          </button>
        </div>
      </div>
    </div>
  );
}

function RequestAnchorRail({ items, activeId, onSelect }: RequestAnchorRailProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [overflowOpen, setOverflowOpen] = useState(false);
  const overflowRef = useRef<HTMLDivElement>(null);
  const visibleItems = items.slice(0, 10);
  const hiddenItems = items.slice(10);

  useEffect(() => {
    if (!overflowOpen) return;

    const onDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!overflowRef.current?.contains(target)) {
        setOverflowOpen(false);
      }
    };

    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, [overflowOpen]);

  return (
    <aside className="hidden xl:flex xl:justify-center">
      <div className="sticky top-1/2 h-fit w-14 -translate-y-1/2">
        <div className="relative mx-auto flex w-full flex-col items-center gap-1.5 py-3">
          {visibleItems.map((item) => {
            const isActive = item.id === activeId;
            const isHovered = item.id === hoveredId;

            return (
              <button
                key={item.id}
                type="button"
                onMouseEnter={() => setHoveredId(item.id)}
                onMouseLeave={() => setHoveredId((current) => (current === item.id ? null : current))}
                onClick={() => onSelect(item)}
                aria-label={item.preview}
                className={`group relative z-10 flex h-3 w-8 items-center justify-center rounded-md transition-all duration-150 ${
                  isActive
                    ? "bg-[#0BA748] shadow-[0_0_0_3px_rgba(0,126,47,0.16)]"
                    : "bg-transparent hover:bg-[#007e2f]/20"
                }`}
              >
                <span className={`h-[2px] w-6 rounded-full ${isActive ? "bg-white" : "bg-[#007e2f]/70"}`} />
                {isHovered && (
                  <span className="pointer-events-none absolute right-[calc(100%+12px)] top-1/2 w-64 -translate-y-1/2 rounded-xl border border-[#007e2f]/35 bg-[linear-gradient(138deg,rgba(239,250,245,0.95)_0%,rgba(229,246,236,0.88)_55%,rgba(218,241,229,0.82)_100%)] px-3 py-2 text-left shadow-[0_14px_30px_rgba(0,126,47,0.22)] backdrop-blur-xl">
                    <span className="block truncate text-xs font-medium text-[var(--text)]">{item.preview}</span>
                    <span className="mt-0.5 block text-[11px] text-[var(--muted)]">{item.time}</span>
                  </span>
                )}
              </button>
            );
          })}

          {hiddenItems.length > 0 && (
            <div className="relative z-20" ref={overflowRef}>
              <button
                type="button"
                onClick={() => setOverflowOpen((current) => !current)}
                aria-label={`${hiddenItems.length} questions supplémentaires`}
                className="flex h-6 w-6 items-center justify-center rounded-full border border-[#007e2f]/45 bg-[#007e2f]/16 text-[11px] font-semibold text-[#007e2f] shadow-[0_8px_18px_rgba(0,126,47,0.2)]"
              >
                Q
              </button>

              {overflowOpen && (
                <div className="absolute right-[calc(100%+12px)] top-1/2 w-72 -translate-y-1/2 overflow-hidden rounded-2xl border border-[#007e2f]/36 bg-[linear-gradient(145deg,rgba(238,250,244,0.95)_0%,rgba(226,244,234,0.86)_52%,rgba(214,238,225,0.8)_100%)] p-2 shadow-[0_16px_36px_rgba(0,126,47,0.24)] backdrop-blur-2xl">
                  <div className="pointer-events-none absolute inset-x-3 top-0 h-px bg-[rgba(255,255,255,0.88)]" />
                  <p className="px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#0d6a31]">
                    Questions cachées ({hiddenItems.length})
                  </p>
                  <div className="mt-1 max-h-60 space-y-1 overflow-y-auto pr-1">
                    {hiddenItems.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          onSelect(item);
                          setOverflowOpen(false);
                        }}
                        className="w-full rounded-lg border border-[#007e2f]/15 bg-white/50 px-2 py-1.5 text-left transition-colors hover:bg-[#007e2f]/18"
                      >
                        <p className="truncate text-xs font-medium text-[#0f2d1b]">{item.preview}</p>
                        <p className="mt-0.5 text-[11px] text-[#2e5b41]/80">{item.time}</p>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

function PreviousChatsMenu({ items, activeId, pendingCreate, deletingSessionId, onSelect, onCreate, onDelete }: PreviousChatsMenuProps) {
  const [open, setOpen] = useState(false);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDown = (event: MouseEvent) => {
      const node = event.target as Node;
      if (!containerRef.current?.contains(node)) setOpen(false);
    };

    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, []);

  useEffect(() => {
    if (!open) setConfirmingDeleteId(null);
  }, [open]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-sm font-medium text-[var(--text)] shadow-[0_4px_12px_rgba(35,30,21,0.06)] transition-colors hover:bg-[var(--surface-soft)]"
      >
        <MessageSquare className="h-4 w-4 text-[var(--muted)]" />
        Chats précédents
        <ChevronDown className={`h-4 w-4 text-[var(--muted)] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-80 max-w-[calc(100vw-1rem)] overflow-hidden rounded-xl border border-[#007e2f]/30 bg-[linear-gradient(145deg,rgba(238,250,244,0.94)_0%,rgba(226,244,234,0.84)_52%,rgba(214,238,225,0.78)_100%)] p-1.5 shadow-[0_10px_24px_rgba(0,126,47,0.18)] backdrop-blur-xl sm:w-[22rem]">
          <div className="pointer-events-none absolute inset-x-3 top-0 h-px bg-[rgba(255,255,255,0.88)]" />
          <button
            type="button"
            onClick={() => {
              onCreate();
              setOpen(false);
            }}
            disabled={pendingCreate}
            className="flex w-full items-center gap-2 rounded-lg border border-[#007e2f]/24 bg-white/55 px-2.5 py-2 text-sm font-semibold text-[#0f2d1b] transition-colors hover:bg-[#007e2f]/18 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Plus className="h-4 w-4" />
            {pendingCreate ? "Création..." : "Nouvelle conversation"}
          </button>

          <div className="mt-1.5 max-h-64 space-y-1 overflow-y-auto">
            {items.map((item) => (
              <div
                key={item.id}
                className={`w-full rounded-lg border border-transparent px-2.5 py-1.5 text-left transition-colors ${
                  activeId === item.id ? "border-[#007e2f]/28 bg-[#007e2f]/18" : "hover:bg-[#007e2f]/12"
                }`}
              >
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(item.id);
                      setOpen(false);
                    }}
                    className="min-w-0 flex-1 text-left"
                  >
                    <p className="truncate text-sm font-semibold text-[#0f2d1b]">{item.title}</p>
                    <p className="mt-0.5 text-xs text-[#2e5b41]/85">
                      {item.time} · {item.messageCount} messages
                    </p>
                  </button>
                  {confirmingDeleteId === item.id ? (
                    <div className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        onClick={() => {
                          setConfirmingDeleteId(null);
                          void onDelete(item.id);
                        }}
                        disabled={pendingCreate || deletingSessionId === item.id}
                        className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-[#007e2f]/30 bg-[#007e2f]/18 text-[#0f2d1b] transition-colors hover:bg-[#007e2f]/28 disabled:cursor-not-allowed disabled:opacity-55"
                        aria-label={`Confirmer la suppression de ${item.title}`}
                      >
                        <Check className="h-3 w-3" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmingDeleteId(null)}
                        disabled={pendingCreate || deletingSessionId === item.id}
                        className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-[#007e2f]/20 bg-white/65 text-[#0f2d1b] transition-colors hover:bg-[#007e2f]/14 disabled:cursor-not-allowed disabled:opacity-55"
                        aria-label={`Annuler la suppression de ${item.title}`}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmingDeleteId(item.id)}
                      disabled={pendingCreate || deletingSessionId === item.id}
                      className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[#007e2f]/20 bg-white/65 text-[#0f2d1b] transition-colors hover:bg-[#007e2f]/16 disabled:cursor-not-allowed disabled:opacity-55"
                      aria-label={`Supprimer la conversation ${item.title}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))}
            {!items.length && <p className="px-3 py-2 text-xs text-[#2e5b41]/85">Aucune conversation enregistrée.</p>}
          </div>
        </div>
      )}
    </div>
  );
}

function ChatComposer({ value, pending, onChange, onSend }: ChatComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const maxHeight = 96; // ~4 lines with current line-height/padding
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
  }, [value]);

  return (
    <div className="mx-auto w-full max-w-4xl shrink-0 rounded-[26px] border border-[rgba(15,35,24,0.16)] bg-white px-2.5 py-2 shadow-[0_6px_16px_rgba(15,35,24,0.06)]">
      <div className="flex items-end gap-2">
        <button
          type="button"
          className="rounded-full border border-[rgba(15,35,24,0.14)] bg-[#f7faf8] p-1 text-[var(--muted)] transition-colors hover:text-[var(--text)]"
          aria-label="Ajouter une pièce jointe"
        >
          <Paperclip className="h-3.5 w-3.5" />
        </button>

        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSend();
            }
          }}
          placeholder="Posez votre question..."
          className="max-h-24 min-h-[26px] flex-1 resize-none overflow-y-auto bg-transparent px-1.5 py-1 text-sm leading-6 text-[var(--text)] outline-none placeholder:text-[var(--muted)]"
        />

        <button
          type="button"
          onClick={onSend}
          disabled={pending || !value.trim()}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[var(--primary)] text-white shadow-[0_5px_12px_rgba(0,126,47,0.22)] transition-transform duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-55"
          aria-label="Envoyer"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

export default function AssistantIAPage() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ConversationMessage[]>([createWelcomeMessage()]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeRequestId, setActiveRequestId] = useState("");
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [loadingStepIndex, setLoadingStepIndex] = useState(0);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const streamEndRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(false);
  const loadingSteps = [
    "Analyse de la question",
    "Consultation des données",
    "Vérification des preuves",
    "Préparation de la réponse",
  ];


  const sessionsQuery = useQuery({
    queryKey: ["assistant-chat-sessions"],
    queryFn: () => apiFetch<ChatSession[]>(endpoints.chat.sessions),
  });

  const messagesQuery = useQuery({
    queryKey: ["assistant-chat-messages", activeSessionId],
    queryFn: () => apiFetch<ChatMessage[]>(endpoints.chat.messages(activeSessionId as string)),
    enabled: Boolean(activeSessionId),
  });

  const createSessionMutation = useMutation({
    mutationFn: (payload: { title?: string }) =>
      apiFetch<ChatSession>(endpoints.chat.sessions, {
        method: "POST",
        body: payload,
      }),
  });

  const deleteSessionMutation = useMutation({
    mutationFn: (sessionId: string) =>
      apiFetch<void>(endpoints.chat.session(sessionId), {
        method: "DELETE",
      }),
  });

  const askMutation = useMutation({
    mutationFn: ({ sessionId, message }: { sessionId: string; message: string }) =>
      apiFetch<AgentChatResponse>(endpoints.chat.agentAsk, {
        method: "POST",
        body: { conversation_id: sessionId, message, language: "fr" },
      }),
  });

  useEffect(() => {
    if (!askMutation.isPending) {
      setLoadingStepIndex(0);
      return;
    }
    const timer = window.setInterval(() => {
      setLoadingStepIndex((value) => (value + 1) % loadingSteps.length);
    }, 1300);
    return () => window.clearInterval(timer);
  }, [askMutation.isPending, loadingSteps.length]);

  useEffect(() => {
    const sessions = sessionsQuery.data ?? [];
    if (!sessions.length) return;
    if (activeSessionId && sessions.some((session) => session.id === activeSessionId)) return;
    setActiveSessionId(sessions[0].id);
  }, [sessionsQuery.data, activeSessionId]);

  useEffect(() => {
    const persisted = (messagesQuery.data ?? []).map(fromStoredMessage).filter(Boolean) as ConversationMessage[];
    if (persisted.length) {
      setMessages(persisted);
      return;
    }
    setMessages([createWelcomeMessage()]);
  }, [messagesQuery.data, activeSessionId]);

  const requestAnchors = useMemo<RequestAnchorItem[]>(
    () =>
      messages
        .filter((msg) => msg.role === "user")
        .map((msg) => ({
          id: msg.id,
          anchorId: msg.id,
          preview: trimText(msg.text, 66),
          time: msg.time,
        })),
    [messages],
  );

  const previousChats = useMemo<PreviousChatSummary[]>(
    () =>
      (sessionsQuery.data ?? []).map((session) => ({
        id: session.id,
        title: session.title || "Conversation sans titre",
        time: formatSessionTime(session.last_message_at ?? session.updated_at ?? session.created_at),
        messageCount: session.message_count,
      })),
    [sessionsQuery.data],
  );

  useEffect(() => {
    if (!activeRequestId && requestAnchors.length) {
      setActiveRequestId(requestAnchors[requestAnchors.length - 1].id);
    }
  }, [requestAnchors, activeRequestId]);

  useEffect(() => {
    if (!shouldAutoScrollRef.current) return;
    streamEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    shouldAutoScrollRef.current = false;
  }, [messages, askMutation.isPending]);

  useEffect(() => {
    const node = chatScrollRef.current;
    if (!node) return;

    const updateScrollHint = () => {
      const distanceToBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
      setShowScrollToBottom(distanceToBottom > 40);
    };

    updateScrollHint();
    node.addEventListener("scroll", updateScrollHint, { passive: true });
    return () => node.removeEventListener("scroll", updateScrollHint);
  }, [messages, activeSessionId, askMutation.isPending]);

  const createNewConversation = async () => {
    try {
      const title = previousChats.length === 0 ? "Conversation test" : "Nouvelle conversation";
      const created = await createSessionMutation.mutateAsync({ title });
      setActiveSessionId(created.id);
      setMessages([createWelcomeMessage()]);
      shouldAutoScrollRef.current = true;
      await sessionsQuery.refetch();
    } catch {
      // ignore menu creation errors to keep interaction lightweight
    }
  };

  const deleteConversation = async (sessionId: string) => {
    try {
      setDeletingSessionId(sessionId);
      await deleteSessionMutation.mutateAsync(sessionId);
      const refreshed = await sessionsQuery.refetch();
      const remaining = refreshed.data ?? [];
      if (activeSessionId === sessionId) {
        if (remaining.length) {
          setActiveSessionId(remaining[0].id);
        } else {
          setActiveSessionId(null);
          setActiveRequestId("");
          setMessages([createWelcomeMessage()]);
        }
      }
    } catch {
      // ignore delete errors to keep interaction lightweight
    } finally {
      setDeletingSessionId(null);
    }
  };

  const sendMessage = async () => {
    const message = draft.trim();
    if (!message || askMutation.isPending) return;

    let sessionId = activeSessionId;
    if (!sessionId) {
      try {
        const created = await createSessionMutation.mutateAsync({ title: "Conversation test" });
        sessionId = created.id;
        setActiveSessionId(created.id);
        await sessionsQuery.refetch();
      } catch (error) {
        const fallback = error instanceof ApiError ? error.message : "Impossible de créer une conversation.";
        setMessages((current) => [
          ...current,
          { id: `assistant-error-${Date.now()}`, role: "assistant", text: `Erreur assistant: ${fallback}`, time: getNowTime() },
        ]);
        return;
      }
    }

    const userMessageId = `user-${Date.now()}`;
    const userMessage: ConversationMessage = { id: userMessageId, role: "user", text: message, time: getNowTime() };
    shouldAutoScrollRef.current = true;
    setDraft("");
    setActiveRequestId(userMessageId);
    setMessages((current) => [...current, userMessage]);

    try {
      const response = await askMutation.mutateAsync({ sessionId, message });
      const normalized = normalizeAssistantResponse(adaptAgentResponseToAssistant(response));
      if (!normalized) {
        const invalidAssistantMessage: ConversationMessage = {
          id: `assistant-invalid-${Date.now()}`,
          role: "assistant",
          text: SAFE_INVALID_RESPONSE_MESSAGE,
          time: getNowTime(),
        };
        shouldAutoScrollRef.current = true;
        setMessages((current) => [...current, invalidAssistantMessage]);
        await sessionsQuery.refetch();
        return;
      }
      const assistantMessage: ConversationMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: normalized.message,
        time: getNowTime(),
        response: normalized,
      };
      shouldAutoScrollRef.current = true;
      setMessages((current) => [...current, assistantMessage]);
      await sessionsQuery.refetch();
    } catch (error) {
      const fallback = error instanceof ApiError ? error.message : "Le service LLM est indisponible pour le moment.";
      const assistantMessage: ConversationMessage = {
        id: `assistant-error-${Date.now()}`,
        role: "assistant",
        text: `Erreur assistant: ${fallback}`,
        time: getNowTime(),
      };
      shouldAutoScrollRef.current = true;
      setMessages((current) => [...current, assistantMessage]);
    }
  };

  const handleRequestSelect = (item: RequestAnchorItem) => {
    setActiveRequestId(item.id);
    document.getElementById(item.anchorId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <main className="flex h-full min-h-0 flex-col overflow-hidden pb-0">
      <PageIntro title="Assistant IA" />

      <div className="-mt-1 mb-3 flex items-center justify-end">
        <PreviousChatsMenu
          items={previousChats}
          activeId={activeSessionId}
          pendingCreate={createSessionMutation.isPending}
          deletingSessionId={deletingSessionId}
          onSelect={(sessionId) => {
            setActiveSessionId(sessionId);
            shouldAutoScrollRef.current = true;
          }}
          onCreate={createNewConversation}
          onDelete={deleteConversation}
        />
      </div>

      <section className="grid min-h-0 flex-1 gap-3 overflow-hidden xl:grid-cols-[minmax(0,1fr)_56px]">
        <div className="min-h-0 min-w-0">
          <div className="relative h-full min-h-0 overflow-hidden">
            <div ref={chatScrollRef} className="scroll-thin absolute inset-0 overflow-y-auto pr-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
              <div className="space-y-4 pb-40">
                {messages.map((entry) =>
                  entry.role === "user" ? (
                    <ChatMessageUser key={entry.id} id={entry.id} text={entry.text} time={entry.time} />
                  ) : (
                    <ChatMessageAI key={entry.id} id={entry.id} text={entry.text} time={entry.time} response={entry.response} />
                  ),
                )}

                {askMutation.isPending && (
                  <div className="flex gap-3">
                    <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-white shadow-[0_8px_18px_rgba(0,126,47,0.22)]">
                      <Bot className="h-5 w-5" />
                    </div>
                    <article className="w-full rounded-[22px] border border-[var(--line)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)] shadow-[0_8px_18px_rgba(35,30,21,0.06)]">
                      <p className="font-medium text-[var(--text)]">Analyse des données...</p>
                      <ul className="mt-2 grid gap-1 text-xs">
                        {loadingSteps.map((step, index) => (
                          <li
                            key={step}
                            className={index === loadingStepIndex ? "font-semibold text-[#0a8f43]" : "text-[var(--muted)]"}
                          >
                            {index + 1}. {step}
                          </li>
                        ))}
                      </ul>
                    </article>
                  </div>
                )}

                <div ref={streamEndRef} />
              </div>
            </div>

            {showScrollToBottom && (
              <button
                type="button"
                onClick={() => {
                  chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" });
                }}
                className="absolute bottom-[calc(env(safe-area-inset-bottom)+6.2rem)] left-1/2 z-30 inline-flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-[rgba(255,255,255,0.62)] bg-[linear-gradient(160deg,rgba(255,255,255,0.62)_0%,rgba(244,252,248,0.44)_50%,rgba(229,245,236,0.34)_100%)] text-[#0f3d27] shadow-[0_12px_24px_rgba(12,49,30,0.16)] backdrop-blur-xl transition-colors hover:bg-[linear-gradient(160deg,rgba(255,255,255,0.74)_0%,rgba(244,252,248,0.56)_50%,rgba(229,245,236,0.42)_100%)]"
                aria-label="Descendre au dernier message"
              >
                <ArrowDown className="h-4 w-4" />
              </button>
            )}

            <div className="absolute inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+0.4rem)] z-20 bg-gradient-to-t from-[#f3f7fb] via-[#f3f7fb]/96 to-transparent pb-0 pt-3">
              <ChatComposer value={draft} pending={askMutation.isPending} onChange={setDraft} onSend={sendMessage} />
              <p className="pointer-events-none mt-2 text-center text-[11px] font-medium tracking-[0.01em] text-[var(--primary)]/80 [text-shadow:0_0_10px_rgba(0,126,47,0.2)]">
                Notre assistant peut faire des erreurs. Vérifiez les informations critiques.
              </p>
            </div>
          </div>
        </div>

        <RequestAnchorRail items={requestAnchors} activeId={activeRequestId} onSelect={handleRequestSelect} />
      </section>
    </main>
  );
}
