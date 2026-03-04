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

function readNpmVersion(env = process.env) {
  const npmUA = env.npm_config_user_agent || "";
  const match = npmUA.match(/npm\/(\d+\.\d+\.\d+)/i);
  if (match) return parseVersion(match[1]);
  return parseVersion(env.npm_version || "");
}

function detectRuntime(env = process.env, nodeVersionRaw = process.version) {
  const nodeVersion = parseVersion(nodeVersionRaw);
  const npmVersion = readNpmVersion(env);
  const nodeOk = nodeVersion && nodeVersion.major === REQUIRED_NODE.major && gte(nodeVersion, REQUIRED_NODE);
  const npmOk = npmVersion && npmVersion.major === REQUIRED_NPM_MAJOR;
  return { nodeVersion, npmVersion, nodeOk: !!nodeOk, npmOk: !!npmOk };
}

function redactSecretLike(text) {
  return String(text || "")
    .replace(/(bearer\s+)[A-Za-z0-9._\-+/=]{8,}/gi, "$1***")
    .replace(/\b(sk|pk|api|token|secret)_[A-Za-z0-9._\-]{8,}\b/gi, "***")
    .replace(/([?&](?:token|api_key|apikey|password|secret)=)[^\s&]+/gi, "$1***")
    .replace(/\b((?:token|api_key|apikey|password|secret)=)[^\s&]+/gi, "$1***");
}

function createFailureMessage(runtime, pinned) {
  const detectedNode = runtime.nodeVersion ? `v${runtime.nodeVersion.raw}` : "unknown";
  const detectedNpm = runtime.npmVersion ? runtime.npmVersion.raw : "unknown";
  return [
    "[runtime-check] Unsupported runtime for apps/web.",
    `[runtime-check] Required: Node >=${REQUIRED_NODE.major}.${REQUIRED_NODE.minor}.${REQUIRED_NODE.patch} <21, npm ${REQUIRED_NPM_MAJOR}.x`,
    `[runtime-check] Detected: Node ${redactSecretLike(detectedNode)}, npm ${redactSecretLike(detectedNpm)}`,
    "[runtime-check] Why this fails fast: mismatched runtimes have produced deterministic build corruption signatures (EISDIR/readlink in Next paths).",
    "[runtime-check] Fix:",
    `  1) switch to Node ${pinned} (from .nvmrc)`,
    "  2) ensure npm major is 10",
    "  3) run: npm ci --no-audit --no-fund && npm run typecheck && npm run build && npm run build",
  ];
}

function runRuntimeCheck() {
  const runtime = detectRuntime();
  if (!runtime.nodeOk || !runtime.npmOk) {
    const nvmrcPath = path.resolve(__dirname, "../.nvmrc");
    const pinned = fs.existsSync(nvmrcPath) ? fs.readFileSync(nvmrcPath, "utf8").trim() : "20.11.1";
    createFailureMessage(runtime, pinned).forEach((line) => console.error(line));
    process.exit(1);
  }

  console.log(`[runtime-check] OK Node ${process.version}, npm ${runtime.npmVersion.raw}`);
}

if (require.main === module) {
  runRuntimeCheck();
}

module.exports = {
  REQUIRED_NODE,
  REQUIRED_NPM_MAJOR,
  parseVersion,
  gte,
  readNpmVersion,
  detectRuntime,
  redactSecretLike,
  createFailureMessage,
};
