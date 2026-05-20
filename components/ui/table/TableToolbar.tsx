"use client";

import type { SortOrder } from "@/lib/table/useTableControls";

type ToolbarFilter = {
  key: string;
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
};

type TableToolbarProps = {
  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  filters?: ToolbarFilter[];
  onFilterChange?: (key: string, value: string) => void;
  sortOrder: SortOrder;
  onSortOrderChange: (value: SortOrder) => void;
  sortAscLabel?: string;
  sortDescLabel?: string;
  rightActions?: React.ReactNode;
};

export function TableToolbar({
  search,
  onSearchChange,
  searchPlaceholder = "Rechercher...",
  filters = [],
  onFilterChange,
  sortOrder,
  onSortOrderChange,
  sortAscLabel = "Date asc",
  sortDescLabel = "Date desc",
  rightActions,
}: TableToolbarProps) {
  return (
    <div className="grid gap-3 lg:grid-cols-[minmax(0,1.7fr)_auto]">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <input
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          className="soft-focus wf-input px-3 py-2.5 text-sm sm:col-span-2 xl:col-span-1"
          placeholder={searchPlaceholder}
        />

        {filters.map((filter) => (
          <select
            key={filter.key}
            value={filter.value}
            onChange={(event) => onFilterChange?.(filter.key, event.target.value)}
            className="soft-focus wf-input px-3 py-2.5 text-sm"
            aria-label={filter.label}
          >
            {filter.options.map((option) => (
              <option key={`${filter.key}-${option.value}`} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        ))}

        <select
          value={sortOrder}
          onChange={(event) => onSortOrderChange(event.target.value as SortOrder)}
          className="soft-focus wf-input px-3 py-2.5 text-sm"
        >
          <option value="desc">{sortDescLabel}</option>
          <option value="asc">{sortAscLabel}</option>
        </select>
      </div>

      {rightActions ? (
        <div className="flex flex-wrap items-center justify-start gap-2 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-2 lg:justify-end">
          {rightActions}
        </div>
      ) : null}
    </div>
  );
}
