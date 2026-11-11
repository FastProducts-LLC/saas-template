import { useEffect, type ReactNode } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children?: ReactNode;
  footer?: ReactNode;
  "data-testid"?: string;
}

// Accessible modal dialog: closes on Escape and backdrop click, renders
// nothing when closed.
export default function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  "data-testid": testId,
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--ink)]/45 px-4 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        data-testid={testId}
        className="w-full max-w-md rounded-lg border border-[var(--line)] bg-white p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {title && <h2 className="text-base font-semibold text-[var(--ink)]">{title}</h2>}
        <div className={title ? "mt-3" : ""}>{children}</div>
        {footer && <div className="mt-6 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}
