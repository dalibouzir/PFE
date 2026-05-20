"use client";

import { useEffect, useMemo, useState } from "react";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import { ContentAreaLoader } from "@/components/ui/ContentAreaLoader";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { TableToolbar } from "@/components/ui/table/TableToolbar";
import { useAuth } from "@/context/auth/AuthContext";
import { useCommercialInvoiceStats, useCommercialInvoices } from "@/hooks/useCommercial";
import { exportRowsToCsv, exportRowsToExcel, type ExportColumn } from "@/lib/export/client";
import { useTableControls } from "@/lib/table/useTableControls";
import type { CommercialInvoice } from "@/lib/api/types";

const COOPERATIVE_PROFILE = {
  name: "Cooperative Deggo Thies",
  legalId: "NINEA SN-DTG-2026-0198",
  address: "Route de Mbour, Thies, Senegal",
  phone: "+221 33 812 45 67",
  email: "facturation@deggo-thies.sn",
};

type InvoiceExportDraft = {
  clientEmail: string;
  clientAddress: string;
  dueDate: string;
  notes: string;
  paymentTerms: string;
  issuerName: string;
  issuerLegalId: string;
  issuerAddress: string;
  issuerPhone: string;
  issuerEmail: string;
};

function money(value: number) {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(value);
}

function statusPill(status: CommercialInvoice["status"]) {
  if (status === "paid") return "bg-[#EAF8EE] text-[#0F7A3B]";
  return "bg-[#FFF4E2] text-[#C96D00]";
}

function fmtDate(value: string) {
  try {
    return new Intl.DateTimeFormat("fr-FR").format(new Date(value));
  } catch {
    return value;
  }
}

function buildInvoiceDraft(invoice: CommercialInvoice): InvoiceExportDraft {
  return {
    clientEmail: invoice.customer_email ?? "",
    clientAddress: invoice.customer_address ?? "",
    dueDate: invoice.due_date ?? "",
    notes: "",
    paymentTerms: "Paiement à 30 jours fin de mois",
    issuerName: COOPERATIVE_PROFILE.name,
    issuerLegalId: COOPERATIVE_PROFILE.legalId,
    issuerAddress: COOPERATIVE_PROFILE.address,
    issuerPhone: COOPERATIVE_PROFILE.phone,
    issuerEmail: COOPERATIVE_PROFILE.email,
  };
}

