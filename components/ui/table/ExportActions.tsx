"use client";

type ExportActionsProps = {
  onCsv: () => void;
  onExcel: () => void;
  onPdf: () => void;
};

export function ExportActions({ onCsv, onExcel, onPdf }: ExportActionsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" onClick={onCsv} className="soft-focus rounded-xl border border-[#B9CCE9] bg-[#F5F9FF] px-3 py-2 text-xs font-semibold text-[#1F5EA8] hover:bg-[#EAF2FF]">
        Export CSV
      </button>
      <button type="button" onClick={onExcel} className="soft-focus rounded-xl border border-[#B9CCE9] bg-[#F5F9FF] px-3 py-2 text-xs font-semibold text-[#1F5EA8] hover:bg-[#EAF2FF]">
        Export Excel
      </button>
      <button type="button" onClick={onPdf} className="soft-focus rounded-xl border border-[#B9CCE9] bg-[#F5F9FF] px-3 py-2 text-xs font-semibold text-[#1F5EA8] hover:bg-[#EAF2FF]">
        Export PDF
      </button>
    </div>
  );
}
