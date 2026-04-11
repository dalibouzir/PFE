type Row = Record<string, string>;

export function SimpleTable({ rows }: { rows: Row[] }) {
  const headers = rows.length > 0 ? Object.keys(rows[0]) : [];

  return (
    <div className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "70ms" }}>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left">
          <thead className="bg-[var(--surface-soft)] text-xs uppercase tracking-wide text-[var(--muted)]">
            <tr>
              {headers.map((header) => (
                <th key={header} className="px-4 py-3 font-medium">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="text-sm text-[var(--text)]">
            {rows.map((row, index) => (
              <tr key={index} className="border-t border-[var(--line)] hover:bg-[var(--surface-soft)]/70">
                {headers.map((header) => (
                  <td key={header} className="px-4 py-3">
                    {row[header]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