function exportInvoicePdf(invoice: CommercialInvoice, draft: InvoiceExportDraft, preparedBy: string) {
  const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "a4" });
  const pageWidth = doc.internal.pageSize.getWidth();
  let y = 52;
  const left = 44;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.setTextColor(31, 94, 168);
  doc.text("EMETTEUR", left, y);
  y += 20;
  doc.setFontSize(20);
  doc.setTextColor(20, 28, 45);
  doc.text(draft.issuerName, left, y);
  y += 18;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(90, 102, 118);
  [draft.issuerAddress, draft.issuerPhone, draft.issuerEmail, draft.issuerLegalId].filter(Boolean).forEach((line) => {
    doc.text(line, left, y);
    y += 14;
  });

  const right = pageWidth - 44;
  let rightY = 52;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.setTextColor(31, 94, 168);
  doc.text("FACTURE", right, rightY, { align: "right" });
  rightY += 20;
  doc.setFontSize(22);
  doc.setTextColor(20, 28, 45);
  doc.text(invoice.invoice_number, right, rightY, { align: "right" });
  rightY += 18;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(90, 102, 118);
  doc.text(`Commande ${invoice.order_number}`, right, rightY, { align: "right" });
  rightY += 14;
  doc.text(`Emission ${fmtDate(invoice.issue_date)}`, right, rightY, { align: "right" });
  rightY += 14;
  doc.text(`Echeance ${draft.dueDate ? fmtDate(draft.dueDate) : "-"}`, right, rightY, { align: "right" });
  rightY += 22;
  doc.setFillColor(invoice.status === "paid" ? 234 : 255, invoice.status === "paid" ? 248 : 244, 226);
  doc.roundedRect(right - 130, rightY - 11, 130, 20, 10, 10, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(9);
  doc.setTextColor(invoice.status === "paid" ? 15 : 201, invoice.status === "paid" ? 122 : 109, invoice.status === "paid" ? 59 : 0);
  doc.text(invoice.status === "paid" ? "PAYEE" : "EN ATTENTE", right - 65, rightY + 2, { align: "center" });

  const cardY = Math.max(y, rightY + 22) + 8;
  doc.setDrawColor(220, 225, 233);
  doc.setFillColor(248, 250, 253);
  doc.roundedRect(left, cardY, pageWidth - 88, 92, 10, 10, "FD");

  doc.setFont("helvetica", "bold");
  doc.setFontSize(9);
  doc.setTextColor(110, 120, 135);
  doc.text("FACTURE A", left + 14, cardY + 18);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.setTextColor(20, 28, 45);
  doc.text(invoice.customer_name, left + 14, cardY + 37);
  doc.setFontSize(10);
  doc.setTextColor(90, 102, 118);
  doc.text(invoice.customer_phone || "-", left + 14, cardY + 53);
  doc.text(draft.clientEmail || "-", left + 14, cardY + 67);
  doc.text(draft.clientAddress || "-", left + 14, cardY + 81);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(9);
  doc.setTextColor(110, 120, 135);
  doc.text("REFERENCE COOPERATIVE", pageWidth / 2 + 18, cardY + 18);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(90, 102, 118);
  doc.text(`ID coop: ${invoice.cooperative_id}`, pageWidth / 2 + 18, cardY + 37);
  doc.text(`Prepare par: ${preparedBy}`, pageWidth / 2 + 18, cardY + 53);
  doc.text(`Date export: ${fmtDate(new Date().toISOString())}`, pageWidth / 2 + 18, cardY + 67);
  if (draft.paymentTerms.trim()) doc.text(`Conditions: ${draft.paymentTerms.trim()}`, pageWidth / 2 + 18, cardY + 81);

  autoTable(doc, {
    startY: cardY + 108,
    margin: { left, right: 44 },
    head: [["Description", "Unite", "Qte", "P.U. (FCFA)", "Total (FCFA)"]],
    body: invoice.lines.map((line) => [
      line.description,
      line.unit,
      String(line.quantity),
      money(line.unit_price_fcfa),
      money(line.line_total_fcfa),
    ]),
    styles: { fontSize: 9, cellPadding: 6, textColor: [35, 44, 58] },
    headStyles: { fillColor: [244, 247, 252], textColor: [35, 44, 58], lineColor: [220, 225, 233] },
    bodyStyles: { lineColor: [232, 236, 243] },
    theme: "grid",
  });

  const tableBottom = (doc as jsPDF & { lastAutoTable?: { finalY?: number } }).lastAutoTable?.finalY ?? cardY + 280;
  const totalsTop = tableBottom + 18;
  const totalsLeft = pageWidth - 280;
  doc.setDrawColor(220, 225, 233);
  doc.roundedRect(totalsLeft, totalsTop, 236, 88, 8, 8, "S");

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(90, 102, 118);
  doc.text("Sous-total HT", totalsLeft + 12, totalsTop + 22);
  doc.text(`${money(invoice.subtotal_fcfa)} FCFA`, totalsLeft + 224, totalsTop + 22, { align: "right" });
  doc.text(`TVA ${(invoice.tax_rate * 100).toFixed(0)}%`, totalsLeft + 12, totalsTop + 42);
  doc.text(`${money(invoice.tax_amount_fcfa)} FCFA`, totalsLeft + 224, totalsTop + 42, { align: "right" });
  doc.setDrawColor(230, 233, 238);
  doc.line(totalsLeft + 12, totalsTop + 52, totalsLeft + 224, totalsTop + 52);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.setTextColor(20, 28, 45);
  doc.text("TOTAL TTC", totalsLeft + 12, totalsTop + 75);
  doc.setTextColor(31, 94, 168);
  doc.text(`${money(invoice.total_amount_fcfa)} FCFA`, totalsLeft + 224, totalsTop + 75, { align: "right" });

  const noteY = totalsTop + 112;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(110, 120, 135);
  if (draft.notes.trim()) {
    doc.text(`Notes: ${draft.notes.trim()}`, left, noteY, { maxWidth: pageWidth - 88 });
  }
  doc.text(`Merci pour votre confiance. Cette facture est generee par ${draft.issuerName}.`, left, noteY + (draft.notes.trim() ? 18 : 0), {
    maxWidth: pageWidth - 88,
  });

  doc.save(`${invoice.invoice_number}.pdf`);
}

