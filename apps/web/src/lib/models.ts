import type { ModelInfo } from "./types";

export type Pref = "speed" | "balanced" | "quality";

export function fit(model: ModelInfo, mem: number | null): { label: string; tone: "ok" | "warn" | "danger" | "neutral" } {
  if (!model.size_bytes || !mem) return { label: "unknown", tone: "neutral" };
  // Heuristic: weights + ~20% overhead for KV cache/runtime at modest context sizes.
  const need = model.size_bytes * 1.2;
  if (need < mem * 0.5) return { label: "likely fits", tone: "ok" };
  if (need < mem * 0.75) return { label: "tight", tone: "warn" };
  return { label: "may not fit", tone: "danger" };
}

export function recommend(models: ModelInfo[], mem: number | null, pref: Pref): ModelInfo | null {
  const usable = models.filter((m) => m.size_bytes && fit(m, mem).tone !== "danger").sort((a, b) => a.size_bytes! - b.size_bytes!);
  if (usable.length === 0) return null;
  if (pref === "speed") return usable[0]!;
  if (pref === "quality") return usable[usable.length - 1]!;
  return usable[Math.floor((usable.length - 1) / 2)]!;
}
