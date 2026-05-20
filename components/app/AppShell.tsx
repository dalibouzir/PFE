"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BellIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  CloseIcon,
  HelpIcon,
  LogoutIcon,
  MenuIcon,
  ProfileIcon,
  SearchIcon,
  SettingsIcon,
  WeatherIcon,
} from "@/components/app/icons";
import type { LucideIcon } from "lucide-react";
import {
  Bot,
  Boxes,
  FileText,
  GitBranch,
  Landmark,
  LayoutDashboard,
  LineChart,
  Map,
  ShoppingCart,
  Sprout,
  Truck,
  Users,
  Wallet,
} from "lucide-react";
import { useAuth } from "@/context/auth/AuthContext";

const THIES_WEATHER_API_URL =
  "https://api.open-meteo.com/v1/forecast?latitude=14.7886&longitude=-16.9260&current=temperature_2m&timezone=Africa%2FDakar";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

type ProfileItem = {
  label: string;
  icon: (props: React.SVGProps<SVGSVGElement>) => React.JSX.Element;
  href?: string;
  action?: () => void;
  tone?: "default" | "danger";
};

export type AppRole = "admin" | "manager" | "super_admin" | "institution_admin";

const navByRole: Record<AppRole, NavItem[]> = {
  super_admin: [
    { href: "/super-admin/dashboard", label: "Tableau de bord", icon: LayoutDashboard },
    { href: "/super-admin/oversight", label: "Insights coopératives", icon: LineChart },
    { href: "/super-admin/institutions", label: "Institutions", icon: Landmark },
    { href: "/super-admin/cooperatives", label: "Cooperatives", icon: Map },
    { href: "/super-admin/hierarchy", label: "Hiérarchie", icon: Users },
  ],
  institution_admin: [
    { href: "/institution-admin/dashboard", label: "Tableau de bord", icon: LayoutDashboard },
    { href: "/institution-admin/oversight", label: "Insights coopératives", icon: LineChart },
    { href: "/institution-admin/institution", label: "Institution", icon: Landmark },
    { href: "/institution-admin/cooperatives", label: "Cooperatives", icon: Map },
  ],
  admin: [
    { href: "/admin/dashboard", label: "Tableau de bord", icon: LayoutDashboard },
    { href: "/admin/cooperatives", label: "Cooperatives", icon: Map },
    { href: "/admin/managers", label: "Managers", icon: Users },
    { href: "/admin/parametres", label: "Parametres", icon: Landmark },
  ],
  manager: [
    { href: "/manager/dashboard", label: "Tableau de bord", icon: LayoutDashboard },
    { href: "/manager/membres", label: "Membres", icon: Users },
    { href: "/manager/parcelles", label: "Parcelles & Culture", icon: Sprout },
    { href: "/manager/avances-producteurs", label: "Avance producteurs", icon: Wallet },
    { href: "/manager/inputs", label: "Collecte", icon: Truck },
    { href: "/manager/stocks", label: "Stocks", icon: Boxes },
    { href: "/manager/lots", label: "Flux matière / lots", icon: GitBranch },
    { href: "/manager/commercialisation", label: "Commercialisation", icon: ShoppingCart },
    { href: "/manager/facturation", label: "Facturation", icon: FileText },
    { href: "/manager/tresorerie", label: "Trésorerie", icon: Landmark },
    { href: "/manager/assistant-ia", label: "Copilote IA", icon: Bot },
  ],
};

const shellMeta: Record<
  AppRole,
  {
    name: string;
    roleLabel: string;
    cooperativeLabel: string;
    navLabel: string;
    locationLabel: string;
    searchPlaceholder: string;
    initials: string;
  }
