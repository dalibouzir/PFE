"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { PageIntro } from "@/components/ui/PageIntro";
import { useAuth } from "@/context/auth/AuthContext";
import type { AuthUserUpdate } from "@/lib/api/types";

export default function ManagerSettingsPage() {
  const { user, updateProfile } = useAuth();
  const [notifCritical, setNotifCritical] = useState(true);
  const [notifCollecte, setNotifCollecte] = useState(true);
  const [notifTransformation, setNotifTransformation] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);

  const { register, handleSubmit, reset, formState } = useForm<AuthUserUpdate>({
    defaultValues: { full_name: "", email: "", phone: "" },
  });

  useEffect(() => {
    if (!user) return;
    reset({ full_name: user.full_name, email: user.email, phone: user.phone ?? "" });
  }, [user, reset]);

  const submitProfile = handleSubmit(async (values) => {
    setFormError(null);
    setFormSuccess(null);
    try {
      const payload: AuthUserUpdate = {
        full_name: values.full_name?.trim(),
        email: values.email?.trim(),
        phone: values.phone?.trim() || null,
      };
      await updateProfile(payload);
      setFormSuccess("Profil mis a jour.");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Impossible de mettre a jour le profil.");
    }
  });

  return (
    <main>
      <PageIntro title="Parametres" subtitle="Profil manager, cooperative et preferences." />

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "60ms" }}>
          <h3 className="text-base font-semibold text-[var(--text)]">Profil utilisateur</h3>
          <form onSubmit={submitProfile} className="mt-4 grid gap-3">
            <label className="block text-sm font-medium text-[var(--text)]">
              Nom complet
              <input
                {...register("full_name", { required: "Nom requis." })}
                className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              />
            </label>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Role</p>
              <p className="text-sm font-semibold text-[var(--text)]">{user?.role === "manager" ? "Manager cooperative" : "-"}</p>
            </div>
            <label className="block text-sm font-medium text-[var(--text)]">
              Email
              <input
                type="email"
                {...register("email", { required: "Email requis." })}
                className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              />
            </label>
            <label className="block text-sm font-medium text-[var(--text)]">
              Telephone
              <input
                {...register("phone")}
                className="mt-2 h-11 w-full rounded-xl border border-[var(--line)] bg-white/90 px-3 text-sm"
              />
            </label>
            {formError && (
              <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
                {formError}
              </p>
            )}
            {formSuccess && (
              <p className="rounded-lg border border-[#cfe3d4] bg-[#f2f7f4] px-3 py-2 text-xs text-[var(--muted)]">
                {formSuccess}
              </p>
            )}
            <button
              type="submit"
              className="soft-focus mt-2 rounded-xl bg-[var(--primary)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--primary-hover)]"
              disabled={formState.isSubmitting}
            >
              {formState.isSubmitting ? "Mise a jour..." : "Mettre a jour le profil"}
            </button>
          </form>
        </article>

        <article className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "120ms" }}>
          <h3 className="text-base font-semibold text-[var(--text)]">Informations cooperative</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3 sm:col-span-2">
              <p className="text-xs text-[var(--muted)]">Nom</p>
              <p className="text-sm font-semibold text-[var(--text)]">Non definie</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Code</p>
              <p className="text-sm font-semibold text-[var(--text)]">-</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Region</p>
              <p className="text-sm font-semibold text-[var(--text)]">-</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Managers</p>
              <p className="text-sm font-semibold text-[var(--text)]">-</p>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs text-[var(--muted)]">Agriculteurs</p>
              <p className="text-sm font-semibold text-[var(--text)]">-</p>
            </div>
          </div>
        </article>
      </section>

      <section className="premium-card reveal mt-4 rounded-2xl p-5" style={{ ["--delay" as string]: "180ms" }}>
        <h3 className="text-base font-semibold text-[var(--text)]">Preferences notifications</h3>
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
