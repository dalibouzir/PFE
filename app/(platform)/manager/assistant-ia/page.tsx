"use client";

import { FormEvent, useMemo, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import {
  assistantMockAnswers,
  assistantSuggestedPrompts,
  assistantThreads,
  type AssistantMessage,
  type AssistantThread,
} from "@/lib/mock-data";

type AssistantAnswer = {
  text: string;
  points: string[];
};

const fallbackAnswer: AssistantAnswer = {
  text: "Je peux vous aider sur les lots, stocks, produits, transformations et collectes membres.",
  points: [
    "Essayez un prompt suggere pour une reponse detaillee",
    "Les reponses affichent des donnees mock synchronisees",
  ],
};

const timeFormatter = new Intl.DateTimeFormat("fr-SN", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function buildAssistantAnswer(question: string): AssistantAnswer {
  const exact = assistantMockAnswers[question];
  if (exact) return exact;

  const text = question.toLowerCase();

  if (text.includes("stock")) return assistantMockAnswers["Montre-moi les stocks critiques"];
  if (text.includes("rendement") || text.includes("produit")) return assistantMockAnswers["Quel produit a le meilleur rendement ?"];
  if (text.includes("transformation")) return assistantMockAnswers["Resume les dernieres transformations"];
  if (text.includes("membre") || text.includes("livre")) return assistantMockAnswers["Quels membres ont livre le plus ce mois-ci ?"];
  if (text.includes("perte") || text.includes("lot")) return assistantMockAnswers["Quel lot a le plus de pertes cette semaine ?"];

  return fallbackAnswer;
}

function messageId(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

export default function AssistantIAPage() {
  const [threads, setThreads] = useState<AssistantThread[]>(assistantThreads);
  const [activeThreadId, setActiveThreadId] = useState<string>("new");
  const [draft, setDraft] = useState("");

  const activeThread = useMemo(
    () => threads.find((thread) => thread.id === activeThreadId) ?? null,
    [threads, activeThreadId],
  );

  const messages: AssistantMessage[] = activeThread?.messages ?? [];

  const startNewConversation = () => {
    setActiveThreadId("new");
    setDraft("");
  };

  const sendMessage = (rawText: string) => {
    const value = rawText.trim();
    if (!value) return;

    const answer = buildAssistantAnswer(value);
    const now = timeFormatter.format(new Date());

    const userMessage: AssistantMessage = {
      id: messageId("USR"),
      role: "user",
      text: value,
      time: now,
    };

    const assistantMessage: AssistantMessage = {
      id: messageId("AST"),
      role: "assistant",
      text: answer.text,
      points: answer.points,
      time: now,
    };

    if (activeThreadId === "new") {
      const newThread: AssistantThread = {
        id: messageId("TH"),
        title: value.length > 32 ? `${value.slice(0, 32)}...` : value,
        updatedAt: `Aujourd hui, ${now}`,
        preview: answer.text,
        messages: [userMessage, assistantMessage],
      };

      setThreads((prev) => [newThread, ...prev]);
      setActiveThreadId(newThread.id);
      setDraft("");
      return;
    }

    setThreads((prev) =>
      prev.map((thread) => {
        if (thread.id !== activeThreadId) return thread;

        return {
          ...thread,
          updatedAt: `Aujourd hui, ${now}`,
          preview: answer.text,
          messages: [...thread.messages, userMessage, assistantMessage],
        };
      }),
    );

    setDraft("");
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    sendMessage(draft);
  };

  return (
    <main>
      <PageIntro title="Assistant IA" subtitle="Assistant conversationnel demo base sur les donnees operationnelles de la cooperative." />

      <section className="grid gap-4 xl:grid-cols-[300px_1fr]">
        <aside className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[var(--green-900)]">Historique</h3>
            <button
              onClick={startNewConversation}
              className="soft-focus rounded-lg border border-[var(--line)] bg-white px-2.5 py-1 text-xs font-semibold text-[var(--green-700)]"
            >
              Nouveau
            </button>
          </div>

          <div className="space-y-2">
            <button
              onClick={startNewConversation}
              className={
                "w-full rounded-xl border px-3 py-2 text-left transition " +
                (activeThreadId === "new"
                  ? "border-[var(--green-500)] bg-[#ebf6ee]"
                  : "border-[var(--line)] bg-[var(--surface-soft)] hover:border-[var(--green-500)]")
              }
            >
              <p className="text-sm font-medium text-[var(--text)]">Nouvelle conversation</p>
              <p className="text-xs text-[var(--muted)]">Aucun message</p>
            </button>

            {threads.map((thread) => (
              <button
                key={thread.id}
                onClick={() => setActiveThreadId(thread.id)}
                className={
                  "w-full rounded-xl border px-3 py-2 text-left transition " +
                  (activeThreadId === thread.id
                    ? "border-[var(--green-500)] bg-[#ebf6ee]"
                    : "border-[var(--line)] bg-[var(--surface-soft)] hover:border-[var(--green-500)]")
                }
              >
                <p className="text-sm font-medium text-[var(--text)]">{thread.title}</p>
                <p className="line-clamp-1 text-xs text-[var(--muted)]">{thread.preview}</p>
                <p className="mt-1 text-[11px] text-[var(--muted)]">{thread.updatedAt}</p>
              </button>
            ))}
          </div>
        </aside>

        <article className="premium-card reveal rounded-2xl p-4 sm:p-5" style={{ ["--delay" as string]: "90ms" }}>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-[var(--green-900)]">Conversation</h3>
              <p className="text-xs text-[var(--muted)]">Mode demo UI - sans logique IA backend</p>
            </div>
            <span className="rounded-full bg-[var(--green-200)] px-2.5 py-1 text-[11px] font-semibold text-[var(--green-800)]">Assistant IA</span>
          </div>

          <div className="h-[430px] rounded-2xl border border-[var(--line)] bg-[var(--surface-soft)] p-3 sm:p-4">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#d9ecd8] text-lg">IA</div>
                <p className="text-sm font-semibold text-[var(--green-900)]">Demarrer une conversation</p>
                <p className="mt-1 max-w-md text-xs text-[var(--muted)]">
                  Posez une question sur les lots, les stocks, les produits ou les transformations. Les reponses sont simulees avec des donnees locales coherentes.
                </p>

                <div className="mt-4 flex max-w-2xl flex-wrap justify-center gap-2">
                  {assistantSuggestedPrompts.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => sendMessage(prompt)}
                      className="soft-focus rounded-full border border-[var(--line)] bg-white px-3 py-1.5 text-xs text-[var(--green-800)] hover:border-[var(--green-500)]"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="scroll-thin h-full space-y-3 overflow-y-auto pr-1">
                {messages.map((message) => {
                  const isUser = message.role === "user";

                  return (
                    <div key={message.id} className={isUser ? "flex justify-end" : "flex justify-start"}>
                      <div
                        className={
                          "max-w-[88%] rounded-2xl px-4 py-3 text-sm " +
                          (isUser
                            ? "bg-[var(--green-900)] text-white"
                            : "border border-[var(--line)] bg-white text-[var(--text)]")
                        }
                      >
                        <p>{message.text}</p>

                        {message.points && message.points.length > 0 && (
                          <ul className="mt-2 space-y-1 text-xs text-[var(--muted)]">
                            {message.points.map((point) => (
                              <li key={point}>- {point}</li>
                            ))}
                          </ul>
                        )}

                        <p className={"mt-2 text-[11px] " + (isUser ? "text-white/80" : "text-[var(--muted)]")}>{message.time}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {assistantSuggestedPrompts.map((prompt) => (
              <button
                key={prompt}
                onClick={() => sendMessage(prompt)}
                className="soft-focus rounded-full border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-1.5 text-xs text-[var(--green-800)] hover:border-[var(--green-500)]"
              >
                {prompt}
              </button>
            ))}
          </div>

          <form onSubmit={onSubmit} className="mt-3 flex gap-2">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Posez une question operationnelle..."
              className="soft-focus flex-1 rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm"
            />
            <button
              type="submit"
              className="soft-focus rounded-xl bg-[var(--green-900)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--green-800)]"
            >
              Envoyer
            </button>
          </form>
        </article>
      </section>
    </main>
  );
}
