#!/usr/bin/env node
/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");

const {
  REQUIRED_NODE,
  REQUIRED_NPM_MAJOR,
  detectRuntime,
} = require("./require-runtime.cjs");

function readPinnedNode() {
  const nvmrcPath = path.resolve(__dirname, "../.nvmrc");
  if (!fs.existsSync(nvmrcPath)) return `${REQUIRED_NODE.major}.${REQUIRED_NODE.minor}.${REQUIRED_NODE.patch}`;
  return fs.readFileSync(nvmrcPath, "utf8").trim();
}

function main() {
  const runtime = detectRuntime();
  const pinnedNode = readPinnedNode();
  const nodeDetected = runtime.nodeVersion ? `v${runtime.nodeVersion.raw}` : "unknown";
  const npmDetected = runtime.npmVersion ? runtime.npmVersion.raw : "unknown";

  console.log("[runtime-doctor] apps/web runtime diagnostics");
  console.log(`[runtime-doctor] Required Node: >=${REQUIRED_NODE.major}.${REQUIRED_NODE.minor}.${REQUIRED_NODE.patch} <21 (pinned: ${pinnedNode})`);
  console.log(`[runtime-doctor] Required npm : ${REQUIRED_NPM_MAJOR}.x`);
  console.log(`[runtime-doctor] Detected Node: ${nodeDetected}`);
  console.log(`[runtime-doctor] Detected npm : ${npmDetected}`);
  console.log(`[runtime-doctor] Status      : ${runtime.nodeOk && runtime.npmOk ? "OK" : "MISMATCH"}`);

  if (runtime.nodeOk && runtime.npmOk) {
    console.log("[runtime-doctor] Next: npm run install:ci && npm run typecheck && npm run build");
    process.exit(0);
  }

  console.log("[runtime-doctor] Next commands (pick one runtime manager):");
  console.log(`  Volta : volta install node@${pinnedNode} npm@10.8.2`);
  console.log(`  nvm   : nvm install ${pinnedNode} && nvm use ${pinnedNode} && npm i -g npm@10.8.2`);
  console.log(`  one-off: npx -y -p node@${pinnedNode} -p npm@10.8.2 -c \"npm run verify:deterministic\"`);
  console.log("[runtime-doctor] Then run: npm run install:ci && npm run verify:deterministic");
  process.exit(1);
}

if (require.main === module) {
  main();
}
