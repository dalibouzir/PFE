type Row = Record<string, string>;

export function SimpleTable({ rows }: { rows: Row[] }) {
  const headers = rows.length > 0 ? Object.keys(rows[0]) : [];

  return (
    <div className="premium-card reveal overflow-hidden rounded-2xl" style={{ ["--delay" as string]: "70ms" }}>
      <div className="overflow-x-auto">
        <table className="wf-table min-w-full text-left">
          <thead>
            <tr>
              {headers.map((header) => (
                <th key={header} className="px-5 py-3.5 font-medium">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="text-sm text-[var(--text)]">
            {rows.map((row, index) => (
              <tr key={index}>
                {headers.map((header) => (
                  <td key={header} className="px-5 py-4">
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
