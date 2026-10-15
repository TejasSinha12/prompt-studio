"use client";

import { CheckCircle2, Cpu, RefreshCw, XCircle } from "lucide-react";
import { useState } from "react";
import { useApp } from "@/components/AppContext";
import { useToast } from "@/components/Toast";
import { Badge, Button, Card, CardHeader, EmptyState, Notice, PageHeader, Select, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/format";
import { useResource } from "@/lib/hooks";
import { fit, type Pref, recommend } from "@/lib/models";
import type { AppSettings, ModelDetails, SystemInfo } from "@/lib/types";

export default function ModelsPage() {
  const toast = useToast();
  const { models, refresh, settings } = useApp();
  const sys = useResource<SystemInfo>("/api/system");
  const [pref, setPref] = useState<Pref>("balanced");
  const [details, setDetails] = useState<Record<string, ModelDetails | "loading" | "error">>({});
  const [busy, setBusy] = useState(false);
  const mem = sys.data?.total_memory_bytes ?? null;

  async function select(name: string | null) {
    if (!settings) return;
    try {
      await api.put<AppSettings>("/api/settings", { ...settings, model: name });
      toast(name ? `Selected ${name}` : "Model cleared");
      await refresh();
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  async function loadDetails(name: string) {
    setDetails((d) => ({ ...d, [name]: "loading" }));
    try {
      const r = await api.get<ModelDetails>(`/api/models/details?name=${encodeURIComponent(name)}`);
      setDetails((d) => ({ ...d, [name]: r }));
    } catch {
      setDetails((d) => ({ ...d, [name]: "error" }));
    }
  }

  const rec = models ? recommend(models.models, mem, pref) : null;
  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      <PageHeader title="Local Models" description="Ollama is optional. Without it, every rule-based feature keeps working."
        actions={<Button icon={<RefreshCw className="size-4" />} busy={busy} onClick={async () => { setBusy(true); await refresh(); setBusy(false); }}>Re-check</Button>} />
      {!models ? <Spinner label="Checking Ollama" /> : (
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader title="Runtime status" />
            <div className="flex flex-col gap-2 px-4 py-3 text-[13px]">
              <p className="flex items-center gap-2">
                {models.available ? <CheckCircle2 className="size-4 text-ok" aria-hidden /> : <XCircle className="size-4 text-danger" aria-hidden />}
                {models.available ? `Ollama reachable at ${models.endpoint}${models.version ? ` (version ${models.version})` : ""}` : `Ollama not reachable at ${models.endpoint}`}
              </p>
              {models.error && <p className="text-xs text-muted">{models.error}</p>}
              <p className="text-xs text-muted">Selected model: <strong className="text-text">{models.selected_model ?? "none"}</strong>
                {models.selected_model && !models.selected_model_installed && <span className="text-danger"> — not installed</span>}
              </p>
              <p className="text-xs text-muted">Endpoint and timeouts are configured in Settings. Only loopback endpoints are allowed unless you explicitly opt in.</p>
            </div>
          </Card>

          {!models.available && (
            <Card>
              <CardHeader title="Set up Ollama (optional)" />
              <div className="flex flex-col gap-2 px-4 py-3 text-[13px]">
                <p>1. Install Ollama from <code>https://ollama.com/download</code> (macOS, Windows, Linux) or on macOS with Homebrew: <code className="rounded bg-panel-2 px-1">brew install ollama</code></p>
                <p>2. Start it: open the Ollama app, or run <code className="rounded bg-panel-2 px-1">ollama serve</code></p>
                <p>3. Download a model yourself, e.g. <code className="rounded bg-panel-2 px-1">ollama pull llama3.2:3b</code> (≈2 GB) or <code className="rounded bg-panel-2 px-1">ollama pull qwen2.5:7b</code> (≈4.7 GB).</p>
                <p>4. Click “Re-check”, then select the model below.</p>
                <Notice>Prompt Studio never downloads models automatically. Sizes are approximate and change between releases; check <code>ollama show</code> after downloading.</Notice>
              </div>
            </Card>
          )}

          {models.available && (
            <Card>
              <CardHeader title={`Installed models (${models.models.length})`}
                actions={models.models.length > 0 ? (
                  <label className="flex items-center gap-2 text-xs text-muted">Preference
                    <Select aria-label="Performance preference" value={pref} onChange={(e) => setPref(e.target.value as Pref)} className="h-7 w-32 text-xs">
                      <option value="speed">Speed</option>
                      <option value="balanced">Balanced</option>
                      <option value="quality">Quality</option>
                    </Select>
                  </label>) : undefined} />
              {models.models.length === 0 ? (
                <EmptyState icon={<Cpu className="size-6" />} title="No models installed">Run <code>ollama pull llama3.2:3b</code> (or another model) in a terminal, then re-check.</EmptyState>
              ) : (
                <>
                  {rec && <p className="px-4 pt-3 text-xs">Suggestion for “{pref}”: <strong>{rec.name}</strong> <span className="text-muted">— based only on download size vs. this machine’s memory ({formatBytes(mem)}). Not benchmarked.</span></p>}
                  <table className="mt-2 w-full text-[13px]">
                    <thead><tr className="border-b border-border text-left text-xs text-muted">
                      <th className="px-4 py-2 font-medium">Model</th><th className="px-2 py-2 font-medium">Size</th><th className="px-2 py-2 font-medium">Params / quant.</th><th className="px-2 py-2 font-medium">Memory fit*</th><th className="px-4 py-2"><span className="sr-only">Actions</span></th>
                    </tr></thead>
                    <tbody className="divide-y divide-border">
                      {models.models.map((m) => {
                        const f = fit(m, mem);
                        const d = details[m.name];
                        return (
                          <tr key={m.name} className="align-top">
                            <td className="px-4 py-2">
                              <p className="font-medium">{m.name} {m.name === models.selected_model && <Badge tone="ok">selected</Badge>}</p>
                              <p className="text-xs text-muted">{m.family ?? "unknown family"} · modified {formatDate(m.modified_at)}</p>
                              {d === "loading" && <Spinner />}
                              {d === "error" && <p className="text-xs text-danger">Could not load details.</p>}
                              {d && typeof d === "object" && <p className="mt-1 text-xs text-muted">Context window: {d.context_length?.toLocaleString() ?? "unknown"} tokens · capabilities: {d.capabilities.join(", ") || "not reported"}</p>}
                            </td>
                            <td className="px-2 py-2 text-xs">{formatBytes(m.size_bytes)}</td>
                            <td className="px-2 py-2 text-xs">{m.parameter_size ?? "—"} / {m.quantization ?? "—"}</td>
                            <td className="px-2 py-2"><Badge tone={f.tone}>{f.label}</Badge></td>
                            <td className="px-4 py-2 text-right whitespace-nowrap">
                              <Button size="sm" variant="ghost" onClick={() => loadDetails(m.name)}>Details</Button>
                              {m.name === models.selected_model ? <Button size="sm" onClick={() => select(null)}>Deselect</Button> : <Button size="sm" variant="primary" onClick={() => select(m.name)}>Select</Button>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <p className="px-4 py-3 text-xs text-muted">* Rough heuristic: download size + 20% vs. total memory. Actual use depends on quantization, context length (num_ctx), runtime settings and architecture. Not all models support structured (JSON) output equally well; malformed output is detected and reported.</p>
                </>
              )}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
