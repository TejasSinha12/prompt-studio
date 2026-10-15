import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { computeLineDiff, DiffView } from "@/components/DiffView";

describe("line diff", () => {
  it("counts added and removed lines with line numbers", () => {
    const { lines, added, removed } = computeLineDiff("a\nb\nc\n", "a\nB\nc\nd\n");
    expect(added).toBe(2);
    expect(removed).toBe(1);
    expect(lines.find((l) => l.type === "del")).toMatchObject({ text: "b", oldNo: 2, newNo: null });
    expect(lines.filter((l) => l.type === "add").map((l) => l.text)).toEqual(["B", "d"]);
  });

  it("shows 'No differences' for identical input", () => {
    render(<DiffView before="same" after="same" beforeLabel="v1" afterLabel="v2" />);
    expect(screen.getByText("No differences.")).toBeInTheDocument();
  });

  it("switches between unified and side-by-side layouts", async () => {
    render(<DiffView before={"one\ntwo"} after={"one\nthree"} beforeLabel="v1" afterLabel="v2" />);
    expect(screen.getByLabelText("Unified diff")).toHaveTextContent("three");
    await userEvent.click(screen.getByRole("tab", { name: "Side by side" }));
    expect(screen.queryByLabelText("Unified diff")).toBeNull();
    expect(screen.getAllByText("one")).toHaveLength(2);
  });
});
