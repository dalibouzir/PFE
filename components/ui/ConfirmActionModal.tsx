"use client";

import { LiquidGlassModal } from "@/components/ui/LiquidGlassModal";

type ConfirmActionModalProps = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "danger" | "primary";
  loading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConfirmActionModal({
  open,
  title,
  message,
  confirmLabel = "Confirmer",
  cancelLabel = "Annuler",
  tone = "primary",
  loading = false,
  onCancel,
  onConfirm,
}: ConfirmActionModalProps) {
  return (
    <LiquidGlassModal
      open={open}
      onClose={onCancel}
      title={title}
      subtitle="Veuillez confirmer cette action"
      size="sm"
      footer={
        <div className="flex items-center justify-end gap-2">
          <button type="button" onClick={onCancel} className="soft-focus wf-btn-secondary px-4 py-2 text-sm font-semibold" disabled={loading}>
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={`soft-focus px-4 py-2 text-sm font-semibold text-white ${
              tone === "danger" ? "rounded-xl bg-[var(--danger)] hover:opacity-90" : "wf-btn-primary"
            }`}
          >
            {loading ? "Traitement..." : confirmLabel}
          </button>
        </div>
      }
    >
      <p className="text-sm text-[var(--text)]">{message}</p>
    </LiquidGlassModal>
  );
}
