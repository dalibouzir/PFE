export function PageIntro({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <header className="mb-4 sm:mb-6">
      <h1 className="text-2xl font-semibold text-[var(--green-900)] sm:text-3xl">{title}</h1>
      <p className="mt-1 text-sm text-[var(--muted)]">{subtitle}</p>
    </header>
  );
}
