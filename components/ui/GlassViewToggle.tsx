"use client";

export type DataViewMode = "table" | "cards";

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function GlassViewToggle({
  value,
  onChange,
  className,
}: {
  value: DataViewMode;
  onChange: (value: DataViewMode) => void;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "inline-flex items-center gap-1 rounded-full border border-white/80 bg-white/45 p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.8),0_6px_14px_rgba(21,44,33,0.08)] backdrop-blur-sm",
        className,
      )}
      aria-label="Affichage des donnees"
    >
      <button
        type="button"
        onClick={() => onChange("table")}
        className={cx(
          "soft-focus rounded-full px-3 py-1.5 text-xs font-semibold transition-all",
          value === "table"
            ? "bg-[var(--green-900)] text-white shadow-[0_8px_16px_rgba(20,61,43,0.26)]"
            : "text-[var(--green-900)] hover:bg-white/65",
        )}
      >
        Tableau
      </button>

      <button
        type="button"
        onClick={() => onChange("cards")}
        className={cx(
          "soft-focus rounded-full px-3 py-1.5 text-xs font-semibold transition-all",
          value === "cards"
            ? "bg-[var(--green-900)] text-white shadow-[0_8px_16px_rgba(20,61,43,0.26)]"
            : "text-[var(--green-900)] hover:bg-white/65",
        )}
      >
        Cartes
      </button>
    </div>
  );
}
