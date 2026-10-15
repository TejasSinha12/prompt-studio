import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "./fixtures";

const TARGET = path.resolve(__dirname, ".results", "handoff-target");

test("custom template: create, use, and save a project as template", async ({ page, external }) => {
  void external;
  await page.goto("/templates");
  await page.getByRole("button", { name: "New template" }).click();
  const dlg = page.getByRole("dialog");
  await dlg.getByLabel("Name").fill("REST endpoint");
  await dlg.getByLabel("Idea skeleton").fill("Add a REST endpoint for [resource].");
  await dlg.getByRole("button", { name: "Add requirement" }).click();
  await dlg.getByLabel("Requirement 1 text").fill("Endpoint is documented in OpenAPI");
  await dlg.getByRole("button", { name: "Save template" }).click();
  await expect(page.getByText("Template saved")).toBeVisible();

  const card = page.locator("div.rounded-lg").filter({ has: page.getByRole("heading", { name: "REST endpoint" }) });
  await card.getByRole("button", { name: "Use template" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\//);
  await page.getByRole("tab", { name: /Requirements/ }).click();
  await expect(page.getByText("Endpoint is documented in OpenAPI")).toBeVisible();
  await expect(page.getByText("proposed", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Save as template" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Save template" }).click();
  await expect(page.getByText("Template saved — find it under Templates")).toBeVisible();
  await page.goto("/templates");
  await expect(page.getByRole("heading", { name: "REST endpoint template" })).toBeVisible();
});

test("agent handoff: preview, keep existing file, write, show command (never executed)", async ({ page, external }) => {
  void external;
  rmSync(TARGET, { recursive: true, force: true });
  mkdirSync(TARGET, { recursive: true });
  writeFileSync(path.join(TARGET, "CLAUDE.md"), "EXISTING RULES");

  await page.goto("/projects");
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByRole("dialog").getByLabel("Name").fill("Handoff E2E");
  await page.getByRole("dialog").getByLabel("Rough idea (optional)").fill("Add rate limiting to the login endpoint.");
  await page.getByRole("dialog").getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\//);
  await page.getByRole("tab", { name: "Prompt", exact: true }).click();
  await page.getByRole("button", { name: "Hand off to agent…" }).click();

  const dlg = page.getByRole("dialog");
  await dlg.getByLabel("Project directory (absolute path)").fill(TARGET);
  await dlg.getByLabel("Agent").selectOption("claude_code");
  await dlg.getByRole("button", { name: "Preview" }).click();
  await expect(dlg.getByText(/exists/)).toBeVisible();
  await expect(dlg.getByRole("button", { name: "Write 2 file(s)" })).toBeDisabled(); // not yet authorized
  await dlg.getByLabel(/I authorize Prompt Studio/).check();
  await dlg.getByRole("button", { name: "Write 2 file(s)" }).click();
  await expect(dlg.getByText(/Kept existing: CLAUDE.md/)).toBeVisible();
  await expect(dlg.locator("pre")).toContainText("claude");

  expect(readFileSync(path.join(TARGET, "CLAUDE.md"), "utf8")).toBe("EXISTING RULES");
  expect(readFileSync(path.join(TARGET, ".prompt-studio", "PROMPT.md"), "utf8")).toContain("rate limiting");
  expect(existsSync(path.join(TARGET, ".prompt-studio", "TASKS.md"))).toBe(true);
});