> = {
  super_admin: {
    name: "Super Admin",
    roleLabel: "Super Admin WeeFarm",
    cooperativeLabel: "Plateforme WeeFarm",
    navLabel: "Navigation super administration",
    locationLabel: "Plateforme Senegal",
    searchPlaceholder: "Rechercher une institution, cooperative...",
    initials: "SA",
  },
  institution_admin: {
    name: "Institution Admin",
    roleLabel: "Admin institution",
    cooperativeLabel: "Institution",
    navLabel: "Navigation institution",
    locationLabel: "Plateforme Senegal",
    searchPlaceholder: "Rechercher une cooperative...",
    initials: "IA",
  },
  admin: {
    name: "Mariam Seck",
    roleLabel: "Admin plateforme",
    cooperativeLabel: "Plateforme WeeFarm",
    navLabel: "Navigation administration",
    locationLabel: "Plateforme Senegal",
    searchPlaceholder: "Rechercher une cooperative, un manager...",
    initials: "MS",
  },
  manager: {
    name: "Aissatou Ndiaye",
    roleLabel: "Manager coopérative",
    cooperativeLabel: "Coopérative",
    navLabel: "Navigation coopérative",
    locationLabel: "Thies · 33°C",
    searchPlaceholder: "Rechercher un lot, agriculteur, stock...",
    initials: "AN",
  },
};

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function buildProfileMenu(role: AppRole, onLogout: () => void): ProfileItem[] {
  const settingsHref =
    role === "manager"
      ? "/manager/parametres"
      : role === "admin"
        ? "/admin/parametres"
        : role === "institution_admin"
          ? "/institution-admin/institution"
          : "/super-admin/dashboard";

  return [
    { label: "Mon profil", icon: ProfileIcon, href: settingsHref },
    { label: "Paramètres", icon: SettingsIcon, href: settingsHref },
    { label: "Aide", icon: HelpIcon },
    { label: "Deconnexion", icon: LogoutIcon, tone: "danger", action: onLogout },
  ];
}

function SidebarNav({
  pathname,
  collapsed,
  role,
  onNavigate,
  onTooltipShow,
  onTooltipHide,
}: {
  pathname: string;
  collapsed: boolean;
  role: AppRole;
  onNavigate?: (href: string) => void;
  onTooltipShow?: (label: string, trigger: HTMLElement) => void;
  onTooltipHide?: () => void;
}) {
  return (
    <nav className={cx(collapsed ? "space-y-3" : "space-y-2.5")}>
      {navByRole[role].map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            title={item.label}
            onClick={() => onNavigate?.(item.href)}
            onMouseEnter={(event) => {
              if (!collapsed) return;
              onTooltipShow?.(item.label, event.currentTarget);
            }}
            onMouseLeave={() => {
              if (!collapsed) return;
              onTooltipHide?.();
            }}
            onFocus={(event) => {
              if (!collapsed) return;
              onTooltipShow?.(item.label, event.currentTarget);
            }}
            onBlur={() => {
              if (!collapsed) return;
              onTooltipHide?.();
            }}
            className={cx(
              "group relative flex h-11 items-center rounded-2xl text-[14px] font-semibold transition-all duration-200",
              collapsed ? "justify-center px-0" : "gap-2.5 px-3",
              collapsed ? "overflow-visible" : "overflow-hidden",
              active
                ? "bg-[var(--primary)] text-white shadow-[0_8px_18px_rgba(0,126,47,0.28)]"
                : "text-[#B7C0BA] hover:bg-[rgba(255,255,255,0.08)] hover:text-white",
            )}
            style={active ? { boxShadow: "0 0 12px rgba(0,126,47,0.34), 0 8px 18px rgba(0,126,47,0.28)" } : undefined}
          >
            <span className={cx("grid place-items-center transition-all duration-200", collapsed ? "w-11" : "w-5")}>
              <Icon className="h-5 w-5 shrink-0 transition-all duration-200 group-hover:scale-105" />
            </span>
            <span
              className={cx(
                "overflow-hidden whitespace-nowrap transition-all duration-200",
                collapsed ? "max-w-0 -translate-x-1 opacity-0" : "max-w-[170px] translate-x-0 opacity-100",
              )}
            >
              {item.label}
            </span>
            <span className={cx("ml-auto h-1.5 w-1.5 rounded-full bg-white/90 transition-opacity duration-200", collapsed ? "opacity-0" : active ? "opacity-100" : "opacity-0")} />

          </Link>
        );
      })}
    </nav>
  );
}

