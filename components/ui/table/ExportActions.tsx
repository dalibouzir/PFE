"use client";

type ExportActionsProps = {
  onCsv: () => void;
  onExcel: () => void;
  onPdf: () => void;
};

export function ExportActions({ onCsv, onExcel, onPdf }: ExportActionsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" onClick={onCsv} className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-soft)]">
        Export CSV
      </button>
      <button type="button" onClick={onExcel} className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-soft)]">
        Export Excel
      </button>
      <button type="button" onClick={onPdf} className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-sm font-semibold text-[var(--text)] hover:bg-[var(--surface-soft)]">
        Export PDF
      </button>
    </div>
  );
}
