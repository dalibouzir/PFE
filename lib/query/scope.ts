"use client";

import { useMemo } from "react";
import { useAuth } from "@/context/auth/AuthContext";
import type { UserRole } from "@/lib/api/types";

export type QueryScope = {
  user_id: string | null;
  role: UserRole | null;
  cooperative_id: string | null;
  institution_id: string | null;
};

export function useQueryScope(): QueryScope {
  const { user } = useAuth();
  return useMemo(
    () => ({
      user_id: user?.id ?? null,
      role: user?.role ?? null,
      cooperative_id: user?.cooperative_id ?? null,
      institution_id: user?.institution_id ?? null,
    }),
    [user?.id, user?.role, user?.cooperative_id, user?.institution_id],
  );
}

function scopeParts(scope: QueryScope) {
  return [
    "scope",
    scope.user_id ?? "anon",
    scope.role ?? "none",
    scope.cooperative_id ?? "none",
    scope.institution_id ?? "none",
  ] as const;
}

export function scopePrefix(base: string | readonly unknown[], scope: QueryScope) {
  const baseParts = Array.isArray(base) ? [...base] : [base];
  return [...baseParts, ...scopeParts(scope)];
}

export function scopedQueryKey(
  base: string | readonly unknown[],
  scope: QueryScope,
  ...rest: unknown[]
) {
  return [...scopePrefix(base, scope), ...rest];
}
