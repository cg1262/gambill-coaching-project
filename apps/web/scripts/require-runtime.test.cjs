const test = require("node:test");
const assert = require("node:assert/strict");

const {
  parseVersion,
  detectRuntime,
  createFailureMessage,
  redactSecretLike,
} = require("./require-runtime.cjs");

test("parseVersion accepts semver-like values and ignores leading v", () => {
  assert.deepEqual(parseVersion("v20.11.1"), { major: 20, minor: 11, patch: 1, raw: "20.11.1" });
  assert.equal(parseVersion("garbage"), null);
});

test("detectRuntime enforces node major 20 and npm major 10", () => {
  const ok = detectRuntime({ npm_config_user_agent: "npm/10.8.2 node/v20.11.1" }, "v20.11.1");
  assert.equal(ok.nodeOk, true);
  assert.equal(ok.npmOk, true);

  const badNode = detectRuntime({ npm_config_user_agent: "npm/10.8.2 node/v24.13.1" }, "v24.13.1");
  assert.equal(badNode.nodeOk, false);
  assert.equal(badNode.npmOk, true);

  const badNpm = detectRuntime({ npm_config_user_agent: "npm/11.8.0 node/v20.11.1" }, "v20.11.1");
  assert.equal(badNpm.nodeOk, true);
  assert.equal(badNpm.npmOk, false);
});

test("redactSecretLike masks secret-looking tokens in diagnostic strings", () => {
  const source = "Bearer sk_test_abc123456789 token=mysecretvalue api_key=abc123456789";
  const redacted = redactSecretLike(source);
  assert.equal(redacted.includes("abc123456789"), false);
  assert.equal(redacted.includes("mysecretvalue"), false);
});

test("failure message does not leak secret-like runtime strings", () => {
  const runtime = {
    nodeVersion: parseVersion("v20.11.1"),
    npmVersion: { major: 10, minor: 8, patch: 2, raw: "10.8.2?token=shh-secret" },
    nodeOk: false,
    npmOk: false,
  };

  const lines = createFailureMessage(runtime, "20.11.1");
  const all = lines.join("\n");
  assert.equal(all.includes("shh-secret"), false);
  assert.match(all, /Detected: Node v20\.11\.1, npm 10\.8\.2\?token=\*\*\*/);
});

test("failure message stays secret-safe when npm version cannot be parsed", () => {
  const runtime = detectRuntime(
    { npm_config_user_agent: "npm/not-semver?token=raw-secret", npm_version: "11.bad?api_key=abc" },
    "v24.13.1",
  );

  const lines = createFailureMessage(runtime, "20.11.1");
  const all = lines.join("\n").toLowerCase();
  assert.equal(all.includes("raw-secret"), false);
  assert.equal(all.includes("api_key=abc"), false);
  assert.match(all, /detected: node v24\.13\.1, npm unknown/);
});
