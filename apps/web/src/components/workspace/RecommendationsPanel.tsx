"use client";

import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import type { Recommendation, RecStatus, ReqKind } from "@/lib/types";
import { useToast } from "../Toast";
import { EmptyState, Tabs } from "../ui";
import { type ApprovePayload, RecommendationCard } from "./RecommendationCard";

export function RecommendationsPanel({ recs, onChanged }: { recs: Recommendation[]; onChanged: () => void }) {
  const toast = useToast();
  const [tab, setTab] = useState<RecStatus>("proposed");
  const [busy, setBusy] = useState<string | null>(null);

  async function act(rec: Recommendation, fn: () => Promise<unknown>, msg: string) {
    setBusy(rec.id);
    try {
      await fn();
      toast(msg);
      onChanged();
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setBusy(null);
    }
  }

  const count = (s: RecStatus) => recs.filter((r) => r.status === s).length;
  const shown = recs.filter((r) => r.status === tab);
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted">Only approved recommendations change the confirmed specification. Rejected ones are never re-proposed automatically.</p>
      <Tabs
        label="Recommendation status"
        size="sm"
        value={tab}
        onChange={setTab}
        tabs={(["proposed", "deferred", "approved", "rejected"] as RecStatus[]).map((s) => ({ id: s, label: s[0]!.toUpperCase() + s.slice(1), count: count(s) }))}
      />
      {shown.length === 0 ? (
        <EmptyState title={`No ${tab} recommendations`}>{recs.length === 0 ? "Run an analysis to generate recommendations for significant findings." : null}</EmptyState>
      ) : (
        shown.map((r) => (
          <RecommendationCard
            key={r.id}
            rec={r}
            busy={busy === r.id}
            onApprove={(p: ApprovePayload) => act(r, () => api.post(`/api/recommendations/${r.id}/approve`, p), "Approved — requirement added")}
            onReject={(note) => act(r, () => api.post(`/api/recommendations/${r.id}/reject`, { note }), "Rejected")}
            onDefer={(note) => act(r, () => api.post(`/api/recommendations/${r.id}/defer`, { note }), "Deferred")}
            onRestore={() => act(r, () => api.post(`/api/recommendations/${r.id}/restore`, {}), "Restored to proposed")}
            onSaveEdit={(text: string, kind: ReqKind) => act(r, () => api.patch(`/api/recommendations/${r.id}`, { requirement_text: text, requirement_kind: kind }), "Edit saved")}
          />
        ))
      )}
    </div>
  );
}
