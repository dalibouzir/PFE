"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/auth/AuthContext";
import { AgriBrandLoader } from "@/components/ui/AgriBrandLoader";
import type { UserRole } from "@/lib/api/types";

export function ProtectedRoute({ children, role }: { children: React.ReactNode; role?: UserRole | UserRole[] }) {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    const allowed = Array.isArray(role) ? role : role ? [role] : [];
    if (allowed.length > 0 && !allowed.includes(user.role)) {
      router.replace(user.role === "admin" ? "/admin/dashboard" : "/manager/dashboard");
    }
  }, [loading, user, role, router]);

  if (loading || !user) {
    return <AgriBrandLoader mode="screen" />;
  }

  return <>{children}</>;
}
