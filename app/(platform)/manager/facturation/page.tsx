"use client";

import { useMemo, useRef, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { ExportActions } from "@/components/ui/table/ExportActions";
import { TableToolbar } from "@/components/ui/table/TableToolbar";
import { useAuth } from "@/context/auth/AuthContext";
import { useCommercialInvoiceStats, useCommercialInvoices } from "@/hooks/useCommercial";
import { exportRowsToCsv, exportRowsToExcel, exportRowsToPdf, type ExportColumn } from "@/lib/export/client";
import { useTableControls } from "@/lib/table/useTableControls";
import type { CommercialInvoice } from "@/lib/api/types";

const COOPERATIVE_PROFILE = {
  name: "Cooperative Deggo Thies",
  legalId: "NINEA SN-DTG-2026-0198",
  address: "Route de Mbour, Thies, Senegal",
  phone: "+221 33 812 45 67",
  email: "facturation@deggo-thies.sn",
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

export default function FacturationPage() {
  const { user } = useAuth();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: stats } = useCommercialInvoiceStats();
  const { data: invoices = [] } = useCommercialInvoices();
  const invoiceRef = useRef<HTMLDivElement>(null);
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
  }, [invoices, tableControls.filters.status, tableControls.search, tableControls.sortOrder]);

  const selected = useMemo(() => {
    if (!visibleInvoices.length) return null;
    if (!selectedId) return visibleInvoices[0];
    return visibleInvoices.find((invoice) => invoice.id === selectedId) ?? visibleInvoices[0];
  }, [selectedId, visibleInvoices]);

  const invoiceExportColumns: ExportColumn<CommercialInvoice>[] = [
    { key: "invoice_number", header: "Facture" },
    { key: "order_number", header: "Commande" },
    { key: "customer_name", header: "Client" },
    { key: "issue_date", header: "Date emission", format: (_, row) => fmtDate(row.issue_date) },
    { key: "due_date", header: "Echeance", format: (_, row) => (row.due_date ? fmtDate(row.due_date) : "-") },
    { key: "total_amount_fcfa", header: "Total TTC (FCFA)", format: (_, row) => row.total_amount_fcfa.toLocaleString("fr-FR") },
    { key: "status", header: "Statut", format: (_, row) => (row.status === "paid" ? "Payee" : "En attente") },
  ];

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

      <section className="mt-4 grid gap-4 xl:grid-cols-[0.9fr_1.6fr]">
        <article className="premium-card overflow-hidden rounded-2xl">
          <div className="border-b border-[var(--line)] p-5 sm:p-6">
            <h3 className="mb-3 text-base font-semibold text-[var(--text)]">Factures</h3>
            <div className="overflow-x-auto">
              <div className="min-w-[780px]">
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
                    <ExportActions
                      onCsv={() => exportRowsToCsv({ filename: "factures", title: "Factures", columns: invoiceExportColumns, rows: visibleInvoices })}
                      onExcel={() => exportRowsToExcel({ filename: "factures", title: "Factures", columns: invoiceExportColumns, rows: visibleInvoices })}
                      onPdf={() => exportRowsToPdf({ filename: "factures", title: "Factures", columns: invoiceExportColumns, rows: visibleInvoices })}
                    />
                  }
                />
              </div>
            </div>
          </div>
          <div className="max-h-[640px] overflow-y-auto">
            {visibleInvoices.length === 0 ? (
              <p className="px-4 py-5 text-sm text-[var(--muted)]">Aucune facture generee pour l&apos;instant.</p>
            ) : (
              visibleInvoices.map((invoice) => {
                const active = selected?.id === invoice.id;
                return (
                  <button
                    key={invoice.id}
                    type="button"
                    onClick={() => setSelectedId(invoice.id)}
                    className={`w-full border-b border-[var(--line)] px-4 py-3 text-left transition-colors ${active ? "bg-[var(--surface-soft)]" : "hover:bg-[var(--surface-soft)]"}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold text-[var(--text)]">{invoice.invoice_number}</p>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusPill(invoice.status)}`}>
                        {invoice.status === "paid" ? "Payee" : "En attente"}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-[var(--text)]">{invoice.customer_name}</p>
                    <p className="mt-0.5 text-xs text-[var(--muted)]">{invoice.order_number} · {fmtDate(invoice.issue_date)}</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--success)]">{money(invoice.total_amount_fcfa)} FCFA</p>
                  </button>
                );
              })
            )}
          </div>
        </article>

        <article className="premium-card rounded-2xl p-6">
          {!selected ? (
            <p className="text-sm text-[var(--muted)]">Selectionnez une facture.</p>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-end gap-2 print:hidden">
                <ExportActions
                  onCsv={() => exportRowsToCsv({ filename: selected.invoice_number, title: `Facture ${selected.invoice_number}`, columns: invoiceExportColumns, rows: [selected] })}
                  onExcel={() => exportRowsToExcel({ filename: selected.invoice_number, title: `Facture ${selected.invoice_number}`, columns: invoiceExportColumns, rows: [selected] })}
                  onPdf={() => exportRowsToPdf({ filename: selected.invoice_number, title: `Facture ${selected.invoice_number}`, columns: invoiceExportColumns, rows: [selected] })}
                />
              </div>

              <div ref={invoiceRef} className="rounded-2xl border border-[var(--line)] bg-white p-5 sm:p-6">
                <div className="grid gap-4 sm:grid-cols-[1.3fr_1fr]">
                  <div>
                    <p className="text-xs uppercase tracking-[0.12em] text-[var(--primary)]">Emetteur</p>
                    <h3 className="mt-1 text-2xl font-semibold text-[var(--text)]">{COOPERATIVE_PROFILE.name}</h3>
                    <p className="mt-2 text-sm text-[var(--muted)]">{COOPERATIVE_PROFILE.address}</p>
                    <p className="text-sm text-[var(--muted)]">{COOPERATIVE_PROFILE.phone}</p>
                    <p className="text-sm text-[var(--muted)]">{COOPERATIVE_PROFILE.email}</p>
                    <p className="mt-1 text-xs text-[var(--muted)]">{COOPERATIVE_PROFILE.legalId}</p>
                  </div>
                  <div className="sm:text-right">
                    <p className="text-sm font-semibold text-[var(--primary)]">FACTURE</p>
                    <p className="text-3xl font-semibold text-[var(--text)]">{selected.invoice_number}</p>
                    <p className="text-sm text-[var(--muted)]">Commande {selected.order_number}</p>
                    <p className="text-xs text-[var(--muted)]">Emission {fmtDate(selected.issue_date)}</p>
                    <p className="text-xs text-[var(--muted)]">Echeance {selected.due_date ? fmtDate(selected.due_date) : "-"}</p>
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
                    <p className="text-sm text-[var(--muted)]">{selected.customer_email ?? "-"}</p>
                    <p className="text-sm text-[var(--muted)]">{selected.customer_address ?? "-"}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.1em] text-[var(--muted)]">Reference cooperative</p>
                    <p className="mt-1 text-sm text-[var(--muted)]">ID coop: {selected.cooperative_id}</p>
                    <p className="text-sm text-[var(--muted)]">Prepare par: {user?.full_name ?? "Manager cooperative"}</p>
                    <p className="text-sm text-[var(--muted)]">Date export: {fmtDate(new Date().toISOString())}</p>
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
                  Merci pour votre confiance. Cette facture est generee par {COOPERATIVE_PROFILE.name}.
                </p>
              </div>
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
