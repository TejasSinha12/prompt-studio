import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ProjectForm, validateProject } from "@/components/ProjectForm";

describe("ProjectForm validation", () => {
  it("requires a name and does not submit when invalid", async () => {
    const onSubmit = vi.fn();
    render(<ProjectForm onSubmit={onSubmit} onCancel={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Name is required.");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits trimmed values", async () => {
    const onSubmit = vi.fn();
    render(<ProjectForm onSubmit={onSubmit} onCancel={() => {}} />);
    await userEvent.type(screen.getByLabelText("Name"), "  My project  ");
    await userEvent.selectOptions(screen.getByLabelText("Task category"), "bug_fix");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: "My project", task_category: "bug_fix" }));
  });

  it("validates lengths", () => {
    expect(validateProject({ name: "x".repeat(201), description: "", original_idea: "", task_category: "", target_agent: "" }).name).toMatch(/200/);
    expect(validateProject({ name: "ok", description: "d".repeat(5001), original_idea: "", task_category: "", target_agent: "" }).description).toBeDefined();
  });
});
