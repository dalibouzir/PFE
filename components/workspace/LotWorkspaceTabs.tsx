"use client";

export type LotWorkspaceTab = "overview" | "process" | "analytics" | "recommendations" | "history";

const tabs: Array<{ id: LotWorkspaceTab; label: string }> = [
  { id: "overview", label: "Vue d'ensemble" },
  { id: "process", label: "Etapes / Transformations" },
  { id: "analytics", label: "Analytique" },
  { id: "recommendations", label: "Recommandations IA" },
  { id: "history", label: "Historique" },
];

export function LotWorkspaceTabs({
  activeTab,
  onChange,
  includeHistory = true,
}: {
  activeTab: LotWorkspaceTab;
  onChange: (tab: LotWorkspaceTab) => void;
  includeHistory?: boolean;
}) {
  const visibleTabs = includeHistory ? tabs : tabs.filter((item) => item.id !== "history");

  return (
    <section className="mt-4">
      <div className="scroll-thin flex gap-2 overflow-x-auto rounded-2xl border border-[var(--line)] bg-[var(--surface-soft)] p-1.5">
        {visibleTabs.map((item) => {
          const active = item.id === activeTab;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={`whitespace-nowrap rounded-xl px-3 py-2 text-sm font-semibold transition ${
                active
                  ? "bg-[var(--primary)] text-white"
                  : "bg-transparent text-[var(--text)] hover:bg-[var(--surface)]"
              }`}
            >
              {item.label}
            </button>
          );
        })}
      </div>
    </section>
  );
}
