#!/usr/bin/env node
/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");

const REQUIRED_NODE = { major: 20, minor: 11, patch: 1 };
const REQUIRED_NPM_MAJOR = 10;

function parseVersion(input) {
  const cleaned = String(input || "").trim().replace(/^v/i, "");
  const match = cleaned.match(/^(\d+)\.(\d+)\.(\d+)/);
  if (!match) return null;
  return { major: Number(match[1]), minor: Number(match[2]), patch: Number(match[3]), raw: cleaned };
}

function gte(a, b) {
  if (a.major !== b.major) return a.major > b.major;
  if (a.minor !== b.minor) return a.minor > b.minor;
  return a.patch >= b.patch;
}

function readNpmVersion() {
  const npmUA = process.env.npm_config_user_agent || "";
  const match = npmUA.match(/npm\/(\d+\.\d+\.\d+)/i);
  if (match) return parseVersion(match[1]);
  return parseVersion(process.env.npm_version || "");
}

const nodeVersion = parseVersion(process.version);
const npmVersion = readNpmVersion();

const nodeOk = nodeVersion && nodeVersion.major === REQUIRED_NODE.major && gte(nodeVersion, REQUIRED_NODE);
const npmOk = npmVersion && npmVersion.major === REQUIRED_NPM_MAJOR;

if (!nodeOk || !npmOk) {
  const nvmrcPath = path.resolve(__dirname, "../.nvmrc");
  const pinned = fs.existsSync(nvmrcPath) ? fs.readFileSync(nvmrcPath, "utf8").trim() : "20.11.1";
  console.error("[runtime-check] Unsupported runtime for apps/web.");
  console.error(`[runtime-check] Required: Node >=${REQUIRED_NODE.major}.${REQUIRED_NODE.minor}.${REQUIRED_NODE.patch} <21, npm ${REQUIRED_NPM_MAJOR}.x`);
  console.error(`[runtime-check] Detected: Node ${process.version}, npm ${npmVersion ? npmVersion.raw : "unknown"}`);
  console.error("[runtime-check] Why this fails fast: mismatched runtimes have produced deterministic build corruption signatures (EISDIR/readlink in Next paths).");
  console.error("[runtime-check] Fix:");
  console.error(`  1) switch to Node ${pinned} (from .nvmrc)`);
  console.error("  2) ensure npm major is 10");
  console.error("  3) run: npm ci --no-audit --no-fund && npm run typecheck && npm run build && npm run build");
  process.exit(1);
}

console.log(`[runtime-check] OK Node ${process.version}, npm ${npmVersion.raw}`);
