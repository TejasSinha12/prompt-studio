// Install dependencies for backend and frontend and initialise the database.
// Does NOT install system tools (Node, Python, uv, Ollama) or download models.
import { API_DIR, has, loadDotEnv, ROOT, run, WEB_DIR } from "./lib.mjs";

loadDotEnv();

const major = Number(process.versions.node.split(".")[0]);
if (major < 20) {
  console.error(`Node.js >= 20.9 is required (found ${process.versions.node}).`);
  process.exit(1);
}
if (!has("uv")) {
  console.error(
    "uv (Python package manager) is required: https://docs.astral.sh/uv/getting-started/installation/\n" +
      "  macOS: brew install uv    Linux/macOS: curl -LsSf https://astral.sh/uv/install.sh | sh\n" +
      "Alternatively install the backend manually: cd apps/api && python3 -m venv .venv && .venv/bin/pip install -e .",
  );
  process.exit(1);
}
run("uv", ["sync"], API_DIR);
run("npm", ["ci"], WEB_DIR, { NEXT_TELEMETRY_DISABLED: "1" });
run("npm", ["ci"], ROOT); // Playwright test runner (browsers are installed separately, see README)
run("uv", ["run", "python", "-m", "prompt_studio.cli", "init-db"], API_DIR);
console.log("\n✓ Setup complete. Start the app with: npm run dev");
console.log("  For end-to-end tests, install the test browser once: npx playwright install chromium");
if (!has("ollama")) {
  console.log("  (Optional) Ollama not found. Install it for local-AI features: https://ollama.com/download");
}
