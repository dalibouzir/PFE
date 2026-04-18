export function PageIntro({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <header className="mb-5 sm:mb-7">
      <h1 className="text-2xl font-semibold tracking-[-0.01em] text-[var(--text)] sm:text-3xl">{title}</h1>
      <p className="mt-1.5 max-w-3xl text-sm text-[var(--muted)]">{subtitle}</p>
    </header>
  );
}
