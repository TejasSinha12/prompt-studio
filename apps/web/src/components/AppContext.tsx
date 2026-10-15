"use client";

import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AppSettings, ModelsStatus } from "@/lib/types";

interface AppState {
  models: ModelsStatus | null;
  modelsError: string | null;
  backendOk: boolean | null;
  settings: AppSettings | null;
  refresh: () => Promise<void>;
  /** True when a local model is reachable and selected. */
  aiReady: boolean;
  aiUnavailableReason: string;
}

const Ctx = createContext<AppState | null>(null);

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside AppProvider");
  return v;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [models, setModels] = useState<ModelsStatus | null>(null);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [m, s] = await Promise.all([api.get<ModelsStatus>("/api/models"), api.get<AppSettings>("/api/settings")]);
      setModels(m);
      setSettings(s);
      setBackendOk(true);
      setModelsError(null);
    } catch (e) {
      setBackendOk(false);
      setModelsError(e instanceof Error ? e.message : "Backend unavailable");
    }
  }, []);

  useEffect(() => {
    void refresh();
    // Light polling so the status bar notices Ollama starting/stopping. No other background work.
    const t = setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 60_000);
    return () => clearInterval(t);
  }, [refresh]);

  const aiReady = Boolean(models?.available && models.selected_model && models.selected_model_installed);
  const aiUnavailableReason = !models
    ? "Checking local model runtime…"
    : !models.available
      ? "Ollama is not reachable. Rule-based features remain available."
      : !models.selected_model
        ? "No local model selected. Choose one on the Local Models page."
        : !models.selected_model_installed
          ? `Selected model "${models.selected_model}" is not installed in Ollama.`
          : "";

  return (
    <Ctx.Provider value={{ models, modelsError, backendOk, settings, refresh, aiReady, aiUnavailableReason }}>
      {children}
    </Ctx.Provider>
  );
}
