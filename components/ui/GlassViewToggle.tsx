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
        "inline-flex items-center gap-1 rounded-full border border-[var(--line)] bg-[var(--surface-soft)] p-1",
        className,
      )}
      aria-label="Affichage des donnees"
    >
      <button
        type="button"
        onClick={() => onChange("table")}
        className={cx(
          "soft-focus rounded-full px-3 py-1.5 text-xs font-semibold transition",
          value === "table"
            ? "bg-[var(--primary)] text-white"
            : "text-[var(--text)] hover:bg-white",
        )}
      >
        Tableau
      </button>

      <button
        type="button"
        onClick={() => onChange("cards")}
        className={cx(
          "soft-focus rounded-full px-3 py-1.5 text-xs font-semibold transition",
          value === "cards"
            ? "bg-[var(--primary)] text-white"
            : "text-[var(--text)] hover:bg-white",
        )}
      >
        Cartes
      </button>
    </div>
  );
}
