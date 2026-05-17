import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

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
  const generatedAt = (options.generatedAt ?? new Date()).toLocaleString("fr-FR");
  const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
  doc.setFontSize(16);
  doc.text(options.title, 40, 36);
  doc.setFontSize(10);
  doc.text(`Date d'export: ${generatedAt}`, 40, 54);

  const head = [options.columns.map((column) => column.header)];
  const body = (options.rows.length > 0
    ? options.rows.map((row) => options.columns.map((column) => resolveCellValue(column, row)))
    : [["Aucune donnée", ...new Array(Math.max(options.columns.length - 1, 0)).fill("")]]) as string[][];

  autoTable(doc, {
    startY: 70,
    head,
    body,
    styles: { fontSize: 8, cellPadding: 4 },
    headStyles: { fillColor: [13, 90, 43] },
    theme: "grid",
  });

  doc.save(`${options.filename}.pdf`);
}
