"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { ConfirmActionModal } from "@/components/ui/ConfirmActionModal";
import { ContentAreaLoader } from "@/components/ui/ContentAreaLoader";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { ExportActions } from "@/components/ui/table/ExportActions";
import { TableToolbar } from "@/components/ui/table/TableToolbar";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { exportRowsToCsv, exportRowsToExcel, exportRowsToPdf, type ExportColumn } from "@/lib/export/client";
import { useTableControls } from "@/lib/table/useTableControls";
import { useBatches } from "@/hooks/useBatches";
import {
  useCancelTreasuryTransaction,
  useCreateTreasuryTransaction,
  useTreasuryStats,
  useTreasuryTransactions,
  useUploadTreasuryJustificatif,
  useUpdateTreasuryTransaction,
} from "@/hooks/useTreasury";
import type {
  TreasuryTransactionStatus,
  TreasuryTransaction,
  TreasuryTransactionCreate,
  TreasuryTransactionType,
} from "@/lib/api/types";

type FilterType = "all" | "income" | "expense";

type TreasuryFormValues = {
  transaction_date: string;
  type: TreasuryTransactionType;
  category: string;
  label: string;
  amount_fcfa: number;
  note: string;
  status: TreasuryTransactionStatus;
  receipt_reference: string;
  source_type: string;
};

type ExportTreasuryRow = {
  reference: string;
  date: string;
  type: string;
  category_source: string;
  label_description: string;
  amount: string;
  status: string;
  related_entity: string;
  note: string;
  justificatif: string;
};

const typeBadge: Record<TreasuryTransactionType, { label: string; tone: "success" | "danger" }> = {
  income: { label: "Recette", tone: "success" },
  expense: { label: "Dépense", tone: "danger" },
};

const statusBadge: Record<string, { label: string; tone: "success" | "danger" | "info" }> = {
  non_enregistre: { label: "Non enregistré", tone: "info" },
  enregistre_sans_justificatif: { label: "Enregistré sans justificatif", tone: "info" },
  enregistre_complet: { label: "Enregistré complet", tone: "success" },
  cancelled: { label: "Annulé", tone: "danger" },
};

function formatAmount(value: number) {
  return `${value.toLocaleString("fr-FR")} FCFA`;
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("fr-FR");
}

function sourceLabel(sourceType: string) {
  if (sourceType === "farmer_advance") return "Avance producteur";
  if (sourceType === "management") return "Gestion";
  if (sourceType === "manual") return "Manuel";
  if (sourceType === "commercial_invoice") return "Facture commerciale";
  return "Manuel / autre";
}

function treasuryExportColumns(): ExportColumn<ExportTreasuryRow>[] {
  return [
    { key: "reference", header: "Référence" },
    { key: "date", header: "Date" },
    { key: "type", header: "Type" },
    { key: "category_source", header: "Catégorie / source" },
    { key: "label_description", header: "Libellé / description" },
    { key: "amount", header: "Montant" },
    { key: "status", header: "Statut" },
    { key: "related_entity", header: "Entité liée" },
    { key: "note", header: "Note" },
    { key: "justificatif", header: "Justificatif" },
  ];
}

function mapTransactionsForExport(transactions: TreasuryTransaction[]): ExportTreasuryRow[] {
  return transactions.map((transaction) => ({
    reference: transaction.reference,
    date: formatDate(transaction.transaction_date),
    type: typeBadge[transaction.type]?.label ?? transaction.type,
    category_source: `${transaction.category} / ${sourceLabel(transaction.source_type)}`,
    label_description: transaction.label,
    amount: formatAmount(transaction.amount_fcfa),
    status: statusBadge[transaction.status]?.label ?? transaction.status,
    related_entity: transaction.farmer_name || transaction.source_id || "—",
    note: transaction.note?.trim() || "—",
    justificatif: transaction.justificatif_file
      ? `Fichier: ${transaction.justificatif_file.filename}`
      : transaction.justificatif_status,
  }));
}

