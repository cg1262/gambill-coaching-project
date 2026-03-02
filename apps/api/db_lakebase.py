from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any
import base64
import hashlib
import hmac
import json
import secrets

from config import settings


def _lakebase_dsn() -> str:
    return (
        f"host={settings.lakebase_host} "
        f"port={settings.lakebase_port} "
        f"dbname={settings.lakebase_db} "
        f"user={settings.lakebase_user} "
        f"password={settings.lakebase_password} "
        f"sslmode={settings.lakebase_sslmode}"
    )


def _requested_backend() -> str:
    return settings.lakebase_backend.strip().lower() or "duckdb"


def _postgres_configured() -> bool:
    return all([
        settings.lakebase_host,
        settings.lakebase_db,
        settings.lakebase_user,
        settings.lakebase_password,
    ])


def _effective_backend() -> str:
    requested = _requested_backend()
    if requested == "duckdb":
        return "duckdb"
    if requested in {"postgres", "lakebase"}:
        return "postgres" if _postgres_configured() else "duckdb"
    return "duckdb"


def _using_duckdb() -> bool:
    return _effective_backend() == "duckdb"


def _duckdb_path() -> str:
    path = (settings.lakebase_duckdb_path or "").strip() or "./lakebase.duckdb"
    return str(Path(path))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 200_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password_hash(password: str, stored: str) -> bool:
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iter_s, salt_b64, hash_b64 = stored.split("$", 3)
            iterations = int(iter_s)
            salt = base64.b64decode(salt_b64.encode())
            expected = base64.b64decode(hash_b64.encode())
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False
    # Backward compatibility for legacy plaintext rows
    return hmac.compare_digest(password, stored)


def _xor_crypt(data: bytes, key: bytes) -> bytes:
    if not key:
        return data
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _encrypt_connection_payload(payload: dict[str, Any]) -> dict[str, Any]:
    key = settings.connection_secret_key_bytes()
    if not key:
        return payload

    out = dict(payload)
    secret_fields = {"token", "connection_string", "password", "client_secret"}
    for f in secret_fields:
        v = out.get(f)
        if v in (None, ""):
            continue
        plain = str(v).encode("utf-8")
        cipher = _xor_crypt(plain, key)
        out[f] = "enc:v1:" + base64.urlsafe_b64encode(cipher).decode("utf-8")
    return out


def _decrypt_connection_payload(payload: dict[str, Any]) -> dict[str, Any]:
    key = settings.connection_secret_key_bytes()
    if not key:
        return payload

    out = dict(payload)
    for f in ["token", "connection_string", "password", "client_secret"]:
        v = out.get(f)
        if not isinstance(v, str) or not v.startswith("enc:v1:"):
            continue
        try:
            blob = base64.urlsafe_b64decode(v.split("enc:v1:", 1)[1].encode("utf-8"))
            out[f] = _xor_crypt(blob, key).decode("utf-8")
        except Exception:
            out[f] = ""
    return out


