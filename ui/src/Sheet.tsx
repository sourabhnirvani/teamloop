import { useEffect, useRef } from "react";
import { Icon } from "./Icon";
import "./hoodie-views.css";

// One overlay for every dialog and panel: a real dialog (role, focus kept inside, focus given back on close),
// closed with the close button, Esc or a click outside. Full screen with a back button on phones.
export function Sheet({ title, onClose, children, wide = false, className = "" }: {
  title: string; onClose: () => void; children: React.ReactNode; wide?: boolean; className?: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const el = box.current;
    el?.querySelector<HTMLElement>("input, textarea, select, button:not(.sheet-close)")?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
      if (e.key !== "Tab" || !el) return;
      const all = [...el.querySelectorAll<HTMLElement>("button, input, textarea, select, a[href], [tabindex]:not([tabindex='-1'])")]
        .filter((x) => !x.hasAttribute("disabled"));
      if (!all.length) return;
      const first = all[0], last = all[all.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      before?.focus?.({ preventScroll: true });
    };
  }, [onClose]);

  return (
    <div className="overlay" onClick={onClose}>
      <div ref={box} className={`sheet hv-sheet ${wide ? "wide" : ""} ${className}`} role="dialog" aria-modal="true" aria-label={title}
           onClick={(e) => e.stopPropagation()}>
        <header className="sheet-head">
          <button className="icon sheet-back" onClick={onClose} aria-label="Back"><Icon name="back" size={24} /></button>
          <b>{title}</b>
          <button className="icon sheet-close hv-close" onClick={onClose} aria-label="Close"><Icon name="no" size={20} /></button>
        </header>
        <div className="sheet-body">{children}</div>
      </div>
    </div>
  );
}