export default function TreasuryPage() {
  const [formOpen, setFormOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<TreasuryTransaction | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [pendingCancelTransaction, setPendingCancelTransaction] = useState<TreasuryTransaction | null>(null);
  const [pendingCompleteTransaction, setPendingCompleteTransaction] = useState<TreasuryTransaction | null>(null);
  const [uploadingTransactionId, setUploadingTransactionId] = useState<string | null>(null);

  const tableControls = useTableControls([
    {
      key: "type",
      label: "Type",
      options: [
        { value: "all", label: "Tous types" },
        { value: "income", label: "Recette" },
        { value: "expense", label: "Dépense" },
      ],
      initialValue: "all",
    },
    {
      key: "source_type",
      label: "Source",
      options: [
        { value: "all", label: "Toutes sources" },
        { value: "farmer_advance", label: "Avance producteur" },
        { value: "management", label: "Gestion" },
        { value: "manual", label: "Manuel / autre" },
      ],
      initialValue: "all",
    },
  ]);

  const transactionsQuery = useTreasuryTransactions({
    type: tableControls.filters.type as FilterType,
    source_type: tableControls.filters.source_type,
    search: tableControls.search,
    sort: tableControls.sortOrder,
  });
  const statsQuery = useTreasuryStats();
  const batchesQuery = useBatches();
  const requiredLoading = statsQuery.isLoading || batchesQuery.isLoading;
  const requiredError = statsQuery.isError || batchesQuery.isError;

  const createTransaction = useCreateTreasuryTransaction();
  const updateTransaction = useUpdateTreasuryTransaction();
  const cancelTransaction = useCancelTreasuryTransaction();
  const uploadJustificatif = useUploadTreasuryJustificatif();

  const { register, handleSubmit, reset, formState } = useForm<TreasuryFormValues>({
    defaultValues: {
      transaction_date: "",
      type: "expense",
      category: "autre",
      label: "",
      amount_fcfa: 0,
      note: "",
      status: "non_enregistre",
      receipt_reference: "",
      source_type: "manual",
    },
  });

  const transactions = useMemo(() => transactionsQuery.data ?? [], [transactionsQuery.data]);
  const stats = statsQuery.data;
  const totalEstimatedCharges = useMemo(
    () =>
      (batchesQuery.data ?? []).reduce(
        (sum, batch) => sum + Number(batch.estimated_charge_fcfa ?? 0),
        0,
      ),
    [batchesQuery.data],
  );

  const exportRows = useMemo(() => mapTransactionsForExport(transactions), [transactions]);
  const exportColumns = useMemo(() => treasuryExportColumns(), []);

  const openCreateForm = () => {
    setEditingTransaction(null);
    reset({
      transaction_date: "",
      type: "expense",
      category: "autre",
      label: "",
      amount_fcfa: 0,
      note: "",
      status: "non_enregistre",
      receipt_reference: "",
      source_type: "manual",
    });
    setFormError(null);
    setFormOpen(true);
  };

  const openEditForm = (transaction: TreasuryTransaction) => {
    setEditingTransaction(transaction);
    reset({
      transaction_date: transaction.transaction_date,
      type: transaction.type,
      category: transaction.category,
      label: transaction.label,
      amount_fcfa: transaction.amount_fcfa,
      note: transaction.note ?? "",
      status: transaction.status,
      receipt_reference: transaction.receipt_reference ?? "",
      source_type: transaction.source_type || "manual",
    });
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setFormError(null);
  };

  const submitTransaction = handleSubmit(async (values) => {
    setFormError(null);
    const payload: TreasuryTransactionCreate = {
      transaction_date: values.transaction_date,
      type: values.type,
      category: values.category.trim(),
      label: values.label.trim(),
      amount_fcfa: Number(values.amount_fcfa),
      note: values.note.trim() || null,
      status: values.status,
      receipt_reference: values.receipt_reference.trim() || null,
      source_type: values.source_type,
    };

    try {
      if (editingTransaction) {
        await updateTransaction.mutateAsync({ id: editingTransaction.id, payload });
      } else {
        await createTransaction.mutateAsync(payload);
      }
      closeForm();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer la transaction.");
    }
  });

  const handleUploadJustificatif = async (transaction: TreasuryTransaction, file: File | null) => {
    if (!file) return;
    setFormError(null);
    setUploadingTransactionId(transaction.id);
    try {
      await uploadJustificatif.mutateAsync({ id: transaction.id, file });
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'uploader le justificatif.");
    } finally {
      setUploadingTransactionId(null);
    }
  };

  const handleConfirmCancel = async () => {
    if (!pendingCancelTransaction || pendingCancelTransaction.status === "cancelled") {
      setPendingCancelTransaction(null);
      return;
    }
    try {
      await cancelTransaction.mutateAsync(pendingCancelTransaction.id);
      setPendingCancelTransaction(null);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'annuler cette transaction.");
    }
  };

  const handleConfirmComplete = async () => {
    if (!pendingCompleteTransaction) return;
    try {
      await updateTransaction.mutateAsync({
        id: pendingCompleteTransaction.id,
        payload: { status: "enregistre_complet" },
      });
      setPendingCompleteTransaction(null);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de marquer complet.");
    }
  };

  const runExport = (kind: "csv" | "excel" | "pdf") => {
    const options = {
      filename: `tresorerie-${new Date().toISOString().slice(0, 10)}`,
      title: "Rapport de trésorerie",
      columns: exportColumns,
      rows: exportRows,
      generatedAt: new Date(),
    };

    if (kind === "csv") {
      exportRowsToCsv(options);
      return;
    }
    if (kind === "excel") {
      exportRowsToExcel(options);
      return;
    }
    exportRowsToPdf(options);
  };

  if (requiredLoading) {
    return (
      <main className="relative min-h-[60vh]">
        <PageIntro title="Trésorerie" />
        <ContentAreaLoader
          title="Chargement Trésorerie"
          subtitle="Synchronisation des transactions, statistiques et lots..."
        />
      </main>
    );
  }

  if (requiredError) {
    return (
      <main>
        <PageIntro title="Trésorerie" />
        <section className="premium-card reveal mt-4 rounded-2xl p-4">
          <p className="text-sm text-[var(--danger)]">Impossible de charger les données requises de la page Trésorerie.</p>
        </section>
      </main>
    );
  }

  return (
    <main>
      <PageIntro title="Trésorerie" />

      <section className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Total donné</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{formatAmount(stats?.total_given ?? 0)}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Total dépenses</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{formatAmount(stats?.total_expenses ?? 0)}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "60ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Total recettes</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{formatAmount(stats?.total_income ?? 0)}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "80ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Solde actuel</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{formatAmount(stats?.current_balance ?? 0)}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "100ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Charges estimées lots</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{formatAmount(totalEstimatedCharges)}</p>
        </article>
      </section>

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <TableToolbar
          search={tableControls.search}
          onSearchChange={tableControls.setSearch}
          searchPlaceholder="Rechercher libellé ou producteur..."
          filters={tableControls.filterDefinitions}
          onFilterChange={tableControls.setFilterValue}
          sortOrder={tableControls.sortOrder}
          onSortOrderChange={tableControls.setSortOrder}
          sortAscLabel="Date asc"
          sortDescLabel="Date desc"
          rightActions={
            <>
              <button type="button" onClick={openCreateForm} className="soft-focus wf-btn-primary px-4 py-2.5 text-sm font-semibold">
                + Nouvelle transaction
              </button>
              <ExportActions onCsv={() => runExport("csv")} onExcel={() => runExport("excel")} onPdf={() => runExport("pdf")} />
            </>
          }
        />
      </section>

      {transactionsQuery.isLoading ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Chargement de la trésorerie...</p>
        </section>
      ) : transactionsQuery.error ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--danger)]">{transactionsQuery.error instanceof Error ? transactionsQuery.error.message : "Erreur de chargement."}</p>
          <button type="button" className="soft-focus wf-btn-secondary mt-3 px-4 py-2 text-sm font-semibold" onClick={() => transactionsQuery.refetch()}>
            Réessayer
          </button>
        </section>
      ) : transactions.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucune transaction enregistrée pour le moment.</p>
          <button type="button" className="soft-focus wf-btn-primary mt-3 px-4 py-2 text-sm font-semibold" onClick={openCreateForm}>
            + Nouvelle transaction
          </button>
        </section>
      ) : (
        <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "90ms" }}>
          <div className="thin-scrollbar overflow-x-auto">
            <table className="wf-table min-w-full text-left text-sm">
              <thead>
	                <tr>
                  <th className="px-5 py-3.5">Référence</th>
                  <th className="px-5 py-3.5">Date</th>
                  <th className="px-5 py-3.5">Type</th>
                  <th className="px-5 py-3.5">Catégorie</th>
                  <th className="px-5 py-3.5">Libellé</th>
                  <th className="px-5 py-3.5">Montant</th>
	                  <th className="px-5 py-3.5">Source</th>
	                  <th className="px-5 py-3.5">Statut</th>
	                  <th className="px-5 py-3.5">Justificatif</th>
	                  <th className="px-5 py-3.5">Actions</th>
	                </tr>
              </thead>
              <tbody>
                {transactions.map((transaction) => {
                  const type = typeBadge[transaction.type] ?? { label: transaction.type, tone: "danger" as const };
                  const status = statusBadge[transaction.status] ?? { label: transaction.status, tone: "info" as const };
	                  const isFarmerAdvance = transaction.source_type === "farmer_advance";
	                  const canEditOrCancel = !isFarmerAdvance && !transaction.is_locked && transaction.status !== "cancelled";

                  return (
                    <tr key={transaction.id}>
                      <td className="px-5 py-4 font-medium text-[var(--text)]">{transaction.reference}</td>
                      <td className="px-5 py-4">{formatDate(transaction.transaction_date)}</td>
                      <td className="px-5 py-4">
                        <StatusBadge label={type.label} tone={type.tone} />
                      </td>
                      <td className="px-5 py-4">{transaction.category}</td>
                      <td className="px-5 py-4">
                        <p>{transaction.label}</p>
                        {transaction.farmer_name ? <p className="text-xs text-[var(--muted)]">{transaction.farmer_name}</p> : null}
                      </td>
                      <td className="px-5 py-4">{formatAmount(transaction.amount_fcfa)}</td>
                      <td className="px-5 py-4">{sourceLabel(transaction.source_type)}</td>
	                      <td className="px-5 py-4">
	                        <StatusBadge label={status.label} tone={status.tone} />
	                      </td>
	                      <td className="px-5 py-4 text-xs">
	                        {transaction.justificatif_file ? (
	                          <a className="font-semibold text-[var(--primary)] hover:underline" href={transaction.justificatif_file.file_url} target="_blank" rel="noreferrer">
	                            {transaction.justificatif_file.filename}
	                          </a>
	                        ) : (
	                          <span className="text-[var(--muted)]">{transaction.justificatif_status}</span>
	                        )}
	                      </td>
	                      <td className="px-5 py-4">
	                        {isFarmerAdvance ? (
	                          <span className="text-xs text-[var(--muted)]">Géré via avances</span>
	                        ) : (
	                          <div className="flex items-center gap-2 flex-wrap">
	                            <button className="text-xs font-semibold text-[var(--primary)] hover:underline disabled:opacity-40" onClick={() => openEditForm(transaction)} disabled={!canEditOrCancel}>
	                              Modifier
	                            </button>
	                            <button
	                              className="text-xs font-semibold text-[var(--danger)] hover:underline disabled:opacity-40"
	                              onClick={() => setPendingCancelTransaction(transaction)}
	                              disabled={!canEditOrCancel || cancelTransaction.isPending}
	                            >
	                              Annuler
	                            </button>
	                            <label className={`text-xs font-semibold ${transaction.is_locked ? "text-[var(--muted)]" : "text-[var(--text)]"} ${transaction.is_locked ? "" : "cursor-pointer hover:underline"}`}>
	                              {uploadingTransactionId === transaction.id ? "Upload..." : "Uploader justificatif"}
	                              <input
	                                type="file"
	                                accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
	                                className="hidden"
	                                disabled={transaction.is_locked || uploadJustificatif.isPending}
	                                onChange={(event) => {
	                                  const file = event.target.files?.[0] ?? null;
	                                  void handleUploadJustificatif(transaction, file);
	                                  event.currentTarget.value = "";
	                                }}
	                              />
	                            </label>
	                            <button
	                              className="text-xs font-semibold text-[var(--success)] hover:underline disabled:opacity-40"
	                              onClick={() => setPendingCompleteTransaction(transaction)}
	                              disabled={transaction.is_locked || transaction.status === "cancelled" || updateTransaction.isPending}
	                            >
	                              Marquer complet
	                            </button>
	                          </div>
	                        )}
	                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <LiquidGlassModal
        open={formOpen}
        onClose={closeForm}
        title={editingTransaction ? "Modifier transaction" : "Nouvelle transaction"}
        subtitle="Transaction manuelle hors avances producteurs."
        size="md"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={closeForm}>
              Annuler
            </button>
            <button type="submit" form="treasury-form" className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        }
      >
        <form id="treasury-form" onSubmit={submitTransaction} className="space-y-3">
          <label className="block text-sm font-medium text-[var(--text)]">
            Date
            <input type="date" {...register("transaction_date", { required: "Date requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Type
              <select {...register("type", { required: "Type requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
                <option value="expense">Dépense</option>
                <option value="income">Recette</option>
              </select>
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Source
              <select {...register("source_type", { required: "Source requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
                <option value="manual">Manuel</option>
                <option value="management">Gestion</option>
                <option value="other">Autre</option>
              </select>
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Catégorie
              <select {...register("category", { required: "Catégorie requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
                <option value="gestion">gestion</option>
                <option value="administration">administration</option>
                <option value="transport">transport</option>
                <option value="operation">opération</option>
                <option value="autre">autre</option>
              </select>
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Montant (FCFA)
              <input
                type="number"
                step="0.01"
                min="0"
                {...register("amount_fcfa", { required: "Montant requis.", valueAsNumber: true, min: 0.01 })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                placeholder="25000"
              />
            </label>
          </div>

          <label className="block text-sm font-medium text-[var(--text)]">
            Libellé
            <input {...register("label", { required: "Libellé requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="Transport vers entrepôt" />
          </label>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Statut
              <select {...register("status", { required: "Statut requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
                <option value="non_enregistre">Non enregistré</option>
                <option value="enregistre_sans_justificatif">Enregistré sans justificatif</option>
                <option value="enregistre_complet">Enregistré complet</option>
              </select>
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Référence reçu/facture (optionnel)
              <input {...register("receipt_reference")} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="INV-2026-001" />
            </label>
          </div>

          <label className="block text-sm font-medium text-[var(--text)]">
            Note
            <textarea {...register("note")} className="wf-input mt-2 min-h-[96px] w-full px-3 py-2 text-sm" placeholder="Commentaire optionnel..." />
          </label>

          {formError && (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {formError}
            </p>
          )}
        </form>
      </LiquidGlassModal>

      <ConfirmActionModal
        open={Boolean(pendingCancelTransaction)}
        title="Annuler la transaction"
        message="Cette transaction passera au statut Annulé. Confirmez-vous l'action ?"
        confirmLabel="Oui, annuler"
        tone="danger"
        loading={cancelTransaction.isPending}
        onCancel={() => setPendingCancelTransaction(null)}
        onConfirm={() => {
          void handleConfirmCancel();
        }}
      />
      <ConfirmActionModal
        open={Boolean(pendingCompleteTransaction)}
        title="Marquer enregistrement complet"
        message="Cette action verrouille la transaction. Vérifiez qu'un justificatif ou une référence de reçu/facture est présent."
        confirmLabel="Oui, marquer complet"
        tone="primary"
        loading={updateTransaction.isPending}
        onCancel={() => setPendingCompleteTransaction(null)}
        onConfirm={() => {
          void handleConfirmComplete();
        }}
      />
    </main>
  );
}
