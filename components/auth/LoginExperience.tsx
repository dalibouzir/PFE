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

const SMART_BANNER_ITEMS = [
  "🌍 Piloter les coopératives",
  "📦 Suivre les lots actifs",
  "🔁 Pré-récolte → Post-récolte",
  "📊 Stock réel en temps réel",
  "🧭 Flux matière maîtrisé",
  "⚠️ Pertes détectées",
  "🔎 Écarts expliqués",
  "💡 Insights par lot",
  "🚜 Recommandations terrain",
  "✅ Décisions basées données",
];

export function LoginExperience() {
  const router = useRouter();
  const { login } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
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
      if (profile.role === "super_admin") {
        router.push("/super-admin/dashboard");
        return;
      }
      if (profile.role === "institution_admin") {
        router.push("/institution-admin/dashboard");
        return;
      }
      router.push(profile.role === "admin" ? "/admin/dashboard" : "/manager/dashboard");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Connexion impossible.");
    }
  });

  return (
    <main className="wf-login-page relative min-h-[100dvh] overflow-x-clip px-4 py-4 sm:px-[6vw] sm:py-5">
      <div className="auth-noise absolute inset-0" />
      <div className="wf-ambient wf-ambient-a" />
      <div className="wf-ambient wf-ambient-b" />

      <div className="relative z-10 mx-auto flex min-h-[calc(100dvh-2rem)] w-full max-w-[1140px] flex-col justify-between gap-4 sm:min-h-[calc(100dvh-2.5rem)]">
        <div className="flex flex-1 flex-col gap-3">
          <div className="smart-banner mx-auto w-full overflow-hidden bg-transparent py-2">
            <p className="px-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-[#1c4a37]">WeeFarm Intelligence Opérationnelle</p>
            <div className="marquee-track mt-2">
              {[...SMART_BANNER_ITEMS, ...SMART_BANNER_ITEMS].map((item, index) => (
                <span key={`${item}-${index}`} className="marquee-chip">
                  {item}
                </span>
              ))}
            </div>
          </div>
          <div className="flex flex-1 items-center">
          <section className="unified-enter mx-auto w-full overflow-hidden rounded-[22px] border border-white/25 bg-transparent shadow-[0_20px_46px_rgba(7,47,33,0.28)]">
            <div className="grid min-h-[560px] grid-cols-1 md:min-h-[620px] md:grid-cols-[58%_42%]">
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
                <div className="mt-8 max-w-[520px]">
                  <p className="text-[30px] font-semibold leading-[1.15] tracking-[-0.01em] text-[#153629] sm:text-[36px]">
                    WeeFarm centralise la gestion opérationnelle des coopératives agricoles.
                  </p>
                  <p className="mt-4 text-[15px] leading-relaxed text-[#23483a]/90">
                    Une plateforme intelligente pour suivre les membres, les lots, la collecte, les stocks, les avances producteurs,
                    la trésorerie et la commercialisation — avec des insights IA pour mieux décider sur le terrain.
                  </p>
                  <Image
                    src="/hand-plant.png"
                    alt="Récolte et suivi terrain"
                    width={560}
                    height={260}
                    className="mt-6 h-[170px] w-full rounded-2xl border border-white/40 object-cover shadow-[0_16px_28px_rgba(8,53,38,0.2)] sm:h-[210px]"
                    priority
                  />
                </div>

              </aside>

              <aside className="order-1 h-full border-b border-white/35 bg-[#edf1f2]/95 px-8 py-7 md:order-2 md:border-b-0 md:border-l md:px-10">
                <div className="mx-auto flex h-full max-w-[360px] flex-col justify-start pt-4">
                  <div className="flex justify-center">
                    <Image src="/logo.png" alt="Logo WeeFarm" width={180} height={70} className="h-auto w-[160px] object-contain" priority />
                  </div>
                  <h3 className="mt-5 text-center text-[20px] font-medium text-[#18382d]">Connexion</h3>
                  <p className="mt-1 text-center text-[13px] text-[#4e635b]">Acces role-based</p>

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
                  <p className="mt-4 text-center text-[12px] text-[#254a3a]">
                    Support: <span className="font-semibold text-[#1a3d2f]">support@wefarm.sn</span>
                  </p>

                </div>
              </aside>
            </div>
          </section>
        </div>
        </div>

        <footer className="flex items-center justify-between gap-3 rounded-xl border border-white/20 bg-black/20 px-3 py-2 text-[11px] text-white/85 backdrop-blur-md sm:px-4 sm:text-xs">
          <div className="flex items-center gap-2">
            <Image src="/logo.png" alt="Logo WeeFarm" width={24} height={24} className="wf-logo-chip wf-logo-chip-ghost h-5 w-6 object-contain p-0.5" />
            <span className="font-medium tracking-[0.04em]">WEEFARM</span>
          </div>
          <span className="whitespace-nowrap text-white/75">Plateforme WeeFarm</span>
        </footer>
      </div>
      <style jsx>{`
        .smart-banner {
          position: relative;
          border-radius: 1.1rem;
          box-shadow: inset 0 1px 0 rgba(230, 255, 244, 0.22), 0 18px 34px rgba(8, 49, 35, 0.2);
        }
        .smart-banner::before {
          content: "";
          position: absolute;
          inset: 0;
          border-radius: inherit;
          background: radial-gradient(circle at 12% 40%, rgba(191, 255, 229, 0.18), transparent 48%),
            radial-gradient(circle at 85% 65%, rgba(145, 245, 227, 0.15), transparent 52%);
          pointer-events: none;
        }
        .marquee-track {
          position: relative;
          display: flex;
          width: max-content;
          gap: 0.75rem;
          animation: wf-marquee 24s linear infinite;
          will-change: transform;
          padding: 0.15rem 0.2rem 0.25rem;
        }
        .marquee-chip {
          display: inline-flex;
          align-items: center;
          white-space: nowrap;
          border-radius: 9999px;
          position: relative;
          overflow: hidden;
          border: 1px solid rgba(168, 241, 214, 0.62);
          background: linear-gradient(135deg, rgba(173, 244, 218, 0.24), rgba(118, 214, 197, 0.18));
          backdrop-filter: blur(10px) saturate(145%);
          -webkit-backdrop-filter: blur(10px) saturate(145%);
          padding: 0.62rem 1.2rem;
          font-size: 14px;
          font-weight: 700;
          letter-spacing: 0.01em;
          color: #ffffff;
          box-shadow: 0 12px 20px rgba(8, 48, 34, 0.2), 0 3px 7px rgba(10, 60, 41, 0.12), inset 0 1px 0 rgba(214, 255, 241, 0.5);
          text-shadow: 0 1px 1px rgba(4, 26, 18, 0.25);
          transform: translateZ(0);
        }
        .marquee-chip::before {
          content: "";
          position: absolute;
          left: 10%;
          right: 10%;
          top: 1px;
          height: 45%;
          border-radius: 9999px;
          background: linear-gradient(180deg, rgba(209, 255, 239, 0.55), rgba(209, 255, 239, 0));
          pointer-events: none;
        }
        @keyframes wf-marquee {
          from {
            transform: translateX(0);
          }
          to {
            transform: translateX(-50%);
          }
        }
      `}</style>
    </main>
  );
}
