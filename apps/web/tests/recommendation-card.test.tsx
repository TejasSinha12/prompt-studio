import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RecommendationCard } from "@/components/workspace/RecommendationCard";
import type { Recommendation } from "@/lib/types";

function rec(over: Partial<Recommendation> = {}): Recommendation {
  return {
    id: "r1", finding_id: null, fingerprint: "fp", engine: "rule_based", model: null, title: "Add acceptance criteria",
    problem: "No acceptance criteria", rationale: "Agent cannot tell when to stop", proposal: "Add criteria",
    benefits: "Clear stopping condition", tradeoffs: "Time", complexity: "low", dependencies: "", disadvantages: "Rigid",
    verification: "Exists", requirement_kind: "acceptance", requirement_text: "All tests pass",
    alternatives: [{ title: "Agent proposes", requirement_text: "Propose criteria first", tradeoffs: "Round-trip" }],
    status: "proposed", needs_edit: false, events: [{ id: "e1", from_status: null, to_status: "proposed", note: "Generated", created_at: "2026-10-15T10:00:00Z" }],
    created_at: "2026-10-15T10:00:00Z", updated_at: "2026-10-15T10:00:00Z", ...over,
  };
}

const noop = () => {};

describe("RecommendationCard", () => {
  it("shows all required recommendation fields", () => {
    render(<RecommendationCard rec={rec()} onApprove={noop} onReject={noop} onDefer={noop} onRestore={noop} onSaveEdit={noop} />);
    for (const t of ["No acceptance criteria", "Agent cannot tell when to stop", "Clear stopping condition", "Rigid", "Exists"]) {
      expect(screen.getByText(t)).toBeInTheDocument();
    }
    expect(screen.getByText("Rule-based")).toBeInTheDocument();
  });

  it("approves with edited text and kind", async () => {
    const onApprove = vi.fn();
    render(<RecommendationCard rec={rec()} onApprove={onApprove} onReject={noop} onDefer={noop} onRestore={noop} onSaveEdit={noop} />);
    const ta = screen.getByLabelText("Requirement text");
    await userEvent.clear(ta);
    await userEvent.type(ta, "sample.csv converts exactly");
    await userEvent.selectOptions(screen.getByLabelText("Type"), "functional");
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(onApprove).toHaveBeenCalledWith({ requirement_text: "sample.csv converts exactly", requirement_kind: "functional", note: "" });
  });

  it("approves a chosen alternative", async () => {
    const onApprove = vi.fn();
    render(<RecommendationCard rec={rec()} onApprove={onApprove} onReject={noop} onDefer={noop} onRestore={noop} onSaveEdit={noop} />);
    await userEvent.click(screen.getByRole("radio", { name: /Agent proposes/ }));
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(onApprove).toHaveBeenCalledWith({ alternative_index: 0, note: "" });
  });

  it("blocks approval while a placeholder remains", () => {
    render(<RecommendationCard rec={rec({ requirement_text: "Target: [state latency target]", alternatives: [] })} onApprove={noop} onReject={noop} onDefer={noop} onRestore={noop} onSaveEdit={noop} />);
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("note")).toHaveTextContent("placeholder");
  });

  it("reject and defer pass the decision note", async () => {
    const onReject = vi.fn();
    const onDefer = vi.fn();
    render(<RecommendationCard rec={rec()} onApprove={noop} onReject={onReject} onDefer={onDefer} onRestore={noop} onSaveEdit={noop} />);
    await userEvent.type(screen.getByLabelText("Decision note (optional)"), "not needed");
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    await userEvent.click(screen.getByRole("button", { name: "Defer" }));
    expect(onReject).toHaveBeenCalledWith("not needed");
    expect(onDefer).toHaveBeenCalledWith("not needed");
  });

  it("rejected recommendations can be restored, not approved", async () => {
    const onRestore = vi.fn();
    render(<RecommendationCard rec={rec({ status: "rejected" })} onApprove={noop} onReject={noop} onDefer={noop} onRestore={onRestore} onSaveEdit={noop} />);
    await userEvent.click(screen.getByRole("button", { name: /Rejected|rejected/ }).closest("article")!.querySelector("button")!);
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Restore to proposed" }));
    expect(onRestore).toHaveBeenCalled();
  });

  it("shows decision history", async () => {
    render(<RecommendationCard rec={rec()} onApprove={noop} onReject={noop} onDefer={noop} onRestore={noop} onSaveEdit={noop} />);
    await userEvent.click(screen.getByRole("button", { name: "History (1)" }));
    expect(screen.getByText(/Generated/)).toBeInTheDocument();
  });
});
