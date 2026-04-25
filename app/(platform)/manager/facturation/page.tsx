"use client";

import { useMemo, useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { useCommercialInvoiceStats, useCommercialInvoices } from "@/hooks/useCommercial";
import type { CommercialInvoice } from "@/lib/api/types";

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
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: stats } = useCommercialInvoiceStats();
  const { data: invoices = [] } = useCommercialInvoices();

  const selected = useMemo(() => {
    if (!invoices.length) return null;
    if (!selectedId) return invoices[0];
    return invoices.find((invoice) => invoice.id === selectedId) ?? invoices[0];
  }, [invoices, selectedId]);

  return (
    <main>
      <PageIntro title="Facturation" subtitle="Factures générées depuis les commandes livrées et suivi d'encaissement." />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="premium-card rounded-2xl p-5">
          <p className="text-xs text-[var(--muted)]">Total facturé</p>
          <p className="mt-2 text-4xl font-semibold text-[var(--text)]">{money(stats?.total_invoiced_fcfa ?? 0)}</p>
          <p className="text-xs text-[var(--muted)]">FCFA TTC</p>
        </article>
        <article className="premium-card rounded-2xl p-5">
          <p className="text-xs text-[var(--muted)]">Payées</p>
          <p className="mt-2 text-4xl font-semibold text-[var(--success)]">{money(stats?.paid_fcfa ?? 0)}</p>
          <p className="text-xs text-[var(--muted)]">FCFA encaissées</p>
        </article>
        <article className="premium-card rounded-2xl p-5">
          <p className="text-xs text-[var(--muted)]">En attente</p>
          <p className="mt-2 text-4xl font-semibold text-[#B67B00]">{money(stats?.pending_fcfa ?? 0)}</p>
          <p className="text-xs text-[var(--muted)]">FCFA à encaisser</p>
        </article>
        <article className="premium-card rounded-2xl p-5">
          <p className="text-xs text-[var(--muted)]">Recouvrement</p>
          <p className="mt-2 text-4xl font-semibold text-[#2673B7]">{(stats?.paid_rate_percent ?? 0).toFixed(1)}%</p>
          <p className="text-xs text-[var(--muted)]">Taux payé</p>
        </article>
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[0.9fr_1.6fr]">
        <article className="premium-card overflow-hidden rounded-2xl">
          <div className="border-b border-[var(--line)] px-4 py-3">
            <h3 className="text-sm font-semibold text-[var(--text)]">Factures</h3>
          </div>
          <div className="max-h-[640px] overflow-y-auto">
            {invoices.length === 0 ? (
              <p className="px-4 py-5 text-sm text-[var(--muted)]">Aucune facture générée pour l&apos;instant.</p>
            ) : (
              invoices.map((invoice) => {
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
                        {invoice.status === "paid" ? "Payée" : "En attente"}
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
            <p className="text-sm text-[var(--muted)]">Sélectionnez une facture.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.12em] text-[var(--muted)]">Facturé à</p>
                  <h3 className="mt-1 text-2xl font-semibold text-[var(--text)]">{selected.customer_name}</h3>
                  <p className="text-sm text-[var(--muted)]">{selected.customer_phone ?? "-"}</p>
                  <p className="text-sm text-[var(--muted)]">{selected.customer_email ?? "-"}</p>
                  <p className="text-sm text-[var(--muted)]">{selected.customer_address ?? "-"}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-[var(--primary)]">FACTURE</p>
                  <p className="text-3xl font-semibold text-[var(--text)]">{selected.invoice_number}</p>
                  <p className="text-sm text-[var(--muted)]">Commande {selected.order_number}</p>
                  <p className="text-xs text-[var(--muted)]">Émise le {fmtDate(selected.issue_date)}</p>
                  <p className="text-xs text-[var(--muted)]">Échéance {selected.due_date ? fmtDate(selected.due_date) : "-"}</p>
                </div>
              </div>

              <div className="mt-5 overflow-hidden rounded-xl border border-[var(--line)]">
                <table className="wf-table min-w-full text-left text-sm">
                  <thead>
                    <tr>
                      <th className="px-4 py-3">Description</th>
                      <th className="px-4 py-3">Qté</th>
                      <th className="px-4 py-3">P.U. (FCFA)</th>
                      <th className="px-4 py-3">Total (FCFA)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.lines.map((line) => (
                      <tr key={line.id}>
                        <td className="px-4 py-3">{line.description}</td>
                        <td className="px-4 py-3">{line.quantity} {line.unit}</td>
                        <td className="px-4 py-3">{money(line.unit_price_fcfa)}</td>
                        <td className="px-4 py-3 font-semibold">{money(line.line_total_fcfa)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-5 ml-auto grid max-w-[340px] gap-2 text-sm">
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
            </>
          )}
        </article>
      </section>
    </main>
  );
}
