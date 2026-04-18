"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { GlassViewToggle, type DataViewMode } from "@/components/ui/GlassViewToggle";
import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useCreateMember, useDeleteMember, useMembers, useUpdateMember } from "@/hooks/useMembers";
import { useFields } from "@/hooks/useFields";
import type { Member, MemberCreate } from "@/lib/api/types";

const statusTone: Record<string, "success" | "warning" | "info"> = {
  active: "success",
  inactive: "warning",
  seasonal: "info",
};

const statusLabel: Record<string, string> = {
  active: "Actif",
  inactive: "Inactif",
  seasonal: "Saisonnier",
};

type MemberTab = "profil" | "parcelles" | "activite";

type MemberSummary = {
  id: string;
  code: string;
  fullName: string;
  phone: string;
  zone: string;
  culture: string;
  parcels: number;
  totalArea: number;
  status: string;
  raw: Member;
};

type MemberFormValues = {
  code?: string;
  full_name: string;
  village: string;
  phone: string;
  main_product: string;
  parcel_count: number;
  area_hectares: number;
  join_date: string;
  status: "active" | "inactive" | "seasonal";
};

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export default function MembersPage() {
  const membersQuery = useMembers();
  const fieldsQuery = useFields();
  const createMember = useCreateMember();
  const updateMember = useUpdateMember();
  const deleteMember = useDeleteMember();

  const [query, setQuery] = useState("");
  const [product, setProduct] = useState<"Tous" | string>("Tous");
  const [status, setStatus] = useState<"Tous" | string>("Tous");
  const [viewMode, setViewMode] = useState<DataViewMode>("table");
  const [selectedMember, setSelectedMember] = useState<MemberSummary | null>(null);
  const [activeTab, setActiveTab] = useState<MemberTab>("profil");
  const [formOpen, setFormOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [editingMember, setEditingMember] = useState<MemberSummary | null>(null);

  const { register, handleSubmit, reset, setValue, watch, formState } = useForm<MemberFormValues>({
    defaultValues: {
      full_name: "",
      village: "",
      phone: "",
      main_product: "",
      parcel_count: 1,
      area_hectares: 1,
      join_date: "",
      status: "active",
    },
  });
  const selectedStatus = watch("status");

  const summaries = useMemo<MemberSummary[]>(() => {
    const members = membersQuery.data ?? [];
    const fields = fieldsQuery.data ?? [];

    return members.map((member) => {
      const memberFields = fields.filter((field) => field.member_id === member.id);
      const fieldsArea = memberFields.reduce((sum, field) => sum + field.area, 0);
      const totalArea = member.area_hectares > 0 ? member.area_hectares : fieldsArea;
      const zone = member.village?.trim() || memberFields[0]?.location || "Zone non renseignee";
      const culture = member.main_product?.trim() || member.specialty?.trim() || "Non renseigne";
      const parcels = member.parcel_count > 0 ? member.parcel_count : memberFields.length;

      return {
        id: member.id,
        code: member.code,
        fullName: member.full_name,
        phone: member.phone,
        zone,
        culture,
        parcels,
        totalArea,
        status: member.status,
        raw: member,
      };
    });
  }, [membersQuery.data, fieldsQuery.data]);

  const specialtyOptions = useMemo(() => {
    const unique = new Set(summaries.map((item) => item.culture).filter((value) => value && value !== "Non renseigne"));
    return Array.from(unique);
  }, [summaries]);

  const filtered = useMemo(() => {
    return summaries.filter((item) => {
      const byProduct = product === "Tous" || item.culture === product;
      const byStatus = status === "Tous" || item.status === status;
      const byText = `${item.fullName} ${item.zone} ${item.phone} ${item.code}`.toLowerCase().includes(query.toLowerCase());
      return byProduct && byStatus && byText;
    });
  }, [summaries, product, status, query]);

  const totalParcels = filtered.reduce((acc, item) => acc + item.parcels, 0);
  const totalSurface = filtered.reduce((acc, item) => acc + item.totalArea, 0);

  const selectedFields = useMemo(() => {
    if (!selectedMember) return [];
    return (fieldsQuery.data ?? []).filter((field) => field.member_id === selectedMember.id);
  }, [fieldsQuery.data, selectedMember]);

  const memberActivity = useMemo(() => {
    if (!selectedMember) return [];
    const monthlyProjection = Math.round(selectedMember.totalArea * 320);
    const productivity = Math.round((selectedMember.totalArea / Math.max(selectedMember.parcels, 1)) * 100) / 100;

    return [
      {
        id: "ACT-1",
        title: "Projection collecte (30 jours)",
        detail: `${monthlyProjection.toLocaleString("fr-FR")} kg estimes sur ${selectedMember.culture}`,
      },
      {
        id: "ACT-2",
        title: "Densite parcellaire",
        detail: `${selectedMember.parcels} parcelles · ${productivity.toFixed(2)} ha par parcelle`,
      },
      {
        id: "ACT-3",
        title: "Etat du profil",
        detail: `Statut actuel: ${statusLabel[selectedMember.status] ?? selectedMember.status} · Code: ${selectedMember.code}`,
      },
    ];
  }, [selectedMember]);

  const openMemberDetails = (member: MemberSummary) => {
    setSelectedMember(member);
    setActiveTab("profil");
  };

  const openCreateForm = () => {
    setEditingMember(null);
    reset({
      code: "",
      full_name: "",
      village: "",
      phone: "",
      main_product: "",
      parcel_count: 1,
      area_hectares: 1,
      join_date: "",
      status: "active",
    });
    setFormError(null);
    setFormOpen(true);
  };

  const openEditForm = (member: MemberSummary) => {
    setEditingMember(member);
    reset({
      code: member.code,
      full_name: member.fullName,
      village: member.raw.village ?? "",
      phone: member.phone,
      main_product: member.raw.main_product ?? member.raw.specialty ?? "",
      parcel_count: member.raw.parcel_count > 0 ? member.raw.parcel_count : member.parcels,
      area_hectares: member.raw.area_hectares > 0 ? member.raw.area_hectares : member.totalArea,
      join_date: member.raw.join_date ?? "",
      status: member.raw.status,
    });
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setFormError(null);
  };

  const submitMember = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const payload: MemberCreate = {
        code: values.code?.trim() || undefined,
        full_name: values.full_name.trim(),
        village: values.village.trim(),
        phone: values.phone.trim(),
        main_product: values.main_product.trim(),
        parcel_count: Number(values.parcel_count),
        area_hectares: Number(values.area_hectares),
        join_date: values.join_date || null,
        specialty: values.main_product.trim() || null,
        status: values.status,
      };

      if (editingMember) {
        await updateMember.mutateAsync({ id: editingMember.id, payload });
      } else {
        await createMember.mutateAsync(payload);
      }
      closeForm();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible d'enregistrer l'agriculteur.");
    }
  });

  const handleDeleteMember = async (member: MemberSummary) => {
    if (!window.confirm("Supprimer cet agriculteur ? Cette action est irreversible.")) return;
    try {
      await deleteMember.mutateAsync(member.id);
      setSelectedMember(null);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de supprimer l'agriculteur.");
    }
  };

  return (
    <main>
      <PageIntro title="Membres" subtitle="Vue claire des membres, cultures, parcelles et statut operationnel." />

      <section className="premium-card reveal mb-4 rounded-2xl p-4" style={{ ["--delay" as string]: "40ms" }}>
        <div className="grid gap-3 lg:grid-cols-[1.3fr_1fr_1fr_auto]">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="soft-focus wf-input px-3 py-2.5 text-sm"
            placeholder="Rechercher un agriculteur..."
          />
          <select
            value={product}
            onChange={(event) => setProduct(event.target.value)}
            className="soft-focus wf-input px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            {specialtyOptions.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="soft-focus wf-input px-3 py-2.5 text-sm"
          >
            <option>Tous</option>
            <option value="active">Actif</option>
            <option value="seasonal">Saisonnier</option>
            <option value="inactive">Inactif</option>
          </select>
          <button
            type="button"
            onClick={openCreateForm}
            className="soft-focus wf-btn-primary px-4 py-2.5 text-sm font-semibold"
          >
            Ajouter agriculteur
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="grid grow gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Agriculteurs visibles</p>
              <p className="text-lg font-semibold text-[var(--text)]">{filtered.length}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Parcelles</p>
              <p className="text-lg font-semibold text-[var(--text)]">{totalParcels}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
              <p className="text-xs text-[var(--muted)]">Superficie totale</p>
              <p className="text-lg font-semibold text-[var(--text)]">{totalSurface.toFixed(1)} ha</p>
            </div>
          </div>

          <GlassViewToggle value={viewMode} onChange={setViewMode} className="shrink-0" />
        </div>
      </section>

      {filtered.length === 0 ? (
        <section className="premium-card reveal rounded-2xl p-6 text-center" style={{ ["--delay" as string]: "90ms" }}>
          <p className="text-sm text-[var(--muted)]">Aucun agriculteur ne correspond aux filtres.</p>
        </section>
      ) : viewMode === "table" ? (
        <section className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "90ms" }}>
          <div className="overflow-x-auto">
            <table className="wf-table min-w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="px-5 py-3.5">Nom</th>
                  <th className="px-5 py-3.5">Telephone</th>
                  <th className="px-5 py-3.5">Zone</th>
                  <th className="px-5 py-3.5">Culture principale</th>
                  <th className="px-5 py-3.5">Parcelles</th>
                  <th className="px-5 py-3.5">Statut</th>
                  <th className="px-5 py-3.5">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id}>
                    <td className="px-5 py-4 font-medium text-[var(--text)]">{item.fullName}</td>
                    <td className="px-5 py-4">{item.phone}</td>
                    <td className="px-5 py-4">{item.zone}</td>
                    <td className="px-5 py-4">
                      <StatusBadge label={item.culture} tone="info" />
                    </td>
                    <td className="px-5 py-4">{item.parcels}</td>
                    <td className="px-5 py-4">
                      <StatusBadge label={statusLabel[item.status] ?? item.status} tone={statusTone[item.status] ?? "info"} />
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <button className="text-xs font-semibold text-[var(--primary)] hover:underline" onClick={() => openMemberDetails(item)}>
                          Voir
                        </button>
                        <button className="text-xs font-semibold text-[var(--danger)] hover:underline" onClick={() => handleDeleteMember(item)}>
                          Supprimer
                        </button>
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
          {filtered.map((item, index) => (
            <article key={item.id} className="premium-card reveal rounded-2xl p-4" style={{ ["--delay" as string]: `${90 + index * 30}ms` }}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[var(--text)]">{item.fullName}</p>
                  <p className="text-xs text-[var(--muted)]">{item.zone}</p>
                </div>
                <StatusBadge label={statusLabel[item.status] ?? item.status} tone={statusTone[item.status] ?? "info"} />
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[11px] text-[var(--muted)]">Culture</p>
                  <p className="text-sm font-semibold text-[var(--text)]">{item.culture}</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-2">
                  <p className="text-[11px] text-[var(--muted)]">Superficie</p>
                  <p className="text-sm font-semibold text-[var(--text)]">{item.totalArea.toFixed(1)} ha</p>
                </div>
              </div>

              <p className="mt-3 text-xs text-[var(--muted)]">{item.phone}</p>

              <button className="mt-3 rounded-full border border-[var(--line)] px-2.5 py-1 text-xs font-semibold text-[var(--primary)] hover:border-[var(--primary)]" onClick={() => openMemberDetails(item)}>
                Ouvrir fiche
              </button>
            </article>
          ))}
        </section>
      )}

      <LiquidGlassModal
        open={Boolean(selectedMember)}
        onClose={() => setSelectedMember(null)}
        title={selectedMember?.fullName ?? "Details agriculteur"}
        subtitle={selectedMember ? `${selectedMember.zone} · ${selectedMember.phone}` : ""}
        size="lg"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button
              type="button"
              className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold"
              onClick={() => selectedMember && openEditForm(selectedMember)}
            >
              Modifier
            </button>
            <button
              type="button"
              className="soft-focus wf-btn-danger px-4 py-2 text-sm font-semibold"
              onClick={() => selectedMember && handleDeleteMember(selectedMember)}
            >
              Supprimer
            </button>
            <button className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" onClick={() => setSelectedMember(null)} type="button">
              Fermer la fiche
            </button>
          </div>
        }
      >
        {selectedMember && (
          <div className="space-y-3">
            <div className="inline-flex rounded-full border border-[var(--line)] bg-[var(--surface-soft)] p-1">
              {([
                ["profil", "Profil"],
                ["parcelles", "Parcelles"],
                ["activite", "Activite"],
              ] as Array<[MemberTab, string]>).map(([tab, label]) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={cx(
                    "soft-focus rounded-full px-3 py-1.5 text-xs font-semibold transition-all",
                    activeTab === tab ? "bg-[var(--primary)] text-white" : "text-[var(--text)] hover:bg-white/70",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>

            {activeTab === "profil" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                  <p className="text-xs text-[var(--muted)]">Culture principale</p>
                  <p className="text-sm font-semibold text-[var(--text)]">{selectedMember.culture}</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                  <p className="text-xs text-[var(--muted)]">Zone principale</p>
                  <p className="text-sm font-semibold text-[var(--text)]">{selectedMember.zone}</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                  <p className="text-xs text-[var(--muted)]">Parcelles actives</p>
                  <p className="text-sm font-semibold text-[var(--text)]">{selectedMember.parcels}</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2">
                  <p className="text-xs text-[var(--muted)]">Superficie totale</p>
                  <p className="text-sm font-semibold text-[var(--text)]">{selectedMember.totalArea.toFixed(1)} ha</p>
                </div>
              </div>
            )}

            {activeTab === "parcelles" && (
              <div className="space-y-2">
                {selectedFields.length === 0 && (
                  <p className="text-xs text-[var(--muted)]">Aucune parcelle enregistree.</p>
                )}
                {selectedFields.map((field) => (
                  <div key={field.id} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 text-sm">
                    <div className="flex items-center justify-between">
                      <p className="font-medium text-[var(--text)]">{field.location}</p>
                      <StatusBadge label="Active" tone="success" />
                    </div>
                    <p className="text-xs text-[var(--muted)]">{field.area.toFixed(1)} ha · Sol {field.soil_type ?? "non renseigne"}</p>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "activite" && (
              <div className="space-y-2">
                {memberActivity.map((activity) => (
                  <div key={activity.id} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2 text-sm">
                    <p className="font-medium text-[var(--text)]">{activity.title}</p>
                    <p className="text-xs text-[var(--muted)]">{activity.detail}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </LiquidGlassModal>

      <LiquidGlassModal
        open={formOpen}
        onClose={closeForm}
        title={editingMember ? "Modifier membre" : "Nouveau membre"}
        subtitle="Ces informations alimentent la base membre de la cooperative."
        size="md"
        footer={
          <div className="flex items-center justify-between gap-3">
            <button type="button" className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" onClick={closeForm}>
              Annuler
            </button>
            <button type="submit" form="member-form" className="soft-focus wf-btn-primary px-4 py-2 text-sm font-semibold" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        }
      >
        <form id="member-form" onSubmit={submitMember} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-[var(--text)]">
              Nom complet
              <input
                {...register("full_name", { required: "Nom requis." })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                placeholder="ex: Mamadou Diallo"
              />
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Village
              <input
                {...register("village", { required: "Village requis." })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                placeholder="Thies"
              />
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Telephone
              <input
                {...register("phone", { required: "Telephone requis." })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                placeholder="+221 77 ..."
              />
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Produit principal
              <input
                {...register("main_product", { required: "Produit principal requis." })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                placeholder="Mangue"
              />
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Nb de parcelles
              <input
                type="number"
                min="0"
                step="1"
                {...register("parcel_count", { required: "Nombre de parcelles requis.", valueAsNumber: true })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
              />
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Superficie (ha)
              <input
                type="number"
                min="0"
                step="0.1"
                {...register("area_hectares", { required: "Superficie requise.", valueAsNumber: true })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
              />
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Date d&apos;adhesion
              <input
                type="date"
                {...register("join_date", { required: "Date d'adhesion requise." })}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
              />
            </label>

            <label className="block text-sm font-medium text-[var(--text)]">
              Code interne (optionnel)
              <input
                {...register("code")}
                className="wf-input mt-2 h-11 w-full px-3 text-sm"
                placeholder="MBR-001"
              />
            </label>
          </div>

          <div>
            <p className="text-sm font-medium text-[var(--text)]">Statut</p>
            <div className="mt-2 grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setValue("status", "active", { shouldDirty: true })}
                className={cx(
                  "soft-focus rounded-xl border px-3 py-2 text-sm font-semibold transition-colors",
                  selectedStatus === "active"
                    ? "border-[#007E2F] bg-[#E8F4EC] text-[#007E2F]"
                    : "border-[var(--line)] bg-[var(--surface-soft)] text-[var(--muted)]",
                )}
              >
                Actif
              </button>
              <button
                type="button"
                onClick={() => setValue("status", "inactive", { shouldDirty: true })}
                className={cx(
                  "soft-focus rounded-xl border px-3 py-2 text-sm font-semibold transition-colors",
                  selectedStatus === "inactive"
                    ? "border-[var(--danger)] bg-[#FFEDEE] text-[var(--danger)]"
                    : "border-[var(--line)] bg-[var(--surface-soft)] text-[var(--muted)]",
                )}
              >
                Inactif
              </button>
              <button
                type="button"
                onClick={() => setValue("status", "seasonal", { shouldDirty: true })}
                className={cx(
                  "soft-focus rounded-xl border px-3 py-2 text-sm font-semibold transition-colors",
                  selectedStatus === "seasonal"
                    ? "border-[var(--info)] bg-[#EEF5FF] text-[var(--info)]"
                    : "border-[var(--line)] bg-[var(--surface-soft)] text-[var(--muted)]",
                )}
              >
                Saisonnier
              </button>
            </div>
          </div>
          {formError && (
            <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
              {formError}
            </p>
          )}
        </form>
      </LiquidGlassModal>
    </main>
  );
}
