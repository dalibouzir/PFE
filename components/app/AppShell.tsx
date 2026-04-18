"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  BellIcon,
  ChatIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  CloseIcon,
  CooperativeIcon,
  DashboardIcon,
  HelpIcon,
  InputsIcon,
  LogoutIcon,
  LotsIcon,
  ManagerIcon,
  MenuIcon,
  ProfileIcon,
  SearchIcon,
  SettingsIcon,
  StocksIcon,
  UsersIcon,
  WeatherIcon,
} from "@/components/app/icons";
import { AgriBrandLoader } from "@/components/ui/AgriBrandLoader";
import { useAuth } from "@/context/auth/AuthContext";

type IconRenderer = (props: React.SVGProps<SVGSVGElement>) => React.JSX.Element;

type NavItem = {
  href: string;
  label: string;
  icon: IconRenderer;
};

type ProfileItem = {
  label: string;
  icon: IconRenderer;
  href?: string;
  action?: () => void;
  tone?: "default" | "danger";
};

export type AppRole = "admin" | "manager";

const navByRole: Record<AppRole, NavItem[]> = {
  admin: [
    { href: "/admin/dashboard", label: "Tableau de bord", icon: DashboardIcon },
    { href: "/admin/cooperatives", label: "Cooperatives", icon: CooperativeIcon },
    { href: "/admin/managers", label: "Managers", icon: ManagerIcon },
    { href: "/admin/parametres", label: "Parametres", icon: SettingsIcon },
  ],
  manager: [
    { href: "/manager/dashboard", label: "Dashboard", icon: DashboardIcon },
    { href: "/manager/membres", label: "Membres", icon: UsersIcon },
    { href: "/manager/inputs", label: "Collecte", icon: InputsIcon },
    { href: "/manager/stocks", label: "Stocks", icon: StocksIcon },
    { href: "/manager/lots", label: "Flux matiere / Lots", icon: LotsIcon },
    { href: "/manager/assistant-ia", label: "Assistant IA", icon: ChatIcon },
  ],
};

const shellMeta: Record<
  AppRole,
  {
    name: string;
    roleLabel: string;
    navLabel: string;
    locationLabel: string;
    searchPlaceholder: string;
    initials: string;
  }
> = {
  admin: {
    name: "Mariam Seck",
    roleLabel: "Admin plateforme",
    navLabel: "Navigation administration",
    locationLabel: "Plateforme Senegal",
    searchPlaceholder: "Rechercher une cooperative, un manager...",
    initials: "MS",
  },
  manager: {
    name: "Aissatou Ndiaye",
    roleLabel: "Manager cooperative",
    navLabel: "Navigation cooperative",
    locationLabel: "Thies · 33°C",
    searchPlaceholder: "Rechercher un lot, agriculteur, stock...",
    initials: "AN",
  },
};

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function buildProfileMenu(role: AppRole, onLogout: () => void): ProfileItem[] {
  const settingsHref = role === "admin" ? "/admin/parametres" : "/manager/parametres";

  return [
    { label: "Mon profil", icon: ProfileIcon, href: settingsHref },
    { label: "Parametres", icon: SettingsIcon, href: settingsHref },
    { label: "Aide", icon: HelpIcon },
    { label: "Deconnexion", icon: LogoutIcon, tone: "danger", action: onLogout },
  ];
}

