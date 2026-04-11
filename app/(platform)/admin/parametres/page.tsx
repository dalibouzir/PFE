"use client";

import { useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { cooperativeProfile } from "@/lib/mock-data";

export default function AdminSettingsPage() {
  const [alertsEmail, setAlertsEmail] = useState(true);
  const [weeklyDigest, setWeeklyDigest] = useState(true);
  const [multiRegionReview, setMultiRegionReview] = useState(false);

  return (
    <main>
      <PageIntro title="Parametres" subtitle="Profil administrateur et preferences plateforme." />

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "60ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Profil administrateur</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Nom</p>
              <p className="text-sm font-semibold text-[var(--text)]">Mariam Seck</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Role</p>
              <p className="text-sm font-semibold text-[var(--text)]">Admin plateforme</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3 sm:col-span-2">
              <p className="text-xs text-[var(--muted)]">Email</p>
              <p className="text-sm font-semibold text-[var(--text)]">admin@wefarm.sn</p>
            </div>
          </div>
        </article>

        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "120ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Plateforme</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Cooperative reference</p>
              <p className="text-sm font-semibold text-[var(--text)]">{cooperativeProfile.nom}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Code</p>
              <p className="text-sm font-semibold text-[var(--text)]">{cooperativeProfile.code}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Region</p>
              <p className="text-sm font-semibold text-[var(--text)]">{cooperativeProfile.region}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Membres demo</p>
              <p className="text-sm font-semibold text-[var(--text)]">{cooperativeProfile.membres}</p>
            </div>
          </div>
        </article>
      </section>

      <section className="premium-card reveal mt-4 rounded-2xl p-5" style={{ ["--delay" as string]: "180ms" }}>
        <h3 className="text-base font-semibold text-[var(--green-900)]">Preferences notifications</h3>
        <div className="mt-4 space-y-3">
          <label className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
            <span className="text-sm text-[var(--text)]">Alertes critiques par email</span>
            <input type="checkbox" checked={alertsEmail} onChange={(event) => setAlertsEmail(event.target.checked)} className="h-4 w-4 accent-[var(--green-700)]" />
          </label>
          <label className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
            <span className="text-sm text-[var(--text)]">Digest hebdomadaire cooperatives</span>
            <input type="checkbox" checked={weeklyDigest} onChange={(event) => setWeeklyDigest(event.target.checked)} className="h-4 w-4 accent-[var(--green-700)]" />
          </label>
          <label className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
            <span className="text-sm text-[var(--text)]">Revues inter-regions</span>
            <input type="checkbox" checked={multiRegionReview} onChange={(event) => setMultiRegionReview(event.target.checked)} className="h-4 w-4 accent-[var(--green-700)]" />
          </label>
        </div>
      </section>
    </main>
  );
}
