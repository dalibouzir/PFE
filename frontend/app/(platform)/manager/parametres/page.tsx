"use client";

import { useState } from "react";
import { PageIntro } from "@/components/ui/PageIntro";
import { cooperativeProfile, managerProfile } from "@/lib/mock-data";

export default function ManagerSettingsPage() {
  const [notifCritical, setNotifCritical] = useState(true);
  const [notifCollecte, setNotifCollecte] = useState(true);
  const [notifTransformation, setNotifTransformation] = useState(false);

  return (
    <main>
      <PageIntro title="Parametres" subtitle="Profil manager, cooperative et preferences." />

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "60ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Profil utilisateur</h3>
          <div className="mt-4 grid gap-3">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Nom</p>
              <p className="text-sm font-semibold text-[var(--text)]">{managerProfile.nom}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Role</p>
              <p className="text-sm font-semibold text-[var(--text)]">{managerProfile.role}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Email</p>
              <p className="text-sm font-semibold text-[var(--text)]">{managerProfile.email}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Telephone</p>
              <p className="text-sm font-semibold text-[var(--text)]">{managerProfile.telephone}</p>
            </div>
          </div>
        </article>

        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "120ms" }}>
          <h3 className="text-base font-semibold text-[var(--green-900)]">Informations cooperative</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3 sm:col-span-2">
              <p className="text-xs text-[var(--muted)]">Nom</p>
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
              <p className="text-xs text-[var(--muted)]">Managers</p>
              <p className="text-sm font-semibold text-[var(--text)]">{cooperativeProfile.managers}</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Membres</p>
              <p className="text-sm font-semibold text-[var(--text)]">{cooperativeProfile.membres}</p>
            </div>
          </div>
        </article>
      </section>

      <section className="premium-card reveal mt-4 rounded-2xl p-5" style={{ ["--delay" as string]: "180ms" }}>
        <h3 className="text-base font-semibold text-[var(--green-900)]">Preferences notifications</h3>
        <div className="mt-4 space-y-3">
          <label className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
            <span className="text-sm text-[var(--text)]">Alertes critiques stocks/lots</span>
            <input type="checkbox" checked={notifCritical} onChange={(event) => setNotifCritical(event.target.checked)} className="h-4 w-4 accent-[var(--green-700)]" />
          </label>
          <label className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
            <span className="text-sm text-[var(--text)]">Resume quotidien collecte</span>
            <input type="checkbox" checked={notifCollecte} onChange={(event) => setNotifCollecte(event.target.checked)} className="h-4 w-4 accent-[var(--green-700)]" />
          </label>
          <label className="flex items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
            <span className="text-sm text-[var(--text)]">Retards transformations</span>
            <input type="checkbox" checked={notifTransformation} onChange={(event) => setNotifTransformation(event.target.checked)} className="h-4 w-4 accent-[var(--green-700)]" />
          </label>
        </div>
      </section>
    </main>
  );
}
