"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

type ModalSize = "sm" | "md" | "lg" | "xl";

type LiquidGlassModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: ModalSize;
  closeLabel?: string;
};

const sizeClass: Record<ModalSize, string> = {
  sm: "max-w-md",
  md: "max-w-2xl",
  lg: "max-w-3xl",
  xl: "max-w-4xl",
};

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function LiquidGlassModal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  size = "md",
  closeLabel = "Fermer",
}: LiquidGlassModalProps) {
  const [mounted, setMounted] = useState(open);
  const [visible, setVisible] = useState(false);
  const exitTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (exitTimerRef.current) {
      window.clearTimeout(exitTimerRef.current);
      exitTimerRef.current = null;
    }

    if (open) {
      setMounted(true);
      requestAnimationFrame(() => setVisible(true));
      return;
    }

    if (!mounted) return;
    setVisible(false);
    exitTimerRef.current = window.setTimeout(() => {
      setMounted(false);
    }, 220);
  }, [open, mounted]);

  useEffect(() => {
    return () => {
      if (exitTimerRef.current) {
        window.clearTimeout(exitTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!mounted) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mounted]);

  useEffect(() => {
    if (!mounted) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mounted, onClose]);

  if (!mounted || typeof document === "undefined") return null;

  return createPortal(
    <div
      className={cx(
        "fixed inset-0 z-[120] flex items-end justify-center px-2 pb-[calc(0.35rem+env(safe-area-inset-bottom))] pt-[calc(0.35rem+env(safe-area-inset-top))] transition-opacity duration-200 sm:items-center sm:p-4",
        visible ? "opacity-100" : "opacity-0",
      )}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <button
        className={cx(
          "absolute inset-0 bg-[rgba(32,26,17,0.36)] backdrop-blur-[1px] transition-opacity duration-200",
          visible ? "opacity-100" : "opacity-0",
        )}
        aria-label="Fermer la fenetre"
        onClick={onClose}
      />

      <div
        className={cx(
          "relative flex w-full min-h-0 max-h-[96dvh] flex-col overflow-hidden rounded-[24px] border border-[var(--line)] bg-[var(--surface)] shadow-[0_20px_44px_rgba(35,30,21,0.2)] transition-all duration-200 sm:max-h-[min(92dvh,860px)]",
          "sm:rounded-[26px]",
          sizeClass[size],
          visible ? "translate-y-0 scale-100 opacity-100" : "translate-y-8 opacity-0 sm:translate-y-3 sm:scale-[0.985]",
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="pointer-events-none absolute inset-x-4 top-0 h-px bg-white/85" />

        <div className="relative flex min-h-0 flex-1 flex-col">
          <div className="flex justify-center pt-2 sm:hidden">
            <span className="h-1 w-10 rounded-full bg-[rgba(74,62,43,0.28)]" />
          </div>

          <header className="flex items-start justify-between gap-3 px-4 pb-3 pt-3 sm:px-5 sm:pt-4">
            <div>
              <h3 className="text-lg font-semibold text-[var(--text)]">{title}</h3>
              {subtitle && <p className="mt-1 text-sm text-[var(--muted)]">{subtitle}</p>}
            </div>

            <button
              className="soft-focus wf-btn-secondary px-3 py-1.5 text-sm font-medium"
              onClick={onClose}
              type="button"
            >
              {closeLabel}
            </button>
          </header>

          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-1 sm:px-5 sm:pb-4">
            {children}
          </div>

          {footer && <footer className="shrink-0 border-t border-[var(--line)] bg-[var(--surface-soft)] px-4 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-3 sm:px-5 sm:py-3">{footer}</footer>}
        </div>
      </div>
    </div>,
    document.body,
  );
}
