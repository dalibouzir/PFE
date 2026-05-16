"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowLeft, ArrowUpRight, CircleAlert } from "lucide-react";
import { Pie, PieChart, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  useInstitutionAdminCooperativeUsers,
  useInstitutionAdminInsightsCooperativeMembers,
} from "@/hooks/useInstitutionAdmin";
import {
  useSuperAdminCooperativeUsers,
  useSuperAdminInsightsCooperativeMembers,
} from "@/hooks/useSuperAdmin";
import type { CooperativeOversightResponse, CooperativeOversightRow } from "@/lib/api/types";

type Scope = "super_admin" | "institution_admin";
type Attention = "Critique" | "À surveiller" | "Normal";
type FilterKey = "all" | "normal" | "watch" | "critical" | "independent";

const palette = {
  green: "#007E2F",
  dark: "#064E3B",
  soft: "#E8F5EE",
  amber: "#D99A00",
  red: "#DC2626",
  slate: "#64748B",
};

function formatKg(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(value)} kg`;
}

function formatPct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(value)} %`;
}

function formatInt(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(value);
}

function attentionLevel(row: CooperativeOversightRow): Attention {
  if (row.loss_rate >= 20 || row.low_stock_alerts_count > 0) return "Critique";
  if (row.loss_rate >= 10 || row.efficiency_rate < 80) return "À surveiller";
  return "Normal";
}

function attentionTone(label: Attention): "danger" | "warning" | "info" {
  if (label === "Critique") return "danger";
  if (label === "À surveiller") return "warning";
  return "info";
}

function roleLabel(role: string) {
  if (role === "manager") return "Manager";
  if (role === "viewer") return "Lecture seule";
  if (role === "owner") return "Propriétaire";
  return role;
}

function insightSentence(level: Attention): string {
  if (level === "Critique") return "Cette coopérative nécessite une attention prioritaire.";
  if (level === "À surveiller") return "Cette coopérative présente des signaux à surveiller.";
  return "Cette coopérative présente une situation globalement stable.";
}