function ProfileDropdown({
  open,
  role,
  onLogout,
  meta,
}: {
  open: boolean;
  role: AppRole;
  onLogout: () => void;
  meta: {
    name: string;
    roleLabel: string;
    cooperativeLabel: string;
    navLabel: string;
    locationLabel: string;
    searchPlaceholder: string;
    initials: string;
  };
}) {
  if (!open) return null;

  const profileMenu = buildProfileMenu(role, onLogout);

  return (
    <div
      className="shell-pop absolute right-0 top-[calc(100%+10px)] z-[80] w-64 overflow-hidden rounded-[18px] border border-[rgba(200,227,214,0.88)] bg-[linear-gradient(148deg,rgba(245,252,248,0.9)_0%,rgba(232,246,238,0.86)_50%,rgba(222,240,230,0.82)_100%)] p-2 text-[#0f2318] shadow-[0_24px_44px_rgba(24,47,34,0.24)] backdrop-blur-2xl"
    >
      <div className="pointer-events-none absolute -inset-3 -z-10 rounded-[26px] bg-[radial-gradient(circle_at_50%_24%,rgba(223,236,228,0.7)_0%,rgba(223,236,228,0.34)_42%,rgba(223,236,228,0)_72%)] blur-2xl" />
      <div className="pointer-events-none absolute inset-x-2 top-0 h-px bg-[rgba(255,255,255,0.92)]" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.4)_0%,rgba(255,255,255,0.12)_38%,rgba(255,255,255,0)_100%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[repeating-linear-gradient(166deg,rgba(255,255,255,0.18)_0_1px,rgba(255,255,255,0)_1px_7px)] opacity-70" />
      <div className="pointer-events-none absolute inset-x-4 -bottom-6 h-10 rounded-[999px] bg-[radial-gradient(ellipse_at_center,rgba(208,223,214,0.66)_0%,rgba(208,223,214,0.3)_48%,rgba(208,223,214,0)_100%)] blur-2xl" />

      <div className="relative px-1">
        <div className="px-2 py-1.5">
          <p className="text-sm font-semibold text-[#0f2318]">{meta.name}</p>
          <p className="text-xs text-[#1b3a2b]/80">{meta.roleLabel}</p>
        </div>

        <div className="overflow-hidden">
          {profileMenu.map((item) => {
            const Icon = item.icon;
            const className = cx(
              "soft-focus group flex h-10 w-full items-center gap-2.5 px-3 text-sm font-medium transition-colors",
              item.tone === "danger"
                ? "text-[#7e1e2a] hover:bg-[rgba(255,218,223,0.5)]"
                : "text-[#0f2318] hover:bg-[rgba(0,96,41,0.58)] hover:text-[#f1fff7]",
            );
            const separatorClass = "border-t border-[rgba(228,250,238,0.36)] first:border-t-0";

            if (item.href) {
              return (
                <Link key={item.label} href={item.href} className={cx(className, separatorClass)}>
                  <Icon className={cx("h-4 w-4 transition-colors", item.tone === "danger" ? "text-[#7e1e2a]" : "text-[#0f3b26] group-hover:text-[#e8fff2]")} />
                  {item.label}
                </Link>
              );
            }

            return (
              <button
                key={item.label}
                className={cx(className, separatorClass)}
                type="button"
                onClick={item.action}
              >
                <Icon className={cx("h-4 w-4 transition-colors", item.tone === "danger" ? "text-[#7e1e2a]" : "text-[#0f3b26] group-hover:text-[#e8fff2]")} />
                {item.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function SidebarBrand({
  collapsed,
  role,
  onExpand,
  onCollapse,
}: {
  collapsed: boolean;
  role: AppRole;
  onExpand: () => void;
  onCollapse: () => void;
}) {
  const meta = shellMeta[role];

  return (
    <div className="px-1 pb-2 pt-1">
      <div className={cx("flex w-full transition-all duration-300", collapsed ? "flex-col items-center gap-2" : "items-start justify-between")}>
        <button
          className={cx(
            "soft-focus flex h-10 w-10 items-center justify-center rounded-lg border border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.06)] text-[#C7CEC9] transition-all duration-200 hover:-translate-y-0.5 hover:text-white",
            collapsed ? "order-1" : "order-2",
          )}
          onClick={collapsed ? onExpand : onCollapse}
          aria-label={collapsed ? "Deplier le menu" : "Reduire le menu"}
        >
          <span className="relative h-[18px] w-[18px]">
            <MenuIcon className={cx("absolute inset-0 transition-all duration-200", collapsed ? "scale-100 opacity-100" : "scale-75 opacity-0")} />
            <ChevronLeftIcon className={cx("absolute inset-0 transition-all duration-200", collapsed ? "scale-75 opacity-0" : "scale-100 opacity-100")} />
          </span>
        </button>

        <div className={cx("transition-all duration-300", collapsed ? "order-2 flex flex-col items-center gap-1" : "order-1 flex items-center gap-3")}>
          <Image src="/logo.png" alt="Logo WeeFarm" width={44} height={44} className="wf-logo-chip wf-logo-chip-dark h-11 w-11 object-contain p-1.5 transition-all duration-300" priority />

          <div
            className={cx(
              "overflow-hidden transition-all duration-300",
              collapsed ? "max-w-0 -translate-x-2 opacity-0" : "max-w-[190px] translate-x-0 opacity-100",
            )}
          >
            <p className="text-[20px] font-semibold leading-tight text-white">WeeFarm</p>
            <p className="text-[11px] tracking-[0.06em] text-[#B6C0B9]">{role === "manager" ? "OPERATIONS COOP" : "ADMIN CONSOLE"}</p>
          </div>
        </div>
      </div>

      <p
        className={cx(
          "mt-2 text-xs text-[#AAB5AE] transition-all duration-300",
          collapsed ? "max-h-0 -translate-y-1 overflow-hidden opacity-0" : "max-h-8 translate-y-0 opacity-100",
        )}
      >
        {role === "manager" ? meta.cooperativeLabel : meta.navLabel}
      </p>
    </div>
  );
}

export function AppShell({ children, role }: { children: React.ReactNode; role: AppRole }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [navLoading, setNavLoading] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const [thiesTemp, setThiesTemp] = useState<number | null>(null);
  const [collapsedTooltip, setCollapsedTooltip] = useState<{ label: string; top: number; left: number } | null>(null);
  const [loaderTop, setLoaderTop] = useState(108);
  const headerRef = useRef<HTMLElement>(null);
  const desktopProfileRef = useRef<HTMLDivElement>(null);
  const mobileProfileRef = useRef<HTMLDivElement>(null);
  const navLoadingStartedAtRef = useRef(0);
  const pendingPathRef = useRef<string | null>(null);
  const navLoadingTimeoutRef = useRef<number | null>(null);
  const navLoadingFailSafeRef = useRef<number | null>(null);
  const meta = useMemo(() => {
    const base = shellMeta[role];
    const name = user?.full_name || base.name;
    const initials = name
      .split(" ")
      .map((part) => part[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase();
    const roleLabel =
      user?.role === "super_admin"
        ? "Super Admin WeeFarm"
        : user?.role === "institution_admin"
          ? "Admin institution"
        : user?.role === "admin"
          ? "Admin plateforme"
          : user?.role === "owner"
            ? "Propriétaire coopérative"
            : user?.role === "viewer"
              ? "Observateur coopérative"
              : user?.role === "manager"
                ? "Manager cooperative"
                : base.roleLabel;
    const cooperativeLabel =
      user?.cooperative_name?.trim() ||
      (user?.role === "institution_admin" ? "Institution" : base.cooperativeLabel);

    return {
      ...base,
      name,
      initials: initials || base.initials,
      roleLabel,
      cooperativeLabel,
    };
  }, [role, user]);
  const isAssistantPage = role === "manager" && pathname.startsWith("/manager/assistant-ia");

  useEffect(() => {
    if (typeof window === "undefined") return;

    const media = window.matchMedia("(max-width: 1260px)");
    const sync = () => setCollapsed(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  const fetchThiesTemperature = useCallback(async () => {
    try {
      const response = await fetch(THIES_WEATHER_API_URL, { cache: "no-store" });
      if (!response.ok) return;

      const data = (await response.json()) as { current?: { temperature_2m?: number } };
      const nextTemperature = data.current?.temperature_2m;
      if (typeof nextTemperature === "number" && Number.isFinite(nextTemperature)) {
        setThiesTemp(Math.round(nextTemperature));
      }
    } catch {
      // Keep previous value when weather API is unavailable.
    }
  }, []);

  useEffect(() => {
    setNow(new Date());
    const timer = window.setInterval(() => setNow(new Date()), 60000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (role !== "manager") {
      setThiesTemp(null);
      return;
    }

    fetchThiesTemperature();
    const timer = window.setInterval(() => {
      fetchThiesTemperature();
    }, 60000);

    return () => window.clearInterval(timer);
  }, [fetchThiesTemperature, role]);

  useEffect(() => {
    setMobileOpen(false);
    setProfileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!navLoading) return;
    if (!pendingPathRef.current) return;

    const target = pendingPathRef.current;
    const reachedTarget = pathname === target || pathname.startsWith(`${target}/`);
    if (!reachedTarget) return;

    if (navLoadingTimeoutRef.current) {
      window.clearTimeout(navLoadingTimeoutRef.current);
      navLoadingTimeoutRef.current = null;
    }

    const elapsed = Date.now() - navLoadingStartedAtRef.current;
    const minimumVisible = 180;
    const settleDelay = 40;
    const remaining = Math.max(settleDelay, minimumVisible - elapsed);

    navLoadingTimeoutRef.current = window.setTimeout(() => {
      setNavLoading(false);
      pendingPathRef.current = null;
      navLoadingTimeoutRef.current = null;
      if (navLoadingFailSafeRef.current) {
        window.clearTimeout(navLoadingFailSafeRef.current);
        navLoadingFailSafeRef.current = null;
      }
    }, remaining);
  }, [navLoading, pathname]);

  useEffect(() => {
    return () => {
      if (navLoadingTimeoutRef.current) {
        window.clearTimeout(navLoadingTimeoutRef.current);
      }
      if (navLoadingFailSafeRef.current) {
        window.clearTimeout(navLoadingFailSafeRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const onDown = (event: MouseEvent) => {
      const target = event.target as Node;
      const inDesktop = desktopProfileRef.current?.contains(target);
      const inMobile = mobileProfileRef.current?.contains(target);

      if (!inDesktop && !inMobile) {
        setProfileOpen(false);
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setProfileOpen(false);
        setMobileOpen(false);
      }
    };

    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKeyDown);

    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return;

    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;

    // Keep browser-level scrolling locked while app shell is mounted.
    // Internal content areas own scrolling to avoid double-scroll on Chrome.
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    let frame = 0;
    const headerElement = headerRef.current;
    const updateLoaderTop = () => {
      frame = 0;
      const rect = headerRef.current?.getBoundingClientRect();
      const nextTop = rect ? Math.round(rect.bottom + (window.innerWidth >= 640 ? 18 : 12)) : 108;

      setLoaderTop((previousTop) => (previousTop === nextTop ? previousTop : nextTop));
    };

    const queueUpdate = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(updateLoaderTop);
    };

    queueUpdate();

    window.addEventListener("resize", queueUpdate);
    window.addEventListener("scroll", queueUpdate, { passive: true });

    const observer =
      typeof ResizeObserver !== "undefined" && headerElement
        ? new ResizeObserver(queueUpdate)
        : null;

    if (observer && headerElement) {
      observer.observe(headerElement);
    }

    return () => {
      window.removeEventListener("resize", queueUpdate);
      window.removeEventListener("scroll", queueUpdate);
      observer?.disconnect();

      if (frame) {
        window.cancelAnimationFrame(frame);
      }
    };
  }, [collapsed, pathname]);

  const timeFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat("fr-SN", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }),
    [],
  );

  const currentTime = timeFormatter.format(now);
  const locationLabel = role === "manager" && typeof thiesTemp === "number" ? `Thies · ${thiesTemp}°C` : meta.locationLabel;
  const shellLayoutStyle = { ["--sidebar-width" as string]: `${collapsed ? 92 : 258}px` } as React.CSSProperties;
  const collapsedTooltipStyle = collapsedTooltip
    ? ({
        top: `${collapsedTooltip.top}px`,
        left: `${collapsedTooltip.left}px`,
      } as React.CSSProperties)
    : undefined;

  const handleCollapsedTooltipShow = useCallback((label: string, trigger: HTMLElement) => {
    const rect = trigger.getBoundingClientRect();
    setCollapsedTooltip({
      label,
      top: rect.top + rect.height / 2,
      left: rect.right + 20,
    });
  }, []);

  const handleCollapsedTooltipHide = useCallback(() => {
    setCollapsedTooltip(null);
  }, []);

  useEffect(() => {
    if (!collapsed) {
      setCollapsedTooltip(null);
    }
  }, [collapsed]);

  const startNavTransition = useCallback((href: string) => {
    const target = href.split("?")[0].split("#")[0];
    if (!target || target === pathname) return;
    navLoadingStartedAtRef.current = Date.now();
    pendingPathRef.current = target;
    if (navLoadingTimeoutRef.current) {
      window.clearTimeout(navLoadingTimeoutRef.current);
      navLoadingTimeoutRef.current = null;
    }
    if (navLoadingFailSafeRef.current) {
      window.clearTimeout(navLoadingFailSafeRef.current);
      navLoadingFailSafeRef.current = null;
    }

    navLoadingFailSafeRef.current = window.setTimeout(() => {
      setNavLoading(false);
      pendingPathRef.current = null;
      navLoadingFailSafeRef.current = null;
    }, 3500);

    setNavLoading(true);
    setProfileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (typeof document === "undefined") return;

    const onInternalLinkClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

      const targetNode = event.target as HTMLElement | null;
      const anchor = targetNode?.closest("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;
      if (anchor.target && anchor.target !== "_self") return;

      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return;

      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      if (url.pathname === pathname) return;

      startNavTransition(url.pathname);
    };

    document.addEventListener("click", onInternalLinkClick, true);
    return () => document.removeEventListener("click", onInternalLinkClick, true);
  }, [pathname, startNavTransition]);

  return (
    <div className="relative h-[100svh] overflow-hidden bg-transparent md:h-[100dvh]" style={shellLayoutStyle}>
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[var(--sidebar-width)] bg-[#f3f7fb] px-3 py-4 transition-[width] duration-300 ease-out md:block">
        <div className="flex h-full flex-col rounded-[24px] border border-[rgba(255,255,255,0.08)] bg-[linear-gradient(180deg,#1C2722_0%,#16201B_100%)] p-3 shadow-[0_18px_40px_rgba(20,16,11,0.32)]">
          <SidebarBrand collapsed={collapsed} role={role} onCollapse={() => setCollapsed(true)} onExpand={() => setCollapsed(false)} />

          <div className="scroll-thin mt-5 flex-1 overflow-y-auto overscroll-y-contain pr-1">
            <SidebarNav
              pathname={pathname}
              collapsed={collapsed}
              role={role}
              onNavigate={startNavTransition}
              onTooltipShow={handleCollapsedTooltipShow}
              onTooltipHide={handleCollapsedTooltipHide}
            />
          </div>

          <div className="mt-auto space-y-2.5">
            {collapsed ? (
              <div className="flex justify-center">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[rgba(255,255,255,0.16)] bg-[rgba(255,255,255,0.08)] text-xs font-semibold text-[#D4DED8]" title="Systeme en ligne">
                  <span className="h-2 w-2 rounded-full bg-[var(--success)]" />
                </span>
              </div>
            ) : (
              <div className="rounded-2xl border border-[rgba(255,255,255,0.14)] bg-[rgba(255,255,255,0.06)] p-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-white">Systeme</p>
                  <span className="inline-flex items-center gap-1 rounded-full bg-[rgba(0,126,47,0.2)] px-2 py-0.5 text-[11px] font-medium text-[#CBE9D6]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" />
                    En ligne
                  </span>
                </div>
                <p className="mt-2 text-xs text-[#A9B4AD]">Derniere synchro: {currentTime}</p>
                <p className="mt-1 text-[11px] text-[#A9B4AD]">Mode production</p>
              </div>
            )}

            <button
              type="button"
              onClick={logout}
              className={cx(
                "soft-focus flex h-10 items-center rounded-xl border border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.05)] text-sm font-medium text-[#FFBABA] transition-all duration-200 hover:-translate-y-0.5 hover:bg-[rgba(214,69,69,0.18)]",
                collapsed ? "mx-auto w-10 justify-center px-0" : "w-full gap-2 px-3",
              )}
            >
              <LogoutIcon className={cx("shrink-0 transition-all duration-200", collapsed ? "h-5 w-5" : "h-4 w-4")} />
              <span className={cx("overflow-hidden whitespace-nowrap transition-all duration-200", collapsed ? "max-w-0 opacity-0" : "max-w-[140px] opacity-100")}>
                Deconnexion
              </span>
            </button>
          </div>
        </div>
      </aside>

      {collapsed && collapsedTooltip && (
        <div
          className="pointer-events-none fixed z-[160] flex h-9 w-36 -translate-y-1/2 items-center justify-center whitespace-nowrap rounded-xl border border-[#007e2f]/45 bg-[#007e2f]/14 px-3 text-xs font-semibold text-[#007e2f] shadow-[0_10px_22px_rgba(0,126,47,0.2)] backdrop-blur-md"
          style={collapsedTooltipStyle}
        >
          {collapsedTooltip.label}
        </div>
      )}

      <div className={cx("fixed inset-0 z-[70] md:hidden transition-opacity duration-200", mobileOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0")}>
        <button className="absolute inset-0 bg-[#1a140c]/50 backdrop-blur-sm" onClick={() => setMobileOpen(false)} aria-label="Fermer le menu" />

        <aside
          className={cx(
            "scroll-thin absolute inset-y-0 left-0 w-[min(86vw,300px)] overflow-y-auto overscroll-y-contain border-r border-[rgba(255,255,255,0.12)] bg-[linear-gradient(180deg,#1D2823_0%,#17211C_100%)] px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-[calc(1rem+env(safe-area-inset-top))] shadow-[0_24px_48px_rgba(15,13,9,0.32)] touch-pan-y transition-transform duration-300",
            mobileOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Image src="/logo.png" alt="Logo WeeFarm" width={40} height={40} className="wf-logo-chip wf-logo-chip-dark h-10 w-10 object-contain p-1.5" />
              <div>
                <p className="text-sm font-semibold text-white">WeeFarm</p>
                <p className="text-[11px] text-[#AAB4AE]">{meta.roleLabel}</p>
              </div>
            </div>
            <button className="soft-focus rounded-lg border border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.06)] p-2 text-[#C7CEC9]" onClick={() => setMobileOpen(false)} aria-label="Fermer">
              <CloseIcon className="h-4 w-4" />
            </button>
          </div>

          <SidebarNav
            pathname={pathname}
            collapsed={false}
            role={role}
            onNavigate={(href) => {
              startNavTransition(href);
              setMobileOpen(false);
            }}
          />

          <div className="mt-4 rounded-2xl border border-[rgba(255,255,255,0.14)] bg-[rgba(255,255,255,0.06)] p-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-white">Systeme</p>
              <span className="inline-flex items-center gap-1 rounded-full bg-[rgba(0,126,47,0.2)] px-2 py-0.5 text-[11px] font-medium text-[#CBE9D6]">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" />
                En ligne
              </span>
            </div>
            <p className="mt-2 text-xs text-[#AAB4AE]">Derniere synchro: {currentTime}</p>
          </div>

          <button
            type="button"
            onClick={logout}
            className="soft-focus mt-3 flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.05)] text-sm font-medium text-[#FFBABA] transition-all hover:bg-[rgba(214,69,69,0.18)]"
          >
            <LogoutIcon className="h-4 w-4" />
            Deconnexion
          </button>
        </aside>
      </div>

      <div
        className={cx(
          "relative z-10 flex h-[100svh] min-w-0 flex-col overflow-hidden bg-[#f3f7fb] px-3 pt-0 touch-pan-y transition-[margin-left] duration-300 ease-out sm:px-5 md:ml-[var(--sidebar-width)] md:h-[100dvh] md:px-7 md:pt-6",
          isAssistantPage ? "pb-0" : "pb-[calc(2rem+env(safe-area-inset-bottom))]",
        )}
      >
        <header
          ref={headerRef}
          className={cx(
            "fixed inset-x-3 top-2 z-50 mb-5 rounded-[18px] border border-[rgba(172,231,194,0.42)] bg-[linear-gradient(135deg,rgba(0,126,47,0.42)_0%,rgba(10,104,47,0.3)_45%,rgba(24,120,62,0.24)_100%)] px-3 py-2.5 shadow-[0_10px_28px_rgba(0,98,42,0.24)] backdrop-blur-xl sm:inset-x-5 sm:px-4 md:sticky md:inset-x-auto md:top-2",
            mobileOpen && "pointer-events-none",
          )}
        >
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_16%_12%,rgba(255,255,255,0.38)_0%,rgba(255,255,255,0.08)_34%,rgba(255,255,255,0)_58%)]" />
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-[rgba(237,255,245,0.78)]" />

          <div className="relative z-10 hidden items-center gap-3 text-[#0f2318] md:grid md:grid-cols-[auto_minmax(0,1fr)_auto]">
            <div className="flex items-center gap-2.5">
              <span className="inline-flex items-center text-sm">🇸🇳</span>
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-[#163325]">
                <WeatherIcon className="h-3.5 w-3.5" />
                {locationLabel}
              </span>
            </div>

            <div className="w-full">
              <div className="flex items-center gap-3">
                <span className="max-w-[260px] shrink-0 truncate border-l border-[#1b3a2b]/25 pl-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#123223]/88">
                  {meta.cooperativeLabel}
                </span>
                <div className="relative min-w-0 flex-1">
                  <SearchIcon className="pointer-events-none absolute left-0.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#1b3a2b]/80" />
                  <input
                    className="h-10 w-full border-0 border-b border-[#1b3a2b]/30 bg-transparent py-2 pl-7 pr-1 text-sm text-[#0f2318] placeholder:text-[#1b3a2b]/70 focus:border-b-[#1b3a2b]/30 focus:shadow-none focus:outline-none"
                    placeholder={meta.searchPlaceholder}
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-[#0f2318]">{currentTime}</span>

              <button className="soft-focus relative p-1.5 text-[#163325]">
                <BellIcon className="h-4 w-4" />
                <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-[var(--warning)]" />
              </button>

              <div className="relative" ref={desktopProfileRef}>
                <button
                  className="soft-focus group flex min-w-[180px] items-center justify-end gap-2.5 px-2 py-1.5 text-left"
                  onClick={() => setProfileOpen((prev) => !prev)}
                  aria-haspopup="menu"
                  aria-expanded={profileOpen}
                >
                  <span className="hidden flex-col leading-tight xl:flex">
                    <span className="text-sm font-semibold text-[#0f2318]">{meta.name}</span>
                    <span className="text-[11px] text-[#1b3a2b]/80">{meta.roleLabel}</span>
                  </span>
                  <span className="text-[12px] font-semibold text-[#0f2318]">
                    {meta.initials}
                  </span>
                  <ChevronDownIcon className={cx("h-3.5 w-3.5 text-[#1b3a2b]/80 transition-transform duration-200", profileOpen && "rotate-180")} />
                </button>

                <ProfileDropdown open={profileOpen} role={role} onLogout={logout} meta={meta} />
              </div>
            </div>
          </div>

          <div className="relative z-10 space-y-3 text-[#0f2318] md:hidden">
            <div className="flex items-center gap-2">
              <button className="soft-focus p-1 text-[#163325]" onClick={() => setMobileOpen(true)} aria-label="Ouvrir le menu">
                <MenuIcon className="h-5 w-5" />
              </button>

              <span className="inline-flex items-center text-xs">🇸🇳</span>
              <span className="inline-flex items-center gap-1.5 text-xs text-[#163325]">
                <WeatherIcon className="h-3.5 w-3.5" />
                {locationLabel}
              </span>

              <div className="ml-auto flex items-center gap-1.5">
                <span className="text-[11px] font-medium text-[#0f2318]">{currentTime}</span>

                <button className="soft-focus relative p-1.5 text-[#163325]">
                  <BellIcon className="h-4 w-4" />
                  <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-[var(--warning)]" />
                </button>

                <div className="relative" ref={mobileProfileRef}>
                  <button className="soft-focus px-1 text-[11px] font-semibold text-[#0f2318]" onClick={() => setProfileOpen((prev) => !prev)} aria-haspopup="menu" aria-expanded={profileOpen}>
                    {meta.initials}
                  </button>

                  <ProfileDropdown open={profileOpen} role={role} onLogout={logout} meta={meta} />
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="max-w-[145px] shrink-0 truncate border-l border-[#1b3a2b]/25 pl-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#123223]/88">{meta.cooperativeLabel}</span>
              <div className="relative min-w-0 flex-1">
                <SearchIcon className="pointer-events-none absolute left-0.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#1b3a2b]/80" />
                <input className="h-9 w-full border-0 border-b border-[#1b3a2b]/30 bg-transparent py-2 pl-7 pr-1 text-sm text-[#0f2318] placeholder:text-[#1b3a2b]/70 focus:border-b-[#1b3a2b]/30 focus:shadow-none focus:outline-none" placeholder={meta.searchPlaceholder} />
              </div>
            </div>
          </div>

        </header>

        <div className="md:hidden" aria-hidden="true" style={{ height: `${loaderTop}px` }} />

        <div
          className={cx(
            "shell-scroll-area relative z-0 min-h-0 flex-1",
            isAssistantPage ? "overflow-hidden" : "overflow-y-auto overflow-x-hidden",
          )}
        >
          <div
            className={cx(
              "transition-opacity duration-150",
              isAssistantPage && "h-full min-h-0",
            )}
          >
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
