import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "./fixtures";

// Under the repo (not os.tmpdir): macOS temp dirs resolve into /private/var, which the app blocks.
const FIXTURE = path.resolve(__dirname, ".results", "fixture-repo");

test.beforeAll(() => {
  rmSync(FIXTURE, { recursive: true, force: true });
  mkdirSync(path.join(FIXTURE, "src"), { recursive: true });
  writeFileSync(path.join(FIXTURE, "package.json"), '{"dependencies":{"express":"5"}}');
  writeFileSync(path.join(FIXTURE, "src", "server.js"), 'const token = "ghp_abcdefghijklmnopqrstuvwxyz0123";\napp.listen(3000);\n');
  writeFileSync(path.join(FIXTURE, ".env"), "DB_PASSWORD=hunter2");
});

test("codebase context: scan, preview exclusions, summarize with redaction, insert and save", async ({ page, external }) => {
  void external;
  await page.goto("/projects");
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByRole("dialog").getByLabel("Name").fill("Codebase E2E");
  await page.getByRole("dialog").getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\//);

  await page.getByRole("button", { name: "Add context from a local codebase…" }).click();
  const dlg = page.getByRole("dialog");
  await dlg.getByLabel("Absolute directory path").fill(FIXTURE);
  await dlg.getByRole("button", { name: "Scan" }).click();
  await expect(dlg.getByText("src/server.js")).toBeVisible();
  await dlg.getByRole("button", { name: /Show excluded entries/ }).click();
  await expect(dlg.getByText("possible secret")).toBeVisible();
  await dlg.getByLabel("Include src/server.js").check();
  await dlg.getByRole("button", { name: /Build summary/ }).click();
  await expect(dlg.getByText("1 line(s) redacted")).toBeVisible();
  await expect(dlg.getByText("app.listen(3000);")).toBeVisible();
  await expect(dlg.getByText(/ghp_abcdef/)).toHaveCount(0);
  await expect(dlg.getByText(/hunter2/)).toHaveCount(0);
  await dlg.getByRole("button", { name: "Insert into “Existing codebase”" }).click();

  await expect(page.getByLabel("Existing codebase information")).toHaveValue(/Detected stack/);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "All changes saved" })).toBeVisible();
  await page.getByRole("tab", { name: "Prompt", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Existing implementation" }).first()).toBeVisible();
});
