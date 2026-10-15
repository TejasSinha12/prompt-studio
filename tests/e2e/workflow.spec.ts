import { readFileSync } from "node:fs";
import { expect, test } from "./fixtures";

const shot = (page: import("@playwright/test").Page, name: string) =>
  process.env.E2E_SCREENSHOTS ? page.screenshot({ path: `tests/e2e/.results/screens/${name}.png` }) : Promise.resolve();

const IDEA =
  "Build a command line tool that converts CSV files to JSON for data analysts. " +
  "It should be fast and user-friendly. Users log in with a password to access shared datasets.";

test("main workflow: project → analysis → recommendations → variants → versions → export (offline)", async ({ page, external }) => {
  void external;
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Local model status" })).toContainText("rule-based mode");

  // Create a project
  await page.getByRole("button", { name: "New project" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Create project" }).click();
  await expect(dialog.getByText("Name is required.")).toBeVisible(); // form validation
  await dialog.getByLabel("Name").fill("CSV converter E2E");
  await dialog.getByLabel("Rough idea (optional)").fill(IDEA);
  await dialog.getByLabel("Task category").selectOption("feature");
  await dialog.getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);
  const projectUrl = page.url();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("CSV converter E2E");

  // Edit + explicit save
  await page.getByLabel("Technology stack").fill("Python 3.12, standard library only");
  await expect(page.getByRole("status").filter({ hasText: "Unsaved changes" })).toBeVisible();
  await page.keyboard.press("ControlOrMeta+s");
  await expect(page.getByRole("status").filter({ hasText: "All changes saved" })).toBeVisible();

  // Rule-based analysis
  await page.getByRole("button", { name: "Run rule-based analysis" }).click();
  const findings = page.getByRole("complementary", { name: "Analysis and recommendations" });
  await expect(findings.getByText("No acceptance criteria")).toBeVisible();
  await expect(findings.getByText("Rule-based").first()).toBeVisible();
  await findings.getByText("No acceptance criteria").click();
  await expect(findings.getByText("How to verify:")).toBeVisible();
  await shot(page, "01-findings");

  // Recommendations: approve one, reject one
  await findings.getByRole("tab", { name: /Recommendations/ }).click();
  const accept = findings.getByRole("article", { name: "Add acceptance criteria" });
  await shot(page, "02-recommendations");
  await accept.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Approved — requirement added")).toBeVisible();
  const tests = findings.getByRole("article", { name: "Specify testing expectations" });
  await tests.getByLabel("Decision note (optional)").fill("Out of scope for this E2E run");
  await tests.getByRole("button", { name: "Reject" }).click();
  await expect(page.getByText("Rejected", { exact: true }).first()).toBeVisible();

  // Re-running analysis must not re-propose the rejected recommendation
  await findings.getByRole("tab", { name: /Findings/ }).click();
  await page.getByRole("button", { name: "Run rule-based analysis" }).click();
  await findings.getByRole("tab", { name: /Recommendations/ }).click();
  await expect(findings.getByRole("article", { name: "Specify testing expectations" })).toHaveCount(0);
  await findings.getByRole("tab", { name: /^Rejected/ }).click();
  await expect(findings.getByRole("article", { name: "Specify testing expectations" })).toBeVisible();

  // Requirements tab shows the approved requirement as confirmed
  await page.getByRole("tab", { name: /Requirements/ }).click();
  await expect(page.getByText("All functional requirements are implemented")).toBeVisible();

  // Variants side by side; all confirmed requirements preserved
  await page.getByRole("tab", { name: "Prompt", exact: true }).click();
  for (const v of ["concise", "balanced", "detailed"]) {
    await expect(page.getByRole("heading", { name: v, exact: true })).toBeVisible();
  }
  await expect(page.getByText(/1\/1 confirmed requirements preserved/).first()).toBeVisible();
  await shot(page, "03-variants");

  // Save balanced as v1
  const cards = page.locator("section[aria-label='Prompt workspace'] .grid > div");
  await cards.nth(1).getByRole("button", { name: "Save version" }).click();
  await expect(page.getByText("Saved as a new version")).toBeVisible();

  // Manual edit of concise → v2
  await cards.nth(0).getByRole("button", { name: "Edit" }).click();
  const editor = page.getByLabel("Prompt content");
  await editor.fill((await editor.inputValue()) + "\n## Extra\n\nManual addition by E2E.\n");
  await page.getByLabel("Change summary").fill("Manual tweak");
  await page.getByRole("button", { name: "Save as version" }).click();
  await expect(page.getByText("Saved as a new version").first()).toBeVisible();

  // Versions: diff and restore v1 → v3
  await page.getByRole("tab", { name: /Versions/ }).click();
  await expect(page.getByText("Manual tweak")).toBeVisible();
  await expect(page.getByLabel("Unified diff")).toContainText("Manual addition by E2E.");
  await page.getByRole("button", { name: "Restore" }).first().click();
  await expect(page.getByText("Restored v1 as a new version")).toBeVisible();
  await expect(page.getByText("Restored from v1")).toBeVisible();

  // Quality evaluation with evidence
  await shot(page, "04-versions-diff");
  await page.getByRole("button", { name: "Evaluate A & B" }).click();
  await expect(page.getByText("Aggregate (heuristic)")).toBeVisible();
  await shot(page, "05-evaluation");

  // Export CLAUDE.md (offline) and plain text
  await page.getByRole("tab", { name: "Prompt", exact: true }).click();
  await page.getByLabel("Export format").selectOption("claude_md");
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download", exact: true }).click()]);
  expect(dl.suggestedFilename()).toBe("CLAUDE.md");
  const claude = readFileSync((await dl.path())!, "utf8");
  expect(claude).toContain("# CSV converter E2E");
  expect(claude).toContain("Python 3.12, standard library only");
  await page.getByLabel("Export format").selectOption("text");
  const [dl2] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download", exact: true }).click()]);
  expect(dl2.suggestedFilename()).toMatch(/\.txt$/);

  // Persistence across reload
  await page.goto(projectUrl);
  await page.getByRole("tab", { name: /Requirements/ }).click();
  await expect(page.getByText("All functional requirements are implemented")).toBeVisible();
  await expect(page.getByLabel("Technology stack")).toHaveCount(0); // requirements tab active

  // Library lists the prompt with 3 versions
  await page.goto("/library");
  await expect(page.getByRole("link", { name: "CSV converter E2E" }).first()).toBeVisible();
  await expect(page.getByText("3 version(s)")).toBeVisible();
  await shot(page, "06-library");
  await page.goto("/");
  await shot(page, "07-dashboard");
  await page.goto("/models");
  await expect(page.getByText("Set up Ollama (optional)")).toBeVisible();
  await shot(page, "08-models");
});

test("keyboard: tabs are arrow-key navigable and dialogs close with Escape", async ({ page, external }) => {
  void external;
  await page.goto("/projects");
  await page.getByRole("button", { name: "New project" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();

  await page.getByRole("link", { name: "CSV converter E2E" }).first().click();
  const tab = page.getByRole("tab", { name: "Idea & context" });
  await tab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /Requirements/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tab", { name: /Requirements/ })).toBeFocused();
});

test("unsafe markdown in an idea is not executed or rendered as HTML", async ({ page, external }) => {
  void external;
  let alerted = false;
  page.on("dialog", (d) => {
    alerted = true;
    void d.dismiss();
  });
  await page.goto("/projects");
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByRole("dialog").getByLabel("Name").fill("XSS check");
  await page.getByRole("dialog").getByLabel("Rough idea (optional)").fill('<img src=x onerror="alert(1)"> [click](javascript:alert(2)) <script>alert(3)</script>');
  await page.getByRole("dialog").getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\//);
  await page.getByRole("tab", { name: "Preview" }).click();
  await page.waitForTimeout(500);
  expect(alerted).toBe(false);
  expect(await page.locator("main img").count()).toBe(0);
  expect(await page.locator('main a[href^="javascript:"]').count()).toBe(0);
});
