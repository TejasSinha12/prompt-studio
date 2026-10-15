// Start backend (FastAPI) and frontend (Next.js) together on loopback.
//   npm run dev          development mode (hot reload)
//   npm run start        production mode (builds the frontend first)
// Ports: PROMPT_STUDIO_API_PORT (default 8000), PROMPT_STUDIO_WEB_PORT (default 3000).
import { API_DIR, has, loadDotEnv, portFree, run, startChild, waitForHttp, WEB_DIR } from "./lib.mjs";

loadDotEnv();

const prod = process.argv.includes("--prod");
const apiPort = Number(process.env.PROMPT_STUDIO_API_PORT ?? 8000);
const webPort = Number(process.env.PROMPT_STUDIO_WEB_PORT ?? 3000);
const host = "127.0.0.1";

if (!has("uv")) {
  console.error("uv is not installed. Run `npm run setup` after installing uv (see README).");
  process.exit(1);
}
for (const [name, port, envVar] of [["Backend", apiPort, "PROMPT_STUDIO_API_PORT"], ["Frontend", webPort, "PROMPT_STUDIO_WEB_PORT"]]) {
  if (!(await portFree(port))) {
    console.error(
      `✗ ${name} port ${port} on ${host} is already in use.\n` +
        `  Find the process:  lsof -iTCP:${port} -sTCP:LISTEN   (Windows: netstat -ano | findstr :${port})\n` +
        `  Or choose another port:  ${envVar}=<port> npm run dev`,
    );
    process.exit(1);
  }
}

const webOrigins = JSON.stringify([`http://${host}:${webPort}`, `http://localhost:${webPort}`]);
const sharedEnv = { NEXT_TELEMETRY_DISABLED: "1", PROMPT_STUDIO_ALLOWED_ORIGINS: webOrigins };

if (prod) run("npx", ["next", "build"], WEB_DIR, sharedEnv);

const children = [];
let shuttingDown = false;
function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log("\nStopping Prompt Studio…");
  for (const c of children) if (c.exitCode === null) c.kill("SIGTERM");
  setTimeout(() => {
    for (const c of children) if (c.exitCode === null) c.kill("SIGKILL");
    process.exit(code);
  }, 4000).unref();
}
process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

const apiArgs = ["run", "uvicorn", "prompt_studio.main:app", "--host", host, "--port", String(apiPort), "--no-server-header"];
if (!prod) apiArgs.push("--reload", "--reload-dir", "prompt_studio");
const api = startChild("api", "uv", apiArgs, API_DIR, sharedEnv, "36");
children.push(api);
api.on("exit", (code) => {
  if (!shuttingDown) {
    console.error(`✗ Backend exited unexpectedly (code ${code}). See the [api] output above.`);
    shutdown(1);
  }
});

if (!(await waitForHttp(`http://${host}:${apiPort}/api/health`, 60000))) {
  console.error("✗ Backend did not become healthy within 60 s.");
  shutdown(1);
} else {
  const web = startChild("web", "npx", ["next", prod ? "start" : "dev", "--hostname", host, "--port", String(webPort)], WEB_DIR,
    { ...sharedEnv, PROMPT_STUDIO_API_URL: `http://${host}:${apiPort}` }, "35");
  children.push(web);
  web.on("exit", (code) => {
    if (!shuttingDown) {
      console.error(`✗ Frontend exited unexpectedly (code ${code}).`);
      shutdown(1);
    }
  });
  if (await waitForHttp(`http://${host}:${webPort}/`, 120000)) {
    console.log(`\n✓ Prompt Studio is running:  http://${host}:${webPort}\n  API: http://${host}:${apiPort}   Press Ctrl+C to stop.\n`);
  }
}
