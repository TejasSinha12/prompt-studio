"use client";

import { Loader2, X } from "lucide-react";
import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  forwardRef,
  useEffect,
  useId,
  useRef,
} from "react";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

// ----------------------------------------------------------------------------- Button

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-fg hover:bg-accent-hover border border-transparent",
  secondary: "bg-panel text-text border border-border hover:bg-panel-2 hover:border-border-strong",
  ghost: "bg-transparent text-text border border-transparent hover:bg-panel-2",
  danger: "bg-panel text-danger border border-border hover:bg-danger-soft hover:border-danger",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  busy?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", busy = false, icon, className, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-8.5 px-3 text-[13px]",
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {busy ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
});

export function IconButton({
  label,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cx(
        "inline-flex size-7 items-center justify-center rounded-md text-muted hover:bg-panel-2 hover:text-text",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

// ----------------------------------------------------------------------------- Form fields

const fieldBase =
  "w-full rounded-md border border-border bg-panel px-2.5 text-[13px] text-text placeholder:text-muted/70 " +
  "focus:border-accent focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-0 disabled:opacity-60";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={cx(fieldBase, "h-8.5", className)} {...rest} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return <textarea ref={ref} className={cx(fieldBase, "py-2 leading-relaxed", className)} {...rest} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, children, ...rest },
  ref,
) {
  return (
    <select ref={ref} className={cx(fieldBase, "h-8.5 pr-7", className)} {...rest}>
      {children}
    </select>
  );
});

export function Field({
  label,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  children: (id: string) => ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={cx("flex flex-col gap-1", className)}>
      <label htmlFor={id} className="text-xs font-medium text-muted">
        {label}
      </label>
      {children(id)}
      {hint && !error && <p className="text-xs text-muted">{hint}</p>}
      {error && (
        <p className="text-xs text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------- Display

type Tone = "neutral" | "accent" | "ok" | "warn" | "danger" | "info";
const TONES: Record<Tone, string> = {
  neutral: "bg-panel-2 text-muted border-border",
  accent: "bg-accent-soft text-accent border-transparent",
  ok: "bg-ok-soft text-ok border-transparent",
  warn: "bg-warn-soft text-warn border-transparent",
  danger: "bg-danger-soft text-danger border-transparent",
  info: "bg-sky-50 text-sky-800 border-transparent dark:bg-sky-950 dark:text-sky-300",
};

export function Badge({ tone = "neutral", children, className, title }: { tone?: Tone; children: ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex items-center gap-1 rounded border px-1.5 py-px text-[11px] font-medium whitespace-nowrap",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const SEVERITY_TONE: Record<string, Tone> = { critical: "danger", high: "danger", medium: "warn", low: "info", info: "neutral" };
export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <Badge tone={SEVERITY_TONE[severity] ?? "neutral"} className="uppercase tracking-wide">
      {severity === "info" ? "Info" : severity}
    </Badge>
  );
}

export function EngineBadge({ engine, model }: { engine: string; model?: string | null }) {
  if (engine === "local_ai")
    return (
      <Badge tone="accent" title="Produced by a local model via Ollama">
        Local AI{model ? ` · ${model}` : ""}
      </Badge>
    );
  if (engine === "manual") return <Badge>Manual</Badge>;
  return (
    <Badge tone="neutral" title="Produced by deterministic rules (no AI)">
      Rule-based
    </Badge>
  );
}

export function Card({ children, className, ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx("rounded-lg border border-border bg-panel", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, actions, subtitle }: { title: ReactNode; actions?: ReactNode; subtitle?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-xs text-muted">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {label}…
    </span>
  );
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      {icon && <div className="text-muted">{icon}</div>}
      <p className="text-sm font-medium">{title}</p>
      {children && <div className="max-w-md text-xs text-muted">{children}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-xs text-danger">
      <span>{message}</span>
      {onRetry && (
        <Button size="sm" variant="secondary" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function Notice({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <div className={cx("rounded-md border px-3 py-2 text-xs", TONES[tone])}>{children}</div>;
}

// ----------------------------------------------------------------------------- Tabs

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
  size = "md",
}: {
  tabs: { id: T; label: ReactNode; count?: number }[];
  value: T;
  onChange: (id: T) => void;
  label: string;
  size?: "sm" | "md";
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: React.KeyboardEvent, i: number) => {
    let next = -1;
    if (e.key === "ArrowRight") next = (i + 1) % tabs.length;
    if (e.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
    if (e.key === "Home") next = 0;
    if (e.key === "End") next = tabs.length - 1;
    if (next >= 0) {
      e.preventDefault();
      const t = tabs[next];
      if (t) onChange(t.id);
      refs.current[next]?.focus();
    }
  };
  return (
    <div role="tablist" aria-label={label} className="flex items-center gap-0.5 overflow-x-auto">
      {tabs.map((t, i) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            role="tab"
            type="button"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(t.id)}
            onKeyDown={(e) => onKey(e, i)}
            className={cx(
              "relative inline-flex items-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-colors",
              size === "sm" ? "px-2 py-1 text-xs" : "px-2.5 py-1.5 text-[13px]",
              active ? "bg-panel-2 text-text" : "text-muted hover:text-text",
            )}
          >
            {t.label}
            {t.count !== undefined && t.count > 0 && (
              <span className="rounded bg-border px-1 text-[10px] font-semibold text-text">{t.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ----------------------------------------------------------------------------- Dialog

export function Dialog({
  open,
  onClose,
  title,
  children,
  footer,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      aria-labelledby="dialog-title"
      className={cx(
        "m-auto rounded-xl border border-border bg-panel p-0 text-text shadow-2xl backdrop:backdrop-blur-[1px]",
        wide ? "w-[min(960px,94vw)]" : "w-[min(520px,94vw)]",
      )}
    >
      {open && (
        <div className="flex max-h-[85vh] flex-col">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h2 id="dialog-title" className="text-sm font-semibold">
              {title}
            </h2>
            <IconButton label="Close dialog" onClick={onClose}>
              <X className="size-4" />
            </IconButton>
          </div>
          <div className="overflow-y-auto px-4 py-4">{children}</div>
          {footer && <div className="flex justify-end gap-2 border-t border-border px-4 py-3">{footer}</div>}
        </div>
      )}
    </dialog>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-0.5 text-[13px] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded border border-border bg-panel-2 px-1 font-mono text-[10px] text-muted">{children}</kbd>;
}
