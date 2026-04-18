"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import type { LucideIcon } from "lucide-react";
import {
  Bot,
  CalendarRange,
  CheckCheck,
  ChevronDown,
  Copy,
  Lightbulb,
  MessageSquare,
  Paperclip,
  Plus,
  Send,
  Tag,
  ThumbsDown,
  ThumbsUp,
  Workflow,
} from "lucide-react";
import { PageIntro } from "@/components/ui/PageIntro";
import { ApiError, apiFetch } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { AssistantChatResponse } from "@/lib/api/types";

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
};

const STAGE_DATA: StageDatum[] = [
  { label: "Nettoyage", value: 8 },
  { label: "Séchage", value: 18, tone: "critical" },
  { label: "Tri", value: 9 },
  { label: "Emballage", value: 4 },
];

const PREVIOUS_CHATS: PreviousChatSummary[] = [
  { id: "chat-1", title: "Analyse pertes post-récolte semaine 16", time: "Aujourd'hui · 23:32", messageCount: 7 },
  { id: "chat-2", title: "État des stocks critiques par produit", time: "Aujourd'hui · 21:48", messageCount: 5 },
  { id: "chat-3", title: "Rendement oignon — comparaison inter-lots", time: "Hier · 20:15", messageCount: 9 },
];

function getNowTime() {
  return new Intl.DateTimeFormat("fr-SN", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date());
}

