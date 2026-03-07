#!/usr/bin/env node

const path = require("path");
const { spawn } = require("child_process");

const shimPath = path.resolve(__dirname, "readlink-shim.cjs").replace(/\\/g, "/");
const existing = process.env.NODE_OPTIONS ? `${process.env.NODE_OPTIONS} ` : "";
const env = {
  ...process.env,
  NODE_OPTIONS: `${existing}--require=${shimPath}`,
};

const nextBin = require.resolve("next/dist/bin/next");
const child = spawn(process.execPath, [nextBin, "build"], {
  stdio: "inherit",
  env,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