export default function FacturationPage() {
  const { user } = useAuth();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [invoicePage, setInvoicePage] = useState(1);
  const [invoicePageSize, setInvoicePageSize] = useState(10);
  const [clientFilter, setClientFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [draft, setDraft] = useState<InvoiceExportDraft | null>(null);
  const statsQuery = useCommercialInvoiceStats();
  const invoicesQuery = useCommercialInvoices();
  const stats = statsQuery.data;
  const invoices = invoicesQuery.data ?? [];
  const tableControls = useTableControls(
    [
      {
        key: "status",
        label: "Statut",
        options: [
          { value: "all", label: "Tous statuts" },
          { value: "paid", label: "Payée" },
          { value: "pending", label: "En attente" },
        ],
        initialValue: "all",
      },
    ],
    "desc",
  );
  const visibleInvoices = useMemo(() => {
    const q = tableControls.search.trim().toLowerCase();
    const filtered = invoices.filter((invoice) => {
      const byStatus = tableControls.filters.status === "all" || invoice.status === tableControls.filters.status;
      const byClient = clientFilter.trim().length === 0 || invoice.customer_name.toLowerCase().includes(clientFilter.trim().toLowerCase());
      const byFrom = dateFrom ? invoice.issue_date >= dateFrom : true;
      const byTo = dateTo ? invoice.issue_date <= dateTo : true;
      if (!byClient || !byFrom || !byTo) return false;
      if (!byStatus) return false;
      if (!q) return true;
      return (
        invoice.invoice_number.toLowerCase().includes(q) ||
        invoice.order_number.toLowerCase().includes(q) ||
        invoice.customer_name.toLowerCase().includes(q)
      );
    });
    const sorted = filtered.slice().sort((a, b) => a.issue_date.localeCompare(b.issue_date));
    return tableControls.sortOrder === "asc" ? sorted : sorted.reverse();
  }, [invoices, tableControls.filters.status, tableControls.search, tableControls.sortOrder, clientFilter, dateFrom, dateTo]);

  const selected = useMemo(() => {
    if (!visibleInvoices.length || !selectedId) return null;
    return visibleInvoices.find((invoice) => invoice.id === selectedId) ?? null;
  }, [selectedId, visibleInvoices]);
  const paginatedInvoices = useMemo(() => {
    const start = (invoicePage - 1) * invoicePageSize;
    return visibleInvoices.slice(start, start + invoicePageSize);
  }, [invoicePage, invoicePageSize, visibleInvoices]);
  const invoiceTotalPages = Math.max(Math.ceil(visibleInvoices.length / invoicePageSize), 1);

  useEffect(() => {
    setInvoicePage(1);
  }, [tableControls.search, tableControls.filters.status, tableControls.sortOrder, invoicePageSize, clientFilter, dateFrom, dateTo]);

  useEffect(() => {
    if (!selected) {
      setDraft(null);
      return;
    }
    setDraft(buildInvoiceDraft(selected));
  }, [selected]);

  const invoiceExportColumns: ExportColumn<CommercialInvoice>[] = [
    { key: "invoice_number", header: "Facture" },
    { key: "order_number", header: "Commande" },
    { key: "customer_name", header: "Client" },
    { key: "issue_date", header: "Date emission", format: (_, row) => fmtDate(row.issue_date) },
    { key: "due_date", header: "Echeance", format: (_, row) => (row.due_date ? fmtDate(row.due_date) : "-") },
    { key: "total_amount_fcfa", header: "Total TTC (FCFA)", format: (_, row) => row.total_amount_fcfa.toLocaleString("fr-FR") },
    { key: "status", header: "Statut", format: (_, row) => (row.status === "paid" ? "Payee" : "En attente") },
  ];

  if (statsQuery.isLoading || invoicesQuery.isLoading) {
    return (
      <main className="relative min-h-[60vh]">
        <PageIntro title="Facturation" />
        <ContentAreaLoader
          title="Chargement Facturation"
          subtitle="Synchronisation des factures et statistiques..."
        />
      </main>
    );
  }

  if (statsQuery.isError || invoicesQuery.isError) {
    return (
      <main>
        <PageIntro title="Facturation" />
        <section className="premium-card reveal mt-4 rounded-2xl p-4">
          <p className="text-sm text-[var(--danger)]">Impossible de charger les données requises de la page Facturation.</p>
        </section>
      </main>
    );
  }

  return (
    <main>
      <PageIntro title="Facturation" />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="premium-card rounded-2xl p-5">
          <p className="text-xs text-[var(--muted)]">Total facture</p>
          <p className="mt-2 text-4xl font-semibold text-[var(--text)]">{money(stats?.total_invoiced_fcfa ?? 0)}</p>
          <p className="text-xs text-[var(--muted)]">FCFA TTC</p>
        </article>
        <article className="premium-card rounded-2xl p-5">
          <p className="text-xs text-[var(--muted)]">Payees</p>
          <p className="mt-2 text-4xl font-semibold text-[var(--success)]">{money(stats?.paid_fcfa ?? 0)}</p>
          <p className="text-xs text-[var(--muted)]">FCFA encaissees</p>
        </article>
        <article className="premium-card rounded-2xl p-5">
          <p className="text-xs text-[var(--muted)]">En attente</p>
          <p className="mt-2 text-4xl font-semibold text-[#B67B00]">{money(stats?.pending_fcfa ?? 0)}</p>
          <p className="text-xs text-[var(--muted)]">FCFA a encaisser</p>
        </article>
        <article className="premium-card rounded-2xl p-5">
          <p className="text-xs text-[var(--muted)]">Recouvrement</p>
          <p className="mt-2 text-4xl font-semibold text-[#2673B7]">{(stats?.paid_rate_percent ?? 0).toFixed(1)}%</p>
          <p className="text-xs text-[var(--muted)]">Taux paye</p>
        </article>
      </section>

      <section className="mt-4">
        <article className="premium-card overflow-hidden rounded-2xl">
          <div className="border-b border-[var(--line)] p-5 sm:p-6">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 className="text-base font-semibold text-[var(--text)]">Factures</h3>
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-[var(--surface-soft)] px-3 py-1 text-xs font-semibold text-[var(--muted)]">
                  {visibleInvoices.length} facture{visibleInvoices.length > 1 ? "s" : ""}
                </span>
              </div>
            </div>
            <div className="mb-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <label className="text-xs font-semibold text-[var(--muted)]">
                Client
                <input
                  value={clientFilter}
                  onChange={(event) => setClientFilter(event.target.value)}
                  className="wf-input mt-1 h-10 w-full px-3 text-sm"
                  placeholder="Nom client"
                />
              </label>
              <label className="text-xs font-semibold text-[var(--muted)]">
                Date de
                <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="wf-input mt-1 h-10 w-full px-3 text-sm" />
              </label>
              <label className="text-xs font-semibold text-[var(--muted)]">
                Date à
                <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="wf-input mt-1 h-10 w-full px-3 text-sm" />
              </label>
              <div className="flex items-end">
                <button
                  type="button"
                  className="soft-focus rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-xs font-semibold text-[var(--text)] hover:bg-[var(--surface-soft)]"
                  onClick={() => {
                    setClientFilter("");
                    setDateFrom("");
                    setDateTo("");
                  }}
                >
                  Réinitialiser filtres
                </button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <TableToolbar
                search={tableControls.search}
                onSearchChange={tableControls.setSearch}
                searchPlaceholder="Recherche n°, commande, client..."
                filters={tableControls.filterDefinitions}
                onFilterChange={tableControls.setFilterValue}
                sortOrder={tableControls.sortOrder}
                onSortOrderChange={tableControls.setSortOrder}
                sortAscLabel="Date asc"
                sortDescLabel="Date desc"
                rightActions={
                  <div className="flex items-center gap-2">
                    <select
                      value={invoicePageSize}
                      onChange={(event) => setInvoicePageSize(Number(event.target.value))}
                      className="wf-input h-9 w-[96px] px-2 text-xs"
                    >
                      <option value={10}>10 / page</option>
                      <option value={20}>20 / page</option>
                      <option value={50}>50 / page</option>
                    </select>
                    <button
                      type="button"
                      className="soft-focus rounded-xl border border-[#B9CCE9] bg-[#F5F9FF] px-3 py-2 text-xs font-semibold text-[#1F5EA8] hover:bg-[#EAF2FF]"
                      onClick={() => exportRowsToCsv({ filename: "factures", title: "Factures", columns: invoiceExportColumns, rows: visibleInvoices })}
                    >
                      Export CSV
                    </button>
                    <button
                      type="button"
                      className="soft-focus rounded-xl border border-[#B9CCE9] bg-[#F5F9FF] px-3 py-2 text-xs font-semibold text-[#1F5EA8] hover:bg-[#EAF2FF]"
                      onClick={() => exportRowsToExcel({ filename: "factures", title: "Factures", columns: invoiceExportColumns, rows: visibleInvoices })}
                    >
                      Export Excel
                    </button>
                  </div>
                }
              />
            </div>
          </div>
          <div className="max-h-[640px] overflow-auto">
            {visibleInvoices.length === 0 ? (
              <p className="px-4 py-5 text-sm text-[var(--muted)]">Aucune facture generee pour l&apos;instant.</p>
            ) : (
              <table className="wf-table w-full text-left text-sm">
                <thead className="sticky top-0 z-10 bg-white">
                  <tr>
                    <th className="px-4 py-3 whitespace-nowrap">Facture</th>
                    <th className="px-4 py-3">Client</th>
                    <th className="px-4 py-3 whitespace-nowrap">Commande</th>
                    <th className="px-4 py-3 whitespace-nowrap">Date émission</th>
                    <th className="px-4 py-3 whitespace-nowrap">Échéance</th>
                    <th className="px-4 py-3 whitespace-nowrap">Statut</th>
                    <th className="px-4 py-3 whitespace-nowrap text-right">Total TTC</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedInvoices.map((invoice) => {
                    const active = selected?.id === invoice.id;
                    return (
                      <tr key={invoice.id} className={`${active ? "bg-[var(--surface-soft)]" : ""} hover:bg-[var(--surface-soft)]`}>
                        <td className="px-4 py-3 whitespace-nowrap font-semibold text-[var(--text)]">{invoice.invoice_number}</td>
                        <td className="px-4 py-3 text-[var(--text)]">{invoice.customer_name}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-[var(--muted)]">{invoice.order_number}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-[var(--muted)]">{fmtDate(invoice.issue_date)}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-[var(--muted)]">{invoice.due_date ? fmtDate(invoice.due_date) : "-"}</td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusPill(invoice.status)}`}>
                            {invoice.status === "paid" ? "Payee" : "En attente"}
                          </span>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-right font-semibold text-[var(--success)]">{money(invoice.total_amount_fcfa)} FCFA</td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap items-center justify-end gap-2">
                            <button
                              type="button"
                              className="soft-focus rounded-lg border border-[var(--line)] px-2.5 py-1 text-xs font-semibold text-[var(--text)] whitespace-nowrap hover:bg-[var(--surface-soft)]"
                              onClick={() => {
                                setSelectedId(invoice.id);
                                setPreviewOpen(true);
                              }}
                            >
                              Voir aperçu
                            </button>
                            <button
                              type="button"
                              className="soft-focus rounded-lg border border-[#A7C3F0] bg-[#EEF5FF] px-2.5 py-1 text-xs font-semibold text-[#1F5EA8] whitespace-nowrap hover:bg-[#E4EEFF]"
                              onClick={() => {
                                setSelectedId(invoice.id);
                                setEditorOpen(true);
                              }}
                            >
                              Modifier avant export
                            </button>
                            <button
                              type="button"
                              className="soft-focus rounded-lg bg-[var(--primary)] px-2.5 py-1 text-xs font-semibold text-white whitespace-nowrap hover:bg-[var(--primary-hover)]"
                              onClick={() => {
                                const rowDraft = selected?.id === invoice.id && draft ? draft : buildInvoiceDraft(invoice);
                                exportInvoicePdf(invoice, rowDraft, user?.full_name ?? "Manager cooperative");
                              }}
                            >
                              Exporter PDF
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          {visibleInvoices.length > 0 ? (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--line)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">
                {Math.min((invoicePage - 1) * invoicePageSize + 1, visibleInvoices.length)}–
                {Math.min(invoicePage * invoicePageSize, visibleInvoices.length)} sur {visibleInvoices.length}
              </p>
              <div className="flex items-center gap-2">
                <button type="button" className="soft-focus rounded-xl border border-[var(--line)] px-3 py-1.5 text-xs font-semibold disabled:opacity-50" disabled={invoicePage <= 1} onClick={() => setInvoicePage((prev) => Math.max(1, prev - 1))}>Précédent</button>
                <span className="text-xs text-[var(--muted)]">{invoicePage}/{invoiceTotalPages}</span>
                <button type="button" className="soft-focus rounded-xl border border-[var(--line)] px-3 py-1.5 text-xs font-semibold disabled:opacity-50" disabled={invoicePage >= invoiceTotalPages} onClick={() => setInvoicePage((prev) => Math.min(invoiceTotalPages, prev + 1))}>Suivant</button>
              </div>
            </div>
          ) : null}
        </article>
      </section>

      <LiquidGlassModal
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        title="Aperçu de la facture"
        subtitle={selected ? `Facture ${selected.invoice_number}` : "Aucune facture sélectionnée"}
        size="xl"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={() => setPreviewOpen(false)}>
              Fermer
            </button>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="soft-focus rounded-xl border border-[#A7C3F0] bg-[#EEF5FF] px-3 py-2 text-sm font-semibold text-[#1F5EA8] hover:bg-[#E4EEFF]"
                onClick={() => {
                  setPreviewOpen(false);
                  setEditorOpen(true);
                }}
                disabled={!selected || !draft}
              >
                Modifier avant export
              </button>
              <button
                type="button"
                className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold"
                disabled={!selected || !draft}
                onClick={() => {
                  if (!selected || !draft) return;
                  exportInvoicePdf(selected, draft, user?.full_name ?? "Manager cooperative");
                }}
              >
                Exporter la facture PDF
              </button>
            </div>
          </div>
        }
      >
        {!selected ? (
          <p className="text-sm text-[var(--muted)]">Sélectionnez une facture pour afficher l&apos;aperçu.</p>
        ) : (
          <div className="rounded-2xl border border-[var(--line)] bg-white p-5 sm:p-6">
            <div className="grid gap-4 sm:grid-cols-[1.3fr_1fr]">
              <div>
                <p className="text-xs uppercase tracking-[0.12em] text-[var(--primary)]">Emetteur</p>
                <h3 className="mt-1 text-2xl font-semibold text-[var(--text)]">{draft?.issuerName ?? COOPERATIVE_PROFILE.name}</h3>
                <p className="mt-2 text-sm text-[var(--muted)]">{draft?.issuerAddress ?? COOPERATIVE_PROFILE.address}</p>
                <p className="text-sm text-[var(--muted)]">{draft?.issuerPhone ?? COOPERATIVE_PROFILE.phone}</p>
                <p className="text-sm text-[var(--muted)]">{draft?.issuerEmail ?? COOPERATIVE_PROFILE.email}</p>
                <p className="mt-1 text-xs text-[var(--muted)]">{draft?.issuerLegalId ?? COOPERATIVE_PROFILE.legalId}</p>
              </div>
              <div className="sm:text-right">
                <p className="text-sm font-semibold text-[var(--primary)]">FACTURE</p>
                <p className="text-3xl font-semibold text-[var(--text)]">{selected.invoice_number}</p>
                <p className="text-sm text-[var(--muted)]">Commande {selected.order_number}</p>
                <p className="text-xs text-[var(--muted)]">Emission {fmtDate(selected.issue_date)}</p>
                <p className="text-xs text-[var(--muted)]">Echeance {draft?.dueDate ? fmtDate(draft.dueDate) : "-"}</p>
                <p className={`mt-2 inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusPill(selected.status)}`}>
                  {selected.status === "paid" ? "Payee" : "En attente"}
                </p>
              </div>
            </div>

            <div className="mt-5 grid gap-4 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-4 sm:grid-cols-2">
              <div>
                <p className="text-xs uppercase tracking-[0.1em] text-[var(--muted)]">Facture a</p>
                <p className="mt-1 text-base font-semibold text-[var(--text)]">{selected.customer_name}</p>
                <p className="text-sm text-[var(--muted)]">{selected.customer_phone ?? "-"}</p>
                <p className="text-sm text-[var(--muted)]">{draft?.clientEmail || "-"}</p>
                <p className="text-sm text-[var(--muted)]">{draft?.clientAddress || "-"}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.1em] text-[var(--muted)]">Reference cooperative</p>
                <p className="mt-1 text-sm text-[var(--muted)]">ID coop: {selected.cooperative_id}</p>
                <p className="text-sm text-[var(--muted)]">Prepare par: {user?.full_name ?? "Manager cooperative"}</p>
                <p className="text-sm text-[var(--muted)]">Date export: {fmtDate(new Date().toISOString())}</p>
                {draft?.paymentTerms ? <p className="text-sm text-[var(--muted)]">Conditions: {draft.paymentTerms}</p> : null}
              </div>
            </div>

            <div className="mt-5 overflow-hidden rounded-xl border border-[var(--line)]">
              <table className="wf-table min-w-full text-left text-sm">
                <thead>
                  <tr>
                    <th className="px-4 py-3">Description</th>
                    <th className="px-4 py-3">Unite</th>
                    <th className="px-4 py-3">Qte</th>
                    <th className="px-4 py-3">P.U. (FCFA)</th>
                    <th className="px-4 py-3">Total (FCFA)</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.lines.map((line) => (
                    <tr key={line.id}>
                      <td className="px-4 py-3">{line.description}</td>
                      <td className="px-4 py-3">{line.unit}</td>
                      <td className="px-4 py-3">{line.quantity}</td>
                      <td className="px-4 py-3">{money(line.unit_price_fcfa)}</td>
                      <td className="px-4 py-3 font-semibold">{money(line.line_total_fcfa)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-5 ml-auto grid max-w-[360px] gap-2 text-sm">
              <div className="flex items-center justify-between border-b border-[var(--line)] pb-2">
                <span className="text-[var(--muted)]">Sous-total HT</span>
                <span className="font-semibold text-[var(--text)]">{money(selected.subtotal_fcfa)} FCFA</span>
              </div>
              <div className="flex items-center justify-between border-b border-[var(--line)] pb-2">
                <span className="text-[var(--muted)]">TVA {(selected.tax_rate * 100).toFixed(0)}%</span>
                <span className="font-semibold text-[var(--text)]">{money(selected.tax_amount_fcfa)} FCFA</span>
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="text-lg font-semibold text-[var(--text)]">TOTAL TTC</span>
                <span className="text-2xl font-semibold text-[var(--primary)]">{money(selected.total_amount_fcfa)} FCFA</span>
              </div>
            </div>

            <p className="mt-5 text-xs text-[var(--muted)]">
              {draft?.notes ? `${draft.notes} · ` : ""}Merci pour votre confiance. Cette facture est generee par {draft?.issuerName ?? COOPERATIVE_PROFILE.name}.
            </p>
          </div>
        )}
      </LiquidGlassModal>

      <LiquidGlassModal
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        title="Préparer la facture"
        subtitle={selected ? `Facture ${selected.invoice_number}` : "Aucune facture sélectionnée"}
        size="lg"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={() => setEditorOpen(false)}>
              Fermer
            </button>
            <button
              type="button"
              className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold"
              disabled={!selected || !draft}
              onClick={() => {
                if (!selected || !draft) return;
                exportInvoicePdf(selected, draft, user?.full_name ?? "Manager cooperative");
              }}
            >
              Exporter la facture PDF
            </button>
          </div>
        }
      >
        {!selected || !draft ? (
          <p className="text-sm text-[var(--muted)]">Sélectionnez une facture pour préparer l&apos;export.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Client email
              <input value={draft.clientEmail} onChange={(event) => setDraft((prev) => (prev ? { ...prev, clientEmail: event.target.value } : prev))} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--text)]">
              Echeance
              <input type="date" value={draft.dueDate || ""} onChange={(event) => setDraft((prev) => (prev ? { ...prev, dueDate: event.target.value } : prev))} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--text)] sm:col-span-2">
              Client adresse
              <input value={draft.clientAddress} onChange={(event) => setDraft((prev) => (prev ? { ...prev, clientAddress: event.target.value } : prev))} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--text)] sm:col-span-2">
              Notes / détails de facture
              <textarea value={draft.notes} onChange={(event) => setDraft((prev) => (prev ? { ...prev, notes: event.target.value } : prev))} className="wf-input mt-2 min-h-[84px] w-full px-3 py-2 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--text)] sm:col-span-2">
              Conditions de paiement
              <input value={draft.paymentTerms} onChange={(event) => setDraft((prev) => (prev ? { ...prev, paymentTerms: event.target.value } : prev))} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--text)]">
              Emetteur
              <input value={draft.issuerName} onChange={(event) => setDraft((prev) => (prev ? { ...prev, issuerName: event.target.value } : prev))} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--text)]">
              ID légal
              <input value={draft.issuerLegalId} onChange={(event) => setDraft((prev) => (prev ? { ...prev, issuerLegalId: event.target.value } : prev))} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--text)] sm:col-span-2">
              Adresse émetteur
              <input value={draft.issuerAddress} onChange={(event) => setDraft((prev) => (prev ? { ...prev, issuerAddress: event.target.value } : prev))} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--text)]">
              Téléphone émetteur
              <input value={draft.issuerPhone} onChange={(event) => setDraft((prev) => (prev ? { ...prev, issuerPhone: event.target.value } : prev))} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
            </label>
            <label className="block text-sm font-medium text-[var(--text)]">
              Email émetteur
              <input value={draft.issuerEmail} onChange={(event) => setDraft((prev) => (prev ? { ...prev, issuerEmail: event.target.value } : prev))} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
            </label>
          </div>
        )}
      </LiquidGlassModal>
    </main>
  );
}