function trimText(input: string, limit: number) {
  if (input.length <= limit) return input;
  return `${input.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
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
  if (response?.citations?.length) {
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

  return [
    { id: "source-dashboard", label: "Contexte: Données coopérative en direct", icon: Tag },
    { id: "source-scope", label: "Périmètre: lots / stocks / collecte", icon: Workflow },
  ];
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
      <p className="text-xs font-medium text-[var(--text)]">
        Sources <span className="font-normal text-[var(--muted)]">(basé sur vos données)</span>
      </p>
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

function ChatMessageAI({ id, text, time, response }: ChatMessageAIProps) {
  const dashboard = response?.dashboard;
  const lossPct = dashboard?.loss_rate ?? 18;
  const efficiencyPct = dashboard?.efficiency_rate ?? 82;
  const qtyIn = 1000;
  const qtyOut = Math.max(Math.round((qtyIn * efficiencyPct) / 100), 0);
  const recommendation = buildRecommendation(text);
  const sources = buildSourceChips(response);

  return (
    <div className="flex scroll-mt-28 gap-3" id={id}>
      <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-white shadow-[0_8px_18px_rgba(0,126,47,0.22)]">
        <Bot className="h-5 w-5" />
      </div>

      <article className="w-full rounded-[24px] border border-[var(--line)] bg-[var(--surface)] p-5 shadow-[0_10px_24px_rgba(35,30,21,0.06)]">
        <div className="flex items-start justify-between gap-3">
          <p className="max-w-4xl text-sm leading-7 text-[var(--text)]">{text}</p>
          <div className="flex flex-col items-end gap-1.5">
            <span className="text-xs text-[var(--muted)]">{time}</span>
            {response?.mode === "llm" ? (
              <span className="rounded-full border border-[#CFE3C8] bg-[#EEF6E7] px-2 py-0.5 text-[10px] font-semibold text-[var(--success)]">
                LLM · {response.llm_provider ?? "provider"} / {response.llm_model ?? "model"}
              </span>
            ) : (
              <span className="rounded-full border border-[var(--line)] bg-[var(--surface-soft)] px-2 py-0.5 text-[10px] font-semibold text-[var(--muted)]">
                Fallback
              </span>
            )}
          </div>
        </div>

        <div className="mt-4 grid gap-3 xl:grid-cols-[1fr_1.45fr_1fr]">
          <MetricsCardSection lossPct={lossPct} efficiencyPct={efficiencyPct} qtyIn={qtyIn} qtyOut={qtyOut} />
          <StageComparisonChart data={STAGE_DATA} />
          <RecommendationCardSection text={recommendation} />
        </div>

        <SourceChips items={sources} />

        <div className="mt-4 flex items-center gap-2 border-t border-[rgba(19,40,31,0.08)] pt-3">
          <button type="button" className="rounded-lg p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--surface-soft)] hover:text-[var(--text)]" aria-label="Utile">
            <ThumbsUp className="h-4 w-4" />
          </button>
          <button type="button" className="rounded-lg p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--surface-soft)] hover:text-[var(--text)]" aria-label="Peu utile">
            <ThumbsDown className="h-4 w-4" />
          </button>
          <button type="button" className="rounded-lg p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--surface-soft)] hover:text-[var(--text)]" aria-label="Copier">
            <Copy className="h-4 w-4" />
          </button>
        </div>
      </article>
    </div>
  );
}

function RequestAnchorRail({ items, activeId, onSelect }: RequestAnchorRailProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <aside className="hidden xl:flex xl:justify-center">
      <div className="sticky top-32 h-fit w-14">
        <div className="relative mx-auto flex w-full flex-col items-center gap-10 py-3">
          <span className="pointer-events-none absolute inset-y-2 left-1/2 w-px -translate-x-1/2 bg-[linear-gradient(180deg,rgba(0,126,47,0.35)_0%,rgba(0,126,47,0.08)_100%)]" />

          {items.map((item) => {
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
                className={`group relative z-10 flex h-4 w-4 items-center justify-center rounded-full border transition-all duration-150 ${
                  isActive
                    ? "border-[#06883A] bg-[#0BA748] shadow-[0_0_0_4px_rgba(0,126,47,0.14)]"
                    : "border-[rgba(0,126,47,0.35)] bg-[var(--surface)] hover:border-[#06883A]"
                }`}
              >
                {isHovered && (
                  <span className="pointer-events-none absolute right-[calc(100%+10px)] top-1/2 w-64 -translate-y-1/2 rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-left shadow-[0_10px_24px_rgba(35,30,21,0.12)]">
                    <span className="block truncate text-xs font-medium text-[var(--text)]">{item.preview}</span>
                    <span className="mt-0.5 block text-[11px] text-[var(--muted)]">{item.time}</span>
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

function PreviousChatsMenu({ items }: PreviousChatsMenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDown = (event: MouseEvent) => {
      const node = event.target as Node;
      if (!containerRef.current?.contains(node)) setOpen(false);
    };

    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, []);

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
        <div className="absolute right-0 z-30 mt-2 w-96 max-w-[80vw] overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-2 shadow-[0_16px_36px_rgba(35,30,21,0.16)]">
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-2.5 text-sm font-semibold text-[var(--text)] transition-colors hover:bg-[var(--surface-soft)]"
          >
            <Plus className="h-4 w-4" />
            Nouvelle conversation
          </button>

          <div className="mt-2 max-h-72 space-y-1 overflow-y-auto">
            {items.map((item) => (
              <button key={item.id} type="button" className="w-full rounded-xl px-3 py-2 text-left transition-colors hover:bg-[var(--surface-soft)]">
                <p className="truncate text-sm font-semibold text-[var(--text)]">{item.title}</p>
                <p className="mt-0.5 text-xs text-[var(--muted)]">
                  {item.time} · {item.messageCount} messages
                </p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ChatComposer({ value, pending, onChange, onSend }: ChatComposerProps) {
  return (
    <div className="shrink-0 space-y-3 rounded-[24px] border border-[var(--line)] bg-[var(--surface)] px-4 py-3 shadow-[0_12px_26px_rgba(35,30,21,0.1)]">
      <div className="flex items-end gap-3">
        <button type="button" className="rounded-full border border-[var(--line)] bg-[var(--surface-soft)] p-2 text-[var(--muted)] transition-colors hover:text-[var(--text)]" aria-label="Ajouter une pièce jointe">
          <Paperclip className="h-4 w-4" />
        </button>

        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSend();
            }
          }}
          placeholder="Posez votre question..."
          className="min-h-[44px] flex-1 resize-none bg-transparent px-1 py-2 text-sm text-[var(--text)] outline-none placeholder:text-[var(--muted)]"
        />

        <button
          type="button"
          onClick={onSend}
          disabled={pending || !value.trim()}
          className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-[var(--primary)] text-white shadow-[0_10px_22px_rgba(0,126,47,0.3)] transition-transform duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-55"
          aria-label="Envoyer"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>

      <p className="text-center text-xs text-[var(--muted)]">Les réponses peuvent contenir des erreurs. Vérifiez les informations importantes.</p>
    </div>
  );
}

export default function AssistantIAPage() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ConversationMessage[]>([
    {
      id: "assistant-welcome",
      role: "assistant",
      text: "Bonjour. Posez votre question opérationnelle, je réponds avec le contexte de votre coopérative.",
      time: getNowTime(),
    },
  ]);
  const [activeRequestId, setActiveRequestId] = useState("");
  const streamEndRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(false);

  const askMutation = useMutation({
    mutationFn: (message: string) =>
      apiFetch<AssistantChatResponse>(endpoints.chat.ask, {
        method: "POST",
        body: { message, top_k: 4 },
      }),
  });

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

  useEffect(() => {
    if (!activeRequestId && requestAnchors.length) {
      setActiveRequestId(requestAnchors[requestAnchors.length - 1].id);
    }
  }, [requestAnchors, activeRequestId]);

  useEffect(() => {
    if (!shouldAutoScrollRef.current) return;
    streamEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    shouldAutoScrollRef.current = false;
  }, [messages]);

  const sendMessage = async () => {
    const message = draft.trim();
    if (!message || askMutation.isPending) return;

    const userMessageId = `user-${Date.now()}`;
    const userMessage: ConversationMessage = { id: userMessageId, role: "user", text: message, time: getNowTime() };
    shouldAutoScrollRef.current = true;
    setDraft("");
    setActiveRequestId(userMessageId);
    setMessages((current) => [...current, userMessage]);

    try {
      const response = await askMutation.mutateAsync(message);
      const assistantMessage: ConversationMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: response.message,
        time: getNowTime(),
        response,
      };
      shouldAutoScrollRef.current = true;
      setMessages((current) => [...current, assistantMessage]);
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
    <main className="pb-4">
      <PageIntro title="Assistant IA" subtitle="Posez vos questions sur vos données. Je m'appuie sur les données de votre coopérative." />

      <div className="-mt-1 mb-3 flex items-center justify-end">
        <PreviousChatsMenu items={PREVIOUS_CHATS} />
      </div>

      <section className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_56px]">
        <div className="min-w-0">
          <div className="flex h-[calc(100dvh-20.25rem)] min-h-[520px] flex-col gap-3">
            <div className="scroll-thin flex-1 space-y-4 overflow-y-auto pr-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
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
                    Analyse en cours...
                  </article>
                </div>
              )}

              <div ref={streamEndRef} />
            </div>

            <ChatComposer value={draft} pending={askMutation.isPending} onChange={setDraft} onSend={sendMessage} />
          </div>
        </div>

        <RequestAnchorRail items={requestAnchors} activeId={activeRequestId} onSelect={handleRequestSelect} />
      </section>
    </main>
  );
}
