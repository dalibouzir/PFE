"use client";

import { useMemo, useState } from "react";

export type SortOrder = "asc" | "desc";

export type FilterOption = {
  value: string;
  label: string;
};

export type TableFilterConfig = {
  key: string;
  label: string;
  options: FilterOption[];
  initialValue?: string;
};

export function useTableControls(filterConfigs: TableFilterConfig[], defaultSort: SortOrder = "desc") {
  const [search, setSearch] = useState("");
  const [sortOrder, setSortOrder] = useState<SortOrder>(defaultSort);

  const [filters, setFilters] = useState<Record<string, string>>(() =>
    filterConfigs.reduce<Record<string, string>>((acc, config) => {
      acc[config.key] = config.initialValue ?? "all";
      return acc;
    }, {}),
  );

  const setFilterValue = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const filterDefinitions = useMemo(
    () => filterConfigs.map((config) => ({ ...config, value: filters[config.key] ?? "all" })),
    [filterConfigs, filters],
  );

  return {
    search,
    setSearch,
    sortOrder,
    setSortOrder,
    filters,
    setFilterValue,
    filterDefinitions,
  };
}
