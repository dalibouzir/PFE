"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { ConfirmActionModal } from "@/components/ui/ConfirmActionModal";
import { GlassViewToggle, type DataViewMode } from "@/components/ui/GlassViewToggle";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ExportActions } from "@/components/ui/table/ExportActions";
import { TableToolbar } from "@/components/ui/table/TableToolbar";
import { useBatches } from "@/hooks/useBatches";
import { useCreateInput, useDeleteInput, useInputs, useUpdateInput, useUploadInputJustificatif } from "@/hooks/useInputs";
import { ApiError } from "@/lib/api/client";
import { useMembers } from "@/hooks/useMembers";
import { useProducts } from "@/hooks/useProducts";
import { exportRowsToCsv, exportRowsToExcel, exportRowsToPdf, type ExportColumn } from "@/lib/export/client";
import { useTableControls } from "@/lib/table/useTableControls";
import type { Batch, Input, InputCreate } from "@/lib/api/types";

const statusTone: Record<string, "success" | "warning" | "info"> = {
  validated: "success",
  quality_control: "warning",
  pending: "info",
};
const statusLabel: Record<string, string> = {
  validated: "Valide",
  quality_control: "Controle qualite",
  pending: "En attente",
};
const gradeTone: Record<string, "success" | "info" | "warning"> = {
  A: "success",
  B: "info",
  C: "warning",
};

function normalizeToken(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function toNullableFiniteNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const num = typeof value === "number" ? value : Number(value);
  return Number.isFinite(num) ? num : null;
}

function formatApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (Array.isArray(error.details)) {
      const details = error.details
        .map((detail) => {
          if (typeof detail === "string") return detail;
          if (detail && typeof detail === "object" && "loc" in detail && "msg" in detail) {
            const loc = Array.isArray((detail as { loc?: unknown }).loc)
              ? (detail as { loc: unknown[] }).loc.join(".")
              : "";
            const msg = typeof (detail as { msg?: unknown }).msg === "string"
              ? (detail as { msg: string }).msg
              : "";
            return [loc, msg].filter(Boolean).join(": ");
          }
          return JSON.stringify(detail);
        })
        .filter(Boolean);
      if (details.length > 0) return details.join(" | ");
    }
    if (typeof error.message === "string" && error.message.trim()) return error.message;
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

function parseSpecialtyTokens(value?: string | null) {
  if (!value) return [];
  const tokens = value
    .split(/[;,/|]+/)
    .map((item) => normalizeToken(item))
    .filter(Boolean);
  return Array.from(new Set(tokens));
}

function mergeMemberProductTokens(products?: string[] | null, mainProduct?: string | null, secondaryProducts?: string | null, specialty?: string | null) {
  const normalizedProducts = (products ?? []).map((item) => normalizeToken(item)).filter(Boolean);
  const merged = [
    ...normalizedProducts,
    ...parseSpecialtyTokens(mainProduct),
    ...parseSpecialtyTokens(secondaryProducts),
    ...parseSpecialtyTokens(specialty),
  ];
  return Array.from(new Set(merged));
}