def _ensure_duckdb_bootstrap(conn) -> None:
    # Bootstrap core app tables so a fresh DB is immediately usable.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS acronym_dictionary (
            acronym VARCHAR PRIMARY KEY,
            description VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS naming_rules (
            rule_key VARCHAR PRIMARY KEY,
            rule_value VARCHAR,
            description VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS canvas_projects (
            project_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            owner VARCHAR,
            environment VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS canvas_versions (
            version_id VARCHAR PRIMARY KEY,
            project_id VARCHAR,
            actor_user VARCHAR,
            ast_json JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_runs (
            run_id VARCHAR PRIMARY KEY,
            project_id VARCHAR,
            actor_user VARCHAR,
            pass_type VARCHAR, -- deterministic | probabilistic
            violations_json JSON,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS impact_runs (
            run_id VARCHAR PRIMARY KEY,
            project_id VARCHAR,
            actor_user VARCHAR,
            pass_type VARCHAR, -- deterministic | probabilistic
            dependencies_json JSON,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS git_repo_settings (
            workspace_id VARCHAR PRIMARY KEY,
            repo_path VARCHAR,
            branch VARCHAR,
            remote VARCHAR,
            updated_by VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_users (
            username VARCHAR PRIMARY KEY,
            password VARCHAR,
            role VARCHAR,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS connection_settings (
            workspace_id VARCHAR,
            connection_type VARCHAR,
            settings_json JSON,
            updated_by VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, connection_type)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coaching_intake_submissions (
            submission_id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR,
            applicant_name VARCHAR,
            applicant_email VARCHAR,
            resume_text VARCHAR,
            self_assessment_text VARCHAR,
            job_links_json JSON,
            preferences_json JSON,
            status VARCHAR,
            coach_review_status VARCHAR,
            coach_notes VARCHAR,
            submitted_by VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    try:
        conn.execute("ALTER TABLE coaching_intake_submissions ADD COLUMN coach_review_status VARCHAR")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE coaching_intake_submissions ADD COLUMN coach_notes VARCHAR")
    except Exception:
        pass

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coaching_generation_runs (
            run_id VARCHAR PRIMARY KEY,
            submission_id VARCHAR,
            workspace_id VARCHAR,
            run_status VARCHAR,
            parsed_jobs_json JSON,
            sow_json JSON,
            validation_json JSON,
            error_message VARCHAR,
            created_by VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coaching_job_parse_cache (
            cache_key VARCHAR PRIMARY KEY,
            source_url VARCHAR,
            parsed_text VARCHAR,
            parsed_json JSON,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coaching_accounts (
            workspace_id VARCHAR,
            username VARCHAR,
            email VARCHAR,
            plan_tier VARCHAR,
            subscription_status VARCHAR,
            renewal_date TIMESTAMP,
            provider_customer_id VARCHAR,
            provider_subscription_id VARCHAR,
            provider_source VARCHAR,
            last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, email)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coaching_subscription_events (
            event_id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR,
            provider VARCHAR,
            event_type VARCHAR,
            email VARCHAR,
            provider_customer_id VARCHAR,
            provider_subscription_id VARCHAR,
            payload_json JSON,
            processed BOOLEAN DEFAULT FALSE,
            processed_at TIMESTAMP,
            received_by VARCHAR,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dependency_mappings (
            workspace_id VARCHAR,
            source_object VARCHAR,
            target_object VARCHAR,
            dependency_type VARCHAR,
            confidence DOUBLE,
            source_system VARCHAR,
            notes VARCHAR,
            updated_by VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS policy_documents (
            document_id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR,
            doc_name VARCHAR,
            doc_type VARCHAR,
            content_text VARCHAR,
            uploaded_by VARCHAR,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS policy_chunks (
            chunk_id VARCHAR PRIMARY KEY,
            document_id VARCHAR,
            workspace_id VARCHAR,
            chunk_index INTEGER,
            chunk_text VARCHAR,
            source_ref VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_policy_config (
            workspace_id VARCHAR PRIMARY KEY,
            standards_template_name VARCHAR,
            standards_template_version VARCHAR,
            regulatory_template_name VARCHAR,
            regulatory_template_version VARCHAR,
            updated_by VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS finding_status (
            workspace_id VARCHAR,
            finding_key VARCHAR,
            status VARCHAR,
            note VARCHAR,
            updated_by VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, finding_key)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS finding_status_audit (
            audit_id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR,
            finding_key VARCHAR,
            old_status VARCHAR,
            new_status VARCHAR,
            note VARCHAR,
            updated_by VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Seed baseline governance content (idempotent)
    conn.execute(
        """
        INSERT INTO acronym_dictionary (acronym, description)
        SELECT 'pk', 'Primary Key'
        WHERE NOT EXISTS (SELECT 1 FROM acronym_dictionary WHERE acronym = 'pk')
        """
    )
    conn.execute(
        """
        INSERT INTO acronym_dictionary (acronym, description)
        SELECT 'fk', 'Foreign Key'
        WHERE NOT EXISTS (SELECT 1 FROM acronym_dictionary WHERE acronym = 'fk')
        """
    )
    conn.execute(
        """
        INSERT INTO acronym_dictionary (acronym, description)
        SELECT 'id', 'Identifier'
        WHERE NOT EXISTS (SELECT 1 FROM acronym_dictionary WHERE acronym = 'id')
        """
    )
    conn.execute(
        """
        INSERT INTO acronym_dictionary (acronym, description)
        SELECT 'utc', 'Coordinated Universal Time'
        WHERE NOT EXISTS (SELECT 1 FROM acronym_dictionary WHERE acronym = 'utc')
        """
    )

    conn.execute(
        """
        INSERT INTO naming_rules (rule_key, rule_value, description)
        SELECT 'table_case', 'snake_lower', 'Table names should be lowercase snake_case'
        WHERE NOT EXISTS (SELECT 1 FROM naming_rules WHERE rule_key = 'table_case')
        """
    )
    conn.execute(
        """
        INSERT INTO naming_rules (rule_key, rule_value, description)
        SELECT 'column_case', 'snake_lower', 'Column names should be lowercase snake_case'
        WHERE NOT EXISTS (SELECT 1 FROM naming_rules WHERE rule_key = 'column_case')
        """
    )
    conn.execute(
        """
        INSERT INTO naming_rules (rule_key, rule_value, description)
        SELECT 'pk_suffix', '_id', 'Primary key columns should end with _id'
        WHERE NOT EXISTS (SELECT 1 FROM naming_rules WHERE rule_key = 'pk_suffix')
        """
    )

    # Default bootstrap user only in dev environment.
    if settings.app_env == "dev":
        conn.execute(
            """
            INSERT INTO app_users (username, password, role, active)
            SELECT ?, ?, 'admin', TRUE
            WHERE NOT EXISTS (SELECT 1 FROM app_users WHERE username = ?)
            """,
            ["admin", hash_password("admin123"), "admin"],
        )


@contextmanager
def lakebase_connection():
    if _using_duckdb():
        import duckdb

        db_path = Path(_duckdb_path())
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = duckdb.connect(str(db_path))
        _ensure_duckdb_bootstrap(conn)
        try:
            yield conn
        finally:
            conn.close()
        return

    import psycopg

    conn = psycopg.connect(_lakebase_dsn())
    try:
        yield conn
    finally:
        conn.close()


def is_configured() -> bool:
    if _using_duckdb():
        # DuckDB can self-bootstrap with a default local file.
        return True
    return _postgres_configured()


def healthcheck() -> tuple[bool, str]:
    if not is_configured():
        if _using_duckdb():
            return False, "LakeBase DuckDB not configured"
        return False, "LakeBase Postgres not configured"

    try:
        with lakebase_connection() as conn:
            if _using_duckdb():
                conn.execute("SELECT 1").fetchone()
                return True, f"ok (duckdb: {_duckdb_path()})"

            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def bootstrap_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "backend": _effective_backend(),
        "backend_requested": settings.lakebase_backend,
        "backend_fallback": (_requested_backend() in {"postgres", "lakebase"}) and (not _postgres_configured()),
        "configured": is_configured(),
        "tables": {},
        "errors": [],
    }

    if _using_duckdb():
        status["duckdb_path"] = _duckdb_path()

    if not status["configured"]:
        return status

    expected_tables = [
        "acronym_dictionary",
        "naming_rules",
        "canvas_projects",
        "canvas_versions",
        "validation_runs",
        "impact_runs",
        "git_repo_settings",
        "connection_settings",
        "coaching_intake_submissions",
        "coaching_generation_runs",
        "coaching_job_parse_cache",
        "coaching_accounts",
        "coaching_subscription_events",
    ]

    try:
        with lakebase_connection() as conn:
            if _using_duckdb():
                for t in expected_tables:
                    try:
                        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                        status["tables"][t] = {"present": True, "row_count": int(count)}
                    except Exception as e:
                        status["tables"][t] = {"present": False, "row_count": None}
                        status["errors"].append(f"{t}: {e}")
            else:
                import psycopg
                with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                    for t in expected_tables:
                        try:
                            cur.execute(f"SELECT COUNT(*) AS c FROM {t}")
                            row = cur.fetchone() or {"c": 0}
                            status["tables"][t] = {"present": True, "row_count": int(row["c"])}
                        except Exception as e:
                            status["tables"][t] = {"present": False, "row_count": None}
                            status["errors"].append(f"{t}: {e}")
    except Exception as e:
        status["errors"].append(str(e))

    return status


def fetch_naming_rules(limit: int = 2000) -> list[dict[str, Any]]:
    if not is_configured():
        return []

    if _using_duckdb():
        candidate_tables = [settings.rules_naming_table]
        if "." in settings.rules_naming_table:
            candidate_tables.append(settings.rules_naming_table.split(".")[-1])

        with lakebase_connection() as conn:
            last_error: Exception | None = None
            for table_name in candidate_tables:
                try:
                    sql = f"SELECT * FROM {table_name} LIMIT ?"
                    rows = conn.execute(sql, [limit]).fetchall()
                    cols = [d[0] for d in conn.description]
                    return [dict(zip(cols, row)) for row in rows]
                except Exception as e:
                    last_error = e
                    continue

            if last_error:
                raise last_error
            return []

    sql = f"SELECT * FROM {settings.rules_naming_table} LIMIT %s"
    import psycopg

    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(sql, (limit,))
            return list(cur.fetchall())


def save_validation_run(run_id: str, project_id: str, actor_user: str, pass_type: str, violations: list[dict[str, Any]]) -> None:
    if not is_configured():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO validation_runs (run_id, project_id, actor_user, pass_type, violations_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                [run_id, project_id, actor_user, pass_type, json.dumps(violations)],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO validation_runs (run_id, project_id, actor_user, pass_type, violations_json)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (run_id, project_id, actor_user, pass_type, json.dumps(violations)),
            )
            conn.commit()


def save_impact_run(run_id: str, project_id: str, actor_user: str, pass_type: str, dependencies: list[dict[str, Any]]) -> None:
    if not is_configured():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO impact_runs (run_id, project_id, actor_user, pass_type, dependencies_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                [run_id, project_id, actor_user, pass_type, json.dumps(dependencies)],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO impact_runs (run_id, project_id, actor_user, pass_type, dependencies_json)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (run_id, project_id, actor_user, pass_type, json.dumps(dependencies)),
            )
            conn.commit()


def save_canvas_version(version_id: str, project_id: str, actor_user: str, ast_payload: dict[str, Any]) -> None:
    if not is_configured():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO canvas_versions (version_id, project_id, actor_user, ast_json)
                VALUES (?, ?, ?, ?)
                """,
                [version_id, project_id, actor_user, json.dumps(ast_payload)],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO canvas_versions (version_id, project_id, actor_user, ast_json)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (version_id, project_id, actor_user, json.dumps(ast_payload)),
            )
            conn.commit()


def get_user_auth(username: str, password: str) -> dict[str, Any] | None:
    if not is_configured():
        return None

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                """
                SELECT username, password, role, active
                FROM app_users
                WHERE username = ?
                LIMIT 1
                """,
                [username],
            ).fetchall()
            if not rows:
                return None
            cols = [d[0] for d in conn.description]
            user = dict(zip(cols, rows[0]))
            if not user.get("active"):
                return None
            stored = str(user.get("password") or "")
            if not verify_password_hash(password, stored):
                return None
            # Migrate legacy plaintext to hashed format on successful login
            if not stored.startswith("pbkdf2_sha256$"):
                conn.execute("UPDATE app_users SET password = ? WHERE username = ?", [hash_password(password), username])
            return {"username": user["username"], "role": user.get("role") or "viewer"}

    import psycopg
    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT username, password, role, active
                FROM app_users
                WHERE username = %s
                LIMIT 1
                """,
                (username,),
            )
            user = cur.fetchone()
            if not user or not user.get("active"):
                return None
            stored = str(user.get("password") or "")
            if not verify_password_hash(password, stored):
                return None
            if not stored.startswith("pbkdf2_sha256$"):
                cur.execute("UPDATE app_users SET password = %s WHERE username = %s", (hash_password(password), username))
                conn.commit()
            return {"username": user["username"], "role": user.get("role") or "viewer"}


def verify_user_credentials(username: str, password: str) -> bool:
    return get_user_auth(username, password) is not None


def list_users() -> list[dict[str, Any]]:
    if not is_configured():
        return []

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                "SELECT username, role, active, created_at FROM app_users ORDER BY username"
            ).fetchall()
            cols = [d[0] for d in conn.description]
            return [dict(zip(cols, row)) for row in rows]

    import psycopg
    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("SELECT username, role, active, created_at FROM app_users ORDER BY username")
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]


def upsert_user(username: str, password: str | None, role: str, active: bool) -> None:
    if not is_configured():
        return

    pwd_hash = hash_password(password) if password else None

    if _using_duckdb():
        with lakebase_connection() as conn:
            if pwd_hash:
                conn.execute(
                    """
                    INSERT INTO app_users (username, password, role, active)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(username) DO UPDATE
                    SET password=excluded.password, role=excluded.role, active=excluded.active
                    """,
                    [username, pwd_hash, role, active],
                )
            else:
                conn.execute(
                    """
                    INSERT INTO app_users (username, password, role, active)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(username) DO UPDATE
                    SET role=excluded.role, active=excluded.active
                    """,
                    [username, hash_password("changeme123"), role, active],
                )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            if pwd_hash:
                cur.execute(
                    """
                    INSERT INTO app_users (username, password, role, active)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(username) DO UPDATE
                    SET password=excluded.password, role=excluded.role, active=excluded.active
                    """,
                    (username, pwd_hash, role, active),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO app_users (username, password, role, active)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(username) DO UPDATE
                    SET role=excluded.role, active=excluded.active
                    """,
                    (username, hash_password("changeme123"), role, active),
                )
            conn.commit()


def upsert_git_repo_settings(workspace_id: str, repo_path: str, branch: str, remote: str, updated_by: str) -> None:
    if not is_configured():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO git_repo_settings (workspace_id, repo_path, branch, remote, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(workspace_id) DO UPDATE
                SET repo_path=excluded.repo_path,
                    branch=excluded.branch,
                    remote=excluded.remote,
                    updated_by=excluded.updated_by,
                    updated_at=CURRENT_TIMESTAMP
                """,
                [workspace_id, repo_path, branch, remote, updated_by],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO git_repo_settings (workspace_id, repo_path, branch, remote, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (workspace_id) DO UPDATE
                SET repo_path=excluded.repo_path,
                    branch=excluded.branch,
                    remote=excluded.remote,
                    updated_by=excluded.updated_by,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (workspace_id, repo_path, branch, remote, updated_by),
            )
            conn.commit()


def get_git_repo_settings(workspace_id: str) -> dict[str, Any] | None:
    if not is_configured():
        return None

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                """
                SELECT workspace_id, repo_path, branch, remote, updated_by, updated_at
                FROM git_repo_settings
                WHERE workspace_id = ?
                LIMIT 1
                """,
                [workspace_id],
            ).fetchall()
            if not rows:
                return None
            cols = [d[0] for d in conn.description]
            return dict(zip(cols, rows[0]))

    import psycopg
    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT workspace_id, repo_path, branch, remote, updated_by, updated_at
                FROM git_repo_settings
                WHERE workspace_id = %s
                LIMIT 1
                """,
                (workspace_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_connection_settings(workspace_id: str, connection_type: str, settings_payload: dict[str, Any], updated_by: str) -> None:
    if not is_configured():
        return

    encrypted_payload = _encrypt_connection_payload(settings_payload)
    payload = json.dumps(encrypted_payload)

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO connection_settings (workspace_id, connection_type, settings_json, updated_by, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(workspace_id, connection_type) DO UPDATE
                SET settings_json=excluded.settings_json,
                    updated_by=excluded.updated_by,
                    updated_at=CURRENT_TIMESTAMP
                """,
                [workspace_id, connection_type, payload, updated_by],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO connection_settings (workspace_id, connection_type, settings_json, updated_by, updated_at)
                VALUES (%s, %s, %s::jsonb, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (workspace_id, connection_type) DO UPDATE
                SET settings_json=excluded.settings_json,
                    updated_by=excluded.updated_by,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (workspace_id, connection_type, payload, updated_by),
            )
            conn.commit()


def get_connection_settings(workspace_id: str, connection_type: str | None = None) -> list[dict[str, Any]]:
    if not is_configured():
        return []

    if _using_duckdb():
        with lakebase_connection() as conn:
            if connection_type:
                rows = conn.execute(
                    """
                    SELECT workspace_id, connection_type, settings_json, updated_by, updated_at
                    FROM connection_settings
                    WHERE workspace_id = ? AND connection_type = ?
                    """,
                    [workspace_id, connection_type],
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT workspace_id, connection_type, settings_json, updated_by, updated_at
                    FROM connection_settings
                    WHERE workspace_id = ?
                    """,
                    [workspace_id],
                ).fetchall()
            cols = [d[0] for d in conn.description]
            out = [dict(zip(cols, row)) for row in rows]
            for r in out:
                payload = r.get("settings_json")
                parsed = json.loads(payload) if isinstance(payload, str) else (payload or {})
                r["settings_json"] = _decrypt_connection_payload(parsed)
            return out

    import psycopg
    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            if connection_type:
                cur.execute(
                    """
                    SELECT workspace_id, connection_type, settings_json, updated_by, updated_at
                    FROM connection_settings
                    WHERE workspace_id = %s AND connection_type = %s
                    """,
                    (workspace_id, connection_type),
                )
            else:
                cur.execute(
                    """
                    SELECT workspace_id, connection_type, settings_json, updated_by, updated_at
                    FROM connection_settings
                    WHERE workspace_id = %s
                    """,
                    (workspace_id,),
                )
            rows = cur.fetchall() or []
            out = [dict(r) for r in rows]
            for r in out:
                payload = r.get("settings_json")
                parsed = json.loads(payload) if isinstance(payload, str) else (payload or {})
                r["settings_json"] = _decrypt_connection_payload(parsed)
            return out


def save_dependency_mapping(
    workspace_id: str,
    source_object: str,
    target_object: str,
    dependency_type: str,
    confidence: float,
    source_system: str,
    notes: str | None,
    updated_by: str,
) -> None:
    if not is_configured():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO dependency_mappings
                (workspace_id, source_object, target_object, dependency_type, confidence, source_system, notes, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [workspace_id, source_object, target_object, dependency_type, confidence, source_system, notes, updated_by],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dependency_mappings
                (workspace_id, source_object, target_object, dependency_type, confidence, source_system, notes, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (workspace_id, source_object, target_object, dependency_type, confidence, source_system, notes, updated_by),
            )
            conn.commit()


def fetch_dependency_mappings(workspace_id: str, source_objects: list[str]) -> list[dict[str, Any]]:
    if not is_configured() or not source_objects:
        return []

    if _using_duckdb():
        with lakebase_connection() as conn:
            placeholders = ",".join(["?"] * len(source_objects))
            rows = conn.execute(
                f"""
                SELECT workspace_id, source_object, target_object, dependency_type, confidence, source_system, notes
                FROM dependency_mappings
                WHERE workspace_id = ? AND source_object IN ({placeholders})
                """,
                [workspace_id, *source_objects],
            ).fetchall()
            cols = [d[0] for d in conn.description]
            return [dict(zip(cols, row)) for row in rows]

    import psycopg
    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT workspace_id, source_object, target_object, dependency_type, confidence, source_system, notes
                FROM dependency_mappings
                WHERE workspace_id = %s AND source_object = ANY(%s)
                """,
                (workspace_id, source_objects),
            )
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]


def save_policy_document(document_id: str, workspace_id: str, doc_name: str, doc_type: str, content_text: str, uploaded_by: str) -> None:
    if not is_configured():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO policy_documents (document_id, workspace_id, doc_name, doc_type, content_text, uploaded_by)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [document_id, workspace_id, doc_name, doc_type, content_text, uploaded_by],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO policy_documents (document_id, workspace_id, doc_name, doc_type, content_text, uploaded_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (document_id, workspace_id, doc_name, doc_type, content_text, uploaded_by),
            )
            conn.commit()


def save_policy_chunks(document_id: str, workspace_id: str, chunks: list[dict[str, Any]]) -> None:
    if not is_configured() or not chunks:
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            for c in chunks:
                conn.execute(
                    """
                    INSERT INTO policy_chunks (chunk_id, document_id, workspace_id, chunk_index, chunk_text, source_ref)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [c["chunk_id"], document_id, workspace_id, c["chunk_index"], c["chunk_text"], c.get("source_ref")],
                )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            for c in chunks:
                cur.execute(
                    """
                    INSERT INTO policy_chunks (chunk_id, document_id, workspace_id, chunk_index, chunk_text, source_ref)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (c["chunk_id"], document_id, workspace_id, c["chunk_index"], c["chunk_text"], c.get("source_ref")),
                )
            conn.commit()


def search_policy_chunks(workspace_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not is_configured() or not query.strip():
        return []

    q = f"%{query.strip().lower()}%"

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, document_id, chunk_index, chunk_text, source_ref
                FROM policy_chunks
                WHERE workspace_id = ? AND lower(chunk_text) LIKE ?
                ORDER BY chunk_index
                LIMIT ?
                """,
                [workspace_id, q, limit],
            ).fetchall()
            cols = [d[0] for d in conn.description]
            return [dict(zip(cols, row)) for row in rows]

    import psycopg
    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT chunk_id, document_id, chunk_index, chunk_text, source_ref
                FROM policy_chunks
                WHERE workspace_id = %s AND lower(chunk_text) LIKE %s
                ORDER BY chunk_index
                LIMIT %s
                """,
                (workspace_id, q, limit),
            )
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]


def list_policy_documents(workspace_id: str) -> list[dict[str, Any]]:
    if not is_configured():
        return []

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                """
                SELECT document_id, workspace_id, doc_name, doc_type, uploaded_by, uploaded_at
                FROM policy_documents
                WHERE workspace_id = ?
                ORDER BY uploaded_at DESC
                """,
                [workspace_id],
            ).fetchall()
            cols = [d[0] for d in conn.description]
            return [dict(zip(cols, row)) for row in rows]

    import psycopg
    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT document_id, workspace_id, doc_name, doc_type, uploaded_by, uploaded_at
                FROM policy_documents
                WHERE workspace_id = %s
                ORDER BY uploaded_at DESC
                """,
                (workspace_id,),
            )
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]


def upsert_workspace_policy_config(
    workspace_id: str,
    standards_template_name: str,
    standards_template_version: str,
    regulatory_template_name: str,
    regulatory_template_version: str,
    updated_by: str,
) -> None:
    if not is_configured():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO workspace_policy_config
                (workspace_id, standards_template_name, standards_template_version, regulatory_template_name, regulatory_template_version, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(workspace_id) DO UPDATE
                SET standards_template_name=excluded.standards_template_name,
                    standards_template_version=excluded.standards_template_version,
                    regulatory_template_name=excluded.regulatory_template_name,
                    regulatory_template_version=excluded.regulatory_template_version,
                    updated_by=excluded.updated_by,
                    updated_at=CURRENT_TIMESTAMP
                """,
                [workspace_id, standards_template_name, standards_template_version, regulatory_template_name, regulatory_template_version, updated_by],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workspace_policy_config
                (workspace_id, standards_template_name, standards_template_version, regulatory_template_name, regulatory_template_version, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT(workspace_id) DO UPDATE
                SET standards_template_name=excluded.standards_template_name,
                    standards_template_version=excluded.standards_template_version,
                    regulatory_template_name=excluded.regulatory_template_name,
                    regulatory_template_version=excluded.regulatory_template_version,
                    updated_by=excluded.updated_by,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (workspace_id, standards_template_name, standards_template_version, regulatory_template_name, regulatory_template_version, updated_by),
            )
            conn.commit()


def get_workspace_policy_config(workspace_id: str) -> dict[str, Any] | None:
    if not is_configured():
        return None

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM workspace_policy_config WHERE workspace_id = ? LIMIT 1",
                [workspace_id],
            ).fetchall()
            if not rows:
                return None
            cols = [d[0] for d in conn.description]
            return dict(zip(cols, rows[0]))

    import psycopg
    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("SELECT * FROM workspace_policy_config WHERE workspace_id = %s LIMIT 1", (workspace_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_finding_status(workspace_id: str, finding_key: str, status: str, note: str | None, updated_by: str) -> None:
    if not is_configured():
        return

    audit_id = secrets.token_hex(12)

    if _using_duckdb():
        with lakebase_connection() as conn:
            existing = conn.execute(
                "SELECT status FROM finding_status WHERE workspace_id = ? AND finding_key = ? LIMIT 1",
                [workspace_id, finding_key],
            ).fetchone()
            old_status = existing[0] if existing else None

            conn.execute(
                """
                INSERT INTO finding_status (workspace_id, finding_key, status, note, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(workspace_id, finding_key) DO UPDATE
                SET status=excluded.status, note=excluded.note, updated_by=excluded.updated_by, updated_at=CURRENT_TIMESTAMP
                """,
                [workspace_id, finding_key, status, note, updated_by],
            )
            conn.execute(
                """
                INSERT INTO finding_status_audit (audit_id, workspace_id, finding_key, old_status, new_status, note, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [audit_id, workspace_id, finding_key, old_status, status, note, updated_by],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM finding_status WHERE workspace_id = %s AND finding_key = %s LIMIT 1",
                (workspace_id, finding_key),
            )
            row = cur.fetchone()
            old_status = row[0] if row else None

            cur.execute(
                """
                INSERT INTO finding_status (workspace_id, finding_key, status, note, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT(workspace_id, finding_key) DO UPDATE
                SET status=excluded.status, note=excluded.note, updated_by=excluded.updated_by, updated_at=CURRENT_TIMESTAMP
                """,
                (workspace_id, finding_key, status, note, updated_by),
            )
            cur.execute(
                """
                INSERT INTO finding_status_audit (audit_id, workspace_id, finding_key, old_status, new_status, note, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (audit_id, workspace_id, finding_key, old_status, status, note, updated_by),
            )
            conn.commit()


def get_finding_status_audit(
    workspace_id: str,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    updated_by: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    if not is_configured():
        return {"rows": [], "total": 0, "page": page, "page_size": page_size}

    page = max(1, int(page))
    page_size = max(1, min(500, int(page_size)))

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                """
                SELECT audit_id, workspace_id, finding_key, old_status, new_status, note, updated_by, updated_at
                FROM finding_status_audit
                WHERE workspace_id = ?
                ORDER BY updated_at DESC
                """,
                [workspace_id],
            ).fetchall()
            cols = [d[0] for d in conn.description]
            data = [dict(zip(cols, row)) for row in rows]
    else:
        import psycopg
        with lakebase_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(
                    """
                    SELECT audit_id, workspace_id, finding_key, old_status, new_status, note, updated_by, updated_at
                    FROM finding_status_audit
                    WHERE workspace_id = %s
                    ORDER BY updated_at DESC
                    """,
                    (workspace_id,),
                )
                rows = cur.fetchall() or []
                data = [dict(r) for r in rows]

    def _norm(v: Any) -> str:
        return str(v or "").strip().lower()

    if status:
        want = _norm(status)
        data = [r for r in data if _norm(r.get("new_status")) == want]
    if updated_by:
        want_user = _norm(updated_by)
        data = [r for r in data if _norm(r.get("updated_by")) == want_user]
    if date_from:
        data = [r for r in data if str(r.get("updated_at") or "") >= date_from]
    if date_to:
        data = [r for r in data if str(r.get("updated_at") or "") <= date_to]

    total = len(data)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "rows": data[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": end < total,
    }


def get_finding_statuses(workspace_id: str) -> dict[str, dict[str, Any]]:
    if not is_configured():
        return {}

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                "SELECT finding_key, status, note, updated_by, updated_at FROM finding_status WHERE workspace_id = ?",
                [workspace_id],
            ).fetchall()
            cols = [d[0] for d in conn.description]
            mapped = [dict(zip(cols, row)) for row in rows]
            return {str(r["finding_key"]): r for r in mapped}

    import psycopg
    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                "SELECT finding_key, status, note, updated_by, updated_at FROM finding_status WHERE workspace_id = %s",
                (workspace_id,),
            )
            rows = cur.fetchall() or []
            return {str(r["finding_key"]): dict(r) for r in rows}


def get_run_history(project_id: str, limit: int = 50) -> list[dict[str, Any]]:
    if not is_configured():
        return []

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                """
                SELECT run_id AS id, 'validation' AS run_type, pass_type, actor_user, checked_at AS run_at
                FROM validation_runs
                WHERE project_id = ?
                UNION ALL
                SELECT run_id AS id, 'impact' AS run_type, pass_type, actor_user, checked_at AS run_at
                FROM impact_runs
                WHERE project_id = ?
                ORDER BY run_at DESC
                LIMIT ?
                """,
                [project_id, project_id, limit],
            ).fetchall()
            cols = [d[0] for d in conn.description]
            return [dict(zip(cols, row)) for row in rows]

    import psycopg
    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT run_id AS id, 'validation' AS run_type, pass_type, actor_user, checked_at AS run_at
                FROM validation_runs
                WHERE project_id = %s
                UNION ALL
                SELECT run_id AS id, 'impact' AS run_type, pass_type, actor_user, checked_at AS run_at
                FROM impact_runs
                WHERE project_id = %s
                ORDER BY run_at DESC
                LIMIT %s
                """,
                (project_id, project_id, limit),
            )
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]


def fetch_acronym_dictionary(limit: int = 5000) -> list[dict[str, Any]]:
    if not is_configured():
        return []

    if _using_duckdb():
        # Expect a local table/view name like: acronym_dictionary.
        # If a dotted name is provided (e.g., governance.acronym_dictionary),
        # fall back to the last segment for convenience.
        candidate_tables = [settings.rules_acronym_table]
        if "." in settings.rules_acronym_table:
            candidate_tables.append(settings.rules_acronym_table.split(".")[-1])

        with lakebase_connection() as conn:
            last_error: Exception | None = None
            for table_name in candidate_tables:
                try:
                    sql = f"SELECT * FROM {table_name} LIMIT ?"
                    rows = conn.execute(sql, [limit]).fetchall()
                    cols = [d[0] for d in conn.description]
                    return [dict(zip(cols, row)) for row in rows]
                except Exception as e:  # try next candidate
                    last_error = e
                    continue

            if last_error:
                raise last_error
            return []

    sql = f"SELECT * FROM {settings.rules_acronym_table} LIMIT %s"
    import psycopg

    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(sql, (limit,))
            return list(cur.fetchall())


def save_coaching_intake_submission(
    submission_id: str,
    workspace_id: str,
    applicant_name: str,
    applicant_email: str,
    resume_text: str,
    self_assessment_text: str,
    job_links: list[str],
    preferences: dict[str, Any],
    status: str,
    submitted_by: str,
) -> None:
    if not is_configured():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO coaching_intake_submissions
                (submission_id, workspace_id, applicant_name, applicant_email, resume_text, self_assessment_text, job_links_json, preferences_json, status, coach_review_status, coach_notes, submitted_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                [submission_id, workspace_id, applicant_name, applicant_email, resume_text, self_assessment_text, json.dumps(job_links), json.dumps(preferences or {}), status, "new", "", submitted_by],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO coaching_intake_submissions
                (submission_id, workspace_id, applicant_name, applicant_email, resume_text, self_assessment_text, job_links_json, preferences_json, status, coach_review_status, coach_notes, submitted_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (submission_id, workspace_id, applicant_name, applicant_email, resume_text, self_assessment_text, json.dumps(job_links), json.dumps(preferences or {}), status, "new", "", submitted_by),
            )
            conn.commit()


def get_coaching_intake_submission(submission_id: str) -> dict[str, Any] | None:
    if not is_configured():
        return None

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM coaching_intake_submissions WHERE submission_id = ? LIMIT 1",
                [submission_id],
            ).fetchall()
            if not rows:
                return None
            cols = [d[0] for d in conn.description]
            row = dict(zip(cols, rows[0]))
    else:
        import psycopg
        with lakebase_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("SELECT * FROM coaching_intake_submissions WHERE submission_id = %s LIMIT 1", (submission_id,))
                dbrow = cur.fetchone()
                row = dict(dbrow) if dbrow else None
                if not row:
                    return None

    for key in ["job_links_json", "preferences_json"]:
        payload = row.get(key)
        if isinstance(payload, str):
            try:
                row[key] = json.loads(payload)
            except Exception:
                row[key] = [] if key == "job_links_json" else {}
    return row


def list_coaching_intake_submissions(workspace_id: str, limit: int = 50) -> list[dict[str, Any]]:
    if not is_configured():
        return []

    limit = max(1, min(500, int(limit)))

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM coaching_intake_submissions
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [workspace_id, limit],
            ).fetchall()
            cols = [d[0] for d in conn.description]
            data = [dict(zip(cols, row)) for row in rows]
    else:
        import psycopg
        with lakebase_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM coaching_intake_submissions
                    WHERE workspace_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (workspace_id, limit),
                )
                data = [dict(r) for r in (cur.fetchall() or [])]

    for row in data:
        for key in ["job_links_json", "preferences_json"]:
            payload = row.get(key)
            if isinstance(payload, str):
                try:
                    row[key] = json.loads(payload)
                except Exception:
                    row[key] = [] if key == "job_links_json" else {}

    return data


def update_coaching_review_status(
    submission_id: str,
    coach_review_status: str,
    coach_notes: str | None,
) -> None:
    if not is_configured():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                UPDATE coaching_intake_submissions
                SET coach_review_status = ?, coach_notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE submission_id = ?
                """,
                [coach_review_status, coach_notes or "", submission_id],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE coaching_intake_submissions
                SET coach_review_status = %s, coach_notes = %s, updated_at = CURRENT_TIMESTAMP
                WHERE submission_id = %s
                """,
                (coach_review_status, coach_notes or "", submission_id),
            )
            conn.commit()


def save_coaching_generation_run(
    run_id: str,
    submission_id: str,
    workspace_id: str,
    run_status: str,
    parsed_jobs: list[dict[str, Any]],
    sow: dict[str, Any],
    validation: dict[str, Any],
    error_message: str | None,
    created_by: str,
) -> None:
    if not is_configured():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO coaching_generation_runs
                (run_id, submission_id, workspace_id, run_status, parsed_jobs_json, sow_json, validation_json, error_message, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                [run_id, submission_id, workspace_id, run_status, json.dumps(parsed_jobs or []), json.dumps(sow or {}), json.dumps(validation or {}), error_message, created_by],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO coaching_generation_runs
                (run_id, submission_id, workspace_id, run_status, parsed_jobs_json, sow_json, validation_json, error_message, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (run_id, submission_id, workspace_id, run_status, json.dumps(parsed_jobs or []), json.dumps(sow or {}), json.dumps(validation or {}), error_message, created_by),
            )
            conn.commit()


def get_latest_coaching_generation_run(submission_id: str) -> dict[str, Any] | None:
    if not is_configured():
        return None

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM coaching_generation_runs
                WHERE submission_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [submission_id],
            ).fetchall()
            if not rows:
                return None
            cols = [d[0] for d in conn.description]
            row = dict(zip(cols, rows[0]))
    else:
        import psycopg
        with lakebase_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM coaching_generation_runs
                    WHERE submission_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (submission_id,),
                )
                dbrow = cur.fetchone()
                row = dict(dbrow) if dbrow else None
                if not row:
                    return None

    for key in ["parsed_jobs_json", "sow_json", "validation_json"]:
        payload = row.get(key)
        if isinstance(payload, str):
            try:
                row[key] = json.loads(payload)
            except Exception:
                row[key] = [] if key == "parsed_jobs_json" else {}

    return row


def list_coaching_generation_runs(submission_id: str, limit: int = 20) -> list[dict[str, Any]]:
    if not is_configured():
        return []

    max_limit = max(1, min(int(limit or 20), 200))

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM coaching_generation_runs
                WHERE submission_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [submission_id, max_limit],
            ).fetchall()
            cols = [d[0] for d in conn.description]
            data = [dict(zip(cols, row)) for row in rows]
    else:
        import psycopg
        with lakebase_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM coaching_generation_runs
                    WHERE submission_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (submission_id, max_limit),
                )
                data = [dict(r) for r in (cur.fetchall() or [])]

    for row in data:
        for key in ["parsed_jobs_json", "sow_json", "validation_json"]:
            payload = row.get(key)
            if isinstance(payload, str):
                try:
                    row[key] = json.loads(payload)
                except Exception:
                    row[key] = [] if key == "parsed_jobs_json" else {}

    return data


def upsert_coaching_job_parse_cache(cache_key: str, source_url: str, parsed_text: str, parsed_json: dict[str, Any]) -> None:
    if not is_configured():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO coaching_job_parse_cache (cache_key, source_url, parsed_text, parsed_json, fetched_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(cache_key) DO UPDATE
                SET source_url=excluded.source_url,
                    parsed_text=excluded.parsed_text,
                    parsed_json=excluded.parsed_json,
                    fetched_at=CURRENT_TIMESTAMP
                """,
                [cache_key, source_url, parsed_text, json.dumps(parsed_json or {})],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO coaching_job_parse_cache (cache_key, source_url, parsed_text, parsed_json, fetched_at)
                VALUES (%s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT(cache_key) DO UPDATE
                SET source_url=excluded.source_url,
                    parsed_text=excluded.parsed_text,
                    parsed_json=excluded.parsed_json,
                    fetched_at=CURRENT_TIMESTAMP
                """,
                (cache_key, source_url, parsed_text, json.dumps(parsed_json or {})),
            )
            conn.commit()


def get_coaching_job_parse_cache(cache_key: str) -> dict[str, Any] | None:
    if not is_configured():
        return None

    if _using_duckdb():
        with lakebase_connection() as conn:
            rows = conn.execute(
                "SELECT cache_key, source_url, parsed_text, parsed_json, fetched_at FROM coaching_job_parse_cache WHERE cache_key = ? LIMIT 1",
                [cache_key],
            ).fetchall()
            if not rows:
                return None
            cols = [d[0] for d in conn.description]
            row = dict(zip(cols, rows[0]))
    else:
        import psycopg
        with lakebase_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(
                    "SELECT cache_key, source_url, parsed_text, parsed_json, fetched_at FROM coaching_job_parse_cache WHERE cache_key = %s LIMIT 1",
                    (cache_key,),
                )
                dbrow = cur.fetchone()
                row = dict(dbrow) if dbrow else None
                if not row:
                    return None

    payload = row.get("parsed_json")
    if isinstance(payload, str):
        try:
            row["parsed_json"] = json.loads(payload)
        except Exception:
            row["parsed_json"] = {}
    return row


def upsert_coaching_account_subscription(
    workspace_id: str,
    email: str,
    plan_tier: str,
    subscription_status: str,
    renewal_date: str | None,
    provider_customer_id: str | None,
    provider_subscription_id: str | None,
    provider_source: str,
    updated_by: str,
    username: str | None = None,
) -> None:
    if not is_configured() or not str(email).strip():
        return

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO coaching_accounts
                (workspace_id, username, email, plan_tier, subscription_status, renewal_date, provider_customer_id, provider_subscription_id, provider_source, last_synced_at, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(workspace_id, email) DO UPDATE
                SET username=excluded.username,
                    plan_tier=excluded.plan_tier,
                    subscription_status=excluded.subscription_status,
                    renewal_date=excluded.renewal_date,
                    provider_customer_id=excluded.provider_customer_id,
                    provider_subscription_id=excluded.provider_subscription_id,
                    provider_source=excluded.provider_source,
                    last_synced_at=CURRENT_TIMESTAMP,
                    updated_by=excluded.updated_by,
                    updated_at=CURRENT_TIMESTAMP
                """,
                [workspace_id, username, email, plan_tier, subscription_status, renewal_date, provider_customer_id, provider_subscription_id, provider_source, updated_by],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO coaching_accounts
                (workspace_id, username, email, plan_tier, subscription_status, renewal_date, provider_customer_id, provider_subscription_id, provider_source, last_synced_at, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, CURRENT_TIMESTAMP)
                ON CONFLICT(workspace_id, email) DO UPDATE
                SET username=excluded.username,
                    plan_tier=excluded.plan_tier,
                    subscription_status=excluded.subscription_status,
                    renewal_date=excluded.renewal_date,
                    provider_customer_id=excluded.provider_customer_id,
                    provider_subscription_id=excluded.provider_subscription_id,
                    provider_source=excluded.provider_source,
                    last_synced_at=CURRENT_TIMESTAMP,
                    updated_by=excluded.updated_by,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (workspace_id, username, email, plan_tier, subscription_status, renewal_date, provider_customer_id, provider_subscription_id, provider_source, updated_by),
            )
            conn.commit()


def get_coaching_account_subscription(workspace_id: str, username: str | None = None, email: str | None = None) -> dict[str, Any] | None:
    if not is_configured():
        return None

    username = (username or "").strip()
    email = (email or "").strip().lower()

    if _using_duckdb():
        with lakebase_connection() as conn:
            if email:
                rows = conn.execute(
                    "SELECT * FROM coaching_accounts WHERE workspace_id = ? AND lower(email) = ? LIMIT 1",
                    [workspace_id, email],
                ).fetchall()
            elif username:
                rows = conn.execute(
                    "SELECT * FROM coaching_accounts WHERE workspace_id = ? AND username = ? LIMIT 1",
                    [workspace_id, username],
                ).fetchall()
            else:
                rows = []
            if not rows:
                return None
            cols = [d[0] for d in conn.description]
            return dict(zip(cols, rows[0]))

    import psycopg
    with lakebase_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            if email:
                cur.execute(
                    "SELECT * FROM coaching_accounts WHERE workspace_id = %s AND lower(email) = %s LIMIT 1",
                    (workspace_id, email),
                )
            elif username:
                cur.execute(
                    "SELECT * FROM coaching_accounts WHERE workspace_id = %s AND username = %s LIMIT 1",
                    (workspace_id, username),
                )
            else:
                return None
            row = cur.fetchone()
            return dict(row) if row else None


def save_coaching_subscription_event(
    event_id: str,
    workspace_id: str,
    provider: str,
    event_type: str,
    email: str | None,
    provider_customer_id: str | None,
    provider_subscription_id: str | None,
    payload: dict[str, Any],
    received_by: str,
) -> None:
    if not is_configured():
        return

    payload_json = json.dumps(payload or {})

    if _using_duckdb():
        with lakebase_connection() as conn:
            conn.execute(
                """
                INSERT INTO coaching_subscription_events
                (event_id, workspace_id, provider, event_type, email, provider_customer_id, provider_subscription_id, payload_json, processed, processed_at, received_by, received_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, FALSE, NULL, ?, CURRENT_TIMESTAMP)
                """,
                [event_id, workspace_id, provider, event_type, email, provider_customer_id, provider_subscription_id, payload_json, received_by],
            )
        return

    with lakebase_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO coaching_subscription_events
                (event_id, workspace_id, provider, event_type, email, provider_customer_id, provider_subscription_id, payload_json, processed, processed_at, received_by, received_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, FALSE, NULL, %s, CURRENT_TIMESTAMP)
                """,
                (event_id, workspace_id, provider, event_type, email, provider_customer_id, provider_subscription_id, payload_json, received_by),
            )
            conn.commit()
