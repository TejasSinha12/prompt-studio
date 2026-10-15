"use client";

import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";
import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";
import { cx } from "./ui";

type ToastTone = "ok" | "error" | "info";
interface ToastItem {
  id: number;
  tone: ToastTone;
  message: string;
}

const ToastCtx = createContext<(message: string, tone?: ToastTone) => void>(() => {});

export function useToast() {
  return useContext(ToastCtx);
}

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const push = useCallback(
    (message: string, tone: ToastTone = "ok") => {
      const id = nextId++;
      setItems((xs) => [...xs.slice(-3), { id, tone, message }]);
      setTimeout(() => dismiss(id), tone === "error" ? 8000 : 3500);
    },
    [dismiss],
  );
  const value = useMemo(() => push, [push]);
  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed right-4 bottom-12 z-50 flex w-80 flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            role={t.tone === "error" ? "alert" : "status"}
            className={cx(
              "pointer-events-auto flex items-start gap-2 rounded-lg border bg-panel px-3 py-2.5 text-[13px] shadow-lg",
              t.tone === "error" ? "border-danger/50" : "border-border",
            )}
          >
            {t.tone === "ok" && <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ok" aria-hidden />}
            {t.tone === "error" && <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />}
            {t.tone === "info" && <Info className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />}
            <span className="flex-1">{t.message}</span>
            <button type="button" aria-label="Dismiss notification" onClick={() => dismiss(t.id)} className="text-muted hover:text-text">
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