export default function InputsPage() {
  const { data: inputs = [] } = useInputs();
  const { data: batches = [] } = useBatches();
  const { data: members = [] } = useMembers();
  const { data: products = [] } = useProducts();
  const createInput = useCreateInput();
  const updateInput = useUpdateInput();
  const deleteInput = useDeleteInput();
  const uploadJustificatif = useUploadInputJustificatif();

  const [productId, setProductId] = useState<string>("Tous");
  const [fromDate, setFromDate] = useState("");
  const [viewMode, setViewMode] = useState<DataViewMode>("table");
  const [formOpen, setFormOpen] = useState(false);
  const [statusEditingId, setStatusEditingId] = useState<string | null>(null);
  const [statusSavingId, setStatusSavingId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [collecteMode, setCollecteMode] = useState<"linked" | "independent">("linked");
  const [selectedLotId, setSelectedLotId] = useState<string>("");
  const [selectedJustificatif, setSelectedJustificatif] = useState<File | null>(null);
  const [uploadingItemId, setUploadingItemId] = useState<string | null>(null);
  const justificatifPickerRef = useRef<HTMLInputElement | null>(null);
  const [pendingValidationItem, setPendingValidationItem] = useState<Input | null>(null);
  const [pendingDeleteItem, setPendingDeleteItem] = useState<Input | null>(null);
  const tableControls = useTableControls(
    [
      {
        key: "status",
        label: "Statut",
        options: [
          { value: "all", label: "Tous statuts" },
          { value: "pending", label: "En attente" },
          { value: "quality_control", label: "Controle qualite" },
          { value: "validated", label: "Valide" },
        ],
        initialValue: "all",
      },
    ],
    "desc",
  );

  const { register, handleSubmit, reset, setValue, watch, getValues, formState } = useForm<InputCreate>({
    defaultValues: {
      member_id: "",
      product_id: "",
      date: "",
      quantity: 0,
      grade: "",
      bl_number: "",
      status: "pending",
      estimated_value: undefined,
    },
  });

  const memberLookup = useMemo(() => new Map(members.map((m) => [m.id, m.full_name])), [members]);
  const productLookup = useMemo(() => new Map(products.map((p) => [p.id, p.name])), [products]);

  const filtered = useMemo(() => {
    return inputs.filter((item) => {
      const byProduct = productId === "Tous" || item.product_id === productId;
      const byDate = fromDate ? item.date >= fromDate : true;
      const byStatus = tableControls.filters.status === "all" || item.status === tableControls.filters.status;
      const q = tableControls.search.trim().toLowerCase();
      const memberName = (memberLookup.get(item.member_id) ?? "").toLowerCase();
      const productName = (productLookup.get(item.product_id) ?? "").toLowerCase();
      const bySearch =
        q.length === 0 ||
        memberName.includes(q) ||
        productName.includes(q) ||
        item.date.toLowerCase().includes(q) ||
        (item.bl_number ?? "").toLowerCase().includes(q) ||
        item.grade.toLowerCase().includes(q);
      return byProduct && byDate && byStatus && bySearch;
    });
  }, [fromDate, inputs, memberLookup, productId, productLookup, tableControls.filters.status, tableControls.search]);

  const sortedFiltered = useMemo(() => {
    const sorted = filtered.slice().sort((a, b) => a.date.localeCompare(b.date));
    return tableControls.sortOrder === "asc" ? sorted : sorted.reverse();
  }, [filtered, tableControls.sortOrder]);

  const totalKg = filtered.reduce((sum, item) => sum + item.quantity, 0);
  const pendingCount = filtered.filter((item) => item.status !== "validated").length;
  const validatedCount = filtered.filter((item) => item.status === "validated").length;
  const gradeA = filtered.filter((item) => item.grade.toUpperCase() === "A").length;

  const selectedMemberId = watch("member_id");
  const selectedMember = useMemo(() => members.find((item) => item.id === selectedMemberId), [members, selectedMemberId]);
  const selectedMemberSpecialtyTokens = useMemo(
    () => mergeMemberProductTokens(selectedMember?.products, selectedMember?.main_product, selectedMember?.secondary_products, selectedMember?.specialty),
    [selectedMember?.products, selectedMember?.main_product, selectedMember?.secondary_products, selectedMember?.specialty],
  );
  const productByNormalizedName = useMemo(() => {
    const map = new Map<string, (typeof products)[number]>();
    for (const product of products) {
      const key = normalizeToken(product.name);
      if (!map.has(key)) map.set(key, product);
    }
    return map;
  }, [products]);

  const availableProducts = useMemo(() => {
    if (!selectedMemberId) return [];
    if (selectedMemberSpecialtyTokens.length === 0) return [];
    const ordered: (typeof products)[number][] = [];
    const seen = new Set<string>();
    for (const token of selectedMemberSpecialtyTokens) {
      const matched = productByNormalizedName.get(token);
      if (!matched) continue;
      if (seen.has(matched.id)) continue;
      seen.add(matched.id);
      ordered.push(matched);
    }
    return ordered;
  }, [selectedMemberId, selectedMemberSpecialtyTokens, productByNormalizedName]);

  const readyForCollecteLots = useMemo(() => {
    return [...batches]
      .filter((batch) =>
        Boolean(
          batch.member_id &&
            batch.parcel_id &&
            batch.preharvest_completed_at &&
            !batch.collecte_created &&
            !batch.stock_in_created &&
            !batch.confirmed_weight_kg,
        ),
      )
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [batches]);

  const selectedLot = useMemo<Batch | null>(
    () => readyForCollecteLots.find((batch) => batch.id === selectedLotId) ?? null,
    [readyForCollecteLots, selectedLotId],
  );

  useEffect(() => {
    if (!formOpen) return;
    const currentProductId = getValues("product_id");
    const stillAvailable = availableProducts.some((product) => product.id === currentProductId);
    if (!stillAvailable && availableProducts.length > 0) {
      setValue("product_id", availableProducts[0]?.id ?? "");
    }
  }, [availableProducts, formOpen, getValues, setValue]);

  const openCreateForm = () => {
    reset({
      member_id: members[0]?.id ?? "",
      product_id: "",
      date: "",
      quantity: 0,
      grade: "",
      bl_number: "",
      status: "pending",
      estimated_value: undefined,
    });
    setFormError(null);
    setCollecteMode("linked");
    setSelectedLotId(readyForCollecteLots[0]?.id ?? "");
    setSelectedJustificatif(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setFormError(null);
  };

  const submitInput = handleSubmit(async (values) => {
    setFormError(null);
    try {
      if (collecteMode === "linked") {
        if (!selectedLot) {
          setFormError("Sélectionnez un lot prêt pour Collecte.");
          return;
        }
        if (!selectedLot.member_id || !selectedLot.product_id) {
          setFormError("Lot invalide: membre/produit manquant.");
          return;
        }
        const payload: InputCreate = {
          member_id: selectedLot.member_id,
          product_id: selectedLot.product_id,
          batch_id: selectedLot.id,
          field_id: null,
          date: values.date,
          quantity: Number(values.quantity),
          grade: values.grade.trim() || "A",
          bl_number: values.bl_number?.trim() || null,
          status: "validated",
          source_type: "lot_linked_collecte",
          estimated_value: toNullableFiniteNumber(values.estimated_value),
        };
        const created = await createInput.mutateAsync(payload);
        if (selectedJustificatif) {
          await uploadJustificatif.mutateAsync({ id: created.id, file: selectedJustificatif });
        }
        closeForm();
        setSelectedJustificatif(null);
        return;
      }

      if (!values.product_id) {
        setFormError("Produit requis.");
        return;
      }
      const payload: InputCreate = {
        member_id: values.member_id,
        product_id: values.product_id,
        field_id: null,
        date: values.date,
        quantity: Number(values.quantity),
        grade: values.grade.trim(),
        bl_number: values.bl_number?.trim() || null,
        status: values.status || "pending",
        estimated_value: toNullableFiniteNumber(values.estimated_value),
      };
      const created = await createInput.mutateAsync(payload);
      if (selectedJustificatif) {
        await uploadJustificatif.mutateAsync({ id: created.id, file: selectedJustificatif });
      }
      closeForm();
      setSelectedJustificatif(null);
    } catch (error) {
      setFormError(formatApiError(error, "Impossible d'enregistrer la collecte."));
    }
  });

  useEffect(() => {
    if (!formOpen || collecteMode !== "linked") return;
    if (!selectedLotId && readyForCollecteLots.length > 0) {
      setSelectedLotId(readyForCollecteLots[0].id);
    }
  }, [collecteMode, formOpen, readyForCollecteLots, selectedLotId]);

  const applyStatusUpdate = async (item: Input, nextStatus: string) => {
    setFormError(null);
    setStatusSavingId(item.id);
    try {
      await updateInput.mutateAsync({ id: item.id, payload: { status: nextStatus } });
      setStatusEditingId(null);
    } catch (error) {
      setFormError(formatApiError(error, "Impossible de mettre à jour le statut."));
    } finally {
      setStatusSavingId(null);
    }
  };

  const handleStatusUpdate = async (item: Input, nextStatus: string) => {
    if (!nextStatus || nextStatus === item.status) {
      setStatusEditingId(null);
      return;
    }
    if (nextStatus === "validated" && item.status !== "validated") {
      setPendingValidationItem(item);
      return;
    }
    await applyStatusUpdate(item, nextStatus);
  };

  const handleDeleteInput = async (item: Input) => {
    try {
      await deleteInput.mutateAsync(item.id);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Impossible de supprimer la collecte.";
      setFormError(message);
      window.alert(message);
    }
  };

  const openJustificatifPicker = (itemId: string) => {
    setUploadingItemId(itemId);
    justificatifPickerRef.current?.click();
  };

  const handleJustificatifPicked = async (file: File | null) => {
    if (!file || !uploadingItemId) return;
    try {
      await uploadJustificatif.mutateAsync({ id: uploadingItemId, file });
      setFormError(null);
    } catch (error) {
      setFormError(formatApiError(error, "Upload justificatif échoué."));
    } finally {
      setUploadingItemId(null);
      if (justificatifPickerRef.current) justificatifPickerRef.current.value = "";
    }
  };

  const exportColumns: ExportColumn<Input>[] = [
    { key: "date", header: "Date" },
    { key: "member_id", header: "Producteur", format: (_, row) => memberLookup.get(row.member_id) ?? row.member_id },
    { key: "product_id", header: "Produit", format: (_, row) => productLookup.get(row.product_id) ?? row.product_id },
    { key: "quantity", header: "Quantite (kg)", format: (_, row) => row.quantity.toLocaleString("fr-FR") },
    { key: "bl_number", header: "BL", format: (_, row) => row.bl_number || "—" },
    { key: "grade", header: "Grade", format: (_, row) => row.grade.toUpperCase() },
    { key: "status", header: "Statut", format: (_, row) => statusLabel[row.status] ?? row.status },
    { key: "justificatif", header: "Justificatif", format: (_, row) => (row.justificatif_file ? "Présent" : "Absent") },
  ];

  return (
    <main>
      <PageIntro title="Collecte" />

      <section className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "20ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Volume collecte</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{totalKg.toLocaleString("fr-FR")} kg</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Collectes validees</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{validatedCount}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "60ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">A traiter</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{pendingCount}</p>
        </article>
        <article className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: "80ms" }}>
          <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Qualite A</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--text)]">{gradeA}</p>
        </article>
      </section>

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto_auto]">
          <select value={productId} onChange={(event) => setProductId(event.target.value)} className="soft-focus wf-input px-3 py-2.5 text-sm">
            <option value="Tous">Tous produits</option>
            {products.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
          <input type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} className="soft-focus wf-input px-3 py-2.5 text-sm" />
          <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5 text-sm text-[var(--muted)]">{filtered.length} enregistrements</div>
          <button type="button" onClick={openCreateForm} className="soft-focus wf-btn-primary px-4 py-2.5 text-sm font-semibold">Nouvelle collecte</button>
        </div>

        <div className="mt-3">
          <TableToolbar
            search={tableControls.search}
            onSearchChange={tableControls.setSearch}
            searchPlaceholder="Recherche date, producteur, produit, BL, grade..."
            filters={tableControls.filterDefinitions}
            onFilterChange={tableControls.setFilterValue}
            sortOrder={tableControls.sortOrder}
            onSortOrderChange={tableControls.setSortOrder}
            sortAscLabel="Date asc"
            sortDescLabel="Date desc"
            rightActions={
              <ExportActions
                onCsv={() => exportRowsToCsv({ filename: "collectes", title: "Collectes", columns: exportColumns, rows: sortedFiltered })}
                onExcel={() => exportRowsToExcel({ filename: "collectes", title: "Collectes", columns: exportColumns, rows: sortedFiltered })}
                onPdf={() => exportRowsToPdf({ filename: "collectes", title: "Collectes", columns: exportColumns, rows: sortedFiltered })}
              />
            }
          />
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="grid grow gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Volume visible</p>
              <p className="text-lg font-semibold text-[var(--text)]">{totalKg.toLocaleString("fr-FR")} kg</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">A traiter</p>
              <p className="text-lg font-semibold text-[var(--text)]">{pendingCount}</p>
            </div>
          </div>
          <GlassViewToggle value={viewMode} onChange={setViewMode} className="shrink-0" />
        </div>
      </section>

      {formError ? (
        <section className="mb-4 rounded-xl border border-[#f2c7c7] bg-[#fff1f1] px-4 py-3 text-sm text-[#8f2f2f]">{formError}</section>
      ) : null}

      {sortedFiltered.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "100ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucune collecte ne correspond aux filtres.</p>
        </section>
      ) : viewMode === "table" ? (
        <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "100ms" }}>
          <input
            ref={justificatifPickerRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(event) => {
              void handleJustificatifPicked(event.target.files?.[0] ?? null);
            }}
          />
          <div className="overflow-x-auto">
            <table className="wf-table min-w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="px-5 py-3.5">Date</th>
                  <th className="px-5 py-3.5">Agriculteur</th>
                  <th className="px-5 py-3.5">Produit</th>
                  <th className="px-5 py-3.5">Quantite</th>
                  <th className="px-5 py-3.5">BL</th>
                  <th className="px-5 py-3.5">Grade</th>
                  <th className="px-5 py-3.5">Statut</th>
                  <th className="px-5 py-3.5">Justificatif</th>
                  <th className="px-5 py-3.5">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedFiltered.map((item) => (
                  <tr key={item.id}>
                    <td className="px-5 py-4">{item.date}</td>
                    <td className="px-5 py-4 font-medium text-[var(--text)]">{memberLookup.get(item.member_id) ?? item.member_id.slice(0, 8)}</td>
                    <td className="px-5 py-4">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</td>
                    <td className="px-5 py-4">{item.quantity.toLocaleString("fr-FR")} kg</td>
                    <td className="px-5 py-4">{item.bl_number || "—"}</td>
                    <td className="px-5 py-4"><StatusBadge label={item.grade.toUpperCase()} tone={gradeTone[item.grade.toUpperCase()] ?? "info"} /></td>
                    <td className="px-5 py-4">
                      {statusEditingId === item.id ? (
                        <select
                          autoFocus
                          className="wf-input h-9 min-w-[170px] px-2 text-xs"
                          value={item.status}
                          disabled={statusSavingId === item.id}
                          onBlur={() => {
                            if (statusSavingId !== item.id) setStatusEditingId(null);
                          }}
                          onChange={(event) => {
                            void handleStatusUpdate(item, event.target.value);
                          }}
                        >
                          <option value="pending">En attente</option>
                          <option value="quality_control">Controle qualite</option>
                          <option value="validated">Valide</option>
                        </select>
                      ) : (
                        <button type="button" className="text-left" onClick={() => setStatusEditingId(item.id)} title="Changer le statut">
                          <StatusBadge label={statusLabel[item.status] ?? item.status} tone={statusTone[item.status] ?? "info"} />
                        </button>
                      )}
                    </td>
                    <td className="px-5 py-4 text-xs">
                      {item.justificatif_file ? (
                        <a className="font-semibold text-[var(--primary)] hover:underline" href={item.justificatif_file.file_url} target="_blank" rel="noreferrer">
                          {item.justificatif_file.filename}
                        </a>
                      ) : (
                        <span className="text-[var(--muted)]">Absent</span>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <button
                          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[var(--primary)] hover:bg-[var(--surface-soft)] disabled:opacity-60"
                          onClick={() => openJustificatifPicker(item.id)}
                          disabled={uploadJustificatif.isPending && uploadingItemId === item.id}
                          title={item.justificatif_file ? "Remplacer justificatif" : "Téléverser justificatif"}
                          aria-label={item.justificatif_file ? "Remplacer justificatif" : "Téléverser justificatif"}
                        >
                          ⬆
                        </button>
                        <button className="text-xs font-semibold text-[var(--danger)] hover:underline" onClick={() => setPendingDeleteItem(item)}>Supprimer</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <input
            ref={justificatifPickerRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(event) => {
              void handleJustificatifPicked(event.target.files?.[0] ?? null);
            }}
          />
          {sortedFiltered.map((item, index) => (
            <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${100 + index * 30}ms` }}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-[var(--text)]">{memberLookup.get(item.member_id) ?? item.member_id.slice(0, 8)}</p>
                  <p className="text-xs text-[var(--muted)]">{item.date}</p>
                </div>
                {statusEditingId === item.id ? (
                  <select
                    autoFocus
                    className="wf-input h-8 min-w-[150px] px-2 text-xs"
                    value={item.status}
                    disabled={statusSavingId === item.id}
                    onBlur={() => {
                      if (statusSavingId !== item.id) setStatusEditingId(null);
                    }}
                    onChange={(event) => {
                      void handleStatusUpdate(item, event.target.value);
                    }}
                  >
                    <option value="pending">En attente</option>
                    <option value="quality_control">Controle qualite</option>
                    <option value="validated">Valide</option>
                  </select>
                ) : (
                  <button type="button" className="text-left" onClick={() => setStatusEditingId(item.id)} title="Changer le statut">
                    <StatusBadge label={statusLabel[item.status] ?? item.status} tone={statusTone[item.status] ?? "info"} />
                  </button>
                )}
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[11px] text-[var(--muted)]">Produit</p>
                  <p className="text-sm font-semibold text-[var(--text)]">{productLookup.get(item.product_id) ?? item.product_id.slice(0, 8)}</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[11px] text-[var(--muted)]">Quantite</p>
                  <p className="text-sm font-semibold text-[var(--text)]">{item.quantity.toFixed(1)} kg</p>
                </div>
              </div>

              <p className="mt-3 text-xs text-[var(--muted)]">Grade {item.grade}</p>
              <p className="mt-1 text-xs text-[var(--muted)]">BL: {item.bl_number || "—"}</p>
              <p className="mt-1 text-xs text-[var(--muted)]">Justificatif: {item.justificatif_file ? item.justificatif_file.filename : "Absent"}</p>

              <div className="mt-3 flex items-center gap-2">
                <button
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[var(--primary)] hover:bg-[var(--surface-soft)] disabled:opacity-60"
                  onClick={() => openJustificatifPicker(item.id)}
                  disabled={uploadJustificatif.isPending && uploadingItemId === item.id}
                  title={item.justificatif_file ? "Remplacer justificatif" : "Téléverser justificatif"}
                  aria-label={item.justificatif_file ? "Remplacer justificatif" : "Téléverser justificatif"}
                >
                  ⬆
                </button>
                <button className="text-xs font-semibold text-[var(--danger)] hover:underline" onClick={() => setPendingDeleteItem(item)}>Supprimer</button>
              </div>
            </article>
          ))}
        </section>
      )}

      <LiquidGlassModal
        open={formOpen}
        onClose={closeForm}
        title="Nouvelle collecte"
        subtitle="La collecte liée confirme la quantité réelle du lot, alimente le stock et débloque la Post-récolte."
        size="lg"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={closeForm}>Annuler</button>
            <button type="submit" form="input-form" className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" disabled={formState.isSubmitting || uploadJustificatif.isPending}>
              {formState.isSubmitting || uploadJustificatif.isPending ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        }
      >
        <form id="input-form" onSubmit={submitInput} className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm font-medium text-[var(--text)] sm:col-span-2">
            Mode de collecte
            <select value={collecteMode} onChange={(event) => setCollecteMode(event.target.value as "linked" | "independent")} className="wf-input mt-2 h-11 w-full px-3 text-sm">
              <option value="linked">Collecte liée à un lot</option>
              <option value="independent">Collecte indépendante</option>
            </select>
          </label>
          {collecteMode === "linked" ? (
            <>
              <label className="block text-sm font-medium text-[var(--text)] sm:col-span-2">
                Lot prêt pour Collecte
                <select value={selectedLotId} onChange={(event) => setSelectedLotId(event.target.value)} className="wf-input mt-2 h-11 w-full px-3 text-sm">
                  {readyForCollecteLots.length === 0 ? (
                    <option value="">Aucun lot prêt pour Collecte</option>
                  ) : (
                    readyForCollecteLots.map((lot) => (
                      <option key={lot.id} value={lot.id}>{lot.code} — {(productLookup.get(lot.product_id) ?? lot.product_id).toString()}</option>
                    ))
                  )}
                </select>
              </label>
              <div className="sm:col-span-2 rounded-xl border border-[#BDD6FB] bg-[#EEF5FF] px-3 py-2 text-xs text-[#2F80ED]">
                La quantité réelle du lot est confirmée ici. Elle alimente le stock et débloque la Post-récolte.
              </div>
            </>
          ) : null}

          <label className="block text-sm font-medium text-[var(--text)]">
            Agriculteur
            <select {...register("member_id", { required: "Agriculteur requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" disabled={collecteMode === "linked"}>
              <option value="" disabled>Selectionner un agriculteur</option>
              {members.map((member) => (
                <option key={member.id} value={member.id}>{member.full_name}</option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Produit
            <select {...register("product_id", { required: "Produit requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" disabled={collecteMode === "linked"}>
              {!selectedMemberId ? (
                <option value="" disabled>Selectionner un agriculteur d&apos;abord</option>
              ) : availableProducts.length === 0 ? (
                <option value="" disabled>Aucun produit disponible pour cet agriculteur</option>
              ) : (
                <option value="" disabled>Selectionner un produit</option>
              )}
              {availableProducts.map((product) => (
                <option key={product.id} value={product.id}>{product.name}</option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Date
            <input type="date" {...register("date", { required: "Date requise." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Quantite (kg)
            <input type="number" step="0.1" min="0" {...register("quantity", { required: "Quantite requise.", valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Grade
            <input {...register("grade", { required: "Grade requis." })} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="A" />
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            BL / Bon de livraison
            <input {...register("bl_number")} className="wf-input mt-2 h-11 w-full px-3 text-sm" placeholder="BL001-15052026" />
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Statut
            <select {...register("status")} className="wf-input mt-2 h-11 w-full px-3 text-sm">
              <option value="pending">En attente</option>
              <option value="quality_control">Controle qualite</option>
              <option value="validated">Valide</option>
            </select>
          </label>

          <label className="block text-sm font-medium text-[var(--text)]">
            Valeur estimee (optionnel)
            <input type="number" step="0.1" min="0" {...register("estimated_value", { valueAsNumber: true })} className="wf-input mt-2 h-11 w-full px-3 text-sm" />
          </label>

          <label className="block text-sm font-medium text-[var(--text)] sm:col-span-2">
            Justificatif (PDF/JPG/JPEG/PNG/WEBP)
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
              className="wf-input mt-2 h-11 w-full px-3 text-sm"
              onChange={(event) => setSelectedJustificatif(event.target.files?.[0] ?? null)}
            />
          </label>

          {formError ? (
            <p className="sm:col-span-2 rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">{formError}</p>
          ) : null}
        </form>
      </LiquidGlassModal>

      <ConfirmActionModal
        open={Boolean(pendingValidationItem)}
        onCancel={() => {
          setPendingValidationItem(null);
          setStatusEditingId(null);
        }}
        onConfirm={() => {
          if (!pendingValidationItem) return;
          void applyStatusUpdate(pendingValidationItem, "validated");
          setPendingValidationItem(null);
        }}
        title="Valider la collecte"
        message="Cette action confirme le statut de la collecte. Le stock n'est pas recréé dans cette étape."
        confirmLabel="Valider"
      />
      <ConfirmActionModal
        open={Boolean(pendingDeleteItem)}
        onCancel={() => setPendingDeleteItem(null)}
        onConfirm={() => {
          if (!pendingDeleteItem) return;
          void handleDeleteInput(pendingDeleteItem);
          setPendingDeleteItem(null);
        }}
        title="Supprimer la collecte"
        message="Cette action supprimera définitivement cette collecte."
        confirmLabel="Supprimer"
      />
    </main>
  );
}
