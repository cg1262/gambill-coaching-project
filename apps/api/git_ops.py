from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import subprocess
from typing import Any

from config import settings
from db_lakebase import get_git_repo_settings, upsert_git_repo_settings


def _run_git(args: list[str], repo_path: Path) -> tuple[bool, str]:
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return False, (res.stderr or res.stdout or "git command failed").strip()
        return True, (res.stdout or "ok").strip()
    except Exception as e:
        return False, str(e)


def _resolve_git_config(workspace_id: str) -> dict[str, str]:
    saved = get_git_repo_settings(workspace_id) or {}
    return {
        "repo_path": str(saved.get("repo_path") or settings.git_ast_repo_path or "").strip(),
        "branch": str(saved.get("branch") or settings.git_ast_branch or "").strip(),
        "remote": str(saved.get("remote") or settings.git_ast_remote or "origin").strip() or "origin",
    }


def set_git_config(workspace_id: str, repo_path: str, branch: str, remote: str = "origin", actor_user: str = "system") -> dict[str, Any]:
    repo = Path(repo_path.strip())
    if not repo_path.strip():
        return {"ok": False, "message": "repo_path is required"}
    if not repo.exists():
        return {"ok": False, "message": f"repo path does not exist: {repo}"}

    ok, out = _run_git(["rev-parse", "--is-inside-work-tree"], repo)
    if not ok:
        return {"ok": False, "message": out}

    upsert_git_repo_settings(workspace_id, str(repo), branch.strip(), (remote or "origin").strip(), updated_by=actor_user)
    return {"ok": True, "message": "Git config saved", "workspace_id": workspace_id}


def git_status(workspace_id: str) -> dict[str, Any]:
    cfg = _resolve_git_config(workspace_id)
    repo_path = Path(cfg["repo_path"]) if cfg["repo_path"] else None
    if not repo_path:
        return {"configured": False, "message": "Git repo is not configured for this workspace"}
    if not repo_path.exists():
        return {"configured": False, "message": f"repo path does not exist: {repo_path}"}

    ok, out = _run_git(["rev-parse", "--is-inside-work-tree"], repo_path)
    if not ok:
        return {"configured": False, "message": out}

    ok_b, current_branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
    return {
        "configured": True,
        "repo_path": str(repo_path),
        "branch": cfg["branch"] or (current_branch if ok_b else "unknown"),
        "current_branch": current_branch if ok_b else "unknown",
        "remote": cfg["remote"],
    }


def save_and_push_ast(ast_payload: dict[str, Any], workspace_id: str, commit_message: str | None = None, push: bool = True) -> dict[str, Any]:
    status = git_status(workspace_id)
    if not status.get("configured"):
        return {"ok": False, "message": status.get("message", "git not configured")}

    repo_path = Path(status["repo_path"])
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    ast_dir = repo_path / "ast" / workspace_id
    ast_dir.mkdir(parents=True, exist_ok=True)

    ast_file = ast_dir / f"ast-{ts}.json"
    ast_file.write_text(json.dumps(ast_payload, indent=2), encoding="utf-8")

    rel_path = ast_file.relative_to(repo_path)

    ok, out = _run_git(["add", str(rel_path)], repo_path)
    if not ok:
        return {"ok": False, "message": f"git add failed: {out}", "file": str(rel_path)}

    msg = commit_message or f"chore(ast): save {workspace_id} AST snapshot {ts}"
    ok, out = _run_git(["commit", "-m", msg], repo_path)
    if not ok:
        if "nothing to commit" in out.lower():
            return {"ok": True, "message": "No changes to commit", "file": str(rel_path), "pushed": False}
        return {"ok": False, "message": f"git commit failed: {out}", "file": str(rel_path)}

    pushed = False
    if push:
        branch = status.get("branch") or status.get("current_branch") or "main"
        remote = status.get("remote") or "origin"
        ok, push_out = _run_git(["push", remote, branch], repo_path)
        if not ok:
            return {
                "ok": False,
                "message": f"Committed but push failed: {push_out}",
                "file": str(rel_path),
                "pushed": False,
            }
        pushed = True

    return {
        "ok": True,
        "message": "AST committed" + (" and pushed" if pushed else ""),
        "file": str(rel_path),
        "pushed": pushed,
    }