function SidebarNav({
  pathname,
  collapsed,
  role,
  onNavigate,
}: {
  pathname: string;
  collapsed: boolean;
  role: AppRole;
  onNavigate?: (href: string) => void;
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
            className={cx(
              "group relative flex h-11 items-center overflow-hidden rounded-2xl text-[14px] font-semibold transition-all duration-200",
              collapsed ? "justify-center px-0" : "gap-2.5 px-3",
              active
                ? "bg-[var(--primary)] text-white shadow-[0_8px_18px_rgba(0,126,47,0.28)]"
                : "text-[#B7C0BA] hover:bg-[rgba(255,255,255,0.08)] hover:text-white",
            )}
            style={active ? { boxShadow: "0 0 12px rgba(34, 197, 94, 0.3), 0 8px 18px rgba(0,126,47,0.28)" } : undefined}
          >
            <span className={cx("grid place-items-center transition-all duration-200", collapsed ? "w-11" : "w-[18px]")}>
              <Icon className={cx("shrink-0 transition-all duration-200", collapsed ? "h-[21px] w-[21px]" : "h-[17px] w-[17px]")} />
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

            {collapsed && (
              <span className="pointer-events-none absolute left-full z-30 ml-3 hidden whitespace-nowrap rounded-xl border border-[var(--line)] bg-[var(--surface)] px-2.5 py-1 text-xs font-medium text-[var(--text)] shadow-md group-hover:block">
                {item.label}
              </span>
            )}
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
      className="shell-pop absolute right-0 top-[calc(100%+10px)] z-[80] w-64 overflow-hidden rounded-[22px] border border-[var(--line)] bg-[var(--surface)] p-2 text-[var(--text)] shadow-[0_16px_34px_rgba(35,30,21,0.14)]"
    >
      <div className="pointer-events-none absolute inset-x-3 top-0 h-px bg-white/90" />

      <div className="relative">
        <div className="mb-2 rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] px-3 py-2.5">
          <p className="text-sm font-semibold text-[var(--text)]">{meta.name}</p>
          <p className="text-xs text-[var(--muted)]">{meta.roleLabel}</p>
        </div>

        <div className="overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--surface)]">
          {profileMenu.map((item) => {
            const Icon = item.icon;
            const className = cx(
              "soft-focus flex w-full items-center gap-2 px-3 py-2 text-sm font-medium transition-colors",
              item.tone === "danger"
                ? "text-[var(--danger)] hover:bg-[#FFEDEE]"
                : "text-[var(--text)] hover:bg-[var(--surface-soft)]",
            );

            const dangerClassName =
              "soft-focus flex h-10 w-full items-center gap-2 border-t border-[#f3d3d3] bg-[#FFEDEE] px-3 text-sm font-medium text-[var(--danger)] transition-colors duration-200 hover:bg-[#FFE4E4]";

            if (item.href) {
              return (
                <Link key={item.label} href={item.href} className={cx(item.tone === "danger" ? dangerClassName : className, item.tone !== "danger" && "border-t border-[rgba(19,40,31,0.08)] first:border-t-0")}>
                  <Icon className={cx("h-4 w-4", item.tone === "danger" ? "text-[var(--danger)]" : "text-[var(--primary)]")} />
                  {item.label}
                </Link>
              );
            }

            return (
              <button
                key={item.label}
                className={cx(className, "border-t border-[rgba(19,40,31,0.08)] first:border-t-0")}
                type="button"
                onClick={item.action}
              >
                <Icon className={cx("h-4 w-4", item.tone === "danger" ? "text-[var(--danger)]" : "text-[var(--primary)]")} />
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
          <Image src="/logo.png" alt="Logo WeeFarm" width={44} height={44} className="h-11 w-11 object-contain transition-all duration-300" priority />

          <div
            className={cx(
              "overflow-hidden transition-all duration-300",
              collapsed ? "max-w-0 -translate-x-2 opacity-0" : "max-w-[190px] translate-x-0 opacity-100",
            )}
          >
            <p className="text-[20px] font-semibold leading-tight text-white">WeeFarm</p>
            <p className="text-[11px] tracking-[0.06em] text-[#B6C0B9]">{role === "admin" ? "ADMIN CONSOLE" : "OPERATIONS COOP"}</p>
          </div>

          <p
            className={cx(
              "text-[10px] font-semibold tracking-wide text-[#D9E2DC] transition-all duration-300",
              collapsed ? "opacity-100" : "pointer-events-none -translate-y-1 opacity-0",
            )}
          >
            WF
          </p>
        </div>
      </div>

      <p
        className={cx(
          "mt-2 text-xs text-[#AAB5AE] transition-all duration-300",
          collapsed ? "max-h-0 -translate-y-1 overflow-hidden opacity-0" : "max-h-8 translate-y-0 opacity-100",
        )}
      >
        {meta.navLabel}
      </p>
    </div>
  );
}

export function AppShell({ children, role }: { children: React.ReactNode; role: AppRole }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [navLoading, setNavLoading] = useState(false);
  const [now, setNow] = useState(() => new Date());
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
    const roleLabel = user?.role === "admin" ? "Admin plateforme" : user?.role === "manager" ? "Manager cooperative" : base.roleLabel;

    return {
      ...base,
      name,
      initials: initials || base.initials,
      roleLabel,
    };
  }, [role, user]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const media = window.matchMedia("(max-width: 1260px)");
    const sync = () => setCollapsed(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60000);
    return () => window.clearInterval(timer);
  }, []);

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
    const minimumVisible = 120;
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
    for (const item of navByRole[role]) {
      router.prefetch(item.href);
    }
  }, [role, router]);

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

    document.body.style.overflow = mobileOpen ? "hidden" : previousBodyOverflow;
    document.documentElement.style.overflow = mobileOpen ? "hidden" : previousHtmlOverflow;

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, [mobileOpen]);

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

  const dateFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat("fr-SN", {
        day: "2-digit",
        month: "short",
      }),
    [],
  );

  const currentTime = timeFormatter.format(now);
  const currentDate = dateFormatter.format(now);
  const shellLayoutStyle = { ["--sidebar-width" as string]: `${collapsed ? 92 : 258}px` } as React.CSSProperties;

  const startNavTransition = (href: string) => {
    if (href === pathname) return;
    router.prefetch(href);
    navLoadingStartedAtRef.current = Date.now();
    pendingPathRef.current = href;
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
    }, 6000);

    setNavLoading(true);
    setProfileOpen(false);
  };

  return (
    <div className="relative min-h-[100svh] overflow-x-clip bg-transparent md:min-h-[100dvh]" style={shellLayoutStyle}>
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[var(--sidebar-width)] px-3 py-4 transition-[width] duration-300 ease-out md:block">
        <div className="flex h-full flex-col rounded-[24px] border border-[rgba(255,255,255,0.08)] bg-[linear-gradient(180deg,#1C2722_0%,#16201B_100%)] p-3 shadow-[0_18px_40px_rgba(20,16,11,0.32)]">
          <SidebarBrand collapsed={collapsed} role={role} onCollapse={() => setCollapsed(true)} onExpand={() => setCollapsed(false)} />

          <div className="scroll-thin mt-5 flex-1 overflow-y-auto overscroll-y-contain pr-1">
            <SidebarNav pathname={pathname} collapsed={collapsed} role={role} onNavigate={startNavTransition} />
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
              <Image src="/logo.png" alt="Logo WeeFarm" width={40} height={40} className="h-10 w-10 rounded-lg border border-[rgba(255,255,255,0.14)] bg-[rgba(255,255,255,0.08)] p-1 object-contain" />
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

      <div className="relative z-10 min-h-[100svh] min-w-0 px-3 pb-[calc(2rem+env(safe-area-inset-bottom))] pt-0 touch-pan-y transition-[margin-left] duration-300 ease-out sm:px-5 md:ml-[var(--sidebar-width)] md:min-h-[100dvh] md:px-7 md:pt-6">
        <header
          ref={headerRef}
          className={cx(
            "fixed inset-x-3 top-3 z-50 mb-6 rounded-[22px] border border-[var(--line)] border-b border-gray-200 bg-[color:rgba(255,253,247,0.9)] px-3 py-3 shadow-sm backdrop-blur-md sm:inset-x-5 sm:px-4 md:sticky md:inset-x-auto md:top-3",
            mobileOpen && "pointer-events-none",
          )}
        >
          <div className="hidden items-center gap-3 md:grid md:grid-cols-[auto_minmax(0,1fr)_auto]">
            <div className="flex items-center gap-2.5">
              <span className="inline-flex h-9 items-center rounded-full border border-[var(--line)] bg-[var(--surface)] px-2.5 text-sm shadow-[0_4px_10px_rgba(38,32,22,0.05)]">🇸🇳</span>
              <span className="inline-flex h-9 items-center gap-1.5 rounded-full border border-[var(--line)] bg-[var(--surface)] px-3 text-xs font-medium text-[var(--muted)] shadow-[0_4px_10px_rgba(38,32,22,0.05)]">
                <WeatherIcon className="h-3.5 w-3.5" />
                {meta.locationLabel}
              </span>
            </div>

            <div className="mx-auto w-full max-w-2xl">
              <div className="relative">
                <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
                <input
                  className="soft-focus h-11 w-full rounded-full border border-[var(--line)] bg-[var(--surface)] py-2.5 pl-10 pr-4 text-sm text-[var(--text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.45),0_6px_16px_rgba(38,32,22,0.05)] transition-all duration-200 placeholder:text-[color:rgba(110,103,89,0.85)] focus:border-[var(--primary)] focus:shadow-[0_0_0_3px_rgba(0,126,47,0.14)]"
                  placeholder={meta.searchPlaceholder}
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="rounded-xl border border-[var(--line)] bg-[var(--surface)] px-2.5 py-1.5 text-xs font-semibold text-[var(--text)] shadow-[0_4px_10px_rgba(38,32,22,0.05)]">{currentTime}</span>

              <button className="soft-focus relative rounded-xl border border-[var(--line)] bg-[var(--surface)] p-2.5 text-[var(--muted)] shadow-[0_4px_10px_rgba(38,32,22,0.05)] transition-all duration-200 hover:-translate-y-0.5 hover:text-[var(--primary)]">
                <BellIcon className="h-4 w-4" />
                <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-[var(--warning)]" />
              </button>

              <div className="relative" ref={desktopProfileRef}>
                <button
                  className="soft-focus group flex items-center gap-2 rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-2.5 py-1.5 text-left shadow-[0_4px_12px_rgba(38,32,22,0.06)] transition-all duration-200 hover:-translate-y-0.5 hover:border-[#CFC5B4]"
                  onClick={() => setProfileOpen((prev) => !prev)}
                  aria-haspopup="menu"
                  aria-expanded={profileOpen}
                >
                  <span className="hidden flex-col leading-tight xl:flex">
                    <span className="text-sm font-semibold text-[var(--text)]">{meta.name}</span>
                    <span className="text-[11px] text-[var(--muted)]">{meta.roleLabel}</span>
                  </span>
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--primary)] text-[11px] font-semibold text-white shadow-[0_6px_12px_rgba(0,126,47,0.28)]">
                    {meta.initials}
                  </span>
                  <ChevronDownIcon className={cx("h-3.5 w-3.5 text-[var(--muted)] transition-transform duration-200", profileOpen && "rotate-180")} />
                </button>

                <ProfileDropdown open={profileOpen} role={role} onLogout={logout} meta={meta} />
              </div>
            </div>
          </div>

          <div className="space-y-3 md:hidden">
            <div className="flex items-center gap-2">
              <button className="soft-focus rounded-xl border border-[var(--line)] bg-[var(--surface)] p-2 text-[var(--muted)] shadow-[0_4px_10px_rgba(38,32,22,0.05)]" onClick={() => setMobileOpen(true)} aria-label="Ouvrir le menu">
                <MenuIcon className="h-5 w-5" />
              </button>

              <span className="inline-flex h-8 items-center rounded-full border border-[var(--line)] bg-[var(--surface)] px-2 text-xs shadow-[0_4px_10px_rgba(38,32,22,0.05)]">🇸🇳</span>
              <span className="inline-flex h-8 items-center gap-1.5 rounded-full border border-[var(--line)] bg-[var(--surface)] px-2.5 text-xs text-[var(--muted)] shadow-[0_4px_10px_rgba(38,32,22,0.05)]">
                <WeatherIcon className="h-3.5 w-3.5" />
                {role === "admin" ? "Plateforme" : "Thies"}
              </span>

              <div className="ml-auto flex items-center gap-1.5">
                <span className="rounded-lg border border-[var(--line)] bg-[var(--surface)] px-2 py-1 text-[11px] font-medium text-[var(--text)]">{currentTime}</span>

                <button className="soft-focus relative rounded-xl border border-[var(--line)] bg-[var(--surface)] p-2 text-[var(--muted)] shadow-[0_4px_10px_rgba(38,32,22,0.05)]">
                  <BellIcon className="h-4 w-4" />
                  <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-[var(--warning)]" />
                </button>

                <div className="relative" ref={mobileProfileRef}>
                  <button className="soft-focus flex h-8 w-8 items-center justify-center rounded-full bg-[var(--primary)] text-[11px] font-semibold text-white shadow-[0_6px_12px_rgba(0,126,47,0.22)]" onClick={() => setProfileOpen((prev) => !prev)} aria-haspopup="menu" aria-expanded={profileOpen}>
                    {meta.initials}
                  </button>

                  <ProfileDropdown open={profileOpen} role={role} onLogout={logout} meta={meta} />
                </div>
              </div>
            </div>

            <div className="relative">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
              <input className="soft-focus h-10 w-full rounded-full border border-[var(--line)] bg-[var(--surface)] py-2 pl-9 pr-3 text-sm shadow-[0_4px_10px_rgba(38,32,22,0.05)] placeholder:text-[color:rgba(110,103,89,0.85)] focus:border-[var(--primary)]" placeholder={meta.searchPlaceholder} />
            </div>
          </div>

          <p className="mt-2 hidden text-right text-[11px] text-[var(--muted)] md:block">{currentDate}</p>
        </header>

        <div className="md:hidden" aria-hidden="true" style={{ height: `${loaderTop}px` }} />

        <div className="relative z-0">
          <div className={cx("transition-opacity duration-150", navLoading && "pointer-events-none opacity-60")}>{children}</div>
        </div>
      </div>

      {navLoading && (
        <div
          className="pointer-events-none fixed bottom-0 left-0 right-0 z-[45] md:left-[var(--sidebar-width)]"
          style={{ top: `${loaderTop}px` }}
        >
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(249,246,239,0.86)_0%,rgba(249,246,239,0.7)_32%,rgba(249,246,239,0.45)_72%,rgba(249,246,239,0.14)_100%)] backdrop-blur-[12px] [mask-image:linear-gradient(180deg,black,black_72%,transparent)]" />
          <div className="absolute inset-x-0 top-0 h-24 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.8),rgba(255,255,255,0))]" />

          <div className="relative flex h-full items-center justify-center px-3 pb-[calc(1rem+env(safe-area-inset-bottom))] sm:px-5 md:px-7">
            <AgriBrandLoader
              mode="panel"
              title="Chargement de section"
              subtitle="Mise a jour des donnees d'exploitation..."
            />
          </div>
        </div>
      )}
    </div>
  );
}
