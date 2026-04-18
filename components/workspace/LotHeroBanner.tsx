"use client";

import { StatusBadge } from "@/components/ui/StatusBadge";

export function LotHeroBanner({
  lotCode,
  productName,
  seasonLabel,
  initialQty,
  currentQty,
  lossPct,
  statusLabel,
  statusTone,
  onEditLot,
}: {
  lotCode: string;
  productName: string;
  seasonLabel: string;
  initialQty: number;
  currentQty: number;
  lossPct: number;
  statusLabel: string;
  statusTone: "success" | "warning" | "danger" | "info";
  onEditLot: () => void;
}) {
  return (
    <section
      className="premium-card reveal overflow-hidden rounded-2xl border-[rgba(38,118,169,0.25)] bg-[linear-gradient(120deg,#E9F4FB_0%,#DDEEF8_52%,#D4E9F7_100%)] p-4 text-[#17374A]"
      style={{ ["--delay" as string]: "40ms" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium tracking-[0.08em] text-[#31566E]">Lot en cours</p>
          <h2 className="mt-1 text-xl font-semibold sm:text-2xl">
            {lotCode} - {productName}
          </h2>
          <p className="mt-1 text-xs text-[#31566E] sm:text-sm">
            Saison {seasonLabel || "N/A"} · {initialQty.toFixed(0)} kg recolte initiale
          </p>
        </div>

        <div className="flex items-center gap-2">
          <StatusBadge label={statusLabel} tone={statusTone} />
          <button
            type="button"
            onClick={onEditLot}
            className="soft-focus rounded-xl border border-[#A7C4D7] bg-white/70 px-3 py-1.5 text-xs font-semibold text-[#17374A] hover:bg-white"
          >
            Modifier lot
          </button>
        </div>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <div className="rounded-xl border border-[#B8D0E0] bg-white/75 px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.1em] text-[#3C6178]">Quantite initiale</p>
          <p className="mt-0.5 text-base font-semibold text-[#17374A]">{initialQty.toFixed(0)} kg</p>
        </div>
        <div className="rounded-xl border border-[#B8D0E0] bg-white/75 px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.1em] text-[#3C6178]">Quantite actuelle</p>
          <p className="mt-0.5 text-base font-semibold text-[#17374A]">{currentQty.toFixed(0)} kg</p>
        </div>
        <div className="rounded-xl border border-[#B8D0E0] bg-white/75 px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.1em] text-[#3C6178]">Perte cumulee</p>
          <p className="mt-0.5 text-base font-semibold text-[#17374A]">{lossPct.toFixed(1)}%</p>
        </div>
      </div>
    </section>
  );
}
