// Opt-in: drives the local-AI UI against a REAL Ollama model.
//   npm run test:e2e:real-model              (default model qwen3:8b)
//   E2E_REAL_MODEL=qwen3:4b npm run test:e2e:real-model
// Skipped in the normal suite and in CI (no model available there).
import { expect, test } from "./fixtures";

const MODEL = process.env.E2E_REAL_MODEL;

test.skip(!MODEL, "set E2E_REAL_MODEL to run against a real local model");

test("local AI through the UI: select model, analyse, refine with diff, cancel", async ({ page, external }) => {
  void external;
  test.setTimeout(600_000);
  await page.goto("/models");
  const row = page.getByRole("row").filter({ hasText: MODEL! });
  await row.getByRole("button", { name: "Select" }).click();
  await expect(page.getByRole("link", { name: "Local model status" })).toContainText(`Local AI ready · ${MODEL}`);

  await page.goto("/projects");
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByRole("dialog").getByLabel("Name").fill("Real model E2E");
  await page.getByRole("dialog").getByLabel("Rough idea (optional)").fill(
    "Build a browser extension that summarises the current web page and stores summaries so users can search them later. It should be fast.",
  );
  await page.getByRole("dialog").getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\//);

  // Local AI analysis: progress line, then labelled findings.
  await page.getByRole("button", { name: "Local AI analysis" }).click();
  await expect(page.getByText(`Local model ${MODEL} working`)).toBeVisible();
  await expect(page.getByText(/Local AI analysis: \d+ finding/)).toBeVisible({ timeout: 400_000 });
  const panel = page.getByRole("complementary", { name: "Analysis and recommendations" });
  await expect(panel.getByText(`Local AI · ${MODEL}`).first()).toBeVisible();

  // Refinement: diff + preservation report, then save as a labelled version.
  await page.getByRole("tab", { name: "Prompt", exact: true }).click();
  const balanced = page.locator("section[aria-label='Prompt workspace'] .grid > div").nth(1);
  await balanced.getByRole("button", { name: "Refine (AI)" }).click();
  await expect(page.getByText(/Local AI refinement of the balanced variant/)).toBeVisible({ timeout: 400_000 });
  await expect(page.getByLabel("Unified diff").or(page.getByText("No differences."))).toBeVisible();
  await page.getByRole("button", { name: "Save as version" }).click();
  await expect(page.getByText("Saved as a new version")).toBeVisible();
  await page.getByRole("tab", { name: /Versions/ }).click();
  await expect(page.getByText(`Local AI · ${MODEL}`).first()).toBeVisible();

  // Cancellation of a running job.
  await page.getByRole("tab", { name: "Prompt", exact: true }).click();
  await balanced.getByRole("button", { name: "Refine (AI)" }).click();
  await expect(page.getByText(`Local model ${MODEL} working`)).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("Local-AI job cancelled.")).toBeVisible({ timeout: 30_000 });
});
