"use client";

import { useMemo, useState } from "react";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { ExportActions } from "@/components/ui/table/ExportActions";
import { TableToolbar } from "@/components/ui/table/TableToolbar";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { exportRowsToCsv, exportRowsToExcel, exportRowsToPdf, type ExportColumn } from "@/lib/export/client";
import { useTableControls } from "@/lib/table/useTableControls";
import { useInputs } from "@/hooks/useInputs";
import { useProducts } from "@/hooks/useProducts";
import { useStocks } from "@/hooks/useStocks";
import { useStockMovementDetail, useStockMovements } from "@/hooks/useStockMovements";
import type { StockMovement } from "@/lib/api/types";

type ViewMode = "cards" | "table";

type MovementTicketRow = {
  cooperative: string;
  movement_reference: string;
  movement_type: string;
  action_type: string;
  movement_date: string;
  product: string;
  quantity_kg: string;
  batch_reference: string;
  input_reference: string;
  member_name: string;
  source: string;
  notes: string;
  generated_at: string;
};

export default function StocksPage() {
  const { data: stocks = [] } = useStocks();
  const { data: products = [] } = useProducts();
  const { data: inputs = [] } = useInputs();

  const [productId, setProductId] = useState<string>("Tous");
  const [viewMode, setViewMode] = useState<ViewMode>("cards");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [batchReference, setBatchReference] = useState("");
  const [inputReference, setInputReference] = useState("");
  const [selectedMovementId, setSelectedMovementId] = useState<string | null>(null);

  const tableControls = useTableControls([
    {
      key: "movement_type",
      label: "Type",
      options: [
        { value: "all", label: "Tous types" },
        { value: "in", label: "Entrée" },
        { value: "out", label: "Sortie" },
      ],
      initialValue: "all",
    },
    {
      key: "source",
      label: "Source",
      options: [
        { value: "all", label: "Toutes sources" },
        { value: "lot_linked_collecte", label: "Collecte liée lot" },
        { value: "manual", label: "Collecte indépendante" },
        { value: "post_harvest_step", label: "Post-récolte" },
        { value: "pre_harvest_confirmed_weight", label: "Poids confirmé pré-récolte" },
      ],
      initialValue: "all",
    },
  ]);

  const movementsQuery = useStockMovements({
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    product_id: productId !== "Tous" ? productId : undefined,
    movement_type: tableControls.filters.movement_type,
    source: tableControls.filters.source,
    batch_reference: batchReference || undefined,
    input_reference: inputReference || undefined,
    search: tableControls.search || undefined,
    sort: tableControls.sortOrder,
  });
  const commercialOutQuery = useStockMovements({
    source: "commercial_catalog",
    sort: "desc",
  });

  const detailQuery = useStockMovementDetail(selectedMovementId);

  const productLookup = useMemo(() => new Map(products.map((p) => [p.id, p.name])), [products]);

  const filtered = useMemo(() => {
    return stocks.filter((item) => (productId === "Tous" ? true : item.product_id === productId));
  }, [stocks, productId]);

  const filteredByUrgency = useMemo(() => {
    return filtered.slice().sort((a, b) => stockUrgencyScore(a.total_stock_kg, a.available_stock_kg) - stockUrgencyScore(b.total_stock_kg, b.available_stock_kg));
  }, [filtered]);

  const criticalCount = useMemo(
    () => filtered.filter((item) => isCriticalStock(item.total_stock_kg, item.available_stock_kg)).length,
    [filtered],
  );

  const collectedByProductKg = useMemo(() => {
    const map = new Map<string, number>();
    for (const input of inputs) {
      map.set(input.product_id, (map.get(input.product_id) ?? 0) + input.quantity);
    }
    return map;
  }, [inputs]);

  const commercialOutByProductKg = useMemo(() => {
    const map = new Map<string, number>();
    for (const movement of commercialOutQuery.data ?? []) {
      const current = map.get(movement.product_id) ?? 0;
      const signed = movement.movement_type === "in" ? -movement.quantity_kg : movement.quantity_kg;
      map.set(movement.product_id, current + signed);
    }
    return map;
  }, [commercialOutQuery.data]);
  const lossesByProductKg = useMemo(() => {
    const map = new Map<string, number>();
    for (const movement of movementsQuery.data ?? []) {
      if (movement.movement_type !== "out") continue;
      if ((movement.source || "").toLowerCase() !== "post_harvest_step") continue;
      map.set(movement.product_id, (map.get(movement.product_id) ?? 0) + movement.quantity_kg);
    }
    return map;
  }, [movementsQuery.data]);

  const movementRows = movementsQuery.data ?? [];
  const journalExportColumns: ExportColumn<StockMovement>[] = [
    { key: "movement_reference", header: "Référence" },
    { key: "movement_type", header: "Type", format: (_, row) => (row.movement_type === "in" ? "Entrée" : "Sortie") },
    { key: "batch_reference", header: "Lot", format: (_, row) => displayLotReference(row) },
    { key: "input_reference", header: "Collecte", format: (_, row) => row.input_reference || "—" },
    { key: "bl_number", header: "BL", format: (_, row) => row.input_reference_bl || "—" },
    { key: "member_name", header: "Producteur", format: (_, row) => row.member_name || "—" },
    { key: "product_name", header: "Produit", format: (_, row) => row.product_name || row.product_id },
    { key: "quantity_kg", header: "Quantité (kg)", format: (_, row) => row.quantity_kg.toLocaleString("fr-FR") },
    { key: "movement_date", header: "Date", format: (_, row) => formatDateTime(row.movement_date) },
    { key: "source", header: "Source", format: (_, row) => row.source_label || row.source },
    { key: "notes", header: "Notes", format: (_, row) => row.notes || "—" },
  ];

  const exportMovementTicket = (movement: StockMovement) => {
    const row: MovementTicketRow = {
      cooperative: movement.cooperative_name || "WeeFarm Cooperative",
      movement_reference: movement.movement_reference,
      movement_type: movement.movement_type,
      action_type: movement.action_type,
      movement_date: formatDateTime(movement.movement_date),
      product: movement.product_name || movement.product_id,
      quantity_kg: `${movement.quantity_kg.toLocaleString("fr-FR")} kg`,
      batch_reference: displayLotReference(movement),
      input_reference: movement.input_reference || "—",
      member_name: movement.member_name || "—",
      source: movement.source_label || movement.source,
      notes: movement.notes || "—",
      generated_at: new Date().toLocaleString("fr-FR"),
    };

    const columns: ExportColumn<MovementTicketRow>[] = [
      { key: "cooperative", header: "Coopérative" },
      { key: "movement_reference", header: "Référence mouvement" },
      { key: "movement_type", header: "Type mouvement" },
      { key: "action_type", header: "Action" },
      { key: "movement_date", header: "Date" },
      { key: "product", header: "Produit" },
      { key: "quantity_kg", header: "Quantité" },
      { key: "batch_reference", header: "Lot" },
      { key: "input_reference", header: "Collecte" },
      { key: "member_name", header: "Producteur" },
      { key: "source", header: "Source" },
      { key: "notes", header: "Notes" },
      { key: "generated_at", header: "Généré le" },
    ];

    exportRowsToPdf({
      filename: `ticket-mouvement-${movement.movement_reference}`,
      title: `Ticket mouvement ${movement.movement_reference}`,
      columns,
      rows: [row],
      generatedAt: new Date(),
    });
  };

  return (
    <main>
      <PageIntro title="Stocks" />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto]">
          <select
            value={productId}
            onChange={(event) => setProductId(event.target.value)}
            className="soft-focus wf-input px-3 py-2.5 text-sm"
          >
            <option value="Tous">Tous produits</option>
            {products.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>

          <div className="rounded-xl border border-[#E8B9B9] bg-[#FFEDEE] px-3 py-2 text-sm text-[var(--danger)]">
            Alertes critiques: <span className="font-semibold">{criticalCount}</span>
          </div>

          <div className="flex gap-1 rounded-lg border border-[var(--line)] bg-[var(--surface-soft)] p-1">
            <button
              onClick={() => setViewMode("cards")}
              className={`soft-focus rounded-md px-2.5 py-1.5 text-xs font-semibold ${viewMode === "cards" ? "bg-[var(--primary)] text-white" : "text-[var(--muted)]"}`}
            >
              Cartes
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={`soft-focus rounded-md px-2.5 py-1.5 text-xs font-semibold ${viewMode === "table" ? "bg-[var(--primary)] text-white" : "text-[var(--muted)]"}`}
            >
              Tableau
            </button>
          </div>
        </div>
      </section>

      {viewMode === "cards" ? (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filteredByUrgency.length === 0 ? (
            <article className="premium-card reveal rounded-2xl p-5 sm:col-span-2 xl:col-span-3" style={{ ["--delay" as string]: "70ms" }}>
              <p className="text-sm text-[var(--muted)]">Aucun produit de stock à afficher pour ce filtre.</p>
            </article>
          ) : (
            filteredByUrgency.map((item, index) => {
              const remainingKg = item.available_stock_kg;
              const remainingDisplay = fromKg(remainingKg, item.unit);
              const isCritical = isCriticalStock(item.total_stock_kg, remainingKg);
              const total = item.total_stock;
              const commercialOut = fromKg(Math.max(commercialOutByProductKg.get(item.product_id) ?? 0, 0), item.unit);
              const losses = fromKg(Math.max(lossesByProductKg.get(item.product_id) ?? 0, 0), item.unit);
              const threshold = total * 0.2;
              const progress = total > 0 ? Math.max(6, Math.min((remainingDisplay / total) * 100, 100)) : 0;
              const barClass = isCritical
                ? "bg-gradient-to-r from-red-400 to-red-600"
                : total > 0 && remainingDisplay < threshold * 1.4
                  ? "bg-gradient-to-r from-amber-400 to-amber-600"
                  : "bg-gradient-to-r from-green-400 to-green-600";
              return (
                <article key={item.product_id} className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: `${70 + index * 25}ms` }}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</p>
                    </div>
                    <StatusBadge label={isCritical ? "Critique" : "Stable"} tone={isCritical ? "danger" : "success"} />
                  </div>

                  <p className="mt-4 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">Stock total</p>
                  <p className="mt-1 text-3xl font-semibold text-[var(--text)]">
                    {total.toFixed(2)} {item.unit}
                  </p>

                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs xl:grid-cols-3">
                    <MetricPill label="Sortie vente" value={commercialOut} unit={item.unit} tone="neutral" />
                    <MetricPill label="Pertes" value={losses} unit={item.unit} tone="danger" hideZero />
                    <MetricPill label="Restant" value={remainingDisplay} unit={item.unit} tone={isCritical ? "danger" : "success"} />
                  </div>

                  <div className="mt-3 h-2.5 rounded-full bg-[#E8E3DB]">
                    <div className={`h-2.5 rounded-full ${barClass}`} style={{ width: `${progress}%` }} />
                  </div>
                </article>
              );
            })
          )}
        </section>
      ) : (
        <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "70ms" }}>
          <div className="overflow-x-auto">
            <table className="wf-table min-w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="px-5 py-3.5">Produit</th>
                  <th className="px-5 py-3.5">Stock total</th>
                  <th className="px-5 py-3.5">Collecté</th>
                  <th className="px-5 py-3.5">Sortie vente</th>
                  <th className="px-5 py-3.5">Pertes</th>
                  <th className="px-5 py-3.5">Restant</th>
                  <th className="px-5 py-3.5">Statut</th>
                </tr>
              </thead>
              <tbody>
                {filteredByUrgency.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-5 py-4 text-center text-sm text-[var(--muted)]">
                      Aucun stock enregistré à afficher pour ce filtre.
                    </td>
                  </tr>
                ) : (
                  filteredByUrgency.map((item) => {
                    const remainingKg = item.available_stock_kg;
                    const isCritical = isCriticalStock(item.total_stock_kg, remainingKg);
                    const collected = fromKg(collectedByProductKg.get(item.product_id) ?? 0, item.unit);
                    const commercialOut = fromKg(Math.max(commercialOutByProductKg.get(item.product_id) ?? 0, 0), item.unit);
                    const losses = fromKg(Math.max(lossesByProductKg.get(item.product_id) ?? 0, 0), item.unit);
                    const remainingDisplay = fromKg(remainingKg, item.unit);
                    return (
                      <tr key={item.product_id}>
                        <td className="px-5 py-4 font-semibold text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</td>
                        <td className="px-5 py-4">{item.total_stock.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4">{collected.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4 text-[var(--danger)]">{commercialOut.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4 text-[var(--danger)]">{losses.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4 font-medium">{remainingDisplay.toFixed(2)} {item.unit}</td>
                        <td className="px-5 py-4">
                          <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${isCritical ? "bg-[#FFEDEE] text-[#A83C3C]" : "bg-[#EAF8EE] text-[#0F7A3B]"}`}>
                            {isCritical ? "Critique" : "Stable"}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="premium-card reveal mt-4 rounded-2xl p-6" style={{ ["--delay" as string]: "120ms" }}>
        <h3 className="mb-4 text-lg font-semibold text-[var(--text)]">Journal des mouvements (persisté)</h3>

        <div className="mb-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="soft-focus wf-input px-3 py-2.5 text-sm" />
          <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="soft-focus wf-input px-3 py-2.5 text-sm" />
          <input value={batchReference} onChange={(event) => setBatchReference(event.target.value)} placeholder="Filtrer lot (ref)" className="soft-focus wf-input px-3 py-2.5 text-sm" />
          <input value={inputReference} onChange={(event) => setInputReference(event.target.value)} placeholder="Filtrer collecte (ref)" className="soft-focus wf-input px-3 py-2.5 text-sm" />
        </div>

        <TableToolbar
          search={tableControls.search}
          onSearchChange={tableControls.setSearch}
          searchPlaceholder="Recherche référence, produit, source, producteur..."
          filters={tableControls.filterDefinitions}
          onFilterChange={tableControls.setFilterValue}
          sortOrder={tableControls.sortOrder}
          onSortOrderChange={tableControls.setSortOrder}
          sortAscLabel="Date asc"
          sortDescLabel="Date desc"
          rightActions={
            <ExportActions
              onCsv={() => exportRowsToCsv({ filename: "journal-mouvements-stock", title: "Journal Mouvements Stock", columns: journalExportColumns, rows: movementRows })}
              onExcel={() => exportRowsToExcel({ filename: "journal-mouvements-stock", title: "Journal Mouvements Stock", columns: journalExportColumns, rows: movementRows })}
              onPdf={() => exportRowsToPdf({ filename: "journal-mouvements-stock", title: "Journal Mouvements Stock", columns: journalExportColumns, rows: movementRows })}
            />
          }
        />

        <div className="mt-4">
          <table className="wf-table w-full table-fixed text-left text-sm">
            <thead>
              <tr>
                <th className="px-3 py-3.5">Type</th>
                <th className="px-3 py-3.5">Lot</th>
                <th className="px-3 py-3.5">Produit</th>
                <th className="px-3 py-3.5">Quantité</th>
                <th className="px-3 py-3.5">Producteur</th>
                <th className="px-3 py-3.5">Date</th>
                <th className="px-3 py-3.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {movementsQuery.isLoading ? (
                <tr>
                  <td colSpan={7} className="px-5 py-4 text-center text-sm text-[var(--muted)]">Chargement des mouvements...</td>
                </tr>
              ) : movementsQuery.error ? (
                <tr>
                  <td colSpan={7} className="px-5 py-4 text-center text-sm text-[var(--danger)]">
                    {movementsQuery.error instanceof Error ? movementsQuery.error.message : "Erreur de chargement du journal."}
                  </td>
                </tr>
              ) : movementRows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-4 text-center text-sm text-[var(--muted)]">Aucun mouvement disponible pour ces filtres.</td>
                </tr>
              ) : (
                movementRows.map((movement) => (
                  <tr key={movement.id}>
                    <td className="px-3 py-4 truncate" title={`${movement.movement_type} · ${movement.action_type}`}>{movement.movement_type} · {movement.action_type}</td>
                    <td className="px-3 py-4">
                      <div className="flex items-center gap-2">
                        <span className="truncate" title={displayLotReference(movement)}>{displayLotReference(movement)}</span>
                        {movement.traceability_status === "legacy_unlinked" ? (
                          <span className="inline-flex rounded-full bg-[#FFF5E8] px-2 py-0.5 text-[11px] font-semibold text-[#A8651A]">
                            Historique / non lié
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-3 py-4 truncate" title={movement.product_name || movement.product_id.slice(0, 8)}>{movement.product_name || movement.product_id.slice(0, 8)}</td>
                    <td className={`px-3 py-4 font-semibold whitespace-nowrap ${movement.movement_type === "in" ? "text-[var(--success)]" : "text-[var(--danger)]"}`}>
                      {movement.movement_type === "in" ? "+" : "-"}{movement.quantity_kg.toLocaleString("fr-FR")} kg
                    </td>
                    <td className="px-3 py-4 truncate" title={displayProducerNameShort(movement.member_name)}>
                      {displayProducerNameShort(movement.member_name)}
                    </td>
                    <td className="px-3 py-4 text-xs text-[var(--muted)] whitespace-nowrap">{formatDateTime(movement.movement_date)}</td>
                    <td className="px-3 py-4">
                      <div className="flex flex-col items-start gap-1 sm:flex-row sm:items-center sm:gap-2">
                        <button type="button" className="text-xs font-semibold text-[var(--primary)] hover:underline" onClick={() => setSelectedMovementId(movement.id)}>
                          Détail
                        </button>
                        <button type="button" className="text-xs font-semibold text-[var(--text)] hover:underline" onClick={() => exportMovementTicket(movement)}>
                          Ticket PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <LiquidGlassModal
        open={Boolean(selectedMovementId)}
        onClose={() => setSelectedMovementId(null)}
        title="Détail mouvement"
        subtitle="Contexte persisté depuis stock_movements"
        size="lg"
      >
        {detailQuery.isLoading ? (
          <p className="text-sm text-[var(--muted)]">Chargement du détail...</p>
        ) : detailQuery.error ? (
          <p className="text-sm text-[var(--danger)]">{detailQuery.error instanceof Error ? detailQuery.error.message : "Erreur de chargement."}</p>
        ) : detailQuery.data ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Info label="Référence" value={detailQuery.data.movement_reference} />
            <Info label="Type" value={`${detailQuery.data.movement_type} · ${detailQuery.data.action_type}`} />
            <Info label="Date" value={formatDateTime(detailQuery.data.movement_date)} />
            <Info label="Produit" value={detailQuery.data.product_name || detailQuery.data.product_id} />
            <Info label="Quantité" value={`${detailQuery.data.quantity_kg.toLocaleString("fr-FR")} kg`} />
            <Info label="Lot" value={displayLotReference(detailQuery.data)} />
            <Info label="Collecte" value={detailQuery.data.input_reference || "—"} />
            <Info label="BL collecte" value={detailQuery.data.input_reference_bl || "—"} />
            <Info label="Producteur" value={detailQuery.data.member_name || "—"} />
            <Info label="Source" value={detailQuery.data.source_label || detailQuery.data.source} />
            <Info label="Coopérative" value={detailQuery.data.cooperative_name || "—"} />
            <Info label="Idempotency key" value={detailQuery.data.idempotency_key} />
            <Info label="Notes" value={detailQuery.data.notes || "—"} />
          </div>
        ) : (
          <p className="text-sm text-[var(--muted)]">Aucune donnée.</p>
        )}
      </LiquidGlassModal>

      {filtered.length === 0 && (
        <section className="premium-card reveal mt-4 rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucun stock enregistré. Les lignes de stock sont créées automatiquement via les collectes.</p>
        </section>
      )}
    </main>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
      <p className="text-xs text-[var(--muted)]">{label}</p>
      <p className="text-sm font-semibold text-[var(--text)] break-all">{value}</p>
    </div>
  );
}

function MetricPill({
  label,
  value,
  unit,
  tone,
  hideZero = false,
}: {
  label: string;
  value: number;
  unit: string;
  tone: "neutral" | "info" | "success" | "danger";
  hideZero?: boolean;
}) {
  const toneClass =
    tone === "danger"
      ? "bg-[#FFEDEE] text-[var(--danger)]"
      : tone === "success"
        ? "bg-[#EAF8EE] text-[var(--success)]"
        : tone === "info"
          ? "bg-[#EEF5FF] text-[var(--text)]"
          : "bg-[var(--surface-soft)] text-[var(--text)]";
  return (
    <div className={`rounded-lg px-2 py-1.5 ${toneClass}`}>
      <p className="font-semibold">
        {hideZero && Math.abs(value) < 1e-9 ? "—" : `${value.toFixed(2)} ${unit}`}
      </p>
      <p>{label}</p>
    </div>
  );
}

function isCriticalStock(totalStockKg: number, remainingKg: number) {
  if (totalStockKg <= 0) return false;
  return remainingKg < totalStockKg * 0.2;
}

function stockUrgencyScore(totalStockKg: number, remainingKg: number) {
  if (totalStockKg <= 0) return 1;
  return remainingKg / totalStockKg;
}

function normalizeMassUnit(unit?: string | null): "kg" | "ton" {
  return String(unit || "kg").toLowerCase() === "ton" ? "ton" : "kg";
}

function fromKg(valueKg: number, unit?: string | null) {
  return normalizeMassUnit(unit) === "ton" ? valueKg / 1000 : valueKg;
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function displayLotReference(movement: Pick<StockMovement, "batch_reference" | "traceability_status">) {
  if (movement.batch_reference) return movement.batch_reference;
  if (movement.traceability_status === "missing_lot" || movement.traceability_status === "legacy_unlinked") {
    return "Lot non renseigné";
  }
  if (movement.traceability_status === "unresolved_lot") return "Lot introuvable";
  return "Lot non renseigné";
}

function displayProducerNameShort(value?: string | null) {
  const text = (value || "").trim();
  if (!text) return "—";
  const match = text.match(/^(.*?)\s*\([^()]*@[^()]*\)\s*$/);
  if (!match) return text;
  return match[1].trim() || text;
}
