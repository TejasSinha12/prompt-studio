"use client";

import {
  BookOpen,
  Boxes,
  ChevronsLeft,
  ChevronsRight,
  Cpu,
  FileStack,
  FolderKanban,
  Gauge,
  LayoutDashboard,
  Library,
  Monitor,
  Moon,
  Settings,
  ShieldCheck,
  Sun,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import { runtimeLabel } from "@/lib/format";
import { useLocalStorage, useResource } from "@/lib/hooks";
import type { Page, ProjectSummary } from "@/lib/types";
import { AppProvider, useApp } from "./AppContext";
import { ToastProvider } from "./Toast";
import { cx, IconButton } from "./ui";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/library", label: "Prompt Library", icon: Library },
  { href: "/templates", label: "Templates", icon: FileStack },
  { href: "/evaluations", label: "Evaluations", icon: Gauge },
  { href: "/models", label: "Local Models", icon: Cpu },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/docs", label: "Documentation", icon: BookOpen },
];

type Theme = "system" | "light" | "dark";

function applyTheme(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function ThemeToggle({ collapsed }: { collapsed: boolean }) {
  const [theme, setTheme] = useLocalStorage<Theme>("ps-theme", "system");
  useEffect(() => {
    applyTheme(theme);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => applyTheme(theme);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [theme]);
  const next: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
  const Icon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  return (
    <button
      type="button"
      onClick={() => setTheme(next[theme])}
      className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[13px] text-muted hover:bg-panel-2 hover:text-text"
      aria-label={`Theme: ${theme}. Click to change.`}
      title={`Theme: ${theme}`}
    >
      <Icon className="size-4 shrink-0" aria-hidden />
      {!collapsed && <span className="capitalize">Theme: {theme}</span>}
    </button>
  );
}

function Sidebar({ collapsed, setCollapsed }: { collapsed: boolean; setCollapsed: (v: boolean) => void }) {
  const pathname = usePathname();
  const recent = useResource<Page<ProjectSummary>>("/api/projects?limit=6");
  useEffect(() => {
    void recent.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh list on navigation
  }, [pathname]);
  return (
    <aside
      className={cx(
        "flex shrink-0 flex-col border-r border-border bg-panel transition-[width] duration-150",
        collapsed ? "w-14" : "w-60",
      )}
      aria-label="Primary"
    >
      <div className="flex h-12 items-center justify-between gap-2 border-b border-border px-3">
        <Link href="/" className="flex min-w-0 items-center gap-2 font-semibold tracking-tight">
          <Boxes className="size-5 shrink-0 text-accent" aria-hidden />
          {!collapsed && <span className="truncate">Prompt Studio</span>}
        </Link>
        <IconButton label={collapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
        </IconButton>
      </div>
      <nav className="flex flex-col gap-0.5 p-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              title={collapsed ? label : undefined}
              className={cx(
                "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] font-medium transition-colors",
                active ? "bg-accent-soft text-accent" : "text-muted hover:bg-panel-2 hover:text-text",
              )}
            >
              <Icon className="size-4 shrink-0" aria-hidden />
              {!collapsed && label}
            </Link>
          );
        })}
      </nav>
      {!collapsed && (
        <div className="mt-2 min-h-0 flex-1 overflow-y-auto border-t border-border px-2 pt-3">
          <p className="px-2 pb-1 text-[11px] font-semibold tracking-wide text-muted uppercase">Recent projects</p>
          {recent.data?.items.length === 0 && <p className="px-2 text-xs text-muted">No projects yet.</p>}
          {recent.data?.items.map((p) => {
            const href = `/projects/${p.id}`;
            return (
              <Link
                key={p.id}
                href={href}
                aria-current={pathname === href ? "page" : undefined}
                className={cx(
                  "block truncate rounded-md px-2 py-1 text-[13px]",
                  pathname === href ? "bg-panel-2 text-text" : "text-muted hover:bg-panel-2 hover:text-text",
                )}
              >
                {p.name}
              </Link>
            );
          })}
        </div>
      )}
      <div className={cx("border-t border-border p-2", collapsed && "mt-auto")}>
        <ThemeToggle collapsed={collapsed} />
      </div>
    </aside>
  );
}

function StatusBar() {
  const { models, backendOk, aiReady } = useApp();
  let ai: ReactNode;
  if (backendOk === false) ai = <span className="text-danger">Backend unreachable</span>;
  else if (!models) ai = <span>Checking local AI…</span>;
  else if (aiReady) ai = <span>Local AI ready · {models.selected_model}</span>;
  else if (models.available) ai = <span>{runtimeLabel(models.provider)} connected · no model selected — rule-based mode</span>;
  else ai = <span>{runtimeLabel(models.provider)} unavailable — rule-based mode</span>;
  return (
    <footer className="flex h-8 shrink-0 items-center justify-between gap-4 border-t border-border bg-panel px-3 text-[11px] text-muted">
      <Link href="/models" className="flex items-center gap-1.5 hover:text-text" aria-label="Local model status">
        <span
          aria-hidden
          className={cx("size-2 rounded-full", backendOk === false ? "bg-danger" : aiReady ? "bg-ok" : "bg-warn")}
        />
        {ai}
      </Link>
      <span className="flex items-center gap-1.5" title="No telemetry. No cloud providers. API bound to 127.0.0.1.">
        <ShieldCheck className="size-3.5" aria-hidden />
        Local-only · no telemetry · no cloud providers
      </span>
    </footer>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useLocalStorage<boolean>("ps-sidebar-collapsed", false);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return (
    <AppProvider>
      <ToastProvider>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-panel focus:px-3 focus:py-2">
          Skip to content
        </a>
        <div className="flex h-screen flex-col">
          <div className="flex min-h-0 flex-1">
            <Sidebar collapsed={mounted && collapsed} setCollapsed={setCollapsed} />
            <main id="main" className="min-w-0 flex-1 overflow-y-auto">
              {children}
            </main>
          </div>
          <StatusBar />
        </div>
      </ToastProvider>
    </AppProvider>
  );
}