function AttentionBadge({ label }: { label: Attention }) {
  const tone = attentionTone(label);
  const classes =
    tone === "danger"
      ? "border-[#f0d6d6] bg-[#fff1f1] text-[#a23f3f]"
      : tone === "warning"
        ? "border-[#f2e8c7] bg-[#fff9ea] text-[#9a6b00]"
        : "border-[#d4e5dc] bg-[#eef8f2] text-[#0b6b43]";
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${classes}`}>{label}</span>;
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="premium-card reveal rounded-2xl p-5">
      <p className="text-xs uppercase tracking-wide text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-[var(--text)]">{value}</p>
    </article>
  );
}

function SignalCard({ title, level }: { title: string; level: "Critique" | "À surveiller" | "Normal" | "Faible" }) {
  const isCritical = level === "Critique";
  const isWatch = level === "À surveiller" || level === "Faible";
  const badgeClass = isCritical
    ? "bg-[#fff1f1] text-[#a23f3f] border-[#f0d6d6]"
    : isWatch
      ? "bg-[#fff9ea] text-[#9a6b00] border-[#f2e8c7]"
      : "bg-[#eef8f2] text-[#0b6b43] border-[#d4e5dc]";
  return (
    <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
      <p className="text-xs uppercase text-[var(--muted)]">{title}</p>
      <span className={`mt-2 inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${badgeClass}`}>{level}</span>
    </div>
  );
}

function EmptyTrendCard({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <article className="premium-card reveal rounded-2xl p-5">
      <h3 className="text-base font-semibold text-[#064E3B]">{title}</h3>
      <div className="mt-3 rounded-xl border border-[var(--line)] bg-[#E8F5EE] px-3 py-6 text-sm text-[var(--muted)]">{subtitle}</div>
    </article>
  );
}

export function CooperativeOversightOverview({
  scope,
  data,
  isLoading,
  isError,
  error,
  institutionsCount,
  institutionName,
}: {
  scope: Scope;
  data?: CooperativeOversightResponse;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  institutionsCount?: number;
  institutionName?: string | null;
}) {
  const summary = data?.summary;
  const rows = useMemo(() => data?.cooperatives || [], [data?.cooperatives]);
  const [searchValue, setSearchValue] = useState("");
  const [filterKey, setFilterKey] = useState<FilterKey>("all");
  const basePath = scope === "super_admin" ? "/super-admin/oversight" : "/institution-admin/oversight";

  const visibleRows = useMemo(() => {
    const query = searchValue.trim().toLowerCase();
    return rows.filter((row) => {
      const level = attentionLevel(row);
      const byFilter =
        filterKey === "all"
          ? true
          : filterKey === "normal"
            ? level === "Normal"
            : filterKey === "watch"
              ? level === "À surveiller"
              : filterKey === "critical"
                ? level === "Critique"
                : row.institution_id === null;
      if (!byFilter) return false;
      if (!query) return true;
      return row.cooperative_name.toLowerCase().includes(query) || (row.institution_name || "").toLowerCase().includes(query);
    });
  }, [rows, searchValue, filterKey]);

  const topSummaryLine =
    scope === "super_admin"
      ? `Institutions: ${formatInt(institutionsCount || 0)} · Coopératives: ${formatInt(summary?.total_cooperatives || 0)} · Membres: ${formatInt(summary?.total_members || 0)}`
      : `Institution: ${institutionName || "—"} · Coopératives: ${formatInt(summary?.total_cooperatives || 0)} · Membres: ${formatInt(summary?.total_members || 0)}`;

  return (
    <main>
      <PageIntro
        title="Insights coopératives"
        subtitle={scope === "super_admin" ? "Vue consolidée des performances coopératives." : "Vue institutionnelle des performances coopératives."}
      />
      {isLoading && <section className="premium-card reveal mb-4 rounded-2xl p-4 text-sm text-[var(--muted)]">Chargement des insights...</section>}
      {isError && <section className="premium-card reveal mb-4 rounded-2xl p-4 text-sm text-[#8f2f2f]">{error instanceof Error ? error.message : "Impossible de charger les insights."}</section>}

      {!isLoading && !isError && summary && (
        <>
          <section className="premium-card reveal rounded-2xl border border-[#d5e8dc] bg-[linear-gradient(180deg,#f4fbf7_0%,#e8f5ee_100%)] p-5">
            <p className="text-xs uppercase tracking-[0.08em] text-[#0b6b43]">{scope === "super_admin" ? "Synthèse plateforme" : "Synthèse institution"}</p>
            <p className="mt-1 text-lg font-semibold text-[#064E3B]">{topSummaryLine}</p>
            <p className="mt-2 text-sm text-[#365a4b]">
              Lots actifs: {formatInt(summary.active_lots)} · Stock disponible: {formatKg(summary.total_available_stock_kg)} · Efficacité moyenne: {formatPct(summary.avg_efficiency_rate)} · Perte moyenne: {formatPct(summary.avg_loss_rate)}
            </p>
          </section>

          <section className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <KpiCard label="Total coopératives" value={formatInt(summary.total_cooperatives)} />
            <KpiCard label="Total membres" value={formatInt(summary.total_members)} />
            <KpiCard label="Lots actifs" value={formatInt(summary.active_lots)} />
            <KpiCard label="Stock disponible" value={formatKg(summary.total_available_stock_kg)} />
            <KpiCard label="Perte moyenne" value={formatPct(summary.avg_loss_rate)} />
            <KpiCard label="Efficacité moyenne" value={formatPct(summary.avg_efficiency_rate)} />
          </section>

          <section className="mt-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-base font-semibold text-[var(--green-900)]">Coopératives</h3>
              <input
                type="text"
                value={searchValue}
                onChange={(event) => setSearchValue(event.target.value)}
                placeholder="Rechercher coopérative / institution..."
                className="w-full rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-sm text-[var(--text)] sm:w-72"
              />
            </div>
            <div className="mb-3 flex flex-wrap gap-2">
              {[
                { key: "all", label: "Tous" },
                { key: "normal", label: "Normal" },
                { key: "watch", label: "À surveiller" },
                { key: "critical", label: "Critique" },
                ...(scope === "super_admin" ? [{ key: "independent", label: "Indépendantes" }] : []),
              ].map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setFilterKey(item.key as FilterKey)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${
                    filterKey === item.key ? "border-[#007E2F] bg-[#E8F5EE] text-[#007E2F]" : "border-[var(--line)] bg-white text-[var(--muted)]"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <div className="overflow-x-auto rounded-xl border border-[var(--line)]">
              <table className="min-w-[1080px] w-full text-left text-sm">
                <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
                  <tr>
                    <th className="px-3 py-2">Coopérative</th>
                    <th className="px-3 py-2">Institution</th>
                    <th className="px-3 py-2">Statut</th>
                    <th className="px-3 py-2">Membres</th>
                    <th className="px-3 py-2">Lots actifs</th>
                    <th className="px-3 py-2">Prêt post-récolte</th>
                    <th className="px-3 py-2">Stock disponible</th>
                    <th className="px-3 py-2">Perte</th>
                    <th className="px-3 py-2">Efficacité</th>
                    <th className="px-3 py-2">Attention</th>
                    <th className="px-3 py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row) => (
                    <tr key={row.cooperative_id} className="border-t border-[var(--line)]">
                      <td className="px-3 py-2 font-medium text-[var(--text)]">{row.cooperative_name}</td>
                      <td className="px-3 py-2">{row.institution_name || "Indépendante"}</td>
                      <td className="px-3 py-2"><StatusBadge label={row.status} tone={row.status === "active" ? "success" : "warning"} /></td>
                      <td className="px-3 py-2">{formatInt(row.members_count)}</td>
                      <td className="px-3 py-2">{formatInt(row.active_lots_count)}</td>
                      <td className="px-3 py-2">{formatInt(row.ready_post_recolte_lots_count)}</td>
                      <td className="px-3 py-2">{formatKg(row.available_stock_kg)}</td>
                      <td className="px-3 py-2">{formatPct(row.loss_rate)}</td>
                      <td className="px-3 py-2">{formatPct(row.efficiency_rate)}</td>
                      <td className="px-3 py-2"><AttentionBadge label={attentionLevel(row)} /></td>
                      <td className="px-3 py-2">
                        <Link href={`${basePath}/${row.cooperative_id}`} className="inline-flex items-center gap-1 rounded-lg border border-[#d4e5dc] bg-[#eef8f2] px-2.5 py-1.5 text-xs font-semibold text-[#0b6b43] hover:bg-[#e4f2ea]">
                          Voir plus <ArrowUpRight className="h-3.5 w-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                  {visibleRows.length === 0 && (
                    <tr><td colSpan={11} className="px-3 py-6 text-center text-sm text-[var(--muted)]">Aucune coopérative pour ce filtre.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

export function CooperativeOversightDetail({
  scope,
  cooperativeId,
  data,
  isLoading,
  isError,
  error,
}: {
  scope: Scope;
  cooperativeId: string;
  data?: CooperativeOversightResponse;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
}) {
  const rows = data?.cooperatives || [];
  const selectedRow = rows.find((row) => String(row.cooperative_id) === cooperativeId) || null;
  const basePath = scope === "super_admin" ? "/super-admin/oversight" : "/institution-admin/oversight";

  const superUsersQuery = useSuperAdminCooperativeUsers(cooperativeId, scope === "super_admin" && Boolean(selectedRow));
  const institutionUsersQuery = useInstitutionAdminCooperativeUsers(cooperativeId, scope === "institution_admin" && Boolean(selectedRow));
  const superMembersQuery = useSuperAdminInsightsCooperativeMembers(cooperativeId, scope === "super_admin" && Boolean(selectedRow));
  const institutionMembersQuery = useInstitutionAdminInsightsCooperativeMembers(cooperativeId, scope === "institution_admin" && Boolean(selectedRow));

  const users = scope === "super_admin" ? superUsersQuery.data || [] : institutionUsersQuery.data || [];
  const usersLoading = scope === "super_admin" ? superUsersQuery.isLoading : institutionUsersQuery.isLoading;
  const usersError = scope === "super_admin" ? superUsersQuery.error : institutionUsersQuery.error;
  const usersIsError = scope === "super_admin" ? superUsersQuery.isError : institutionUsersQuery.isError;

  const members = scope === "super_admin" ? superMembersQuery.data || [] : institutionMembersQuery.data || [];
  const membersLoading = scope === "super_admin" ? superMembersQuery.isLoading : institutionMembersQuery.isLoading;
  const membersError = scope === "super_admin" ? superMembersQuery.error : institutionMembersQuery.error;
  const membersIsError = scope === "super_admin" ? superMembersQuery.isError : institutionMembersQuery.isError;

  const attention = selectedRow ? attentionLevel(selectedRow) : null;

  return (
    <main>
      <div className="mb-4">
        <Link href={basePath} className="inline-flex items-center gap-1 text-sm font-medium text-[#0b6b43] hover:underline">
          <ArrowLeft className="h-4 w-4" /> Retour aux coopératives
        </Link>
      </div>
      <PageIntro title="Insights coopératives" subtitle="Dashboard coopératif détaillé (lecture seule)." />

      {isLoading && <section className="premium-card reveal mb-4 rounded-2xl p-4 text-sm text-[var(--muted)]">Chargement des insights...</section>}
      {isError && <section className="premium-card reveal mb-4 rounded-2xl p-4 text-sm text-[#8f2f2f]">{error instanceof Error ? error.message : "Impossible de charger les insights."}</section>}
      {!isLoading && !isError && !selectedRow && (
        <section className="premium-card reveal rounded-2xl p-5 text-sm text-[var(--muted)]">
          Coopérative non trouvée dans votre périmètre d’accès.
        </section>
      )}

      {!isLoading && !isError && selectedRow && attention && (
        <>
          <section className="premium-card reveal rounded-2xl border border-[#d5e8dc] bg-[linear-gradient(180deg,#f4fbf7_0%,#e8f5ee_100%)] p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-lg font-semibold text-[#064E3B]">{selectedRow.cooperative_name}</p>
              <AttentionBadge label={attention} />
            </div>
            <p className="mt-1 text-sm text-[#365a4b]">
              {selectedRow.institution_name || "Indépendante"} · Statut: {selectedRow.status} · Membres: {formatInt(selectedRow.members_count)} · Utilisateurs: {formatInt(selectedRow.users_count)} · Lots actifs: {formatInt(selectedRow.active_lots_count)} · Prêt post-récolte: {formatInt(selectedRow.ready_post_recolte_lots_count)} · Stock disponible: {formatKg(selectedRow.available_stock_kg)} · Perte: {formatPct(selectedRow.loss_rate)} · Efficacité: {formatPct(selectedRow.efficiency_rate)}
            </p>
            <p className="mt-2 text-sm text-[#365a4b]">{insightSentence(attention)}</p>
          </section>

          <section className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="Membres / producteurs" value={formatInt(selectedRow.members_count)} />
            <KpiCard label="Utilisateurs actifs" value={formatInt(selectedRow.users_count)} />
            <KpiCard label="Lots actifs" value={formatInt(selectedRow.active_lots_count)} />
            <KpiCard label="Prêt post-récolte" value={formatInt(selectedRow.ready_post_recolte_lots_count)} />
            <KpiCard label="Stock disponible" value={formatKg(selectedRow.available_stock_kg)} />
            <KpiCard label="Stock total" value={formatKg(selectedRow.total_stock_kg)} />
            <KpiCard label="Perte" value={formatPct(selectedRow.loss_rate)} />
            <KpiCard label="Efficacité" value={formatPct(selectedRow.efficiency_rate)} />
          </section>

          <section className="mt-4 grid gap-4 xl:grid-cols-2">
            <article className="premium-card reveal rounded-2xl p-5">
              <h3 className="text-base font-semibold text-[var(--green-900)]">Managers / Utilisateurs</h3>
              <div className="mt-3 overflow-x-auto rounded-xl border border-[var(--line)]">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
                    <tr>
                      <th className="px-3 py-2">Nom</th>
                      <th className="px-3 py-2">Email</th>
                      <th className="px-3 py-2">Téléphone</th>
                      <th className="px-3 py-2">Rôle</th>
                      <th className="px-3 py-2">Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usersLoading && <tr><td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted)]">Chargement...</td></tr>}
                    {usersIsError && <tr><td colSpan={5} className="px-3 py-6 text-center text-sm text-[#8f2f2f]">{usersError instanceof Error ? usersError.message : "Impossible de charger."}</td></tr>}
                    {!usersLoading && !usersIsError && users.map((user) => (
                      <tr key={user.id} className="border-t border-[var(--line)]">
                        <td className="px-3 py-2 font-medium">{user.full_name}</td>
                        <td className="px-3 py-2">{user.email}</td>
                        <td className="px-3 py-2">{user.phone || "—"}</td>
                        <td className="px-3 py-2">{roleLabel(user.role)}</td>
                        <td className="px-3 py-2"><StatusBadge label={user.status} tone={user.status === "active" ? "success" : "warning"} /></td>
                      </tr>
                    ))}
                    {!usersLoading && !usersIsError && users.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted)]">Aucun utilisateur.</td></tr>}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="premium-card reveal rounded-2xl p-5">
              <h3 className="text-base font-semibold text-[var(--green-900)]">Membres / Producteurs</h3>
              <div className="mt-3 overflow-x-auto rounded-xl border border-[var(--line)]">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
                    <tr>
                      <th className="px-3 py-2">Nom</th>
                      <th className="px-3 py-2">Téléphone</th>
                      <th className="px-3 py-2">Parcelles</th>
                      <th className="px-3 py-2">Surface totale</th>
                      <th className="px-3 py-2">Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {membersLoading && <tr><td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted)]">Chargement...</td></tr>}
                    {membersIsError && <tr><td colSpan={5} className="px-3 py-6 text-center text-sm text-[#8f2f2f]">{membersError instanceof Error ? membersError.message : "Impossible de charger."}</td></tr>}
                    {!membersLoading && !membersIsError && members.map((member) => (
                      <tr key={member.id} className="border-t border-[var(--line)]">
                        <td className="px-3 py-2 font-medium">{member.full_name}</td>
                        <td className="px-3 py-2">{member.phone || "—"}</td>
                        <td className="px-3 py-2">{formatInt(member.parcel_count)}</td>
                        <td className="px-3 py-2">{new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(member.area_hectares)} ha</td>
                        <td className="px-3 py-2"><StatusBadge label={member.status} tone={member.status === "active" ? "success" : "warning"} /></td>
                      </tr>
                    ))}
                    {!membersLoading && !membersIsError && members.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-sm text-[var(--muted)]">Aucun producteur enregistré pour cette coopérative.</td></tr>}
                  </tbody>
                </table>
              </div>
            </article>
          </section>

          <section className="mt-4 grid gap-4 xl:grid-cols-2">
            <EmptyTrendCard title="Stock activity (IN / OUT / disponible)" subtitle="Historique mensuel du stock non encore connecté." />

            <article className="premium-card reveal rounded-2xl p-5">
              <h3 className="text-base font-semibold text-[#064E3B]">Répartition des lots</h3>
              <div className="mt-3 h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        { name: "Lots actifs", value: selectedRow.active_lots_count },
                        { name: "Prêt post-récolte", value: selectedRow.ready_post_recolte_lots_count },
                        {
                          name: "Autres",
                          value: Math.max(0, (selectedRow.lots_count || 0) - (selectedRow.active_lots_count || 0) - (selectedRow.ready_post_recolte_lots_count || 0)),
                        },
                      ]}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={90}
                      dataKey="value"
                    >
                      <Cell fill={palette.green} />
                      <Cell fill={palette.amber} />
                      <Cell fill={palette.slate} />
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </article>
          </section>

          <section className="premium-card reveal mt-4 rounded-2xl p-5">
            <h3 className="flex items-center gap-2 text-base font-semibold text-[var(--green-900)]">
              <CircleAlert className="h-4 w-4" /> Signaux d’attention
            </h3>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <SignalCard title="Alerte stock" level={selectedRow.low_stock_alerts_count > 0 ? "Critique" : "Normal"} />
              <SignalCard title="Risque perte" level={selectedRow.loss_rate >= 20 ? "Critique" : selectedRow.loss_rate >= 10 ? "À surveiller" : "Normal"} />
              <SignalCard title="Signal efficacité" level={selectedRow.efficiency_rate < 70 ? "Critique" : selectedRow.efficiency_rate < 80 ? "À surveiller" : "Normal"} />
              <SignalCard title="Activité opérationnelle" level={selectedRow.active_lots_count === 0 ? "Faible" : "Normal"} />
            </div>
          </section>
        </>
      )}
    </main>
  );
}
