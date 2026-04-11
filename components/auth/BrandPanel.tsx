export function BrandPanel() {
  return (
    <section className="relative hidden h-full overflow-hidden lg:flex">
      <div className="auth-noise absolute inset-0" />

      <div className="auth-orb auth-orb-one" />
      <div className="auth-orb auth-orb-two" />
      <div className="auth-orb auth-orb-three" />

      <div className="login-fade relative z-10 flex max-w-2xl flex-col justify-center px-16 xl:px-20">
        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-emerald-100/90">WEFARM</p>
        <h1 className="mt-5 max-w-xl text-5xl font-semibold leading-[1.08] tracking-[-0.02em] text-white xl:text-6xl">
          Décisions agricoles plus claires, chaque jour.
        </h1>
        <p className="mt-6 max-w-lg text-lg leading-relaxed text-emerald-100/86">
          Une interface simple pour piloter production, pertes et qualité.
        </p>
      </div>
    </section>
  );
}
