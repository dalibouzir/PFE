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
    <div className="grid gap-3 lg:grid-cols-[1.2fr_1fr_1fr_auto]">
      <input
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        className="soft-focus wf-input px-3 py-2.5 text-sm"
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

      {rightActions ? <div className="flex flex-wrap items-center gap-2">{rightActions}</div> : null}
    </div>
  );
}
