import type { CanvasAST } from "./types";

export type Severity = "HIGH" | "MED" | "LOW";

export interface Violation {
  code: string;
  severity: Severity;
  message: string;
  table_id?: string;
  column_name?: string;
  source: "deterministic" | "probabilistic";
  confidence?: number;
}

export interface ValidationResult {
  violations: Violation[];
  checked_at: string;
}

export interface Dependency {
  object_name: string;
  dependency_type: "table" | "view" | "pipeline" | "code_ref";
  source: "deterministic" | "probabilistic";
  confidence: number;
  color: "red" | "yellow" | "green";
}

export interface ImpactResult {
  dependencies: Dependency[];
  checked_at: string;
}

export interface BootstrapTableStatus {
  present: boolean;
  row_count: number | null;
}

export interface BootstrapStatusResult {
  status: "ok";
  lakebase: {
    backend: string;
    configured: boolean;
    duckdb_path?: string;
    tables: Record<string, BootstrapTableStatus>;
    errors: string[];
  };
}

export interface GitStatusResult {
  configured: boolean;
  message?: string;
  repo_path?: string;
  branch?: string;
  current_branch?: string;
  remote?: string;
}

export interface GitConfigResult {
  ok: boolean;
  message: string;
  workspace_id?: string;
}

export interface GitPushAstResult {
  ok: boolean;
  message: string;
  file?: string;
  pushed?: boolean;
}

export interface LoginResult {
  ok: boolean;
  message?: string;
  token?: string;
  username?: string;
}

export interface ConnectionTemplateResult {
  templates: Record<string, Record<string, any>>;
}

export interface ConnectionSettingsRow {
  workspace_id: string;
  connection_type: string;
  settings_json: any;
  updated_by?: string;
  updated_at?: string;
}

export interface ConnectionSettingsResult {
  workspace_id: string;
  connections: ConnectionSettingsRow[];
}

export interface StandardsTemplateResult {
  templates: Record<string, Record<string, any>>;
}

export interface StandardsDocumentsResult {
  workspace_id: string;
  documents: Array<{ document_id: string; doc_name: string; doc_type: string; uploaded_by?: string; uploaded_at?: string }>;
}

export interface RunHistoryResult {
  workspace_id: string;
  runs: Array<{ id: string; run_type: string; pass_type: string; actor_user: string; run_at: string }>;
}

export interface PolicyConfigResult {
  workspace_id: string;
  config?: {
    standards_template_name: string;
    standards_template_version: string;
    regulatory_template_name: string;
    regulatory_template_version: string;
  };
}

export interface DatabricksSchemaSyncResult {
  ok: boolean;
  workspace_id: string;
  table_count?: number;
  column_count?: number;
  message?: string;
  ast?: any;
}

export interface DatabricksSchemasResult {
  ok: boolean;
  workspace_id: string;
  schemas: string[];
  message?: string;
}

export interface DemoReadinessResult {
  workspace_id: string;
  ready: boolean;
  summary: {
    connections_configured: number;
    connection_types: string[];
    databricks_configured: boolean;
    policy_documents: number;
    validation_runs: number;
    impact_runs: number;
    total_runs: number;
  };
  blockers: string[];
}

export interface CoachingIntakeSubmission {
  submission_id: string;
  workspace_id: string;
  applicant_name: string;
  applicant_email?: string;
  status?: string;
  submitted_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface CoachingIntakeSubmissionListResult {
  workspace_id: string;
  submissions: CoachingIntakeSubmission[];
  total: number;
}

export interface CoachingIntakeSubmissionDetail extends CoachingIntakeSubmission {
  resume_text?: string;
  self_assessment_text?: string;
  job_links_json?: string[];
  preferences_json?: {
    target_role?: string;
    preferred_stack?: string;
    timeline_weeks?: string | number;
    [key: string]: any;
  };
}

export interface CoachingIntakeSubmissionDetailResult {
  ok: boolean;
  message?: string;
  submission_id?: string;
  submission?: CoachingIntakeSubmissionDetail;
  latest_generation_run?: Record<string, any> | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
let AUTH_TOKEN = "";

export function setAuthToken(token: string) {
  AUTH_TOKEN = token;
}

function toApiAst(payload: any): any {
  if (!payload?.tables) return payload;
  return {
    version: payload.version,
    workspace_id: payload.workspaceId,
    tables: (payload.tables ?? []).map((t: any) => ({
      id: t.id,
      catalog: t.catalog,
      schema: t.schema,
      table: t.table,
      description: t.description,
      columns: (t.columns ?? []).map((c: any) => ({
        name: c.name,
        data_type: c.dataType,
        nullable: c.nullable,
        is_primary_key: c.isPrimaryKey ?? false,
      })),
      position: t.position,
      source: t.source,
    })),
    relationships: (payload.relationships ?? []).map((r: any) => ({
      id: r.id,
      from_table_id: r.fromTableId,
      to_table_id: r.toTableId,
      from_column: r.fromColumn,
      to_column: r.toColumn,
      relationship_type: r.relationshipType,
    })),
    modified_table_ids: payload.modifiedTableIds ?? [],
  };
}

async function getJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : undefined,
    });
  } catch {
    throw new Error(`Failed to reach API at ${API_BASE}. Start backend (uvicorn) and retry.`);
  }

  if (!res.ok) throw new Error(`${path} failed (${res.status})`);
  return (await res.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : {}),
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error(`Failed to reach API at ${API_BASE}. Start backend (uvicorn) and retry.`);
  }

  if (!res.ok) throw new Error(`${path} failed (${res.status})`);
  return (await res.json()) as T;
}

