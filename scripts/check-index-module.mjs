import { spawnSync } from "node:child_process";
import { readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
const scripts = [...html.matchAll(/<script\b[^>]*type=["']module["'][^>]*>([\s\S]*?)<\/script>/gi)];
if (scripts.length !== 1) {
  throw new Error(`Expected one module script in index.html, found ${scripts.length}`);
}

const checkPath = join(tmpdir(), `pangpang-index-check-${process.pid}.mjs`);
try {
  await writeFile(checkPath, scripts[0][1], "utf8");
  const result = spawnSync(process.execPath, ["--check", checkPath], { encoding: "utf8" });
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || "index module syntax check failed");
  }
  console.log("index.html module syntax: ok");
} finally {
  await rm(checkPath, { force: true });
}
