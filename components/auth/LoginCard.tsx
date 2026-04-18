import Image from "next/image";
import Link from "next/link";
import { AuthInput } from "@/components/auth/AuthInput";

export function LoginCard() {
  return (
    <section className="relative z-10 flex min-h-screen items-center justify-center px-5 py-10 sm:px-8 lg:min-h-0 lg:px-10">
      <div className="auth-card card-pop w-full max-w-md rounded-[24px] p-7 sm:p-8">
        <div className="mb-6 flex items-center gap-3">
          <Image
            src="/logo.png"
            alt="Logo WeFarm"
            width={36}
            height={36}
            className="h-9 w-9 rounded-lg object-contain"
            priority
          />
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-100/80">WeeFarm</p>
            <h2 className="text-2xl font-semibold tracking-[-0.02em] text-white">Connexion</h2>
            <p className="text-sm text-white/72">Accès réservé aux membres</p>
          </div>
        </div>

        <form className="space-y-4">
          <AuthInput label="Email" type="email" placeholder="nom@wefarm.sn" autoComplete="email" />
          <AuthInput
            label="Mot de passe"
            type="password"
            placeholder="••••••••"
            autoComplete="current-password"
          />

          <button
            type="button"
            className="soft-focus auth-cta mt-1 w-full rounded-xl px-4 py-3 text-sm font-semibold text-white"
          >
            Se connecter
          </button>
        </form>

        <div className="mt-5 flex items-center justify-between text-xs">
          <a href="#" className="text-emerald-100/85 transition hover:text-white hover:underline">
            Mot de passe oublié ?
          </a>
          <Link href="/manager/dashboard" className="font-medium text-emerald-200 transition hover:text-white hover:underline">
            Entrer en mode demo
          </Link>
        </div>
      </div>
    </section>
  );
}
