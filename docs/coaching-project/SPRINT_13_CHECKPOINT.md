# Sprint 13 Checkpoint (2026-03-06)

## Windows build blocker status

### Confirmed deterministic blocker signature
Under compliant runtime (`Node v20.11.1`, `npm 10.8.2` via Volta), install/build currently fail in this workspace due to a locked SWC native binary path:

- `EPERM: operation not permitted, lstat ... node_modules\@next\swc-win32-x64-msvc\next-swc.win32-x64-msvc.node`
- `ENOTEMPTY/EPERM` variants during `npm ci`
- resulting follow-on failures:
  - `'tsc' is not recognized`
  - `'next' is not recognized`

This is a local filesystem/permission corruption state (non-admin shell cannot remove or ACL-read the affected file), not a runtime version mismatch.

## Runtime parity + startup path

- Runtime guardrails remain enforced via:
  - `scripts/require-runtime.cjs`
  - `predev`, `pretypecheck`, `prebuild`, `prebuild:clean`
- Startup script `run-coaching.ps1` still enforces/repairs runtime to Node 20.11.1 + npm 10.x via Volta/nvm fallback.

## New remediation hardening added this sprint

### 1) Install recovery script
Added `apps/web/scripts/install-ci.ps1` and wired:

- `package.json` -> `"install:ci": "powershell -ExecutionPolicy Bypass -File ./scripts/install-ci.ps1"`

Behavior:
- retries `npm ci` up to 3 times
- detects `EPERM/ENOTEMPTY/EISDIR` signatures
- attempts stale Node process kill + SWC folder cleanup between retries
- exits with explicit remediation message when unrecoverable without elevation

### 2) Clean build recovery expanded
`apps/web/scripts/build-clean.ps1` now treats `EPERM`/`operation not permitted` as recoverable signatures and includes SWC cleanup path before retry.

## Coach workflow UX upgrades

Implemented in `apps/web/src/components/coaching/CoachingProjectWorkbench.tsx`:

- **Quick feedback templates** (one-click note insertion + auto-tagging)
- **Batch review actions** (multi-select submissions + batch status updates)
- **Regenerate recipes** (scope/architecture/story repair buttons that add guidance + trigger regeneration)
- **Resume confidence explainability** (factor breakdown shown near confidence band)

## Validation run evidence (current workspace)

Runtime check under Volta pin succeeds:
- `node v20.11.1`
- `npm 10.8.2`

But deterministic flow is blocked by local ACL corruption:
- `npm run install:ci` -> EPERM on `next-swc.win32-x64-msvc.node`
- `npm run typecheck` -> `tsc` missing
- `npm run build` -> `next` missing

## Required host-level remediation to complete deterministic proof

Run elevated (Administrator PowerShell) once:

```powershell
cd E:\gde_git\gambill-coaching-project\apps\web

# hard reset of locked dependency tree
cmd /c rmdir /s /q node_modules

# if Access is denied persists, repair ACL then retry delete
icacls node_modules /grant "%USERNAME%":(OI)(CI)F /T
cmd /c rmdir /s /q node_modules

# deterministic install + two-build proof under pinned runtime
"C:\Program Files\Volta\volta.exe" run --node 20.11.1 --npm 10.8.2 npm run install:ci
"C:\Program Files\Volta\volta.exe" run --node 20.11.1 --npm 10.8.2 npm run typecheck
"C:\Program Files\Volta\volta.exe" run --node 20.11.1 --npm 10.8.2 npm run build
"C:\Program Files\Volta\volta.exe" run --node 20.11.1 --npm 10.8.2 npm run build
"C:\Program Files\Volta\volta.exe" run --node 20.11.1 --npm 10.8.2 npm run build:clean
```

Expected outcome after ACL reset: deterministic proof closes with 2 consecutive successful builds.
