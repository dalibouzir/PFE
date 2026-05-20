"use client";

import { useEffect, useMemo, useState } from "react";
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
  const [detailTransaction, setDetailTransaction] = useState<TreasuryTransaction | null>(null);
  const [uploadingTransactionId, setUploadingTransactionId] = useState<string | null>(null);
  const [selectedCreateJustificatif, setSelectedCreateJustificatif] = useState<File | null>(null);
  const [createUploadWarning, setCreateUploadWarning] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | TreasuryTransaction["status"]>("all");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

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
      source_type: "manual",
    },
  });

  const transactions = useMemo(() => transactionsQuery.data ?? [], [transactionsQuery.data]);
  const filteredTransactions = useMemo(() => {
    return transactions.filter((tx) => {
      const byStatus = statusFilter === "all" || tx.status === statusFilter;
      const byFrom = fromDate ? tx.transaction_date >= fromDate : true;
      const byTo = toDate ? tx.transaction_date <= toDate : true;
      return byStatus && byFrom && byTo;
    });
  }, [transactions, statusFilter, fromDate, toDate]);
  const pagedTransactions = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredTransactions.slice(start, start + pageSize);
  }, [filteredTransactions, page, pageSize]);
  const totalPages = Math.max(Math.ceil(filteredTransactions.length / pageSize), 1);
  const stats = statsQuery.data;
  const totalEstimatedCharges = useMemo(
    () =>
      (batchesQuery.data ?? []).reduce(
        (sum, batch) => sum + Number(batch.estimated_charge_fcfa ?? 0),
        0,
      ),
    [batchesQuery.data],
  );

  const exportRows = useMemo(() => mapTransactionsForExport(filteredTransactions), [filteredTransactions]);
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
      source_type: "manual",
    });
    setFormError(null);
    setCreateUploadWarning(null);
    setSelectedCreateJustificatif(null);
    setFormOpen(true);
  };
  useEffect(() => {
    setPage(1);
  }, [statusFilter, fromDate, toDate, tableControls.search, tableControls.filters.type, tableControls.filters.source_type, tableControls.sortOrder, pageSize]);

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
      source_type: transaction.source_type || "manual",
    });
    setFormError(null);
    setCreateUploadWarning(null);
    setSelectedCreateJustificatif(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setFormError(null);
    setCreateUploadWarning(null);
    setSelectedCreateJustificatif(null);
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
      source_type: values.source_type,
    };

    try {
      if (editingTransaction) {
        await updateTransaction.mutateAsync({ id: editingTransaction.id, payload });
      } else {
        const created = await createTransaction.mutateAsync(payload);
        if (selectedCreateJustificatif) {
          try {
            await uploadJustificatif.mutateAsync({ id: created.id, file: selectedCreateJustificatif });
          } catch (uploadError) {
            setCreateUploadWarning(
              uploadError instanceof Error
                ? `Transaction créée, mais upload justificatif échoué: ${uploadError.message}`
                : "Transaction créée, mais upload justificatif échoué.",
            );
            return;
          }
        }
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
        <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "all" | TreasuryTransaction["status"])} className="soft-focus wf-input px-3 py-2.5 text-sm">
            <option value="all">Tous statuts</option>
            <option value="non_enregistre">Non enregistré</option>
            <option value="enregistre_sans_justificatif">Sans justificatif</option>
            <option value="enregistre_complet">Enregistré complet</option>
            <option value="cancelled">Annulé</option>
          </select>
          <input type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} className="soft-focus wf-input px-3 py-2.5 text-sm" />
          <input type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} className="soft-focus wf-input px-3 py-2.5 text-sm" />
          <button type="button" onClick={openCreateForm} className="soft-focus wf-btn-primary px-4 py-2.5 text-sm font-semibold">
            + Nouvelle transaction
          </button>
        </div>
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
              <select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))} className="wf-input h-10 w-[110px] px-2 text-xs">
                <option value={10}>10 / page</option>
                <option value={20}>20 / page</option>
                <option value={50}>50 / page</option>
              </select>
              <ExportActions onCsv={() => runExport("csv")} onExcel={() => runExport("excel")} onPdf={() => runExport("pdf")} />
            </>
          }
        />
        <p className="mt-3 text-xs text-[var(--muted)]">
          Exporte toutes les lignes filtrées.
        </p>
        <p className="text-xs text-[var(--muted)]">
          Le dernier fichier importé est lié à l&apos;enregistrement.
        </p>
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
      ) : filteredTransactions.length === 0 ? (
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
                  <th className="px-5 py-3.5">Montant</th>
                  <th className="px-5 py-3.5">Source</th>
                  <th className="px-5 py-3.5">Statut</th>
                  <th className="px-5 py-3.5">Justificatif</th>
                  <th className="px-5 py-3.5">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pagedTransactions.map((transaction) => {
                  const type = typeBadge[transaction.type] ?? { label: transaction.type, tone: "danger" as const };
                  const status = statusBadge[transaction.status] ?? { label: transaction.status, tone: "info" as const };
                  const hasJustificatif = Boolean(transaction.justificatif_file);

                  return (
                    <tr key={transaction.id}>
                      <td className="px-5 py-4 font-medium text-[var(--text)]">{transaction.reference}</td>
                      <td className="px-5 py-4">{formatDate(transaction.transaction_date)}</td>
                      <td className="px-5 py-4">
                        <StatusBadge label={type.label} tone={type.tone} />
                      </td>
                      <td className="px-5 py-4">{transaction.category}</td>
                      <td className="px-5 py-4">{formatAmount(transaction.amount_fcfa)}</td>
                      <td className="px-5 py-4">{sourceLabel(transaction.source_type)}</td>
                      <td className="px-5 py-4">
                        <StatusBadge label={status.label} tone={status.tone} />
                      </td>
                      <td className="px-5 py-4">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                            hasJustificatif ? "bg-[#EAF8EE] text-[#0F7A3B]" : "bg-[#FFEDEE] text-[#A83C3C]"
                          }`}
                        >
                          {hasJustificatif ? "Fait" : "Non fait"}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <label
                            className={`soft-focus rounded-lg border px-2.5 py-1 text-xs font-semibold ${
                              transaction.is_locked
                                ? "border-[var(--line)] bg-[var(--surface-soft)] text-[var(--muted)]"
                                : "cursor-pointer border-[#D6DCE8] bg-white text-[var(--text)] hover:bg-[var(--surface-soft)]"
                            }`}
                          >
                            {uploadingTransactionId === transaction.id ? "Upload..." : "Ajouter justificatif"}
                            <input
                              type="file"
                              accept=".pdf,.jpg,.jpeg,.png,.webp,.xls,.xlsx,application/pdf,image/jpeg,image/png,image/webp,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
                            type="button"
                            className="soft-focus rounded-lg border border-[#A7C3F0] bg-[#EEF5FF] px-2.5 py-1 text-xs font-semibold text-[#1F5EA8] hover:bg-[#E4EEFF]"
                            onClick={() => setDetailTransaction(transaction)}
                          >
                            Voir plus
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-[var(--line)] px-4 py-3">
            <p className="text-xs text-[var(--muted)]">
              {Math.min((page - 1) * pageSize + 1, filteredTransactions.length)}–{Math.min(page * pageSize, filteredTransactions.length)} sur {filteredTransactions.length}
            </p>
            <div className="ml-auto flex items-center gap-2">
              <button type="button" className="soft-focus rounded-xl border border-[var(--line)] px-3 py-1.5 text-xs font-semibold disabled:opacity-50" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>Précédent</button>
              <span className="text-xs text-[var(--muted)]">{page}/{totalPages}</span>
              <button type="button" className="soft-focus rounded-xl border border-[var(--line)] px-3 py-1.5 text-xs font-semibold disabled:opacity-50" disabled={page >= totalPages} onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}>Suivant</button>
            </div>
          </div>
        </section>
      )}

      <LiquidGlassModal
        open={Boolean(detailTransaction)}
        onClose={() => setDetailTransaction(null)}
        title={detailTransaction ? `Transaction ${detailTransaction.reference}` : "Détail transaction"}
        subtitle="Informations détaillées et actions"
        size="lg"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={() => setDetailTransaction(null)}>
              Fermer
            </button>
            {detailTransaction ? (
              <div className="flex flex-wrap items-center gap-2">
                {(() => {
                  const isFarmerAdvance = detailTransaction.source_type === "farmer_advance";
                  const canEditOrCancel = !isFarmerAdvance && !detailTransaction.is_locked && detailTransaction.status !== "cancelled";
                  return (
                    <>
                      <button
                        type="button"
                        className="soft-focus rounded-lg border border-[var(--line)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--text)] hover:bg-[var(--surface-soft)] disabled:opacity-40"
                        onClick={() => {
                          openEditForm(detailTransaction);
                          setDetailTransaction(null);
                        }}
                        disabled={!canEditOrCancel}
                      >
                        Modifier
                      </button>
                      <button
                        type="button"
                        className="soft-focus rounded-lg border border-[#E0A5A5] bg-[#FFF0F0] px-3 py-1.5 text-xs font-semibold text-[#A83C3C] hover:bg-[#FFE7E7] disabled:opacity-40"
                        onClick={() => {
                          setPendingCancelTransaction(detailTransaction);
                          setDetailTransaction(null);
                        }}
                        disabled={!canEditOrCancel || cancelTransaction.isPending}
                      >
                        Annuler
                      </button>
                      <button
                        type="button"
                        className="soft-focus rounded-lg border border-[#9DD3AF] bg-[#EFFAF2] px-3 py-1.5 text-xs font-semibold text-[#0F7A3B] hover:bg-[#E5F6EB] disabled:opacity-40"
                        onClick={() => {
                          setPendingCompleteTransaction(detailTransaction);
                          setDetailTransaction(null);
                        }}
                        disabled={detailTransaction.is_locked || detailTransaction.status === "cancelled" || updateTransaction.isPending}
                      >
                        Marquer complet
                      </button>
                    </>
                  );
                })()}
              </div>
            ) : null}
          </div>
        }
      >
        {detailTransaction ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <DetailItem label="Référence" value={detailTransaction.reference} />
              <DetailItem label="Date" value={formatDate(detailTransaction.transaction_date)} />
              <DetailItem label="Type" value={typeBadge[detailTransaction.type]?.label ?? detailTransaction.type} />
              <DetailItem label="Statut" value={statusBadge[detailTransaction.status]?.label ?? detailTransaction.status} />
              <DetailItem label="Catégorie" value={detailTransaction.category} />
              <DetailItem label="Source" value={sourceLabel(detailTransaction.source_type)} />
              <DetailItem label="Montant" value={formatAmount(detailTransaction.amount_fcfa)} />
              <DetailItem label="Producteur lié" value={detailTransaction.farmer_name || "—"} />
              <DetailItem label="Libellé" value={detailTransaction.label} />
              <DetailItem label="Réf. externe" value={detailTransaction.receipt_reference || "—"} />
            </div>
            <DetailItem label="Note" value={detailTransaction.note?.trim() || "—"} />

            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Justificatif</p>
              {detailTransaction.justificatif_file ? (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="inline-flex rounded-full bg-[#EAF8EE] px-2 py-0.5 text-[11px] font-semibold text-[#0F7A3B]">Joint</span>
                  <p className="text-xs text-[var(--text)]">{detailTransaction.justificatif_file.filename}</p>
                  <a
                    className="soft-focus rounded-lg border border-[#A7C3F0] bg-[#EEF5FF] px-2.5 py-1 text-xs font-semibold text-[#1F5EA8] hover:bg-[#E4EEFF]"
                    href={detailTransaction.justificatif_file.file_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Voir
                  </a>
                  <a
                    className="soft-focus rounded-lg border border-[#A7C3F0] bg-[#EEF5FF] px-2.5 py-1 text-xs font-semibold text-[#1F5EA8] hover:bg-[#E4EEFF]"
                    href={detailTransaction.justificatif_file.file_url}
                    download={detailTransaction.justificatif_file.filename}
                  >
                    Télécharger
                  </a>
                </div>
              ) : (
                <p className="mt-2 text-xs text-[var(--muted)]">{detailTransaction.justificatif_status || "Aucun justificatif."}</p>
              )}
            </div>

            {detailTransaction.source_type === "farmer_advance" && detailTransaction.linked_advance_devis_file ? (
              <div className="rounded-xl border border-[#D8E4FA] bg-[#F7FAFF] p-3">
                <p className="text-xs uppercase tracking-wide text-[#466B9F]">Devis Avance Producteur</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <a
                    className="soft-focus rounded-lg border border-[#C8D7F6] bg-[#F4F8FF] px-2.5 py-1 text-xs font-semibold text-[#355E9C] hover:bg-[#EAF2FF]"
                    href={detailTransaction.linked_advance_devis_file.file_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Voir devis
                  </a>
                  <a
                    className="soft-focus rounded-lg border border-[#C8D7F6] bg-[#F4F8FF] px-2.5 py-1 text-xs font-semibold text-[#355E9C] hover:bg-[#EAF2FF]"
                    href={detailTransaction.linked_advance_devis_file.file_url}
                    download={detailTransaction.linked_advance_devis_file.filename}
                  >
                    Télécharger devis
                  </a>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </LiquidGlassModal>

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
              {formState.isSubmitting || uploadJustificatif.isPending ? "Enregistrement..." : "Enregistrer"}
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

          <div className="grid gap-3 sm:grid-cols-1">
            <label className="block text-sm font-medium text-[var(--text)]">
              Statut
              <select {...register("status", { required: "Statut requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm">
                <option value="non_enregistre">Non enregistré</option>
                <option value="enregistre_sans_justificatif">Enregistré sans justificatif</option>
                <option value="enregistre_complet">Enregistré complet</option>
              </select>
            </label>
          </div>

          <label className="block text-sm font-medium text-[var(--text)]">
            Note
            <textarea {...register("note")} className="wf-input mt-2 min-h-[96px] w-full px-3 py-2 text-sm" placeholder="Commentaire optionnel..." />
          </label>

          {!editingTransaction ? (
            <label className="block text-sm font-medium text-[var(--text)]">
              Justificatif (optionnel, PDF/JPG/JPEG/PNG/WEBP/XLS/XLSX)
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.webp,.xls,.xlsx,application/pdf,image/jpeg,image/png,image/webp,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                onChange={(event) => setSelectedCreateJustificatif(event.target.files?.[0] ?? null)}
              />
            </label>
          ) : null}

          {formError && (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {formError}
            </p>
          )}
          {createUploadWarning && (
            <p className="rounded-lg border border-[#F2D7A5] bg-[#FFF8EA] px-3 py-2 text-xs text-[#8A5B00]">
              {createUploadWarning}
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
        message="Cette action verrouille la transaction. Vérifiez qu'un justificatif ou une référence externe est présent."
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

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
      <p className="text-[11px] uppercase tracking-wide text-[var(--muted)]">{label}</p>
      <p className="mt-1 text-sm text-[var(--text)]">{value}</p>
    </div>
  );
}