export const api = {
  login: async (username: string, password: string) => {
    const res = await postJson<LoginResult>("/auth/login", { username, password });
    if (res.ok && res.token) setAuthToken(res.token);
    return res;
  },
  me: () => getJson<{ authenticated: boolean; username?: string }>("/auth/me"),
  validateDeterministic: (ast: CanvasAST) => postJson<ValidationResult>("/validate/deterministic", toApiAst(ast)),
  validateProbabilistic: (ast: CanvasAST) => postJson<ValidationResult>("/validate/probabilistic", toApiAst(ast)),
  impactDeterministic: (ast: CanvasAST) => postJson<ImpactResult>("/impact/deterministic", toApiAst(ast)),
  impactProbabilistic: (ast: CanvasAST) => postJson<ImpactResult>("/impact/probabilistic", toApiAst(ast)),
  bootstrapStatus: () => getJson<BootstrapStatusResult>("/admin/bootstrap-status"),
  gitStatus: (workspaceId: string) => getJson<GitStatusResult>(`/git/status?workspace_id=${encodeURIComponent(workspaceId)}`),
  setGitConfig: (workspaceId: string, repoPath: string, branch: string, remote = "origin") =>
    postJson<GitConfigResult>("/git/config", {
      workspace_id: workspaceId,
      repo_path: repoPath,
      branch,
      remote,
    }),
  pushAstToGit: (ast: CanvasAST, commitMessage?: string, push = true) =>
    postJson<GitPushAstResult>("/git/push-ast", {
      ast: toApiAst(ast),
      commit_message: commitMessage,
      push,
    }),
  connectionTemplates: () => getJson<ConnectionTemplateResult>("/connections/templates"),
  connectionSettings: (workspaceId: string, connectionType?: string) =>
    getJson<ConnectionSettingsResult>(
      `/connections/settings?workspace_id=${encodeURIComponent(workspaceId)}${connectionType ? `&connection_type=${encodeURIComponent(connectionType)}` : ""}`
    ),
  saveConnectionSettings: (workspaceId: string, connectionType: string, settings: Record<string, any>) =>
    postJson<{ ok: boolean; workspace_id: string; connection_type: string }>("/connections/settings", {
      workspace_id: workspaceId,
      connection_type: connectionType,
      settings,
    }),
  validateDatabricksConnection: (workspaceId: string, settings: Record<string, any>, runLiveTest = false) =>
    postJson<{ ok: boolean; message: string; mode?: string; connection_string_preview?: string; live_test?: { attempted: boolean; ok: boolean | null; message: string } }>("/connections/validate/databricks-uc", {
      workspace_id: workspaceId,
      settings,
      run_live_test: runLiveTest,
    }),
  syncDatabricksSchema: (workspaceId: string, settings?: Record<string, any>, limitTables = 300, limitColumns = 4000) =>
    postJson<DatabricksSchemaSyncResult>("/connections/sync/databricks-schema", {
      workspace_id: workspaceId,
      settings,
      limit_tables: limitTables,
      limit_columns: limitColumns,
    }),
  databricksSchemas: (workspaceId: string, settings?: Record<string, any>) =>
    postJson<DatabricksSchemasResult>("/connections/databricks/schemas", {
      workspace_id: workspaceId,
      settings,
    }),
  addDependencyMapping: (payload: {
    workspace_id: string;
    source_object: string;
    target_object: string;
    dependency_type: string;
    confidence?: number;
    source_system?: string;
    notes?: string;
  }) => postJson<{ ok: boolean }>("/impact/mappings", payload),
  standardsTemplates: () => getJson<StandardsTemplateResult>("/standards/templates"),
  uploadStandardsDocument: (workspaceId: string, docName: string, docType: string, contentText: string) =>
    postJson<{ ok: boolean; document_id: string }>("/standards/documents", {
      workspace_id: workspaceId,
      doc_name: docName,
      doc_type: docType,
      content_text: contentText,
    }),
  standardsDocuments: (workspaceId: string) =>
    getJson<StandardsDocumentsResult>(`/standards/documents?workspace_id=${encodeURIComponent(workspaceId)}`),
  standardsEvaluate: (ast: CanvasAST) => postJson<{ workspace_id: string; findings: any[] }>("/standards/evaluate", toApiAst(ast)),
  savePolicyConfig: (
    workspaceId: string,
    standardsTemplateName: string,
    standardsTemplateVersion: string,
    regulatoryTemplateName: string,
    regulatoryTemplateVersion: string
  ) =>
    postJson<{ ok: boolean; workspace_id: string }>("/standards/policy-config", {
      workspace_id: workspaceId,
      standards_template_name: standardsTemplateName,
      standards_template_version: standardsTemplateVersion,
      regulatory_template_name: regulatoryTemplateName,
      regulatory_template_version: regulatoryTemplateVersion,
    }),
  policyConfig: (workspaceId: string) =>
    getJson<PolicyConfigResult>(`/standards/policy-config?workspace_id=${encodeURIComponent(workspaceId)}`),
  setFindingStatus: (workspaceId: string, findingKey: string, status: string, note?: string) =>
    postJson<{ ok: boolean }>("/standards/finding-status", {
      workspace_id: workspaceId,
      finding_key: findingKey,
      status,
      note,
    }),
  setFindingStatusBulk: (workspaceId: string, findingKeys: string[], status: string, note?: string) =>
    postJson<{ ok: boolean; updated: number }>("/standards/finding-status/bulk", {
      workspace_id: workspaceId,
      finding_keys: findingKeys,
      status,
      note,
    }),
  prSummary: (ast: CanvasAST) => postJson<{ workspace_id: string; markdown: string; findings: any[] }>("/reports/pr-summary", toApiAst(ast)),
  postPrWebhook: (webhookUrl: string, markdown: string) =>
    postJson<{ ok: boolean; status_code?: number; message?: string }>("/reports/pr-webhook", {
      webhook_url: webhookUrl,
      markdown,
    }),
  postPrCommentProvider: (payload: {
    provider: "github" | "gitlab";
    api_url: string;
    token: string;
    repo?: string;
    pr_number?: number;
    project_id?: string;
    merge_request_iid?: number;
    markdown: string;
  }) => postJson<{ ok: boolean; status_code?: number; message?: string; provider?: string }>("/reports/pr-comment", payload),
  postGithubArtifacts: (payload: {
    api_url: string;
    token: string;
    repo: string;
    branch: string;
    base_path?: string;
    ast: Record<string, any>;
    findings: any[];
  }) => postJson<{ ok: boolean; files?: Array<{ path: string; status_code: number }>; message?: string }>("/reports/github-artifacts", payload),
  findingStatusAudit: (
    workspaceId: string,
    opts?: { page?: number; pageSize?: number; status?: string; updatedBy?: string; dateFrom?: string; dateTo?: string }
  ) => {
    const q = new URLSearchParams({ workspace_id: workspaceId });
    if (opts?.page) q.set("page", String(opts.page));
    if (opts?.pageSize) q.set("page_size", String(opts.pageSize));
    if (opts?.status) q.set("status", opts.status);
    if (opts?.updatedBy) q.set("updated_by", opts.updatedBy);
    if (opts?.dateFrom) q.set("date_from", opts.dateFrom);
    if (opts?.dateTo) q.set("date_to", opts.dateTo);
    return getJson<{ workspace_id: string; audit: any[]; meta?: any }>(`/standards/finding-status/audit?${q.toString()}`);
  },
  runHistory: (workspaceId: string, limit = 25) =>
    getJson<RunHistoryResult>(`/runs/history?workspace_id=${encodeURIComponent(workspaceId)}&limit=${limit}`),
  demoReadiness: (workspaceId: string) =>
    getJson<DemoReadinessResult>(`/demo/readiness?workspace_id=${encodeURIComponent(workspaceId)}`),
  listCoachingIntakeSubmissions: (workspaceId: string, limit = 50) =>
    getJson<CoachingIntakeSubmissionListResult>(
      `/coaching/intake/submissions?workspace_id=${encodeURIComponent(workspaceId)}&limit=${limit}`
    ),
  coachingIntakeSubmissionDetail: (submissionId: string) =>
    getJson<CoachingIntakeSubmissionDetailResult>(
      `/coaching/intake/submissions/${encodeURIComponent(submissionId)}`
    ),
  coachingIntake: (payload: {
    workspace_id: string;
    applicant_name: string;
    applicant_email?: string;
    resume_text?: string;
    self_assessment_text?: string;
    job_links?: string[];
    preferences?: Record<string, any>;
  }) => postJson<{ ok: boolean; submission_id: string; workspace_id: string }>("/coaching/intake", payload),
};
