// Shared helpers for the orchestration scripts. Node built-ins only.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const API_DIR = path.join(ROOT, "apps", "api");
export const WEB_DIR = path.join(ROOT, "apps", "web");

export function has(cmd) {
  return spawnSync(process.platform === "win32" ? "where" : "which", [cmd], { stdio: "ignore" }).status === 0;
}

export function run(cmd, args, cwd, env = {}) {
  console.log(`\n$ ${cmd} ${args.join(" ")}   (in ${path.relative(ROOT, cwd) || "."})`);
  const r = spawnSync(cmd, args, { cwd, stdio: "inherit", env: { ...process.env, ...env }, shell: process.platform === "win32" });
  if (r.status !== 0) {
    console.error(`\n✗ Command failed: ${cmd} ${args.join(" ")}`);
    process.exit(r.status ?? 1);
  }
}

export function portFree(port, host = "127.0.0.1") {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.once("error", () => resolve(false));
    srv.once("listening", () => srv.close(() => resolve(true)));
    srv.listen(port, host);
  });
}

export async function waitForHttp(url, timeoutMs = 60000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const r = await fetch(url);
      if (r.status < 500) return true;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

/** Start a long-running child with prefixed output. */
export function startChild(name, cmd, args, cwd, env, color) {
  const child = spawn(cmd, args, { cwd, env: { ...process.env, ...env }, stdio: ["ignore", "pipe", "pipe"], shell: process.platform === "win32" });
  const prefix = `\x1b[${color}m[${name}]\x1b[0m `;
  const pipe = (stream, out) => {
    let buf = "";
    stream.on("data", (d) => {
      buf += d.toString();
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const l of lines) out.write(prefix + l + "\n");
    });
  };
  pipe(child.stdout, process.stdout);
  pipe(child.stderr, process.stderr);
  return child;
}

/** Load PROMPT_STUDIO_* variables from ./.env (if present) without overriding the real environment. */
export function loadDotEnv() {
  const file = path.join(ROOT, ".env");
  if (!existsSync(file)) return;
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*(PROMPT_STUDIO_[A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
}
