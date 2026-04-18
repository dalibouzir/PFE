"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useAuth } from "@/context/auth/AuthContext";

type LoginForm = {
  email: string;
  password: string;
};

export function LoginExperience() {
  const router = useRouter();
  const { login } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setValue,
    formState: { isSubmitting },
  } = useForm<LoginForm>({
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const submitForm = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const profile = await login(values.email, values.password);
      router.push(profile.role === "admin" ? "/admin/dashboard" : "/manager/dashboard");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Connexion impossible.");
    }
  });

  const fillDemo = () => {
    setValue("email", "admin@weefarm.local");
    setValue("password", "Admin123!");
  };

  return (
    <main className="wf-login-page relative min-h-[100dvh] overflow-x-clip px-4 py-4 sm:px-[6vw] sm:py-5">
      <div className="auth-noise absolute inset-0" />
      <div className="wf-ambient wf-ambient-a" />
      <div className="wf-ambient wf-ambient-b" />

      <div className="relative z-10 mx-auto flex min-h-[calc(100dvh-2rem)] w-full max-w-[1020px] flex-col justify-between gap-4 sm:min-h-[calc(100dvh-2.5rem)]">
        <div className="flex flex-1 items-center">
          <section className="unified-enter w-full overflow-hidden rounded-[22px] border border-white/25 bg-transparent shadow-[0_20px_46px_rgba(7,47,33,0.28)]">
            <div className="grid min-h-[560px] grid-cols-1 md:min-h-[620px] md:grid-cols-[60%_40%]">
              <aside className="order-2 flex h-full flex-col bg-gradient-to-r from-[#90d0b5] to-[#89c7c8] px-7 py-6 text-[#173126] sm:px-10 md:order-1">
                <div className="flex items-start justify-between gap-4">
                  <Image
                    src="/logo.png"
                    alt="Logo WeeFarm"
                    width={138}
                    height={58}
                    className="h-auto w-[118px] object-contain sm:w-[132px]"
                    priority
                  />
                  <div className="pt-1 text-center">
                    <p className="text-[26px] font-semibold leading-none tracking-[0.01em] text-[#163527]">WeeFarm</p>
                    <p className="mt-1 text-[15px] font-medium text-[#2f5f4a]">AI-first cooperative operations dashboard</p>
                  </div>
                </div>

                <div className="mt-5 max-w-[560px] space-y-3">
                  <h1 className="text-[30px] font-bold leading-[1.14] tracking-[-0.01em] text-[#1a3d2f] sm:text-[36px]">
                    Pilotage operations cooperative, de la collecte au bilan matiere.
                  </h1>
                  <p className="max-w-[520px] text-[14px] leading-relaxed text-[#23483a]/90">
                    Interface demo pour administrer les cooperatives, suivre les membres, les lots, les stocks et les
                    transformations post-recolte.
                  </p>
                </div>

                <div className="wf-liquid-card mt-7 rounded-2xl p-5 sm:mt-8 sm:p-6">
                  <ul className="space-y-1.5 text-[14px] font-medium leading-relaxed text-[#163529]">
                    <li>- Gestion cooperatives et managers (admin)</li>
                    <li>- Suivi membres, parcelles, stocks et lots (manager)</li>
                    <li>- Transformations et analytique operationnelle</li>
                  </ul>
                  <p className="mt-3 text-[13px] leading-relaxed text-[#1e4335]/90">
                    Support: <span className="font-semibold text-[#18392c]">support@wefarm.sn</span>
                  </p>
                </div>
              </aside>

              <aside className="order-1 h-full border-b border-white/35 bg-[#edf1f2]/95 px-8 py-7 md:order-2 md:border-b-0 md:border-l md:px-10">
                <div className="mx-auto flex h-full max-w-[330px] flex-col justify-start pt-4">
                  <div className="flex justify-center">
                    <Image src="/logo.png" alt="Logo WeeFarm" width={180} height={70} className="h-auto w-[160px] object-contain" priority />
                  </div>
                  <h3 className="mt-5 text-center text-[20px] font-medium text-[#18382d]">Connexion</h3>
                  <p className="mt-1 text-center text-[13px] text-[#4e635b]">Acces demo role-based</p>

                  <form className="mt-6 space-y-3.5" onSubmit={submitForm}>
                    <label className="block text-[14px] font-medium text-[#243730]">
                      Email
                      <input
                        type="email"
                        autoComplete="email"
                        placeholder="nom@cooperative.sn"
                        {...register("email", { required: "Email requis." })}
                        className="mt-2 h-12 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3.5 text-[14px] text-[var(--text)] outline-none transition focus:border-[var(--primary)] focus:ring-4 focus:ring-[#007E2F]/15"
                      />
                    </label>

                    <label className="block text-[14px] font-medium text-[#243730]">
                      Mot de passe
                      <input
                        type="password"
                        autoComplete="current-password"
                        placeholder="••••••••"
                        {...register("password", { required: "Mot de passe requis." })}
                        className="mt-2 h-12 w-full rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3.5 text-[14px] text-[var(--text)] outline-none transition focus:border-[var(--primary)] focus:ring-4 focus:ring-[#007E2F]/15"
                      />
                    </label>

                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="mt-1 h-12 w-full rounded-xl bg-[var(--primary)] px-4 text-[15px] font-semibold text-white shadow-[0_10px_18px_rgba(0,126,47,0.22)] transition hover:-translate-y-[1px] hover:bg-[var(--primary-hover)] hover:shadow-[0_14px_24px_rgba(0,126,47,0.28)] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      {isSubmitting ? "Connexion..." : "Se connecter"}
                    </button>

                    {formError && (
                      <p className="rounded-lg border border-[#f2c7c7] bg-[#fff1f1] px-3 py-2 text-xs text-[#8f2f2f]">
                        {formError}
                      </p>
                    )}
                  </form>

                  <div className="mt-5 flex items-center gap-3">
                    <div className="h-px flex-1 bg-[#c9d5cf]" />
                    <span className="text-[11px] uppercase tracking-[0.1em] text-[#6a7d75]">Demonstration</span>
                    <div className="h-px flex-1 bg-[#c9d5cf]" />
                  </div>

                  <div className="mt-3 grid gap-2">
                    <button
                      type="button"
                      onClick={fillDemo}
                      className="block w-full rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-4 py-2.5 text-center text-[14px] font-medium text-[var(--text)] transition hover:border-[var(--primary)] hover:bg-[#eef7f1]"
                    >
                      Utiliser le demo Admin
                    </button>
                  </div>

                  <div className="mt-4 text-center text-[12px] text-[#6a7d75]">Donnees locales de demonstration</div>
                </div>
              </aside>
            </div>
          </section>
        </div>

        <footer className="flex items-center justify-between gap-3 rounded-xl border border-white/20 bg-black/20 px-3 py-2 text-[11px] text-white/85 backdrop-blur-md sm:px-4 sm:text-xs">
          <div className="flex items-center gap-2">
            <Image src="/logo.png" alt="Logo WeeFarm" width={24} height={24} className="h-5 w-6 object-contain" />
            <span className="font-medium tracking-[0.04em]">WEEFARM</span>
          </div>
          <span className="whitespace-nowrap text-white/75">Demo locale WeeFarm</span>
        </footer>
      </div>
    </main>
  );
}
