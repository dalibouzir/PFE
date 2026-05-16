export type ExportColumn<T> = {
  key: keyof T | string;
  header: string;
  format?: (value: unknown, row: T) => string;
};

export type ExportOptions<T> = {
  filename: string;
  title: string;
  columns: ExportColumn<T>[];
  rows: T[];
  generatedAt?: Date;
};

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function resolveCellValue<T>(column: ExportColumn<T>, row: T): string {
  const raw = (row as Record<string, unknown>)[String(column.key)];
  if (column.format) return column.format(raw, row);
  if (raw === null || raw === undefined) return "";
  return String(raw);
}

function downloadBlob(filename: string, blob: Blob) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export function exportRowsToCsv<T>(options: ExportOptions<T>) {
  const lines = [
    options.columns.map((column) => `"${column.header.replace(/\"/g, '""')}"`).join(";"),
    ...options.rows.map((row) =>
      options.columns
        .map((column) => {
          const value = resolveCellValue(column, row).replace(/\"/g, '""');
          return `"${value}"`;
        })
        .join(";"),
    ),
  ];

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  downloadBlob(`${options.filename}.csv`, blob);
}

export function exportRowsToExcel<T>(options: ExportOptions<T>) {
  const headers = options.columns.map((column) => `<th>${escapeHtml(column.header)}</th>`).join("");
  const rows = options.rows
    .map(
      (row) =>
        `<tr>${options.columns
          .map((column) => `<td>${escapeHtml(resolveCellValue(column, row))}</td>`)
          .join("")}</tr>`,
    )
    .join("");

  const generatedAt = (options.generatedAt ?? new Date()).toLocaleString("fr-FR");
  const html = `<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>${escapeHtml(options.title)}</title>
</head>
<body>
  <h2>${escapeHtml(options.title)}</h2>
  <p>Export: ${escapeHtml(generatedAt)}</p>
  <table border="1">
    <thead><tr>${headers}</tr></thead>
    <tbody>${rows || `<tr><td colspan="${options.columns.length}">Aucune donnée</td></tr>`}</tbody>
  </table>
</body>
</html>`;

  const blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8;" });
  downloadBlob(`${options.filename}.xls`, blob);
}

export function exportRowsToPdf<T>(options: ExportOptions<T>) {
  const headers = options.columns
    .map((column) => `<th>${escapeHtml(column.header)}</th>`)
    .join("");
  const bodyRows = options.rows
    .map(
      (row) =>
        `<tr>${options.columns
          .map((column) => `<td>${escapeHtml(resolveCellValue(column, row))}</td>`)
          .join("")}</tr>`,
    )
    .join("");

  const generatedAt = (options.generatedAt ?? new Date()).toLocaleString("fr-FR");
  const html = `<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>${escapeHtml(options.title)}</title>
    <style>
      body { font-family: Arial, sans-serif; color: #1d2a24; padding: 24px; }
      h1 { margin: 0 0 6px; color: #0d5a2b; font-size: 22px; }
      .meta { margin-bottom: 16px; font-size: 12px; color: #44554c; }
      table { width: 100%; border-collapse: collapse; font-size: 12px; }
      th, td { border: 1px solid #dbe8df; padding: 8px; text-align: left; vertical-align: top; }
      th { background: #eef7f1; color: #1f4d33; }
      @media print { body { padding: 10px; } }
    </style>
  </head>
  <body>
    <h1>${escapeHtml(options.title)}</h1>
    <div class="meta">Date d'export: ${escapeHtml(generatedAt)}</div>
    <table>
      <thead><tr>${headers}</tr></thead>
      <tbody>${bodyRows || `<tr><td colspan="${options.columns.length}">Aucune donnée</td></tr>`}</tbody>
    </table>
  </body>
</html>`;

  const printWindow = window.open("", "_blank", "noopener,noreferrer,width=1100,height=900");
  if (!printWindow) return;
  printWindow.document.open();
  printWindow.document.write(html);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}
