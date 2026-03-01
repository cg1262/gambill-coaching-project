"use client";

import { useMemo, useRef, useState, useEffect } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Edge,
  Node,
  OnNodesChange,
  OnEdgesChange,
  Connection,
  applyNodeChanges,
  applyEdgeChanges,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import { api, type BootstrapStatusResult, type ConnectionSettingsRow, type Dependency, type GitStatusResult, type Violation } from "../lib/api";
import { toCanvasAST } from "../lib/astTransform";
import { loadDemoToFlow, type DemoKey } from "../lib/demoLoader";
import { downloadCsv, downloadJson, readJsonFile } from "../lib/io";
import type { ColumnDef, EditableNodeData } from "../lib/types";
import { DATATUNE_STEPS } from "../lib/presenterScript";
import TableNode from "./editor/TableNode";
import ErdEdge from "./editor/ErdEdge";
import CoachingProjectWorkbench from "./coaching/CoachingProjectWorkbench";

const starterNodes: Node[] = [
  {
    id: "orders",
    position: { x: 60, y: 100 },
    data: {
      label: "orders",
      schema: "demo",
      columns: [
        { name: "order_id", dataType: "string", nullable: false, isPrimaryKey: true },
        { name: "customer_id", dataType: "string", nullable: false },
      ],
    },
    type: "tableNode",
  },
  {
    id: "customers",
    position: { x: 360, y: 220 },
    data: {
      label: "customers",
      schema: "demo",
      columns: [{ name: "customer_id", dataType: "string", nullable: false, isPrimaryKey: true }],
    },
    type: "tableNode",
  },
];

const starterEdges: Edge[] = [{ id: "orders-customers", source: "orders", target: "customers", label: "many_to_one", type: "erd", markerStart: { type: MarkerType.ArrowClosed }, markerEnd: { type: MarkerType.Arrow } }];

type RelType = "one_to_one" | "one_to_many" | "many_to_one" | "many_to_many";

export default function ModelCanvas() {
  const [nodes, setNodes] = useState<Node[]>(starterNodes);
  const [edges, setEdges] = useState<Edge[]>(starterEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string>(starterNodes[0].id);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string>(starterEdges[0].id);

  const [violations, setViolations] = useState<Violation[]>([]);
  const [dependencies, setDependencies] = useState<Dependency[]>([]);
  const [bootstrapStatus, setBootstrapStatus] = useState<BootstrapStatusResult | null>(null);
  const [gitStatus, setGitStatus] = useState<GitStatusResult | null>(null);
  const [gitRepoPath, setGitRepoPath] = useState("");
  const [gitBranch, setGitBranch] = useState("main");
  const [gitRemote, setGitRemote] = useState("origin");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [activeUser, setActiveUser] = useState("");
  const [themeMode, setThemeMode] = useState<"dark-premium" | "clean-enterprise">("dark-premium");
  const [connType, setConnType] = useState<"databricks_uc" | "information_schema" | "git" | "power_bi">("databricks_uc");
  const [connPayload, setConnPayload] = useState("{}");
  const [connRows, setConnRows] = useState<ConnectionSettingsRow[]>([]);
  const [standardsTemplates, setStandardsTemplates] = useState<Record<string, any>>({});
  const [selectedTemplateKey, setSelectedTemplateKey] = useState("");
  const [policyDocName, setPolicyDocName] = useState("custom-policy.txt");
  const [standardsTemplateVersion, setStandardsTemplateVersion] = useState("1.0");
  const [regulatoryTemplateVersion, setRegulatoryTemplateVersion] = useState("1.0");
  const [policyDocType, setPolicyDocType] = useState("custom");
  const [policyDocContent, setPolicyDocContent] = useState("");
  const [policyDocsCount, setPolicyDocsCount] = useState(0);
  const [runHistoryCount, setRunHistoryCount] = useState(0);
  const [runHistoryRows, setRunHistoryRows] = useState<Array<{ id: string; run_type: string; pass_type: string; actor_user: string; run_at: string }>>([]);
  const [standardsFindings, setStandardsFindings] = useState<any[]>([]);
  const [findingsSeverityFilter, setFindingsSeverityFilter] = useState<"ALL" | "HIGH" | "MED" | "LOW">("ALL");
  const [findingsSearch, setFindingsSearch] = useState("");
  const [impactSourceObject, setImpactSourceObject] = useState("demo.orders");
  const [impactTargetObject, setImpactTargetObject] = useState("pipeline:orders_daily");
  const [databricksValidationMsg, setDatabricksValidationMsg] = useState("");
  const [importedDatabricksObjects, setImportedDatabricksObjects] = useState<string[]>([]);
  const [databricksSchemas, setDatabricksSchemas] = useState<string[]>([]);
  const [demoReadiness, setDemoReadiness] = useState<{ ready: boolean; blockers: string[]; summary?: any } | null>(null);
  const [prWebhookUrl, setPrWebhookUrl] = useState("");
  const [prProvider, setPrProvider] = useState<"github" | "gitlab">("github");
  const [resultsTab, setResultsTab] = useState<"impact" | "violations" | "findings" | "audit" | "ast">("impact");
  const [performanceMode, setPerformanceMode] = useState(true);
  const [showToken, setShowToken] = useState(false);
  const [prApiUrl, setPrApiUrl] = useState("https://api.github.com");
  const [prToken, setPrToken] = useState("");
  const [prRepo, setPrRepo] = useState("");
  const [prNumber, setPrNumber] = useState("1");
  const [gitlabProjectId, setGitlabProjectId] = useState("");
  const [gitlabMrIid, setGitlabMrIid] = useState("1");
  const [githubArtifactsPath, setGithubArtifactsPath] = useState("governance-reports");
  const [findingAuditRows, setFindingAuditRows] = useState<any[]>([]);
  const [loading, setLoading] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [demoMode, setDemoMode] = useState(false);
  const [selectedDemo, setSelectedDemo] = useState<"starter" | DemoKey>("starter");
  const [presentationMode, setPresentationMode] = useState(false);
  const [showPresenterGuide, setShowPresenterGuide] = useState(false);
  const [presenterStep, setPresenterStep] = useState(0);
  const [inlineEditNodeId, setInlineEditNodeId] = useState<string>("");
  const [sidebarWidth, setSidebarWidth] = useState(420);
  const [draggingSplit, setDraggingSplit] = useState(false);

  const fileRef = useRef<HTMLInputElement>(null);

  const ast = useMemo(() => toCanvasAST(nodes, edges), [nodes, edges]);
  const nodeTypes = useMemo(() => ({ tableNode: TableNode }), []);
  const edgeTypes = useMemo(() => ({ erd: ErdEdge }), []);
  const databricksDraft = useMemo(() => {
    try {
      return JSON.parse(connPayload || "{}") as Record<string, any>;
    } catch {
      return {} as Record<string, any>;
    }
  }, [connPayload]);
  const filteredStandardsFindings = useMemo(
    () => standardsFindings
      .filter((f) => findingsSeverityFilter === "ALL" || (f.severity ?? "LOW") === findingsSeverityFilter)
      .filter((f) => {
        const q = findingsSearch.trim().toLowerCase();
        if (!q) return true;
        const hay = [f.table, f.finding, f.source_ref, f.document_id, f.severity].map((v) => String(v ?? "").toLowerCase()).join(" ");
        return hay.includes(q);
      }),
    [standardsFindings, findingsSeverityFilter, findingsSearch]
  );

  const demoLessons: Record<string, string[]> = {
    star_schema: [
      "Identify fact and dimension tables.",
      "Validate many-to-one relationships from fact to dimensions.",
      "Run standards checks for naming and PK/FK expectations.",
    ],
    galaxy_schema: [
      "Compare shared dimensions across multiple fact tables.",
      "Check consistency of key naming between facts.",
      "Estimate blast radius for a change in a shared dimension.",
    ],
    snowflake_schema: [
      "Trace normalized dimension chains (e.g., product -> category).",
      "Evaluate join complexity impact on analytics use-cases.",
      "Confirm relationship joins include all needed key pairs.",
    ],
  };

  function inlineRename(nodeId: string, idx: number, name: string) {
    setNodes((prev) => prev.map((n) => {
      if (n.id !== nodeId) return n;
      const d = (n.data ?? {}) as EditableNodeData;
      const cols = [...(d.columns ?? [])];
      if (!cols[idx]) return n;
      cols[idx] = { ...cols[idx], name };
      return { ...n, data: { ...d, columns: cols } };
    }));
  }

  const displayNodes = useMemo(
    () => nodes.map((n) => ({
      ...n,
      data: {
        ...(n.data as object),
        inlineEdit: inlineEditNodeId === n.id,
        compact: performanceMode && nodes.length > 120,
        onInlineRename: (idx: number, name: string) => inlineRename(n.id, idx, name),
      },
    })),
    [nodes, inlineEditNodeId]
  );

  const onNodesChange: OnNodesChange = (changes) => setNodes((nds) => applyNodeChanges(changes, nds));
  const onEdgesChange: OnEdgesChange = (changes) => setEdges((eds) => applyEdgeChanges(changes, eds));

  useEffect(() => {
    if (!draggingSplit) return;

    const onMove = (e: MouseEvent) => {
      const next = Math.min(640, Math.max(320, e.clientX));
      setSidebarWidth(next);
    };
    const onUp = () => setDraggingSplit(false);

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [draggingSplit]);

  const selected = nodes.find((n) => n.id === selectedNodeId);
  const selectedData = (selected?.data ?? {}) as EditableNodeData;
  const selectedColumns: ColumnDef[] = selectedData.columns ?? [];

  const selectedEdge = edges.find((e) => e.id === selectedEdgeId);

  function updateSelected(mutator: (d: EditableNodeData) => EditableNodeData) {
    setNodes((prev) =>
      prev.map((n) => {
        if (n.id !== selectedNodeId) return n;
        const current = (n.data ?? { label: n.id }) as EditableNodeData;
        return { ...n, data: mutator(current) };
      })
    );
  }

  function renameSelectedNode(newLabel: string) {
    updateSelected((d) => ({ ...d, label: newLabel }));
  }

  function renameSchema(schema: string) {
    updateSelected((d) => ({ ...d, schema }));
  }

  function updateColumn(idx: number, key: keyof ColumnDef, value: any) {
    updateSelected((d) => {
      const cols = [...(d.columns ?? [])];
      cols[idx] = { ...cols[idx], [key]: value };
      return { ...d, columns: cols };
    });
  }

  function addColumn() {
    updateSelected((d) => ({ ...d, columns: [...(d.columns ?? []), { name: "new_col", dataType: "string", nullable: true }] }));
  }

  function removeColumn(idx: number) {
    updateSelected((d) => {
      const cols = [...(d.columns ?? [])];
      cols.splice(idx, 1);
      return { ...d, columns: cols };
    });
  }

  function injectValidationExample() {
    updateSelected((d) => ({
      ...d,
      label: String(d.label ?? "TABLE_BAD"),
      columns: (d.columns ?? []).map((c) => ({ ...c, isPrimaryKey: false })),
    }));
  }

  function decorateEdge(e: Edge): Edge {
    const rel = String(e.label ?? "many_to_one");
    const sourceMany = rel === "many_to_one" || rel === "many_to_many";
    const targetMany = rel === "one_to_many" || rel === "many_to_many";
    return {
      ...e,
      type: "erd",
      label: rel,
      markerStart: { type: sourceMany ? MarkerType.ArrowClosed : MarkerType.Arrow },
      markerEnd: { type: targetMany ? MarkerType.ArrowClosed : MarkerType.Arrow },
    } as Edge;
  }

  function updateSelectedEdge(key: "source" | "target" | "label", value: string) {
    setEdges((prev) => prev.map((e) => (e.id === selectedEdgeId ? decorateEdge({ ...e, [key]: value }) : e)));
  }

  function getSelectedEdgeJoinColumns(): Array<{ fromColumn: string; toColumn: string }> {
    const joins = (selectedEdge?.data as any)?.joinColumns;
    if (Array.isArray(joins) && joins.length) {
      return joins.map((j: any) => ({ fromColumn: String(j.fromColumn || ""), toColumn: String(j.toColumn || "") }));
    }
    return [{
      fromColumn: String((selectedEdge?.data as any)?.fromColumn ?? "id"),
      toColumn: String((selectedEdge?.data as any)?.toColumn ?? "id"),
    }];
  }

  function setSelectedEdgeJoinColumns(joins: Array<{ fromColumn: string; toColumn: string }>) {
    const normalized = joins.map((j) => ({ fromColumn: String(j.fromColumn || "").trim(), toColumn: String(j.toColumn || "").trim() }))
      .filter((j) => j.fromColumn && j.toColumn);

    setEdges((prev) =>
      prev.map((e) => {
        if (e.id !== selectedEdgeId) return e;
        return decorateEdge({
          ...e,
          data: {
            ...(e.data as any),
            joinColumns: normalized,
            fromColumn: normalized[0]?.fromColumn || "id",
            toColumn: normalized[0]?.toColumn || "id",
          },
        });
      })
    );
  }

  function updateSelectedEdgeJoinPair(idx: number, key: "fromColumn" | "toColumn", value: string) {
    const joins = getSelectedEdgeJoinColumns();
    joins[idx] = { ...joins[idx], [key]: value };
    setSelectedEdgeJoinColumns(joins);
  }

  function addSelectedEdgeJoinPair() {
    const joins = getSelectedEdgeJoinColumns();
    joins.push({ fromColumn: "", toColumn: "" });
    setSelectedEdgeJoinColumns(joins);
  }

  function removeSelectedEdgeJoinPair(idx: number) {
    const joins = getSelectedEdgeJoinColumns();
    joins.splice(idx, 1);
    setSelectedEdgeJoinColumns(joins.length ? joins : [{ fromColumn: "id", toColumn: "id" }]);
  }

  function addEdgeManual() {
    if (nodes.length < 2) return;
    const source = nodes[0].id;
    const target = nodes[1].id;
    const id = `edge-${Date.now()}`;
    const e: Edge = decorateEdge({ id, source, target, label: "many_to_one" });
    setEdges((prev) => [...prev, e]);
    setSelectedEdgeId(id);
  }

  function onConnect(connection: Connection) {
    if (!connection.source || !connection.target) return;
    const id = `edge-${Date.now()}`;
    const rel = "many_to_one";
    const e: Edge = decorateEdge({
      id,
      source: connection.source,
      target: connection.target,
      label: rel,
    });
    setEdges((prev) => [...prev, e]);
    setSelectedEdgeId(id);
  }

  function addObject() {
    const id = `table_${nodes.length + 1}`;
    const n: Node = {
      id,
      type: "tableNode",
      position: { x: 120 + nodes.length * 40, y: 120 + nodes.length * 20 },
      data: {
        label: id,
        schema: "demo",
        columns: [{ name: "id", dataType: "string", nullable: false, isPrimaryKey: true }],
      },
    };
    setNodes((prev) => [...prev, n]);
    setSelectedNodeId(id);
  }

  function removeSelectedEdge() {
    setEdges((prev) => prev.filter((e) => e.id !== selectedEdgeId));
    setSelectedEdgeId("");
  }

  function applyAiModelSuggestions() {
    const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

    setNodes((prev) => prev.map((n) => {
      const d = (n.data ?? {}) as EditableNodeData;
      const cols = [...(d.columns ?? [])];
      const hasPk = cols.some((c) => !!c.isPrimaryKey);
      if (!hasPk && cols.length) {
        const tableNorm = normalize(String(d.label ?? n.id)).replace(/^dim|^fact/, "");
        const pkIdx = cols.findIndex((c) => {
          const cNorm = normalize(c.name);
          return cNorm === "id" || cNorm === `${tableNorm}id` || cNorm.endsWith("id");
        });
        if (pkIdx >= 0) cols[pkIdx] = { ...cols[pkIdx], isPrimaryKey: true, nullable: false };
      }
      return { ...n, data: { ...d, columns: cols } };
    }));

    const snapshotNodes = nodes.map((n) => ({ id: n.id, data: n.data as EditableNodeData }));
    const pkByTable: Record<string, string[]> = {};
    for (const n of snapshotNodes) {
      const cols = n.data?.columns ?? [];
      const pkCols = cols.filter((c) => c.isPrimaryKey || c.name.toLowerCase() === "id").map((c) => c.name.toLowerCase());
      pkByTable[n.id] = pkCols;
    }

    const existing = new Set(edges.map((e) => `${e.source}->${e.target}:${String(e.label ?? "")}`));
    const inferred: Edge[] = [];
    for (const src of snapshotNodes) {
      const srcCols = src.data?.columns ?? [];
      for (const c of srcCols) {
        const name = c.name.toLowerCase();
        if (!name.endsWith("_id") || c.isPrimaryKey) continue;
        for (const tgt of snapshotNodes) {
          if (tgt.id === src.id) continue;
          const pks = pkByTable[tgt.id] ?? [];
          if (!pks.includes(name) && !pks.includes("id")) continue;
          const key = `${src.id}->${tgt.id}:many_to_one`;
          if (existing.has(key)) continue;
          existing.add(key);
          inferred.push(decorateEdge({ id: `ai-${src.id}-${tgt.id}-${name}`, source: src.id, target: tgt.id, label: "many_to_one" }));
          break;
        }
      }
    }

    if (inferred.length) setEdges((prev) => [...prev, ...inferred]);
  }

  async function login() {
    try {
      setLoading("login");
      setError("");
      const res = await api.login(username, password);
      if (!res.ok) throw new Error(res.message || "Login failed");
      setActiveUser(res.username || username);
      await loadBootstrapStatus();
      await loadGitStatus();
      await loadConnectionSettings();
      await loadStandardsTemplates();
      await refreshRunHistory();
      await refreshFindingAudit();
      await refreshDemoReadiness();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function loadBootstrapStatus() {
    try {
      setLoading("bootstrap-status");
      setError("");
      const res = await api.bootstrapStatus();
      setBootstrapStatus(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function loadGitStatus() {
    try {
      setLoading("git-status");
      setError("");
      const res = await api.gitStatus(ast.workspaceId);
      setGitStatus(res);
      if (res.repo_path) setGitRepoPath(res.repo_path);
      if (res.branch) setGitBranch(res.branch);
      if (res.remote) setGitRemote(res.remote);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function loadConnectionSettings() {
    try {
      setLoading("connections-load");
      setError("");
      const res = await api.connectionSettings(ast.workspaceId);
      setConnRows(res.connections ?? []);
      const row = (res.connections ?? []).find((r) => r.connection_type === connType);
      if (row?.settings_json) {
        const parsed = typeof row.settings_json === "string" ? JSON.parse(row.settings_json) : row.settings_json;
        setConnPayload(JSON.stringify(parsed, null, 2));
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  function updateDatabricksField(field: string, value: string) {
    const next = { ...(databricksDraft || {}), [field]: value };
    setConnPayload(JSON.stringify(next, null, 2));
  }

  async function saveConnectionSettings() {
    try {
      setLoading("connections-save");
      setError("");
      const parsed = JSON.parse(connPayload || "{}");
      await api.saveConnectionSettings(ast.workspaceId, connType, parsed);
      if (connType === "databricks_uc") {
        const v = await api.validateDatabricksConnection(ast.workspaceId, parsed);
        if (!v.ok) throw new Error(v.message || "Databricks config validation failed");
        setDatabricksValidationMsg(v.message || "Databricks config valid");
      }
      await loadConnectionSettings();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function loadStandardsTemplates() {
    try {
      const res = await api.standardsTemplates();
      setStandardsTemplates(res.templates ?? {});
      const first = Object.keys(res.templates ?? {})[0] ?? "";
      if (first && !selectedTemplateKey) setSelectedTemplateKey(first);

      const cfg = await api.policyConfig(ast.workspaceId);
      if (cfg.config?.standards_template_name) {
        setSelectedTemplateKey(cfg.config.standards_template_name);
        setStandardsTemplateVersion(cfg.config.standards_template_version || "1.0");
        setRegulatoryTemplateVersion(cfg.config.regulatory_template_version || "1.0");
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function savePolicyConfig() {
    try {
      setLoading("policy-config");
      setError("");
      await api.savePolicyConfig(
        ast.workspaceId,
        selectedTemplateKey || "standards_template_basic",
        standardsTemplateVersion,
        "regulatory_template_basic",
        regulatoryTemplateVersion
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function uploadPolicyDocument() {
    try {
      setLoading("policy-upload");
      setError("");
      await api.uploadStandardsDocument(ast.workspaceId, policyDocName, policyDocType, policyDocContent);
      const docs = await api.standardsDocuments(ast.workspaceId);
      setPolicyDocsCount(docs.documents?.length ?? 0);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function refreshRunHistory() {
    try {
      const history = await api.runHistory(ast.workspaceId, 50);
      setRunHistoryCount(history.runs?.length ?? 0);
      setRunHistoryRows(history.runs ?? []);
    } catch {
      // non-blocking for UX scaffold
    }
  }

  async function refreshFindingAudit() {
    try {
      const res = await api.findingStatusAudit(ast.workspaceId, { page: 1, pageSize: 100 });
      setFindingAuditRows(res.audit ?? []);
    } catch {
      // non-blocking for UX scaffold
    }
  }

  async function runStandardsEvaluation() {
    try {
      setLoading("standards-evaluate");
      setError("");
      const res = await api.standardsEvaluate(ast as any);
      setStandardsFindings(res.findings ?? []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function setFindingLifecycleStatus(findingKey: string, status: string) {
    try {
      setStandardsFindings((prev) => prev.map((f) => String(f.finding_key) === findingKey ? { ...f, status } : f));
      await api.setFindingStatus(ast.workspaceId, findingKey, status);
      await runStandardsEvaluation();
      await refreshFindingAudit();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function setFilteredFindingsStatus(status: string) {
    try {
      const keys = filteredStandardsFindings.map((f) => String(f.finding_key || "")).filter(Boolean);
      if (!keys.length) return;
      setStandardsFindings((prev) => prev.map((f) => keys.includes(String(f.finding_key || "")) ? { ...f, status } : f));
      await api.setFindingStatusBulk(ast.workspaceId, keys, status);
      await runStandardsEvaluation();
      await refreshFindingAudit();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function copyPrSummary() {
    try {
      const res = await api.prSummary(ast as any);
      await navigator.clipboard.writeText(res.markdown || "");
      alert("PR summary copied to clipboard");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function postPrSummaryWebhook() {
    try {
      setLoading("pr-webhook");
      setError("");
      const res = await api.prSummary(ast as any);
      const out = await api.postPrWebhook(prWebhookUrl, res.markdown || "");
      if (!out.ok) throw new Error(out.message || "Webhook post failed");
      alert(`Webhook posted (${out.status_code ?? "ok"})`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function postProviderPrComment() {
    try {
      setLoading("pr-comment-provider");
      setError("");
      const summary = await api.prSummary(ast as any);
      const out = await api.postPrCommentProvider({
        provider: prProvider,
        api_url: prApiUrl,
        token: prToken,
        repo: prProvider === "github" ? prRepo : undefined,
        pr_number: prProvider === "github" ? Number(prNumber) : undefined,
        project_id: prProvider === "gitlab" ? gitlabProjectId : undefined,
        merge_request_iid: prProvider === "gitlab" ? Number(gitlabMrIid) : undefined,
        markdown: summary.markdown || "",
      });
      if (!out.ok) throw new Error(out.message || "Provider PR comment failed");
      alert(`Posted ${out.provider ?? prProvider} PR comment (${out.status_code ?? "ok"})`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function postGithubArtifacts() {
    try {
      setLoading("github-artifacts");
      setError("");
      const out = await api.postGithubArtifacts({
        api_url: prApiUrl,
        token: prToken,
        repo: prRepo,
        branch: gitBranch || "main",
        base_path: githubArtifactsPath,
        ast: ast as any,
        findings: standardsFindings,
      });
      if (!out.ok) throw new Error(out.message || "GitHub artifacts upload failed");
      alert(`Uploaded artifacts: ${(out.files ?? []).map((f) => f.path).join(", ")}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  function exportRunHistory() {
    downloadJson(`run-history-${ast.workspaceId}.json`, runHistoryRows);
  }

  function exportRunHistoryCsv() {
    downloadCsv(`run-history-${ast.workspaceId}.csv`, runHistoryRows as Record<string, any>[]);
  }

  function exportStandardsFindings() {
    downloadJson(`standards-findings-${ast.workspaceId}.json`, standardsFindings);
  }

  function exportStandardsFindingsCsv() {
    downloadCsv(`standards-findings-${ast.workspaceId}.csv`, filteredStandardsFindings as Record<string, any>[]);
  }

  async function copyReportSummary() {
    const bySeverity = filteredStandardsFindings.reduce<Record<string, number>>((acc, f) => {
      const sev = String(f.severity ?? "LOW");
      acc[sev] = (acc[sev] ?? 0) + 1;
      return acc;
    }, {});

    const topTables = Object.entries(
      filteredStandardsFindings.reduce<Record<string, number>>((acc, f) => {
        const t = String(f.table ?? "unknown");
        acc[t] = (acc[t] ?? 0) + 1;
        return acc;
      }, {})
    )
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([table, count]) => `- ${table}: ${count}`)
      .join("\n");

    const summary = [
      `Workspace: ${ast.workspaceId}`,
      `Run history entries: ${runHistoryRows.length}`,
      `Standards findings (filtered): ${filteredStandardsFindings.length}`,
      `Severity counts: HIGH=${bySeverity.HIGH ?? 0}, MED=${bySeverity.MED ?? 0}, LOW=${bySeverity.LOW ?? 0}`,
      "Top affected tables:",
      topTables || "- none",
    ].join("\n");

    try {
      await navigator.clipboard.writeText(summary);
      alert("Report summary copied to clipboard.");
    } catch {
      alert(summary);
    }
  }

  async function testDatabricksConnectionLive() {
    try {
      setLoading("databricks-live-test");
      setError("");
      const parsed = JSON.parse(connPayload || "{}");
      const res = await api.validateDatabricksConnection(ast.workspaceId, parsed, true);
      const live = res.live_test;
      setDatabricksValidationMsg(live?.attempted ? `Live test: ${live.message}` : (res.message || "Validation complete"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function refreshDemoReadiness() {
    try {
      const res = await api.demoReadiness(ast.workspaceId);
      setDemoReadiness({ ready: res.ready, blockers: res.blockers ?? [], summary: res.summary });
    } catch {
      // non-blocking
    }
  }

  async function loadDatabricksSchemas() {
    try {
      setLoading("databricks-schemas");
      setError("");
      const parsed = JSON.parse(connPayload || "{}");
      const res = await api.databricksSchemas(ast.workspaceId, parsed);
      if (!res.ok) throw new Error(res.message || "Could not load schemas");
      setDatabricksSchemas(res.schemas ?? []);
      if ((res.schemas ?? []).length) {
        const current = String(parsed.schema ?? "").trim();
        if (!current || (current !== "*" && !res.schemas.includes(current))) {
          updateDatabricksField("schema", "*");
        }
      }
      setDatabricksValidationMsg(`Schemas loaded: ${(res.schemas ?? []).length}`);
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      setDatabricksValidationMsg(`Schema list failed: ${msg}`);
    } finally {
      setLoading("");
    }
  }

  async function syncDatabricksSchemaToCanvas() {
    try {
      setLoading("databricks-schema-sync");
      setError("");
      setDatabricksValidationMsg("Importing Databricks schema...");
      const parsed = JSON.parse(connPayload || "{}");
      const res = await api.syncDatabricksSchema(ast.workspaceId, parsed, 300, 5000);
      if (!res.ok || !res.ast) throw new Error(res.message || "Schema sync failed");

      const tables = res.ast.tables ?? [];
      const relationships = res.ast.relationships ?? [];
      const importedNodes: Node[] = tables.map((t: any) => ({
        id: t.id,
        type: "tableNode",
        position: t.position ?? { x: 0, y: 0 },
        data: {
          label: t.table,
          schema: t.schema,
          columns: (t.columns ?? []).map((c: any) => ({
            name: c.name,
            dataType: c.data_type ?? c.dataType ?? "string",
            nullable: Boolean(c.nullable),
            isPrimaryKey: Boolean(c.is_primary_key ?? c.isPrimaryKey),
          })),
        },
      }));

      const importedEdges: Edge[] = relationships.map((r: any) => ({
        id: r.id,
        source: r.from_table_id ?? r.fromTableId,
        target: r.to_table_id ?? r.toTableId,
        label: r.relationship_type ?? r.relationshipType ?? "many_to_one",
      }));

      if (performanceMode && importedNodes.length > 150) {
        setNodes([]);
        for (let i = 0; i < importedNodes.length; i += 120) {
          const batch = importedNodes.slice(i, i + 120);
          setNodes((prev) => [...prev, ...batch]);
          await new Promise((r) => setTimeout(r, 0));
        }
      } else {
        setNodes(importedNodes);
      }
      setEdges(importedEdges.map(decorateEdge));
      setSelectedNodeId(importedNodes[0]?.id ?? "");
      setSelectedEdgeId(importedEdges[0]?.id ?? "");
      setImportedDatabricksObjects(importedNodes.map((n) => `${(n.data as any)?.schema ?? ""}.${(n.data as any)?.label ?? n.id}`));
      setDatabricksValidationMsg(`Import succeeded: ${res.table_count ?? importedNodes.length} tables / ${res.column_count ?? 0} columns`);
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      setDatabricksValidationMsg(`Import failed: ${msg}`);
    } finally {
      setLoading("");
    }
  }

  async function addImpactMapping() {
    try {
      setLoading("impact-mapping");
      setError("");
      await api.addDependencyMapping({
        workspace_id: ast.workspaceId,
        source_object: impactSourceObject,
        target_object: impactTargetObject,
        dependency_type: "pipeline",
        confidence: 90,
        source_system: "manual",
      });
      await runDeterministicImpact();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function saveGitConfig() {
    try {
      setLoading("git-config");
      setError("");
      const res = await api.setGitConfig(ast.workspaceId, gitRepoPath, gitBranch, gitRemote);
      if (!res.ok) throw new Error(res.message);
      await loadGitStatus();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function pushAstToGit() {
    try {
      setLoading("git-push");
      setError("");
      const res = await api.pushAstToGit(ast as any);
      if (!res.ok) throw new Error(res.message);
      await loadGitStatus();
      alert(`${res.message}${res.file ? `\n${res.file}` : ""}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", themeMode);
  }, [themeMode]);

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        if (me.authenticated) {
          setActiveUser(me.username || "");
          await loadBootstrapStatus();
          await loadGitStatus();
          await loadConnectionSettings();
          await loadStandardsTemplates();
          await refreshRunHistory();
          await refreshFindingAudit();
        }
      } catch {
        // not logged in yet
      }
    })();
  }, [ast.workspaceId]);

  useEffect(() => {
    const row = connRows.find((r) => r.connection_type === connType);
    if (!row?.settings_json) return;
    const parsed = typeof row.settings_json === "string" ? JSON.parse(row.settings_json) : row.settings_json;
    setConnPayload(JSON.stringify(parsed, null, 2));
  }, [connType, connRows]);

  async function runDeterministicValidation(payload = ast) {
    try {
      setLoading("deterministic-validation");
      setError("");
      const res = await api.validateDeterministic(payload as any);
      setViolations(res.violations ?? []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function runDeterministicImpact(payload = ast) {
    try {
      setLoading("deterministic-impact");
      setError("");
      const res = await api.impactDeterministic(payload as any);
      setDependencies(res.dependencies ?? []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function runProbabilisticValidation() {
    try {
      setLoading("prob-validation");
      setError("");
      const res = await api.validateProbabilistic(ast as any);
      setViolations(res.violations ?? []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function runProbabilisticImpact() {
    try {
      setLoading("prob-impact");
      setError("");
      const res = await api.impactProbabilistic(ast as any);
      setDependencies(res.dependencies ?? []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function loadDemo(kind: "starter" | DemoKey) {
    setSelectedDemo(kind);
    if (kind === "starter") {
      setNodes(starterNodes);
      setEdges(starterEdges);
      setSelectedNodeId(starterNodes[0].id);
      setSelectedEdgeId(starterEdges[0].id);
      return;
    }
    try {
      setLoading("load-demo");
      const { nodes: demoNodes, edges: demoEdges, raw } = await loadDemoToFlow(kind);
      setNodes(demoNodes);
      setEdges(demoEdges.map(decorateEdge));
      setSelectedNodeId(demoNodes[0]?.id ?? "");
      setSelectedEdgeId(demoEdges[0]?.id ?? "");
      if (demoMode) {
        await runDeterministicValidation(raw as any);
        await runDeterministicImpact(raw as any);
        await runProbabilisticImpact();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function onImportFile(file?: File) {
    if (!file) return;
    try {
      const imported = await readJsonFile<any>(file);
      const tables = imported.tables ?? [];
      const relationships = imported.relationships ?? [];
      const importedNodes: Node[] = tables.map((t: any) => ({
        id: t.id,
        type: "tableNode",
        position: t.position ?? { x: 0, y: 0 },
        data: { label: t.table, schema: t.schema, columns: t.columns ?? [] },
      }));
      const importedEdges: Edge[] = relationships.map((r: any) => ({
        id: r.id,
        source: r.fromTableId,
        target: r.toTableId,
        label: r.relationshipType,
      }));
      setNodes(importedNodes);
      setEdges(importedEdges.map(decorateEdge));
      setSelectedNodeId(importedNodes[0]?.id ?? "");
      setSelectedEdgeId(importedEdges[0]?.id ?? "");
    } catch (e) {
      setError(`Import failed: ${(e as Error).message}`);
    }
  }

  function exportAst() {
    downloadJson(`ast-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`, ast);
  }

  async function runDemoScript() {
    try {
      setDemoMode(true);
      await loadDemo("star_schema");
      await runDeterministicValidation();
      await runDeterministicImpact();
      await runProbabilisticImpact();
    } finally {
      setDemoMode(false);
    }
  }

  async function runFullCoachingExercise() {
    try {
      setLoading("coaching-exercise");
      setError("");
      if (selectedDemo === "starter") {
        await loadDemo("star_schema");
      }
      await applyAiModelSuggestions();
      await runDeterministicValidation();
      await runDeterministicImpact();
      await runStandardsEvaluation();
      await refreshRunHistory();
      await refreshFindingAudit();
      await refreshDemoReadiness();
      setResultsTab("findings");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading("");
    }
  }

  async function runPresenterStepAction(stepId: string) {
    if (stepId === "load") await loadDemo("star_schema");
    if (stepId === "det-validate") await runDeterministicValidation();
    if (stepId === "det-impact") await runDeterministicImpact();
    if (stepId === "prob") await runProbabilisticImpact();
  }

  async function nextPresenterStep() {
    const next = Math.min(presenterStep + 1, DATATUNE_STEPS.length - 1);
    setPresenterStep(next);
    await runPresenterStepAction(DATATUNE_STEPS[next].id);
  }

  async function prevPresenterStep() {
    const prev = Math.max(presenterStep - 1, 0);
    setPresenterStep(prev);
  }

  return (
    <>
    <div className="top-menu-bar">
      <div className="menu-group"><strong>File</strong><button onClick={exportAst}>Save/Export</button><button onClick={() => fileRef.current?.click()}>Import</button></div>
      <div className="menu-group"><strong>Insert</strong><button onClick={addObject}>New Object</button><button onClick={addEdgeManual}>New Relationship</button></div>
      <div className="menu-group"><strong>Connections</strong><button onClick={() => alert("Connection manager (LakeBase/UC) UI placeholder")}>Connectors</button></div>
      <div className="menu-group"><strong>Run</strong><button onClick={() => runDeterministicValidation()}>Validate</button><button onClick={() => runDeterministicImpact()}>Impact</button></div>
      <div className="menu-group"><strong>View</strong><button onClick={() => setPresentationMode((v) => !v)}>{presentationMode ? "Exit Presentation" : "Presentation"}</button><select value={themeMode} onChange={(e) => setThemeMode(e.target.value as "dark-premium" | "clean-enterprise")}><option value="dark-premium">Dark Premium</option><option value="clean-enterprise">Clean Enterprise</option></select></div>
    </div>
    <div className={presentationMode ? "app-shell presentation" : "app-shell"}>
      <div className="sidebar-pane" style={{ width: sidebarWidth }}>
      <div className="side-panel">
        <h3 style={{ marginTop: 0 }}>Validation & Impact</h3>

        <CoachingProjectWorkbench />

        <div style={{ display: "grid", gap: 8, marginBottom: 12 }}>
          <select onChange={(e) => loadDemo(e.target.value as any)} value={selectedDemo}>
            <option value="starter">Starter graph</option>
            <option value="star_schema">Star Schema example</option>
            <option value="galaxy_schema">Galaxy Schema example</option>
            <option value="snowflake_schema">Snowflake Schema example</option>
          </select>
          <button style={{ marginTop: 6 }} onClick={runFullCoachingExercise}>Run Full Coaching Exercise</button>
          {selectedDemo !== "starter" && demoLessons[selectedDemo] && (
            <div className="card" style={{ marginTop: 8 }}>
              <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 4 }}>Lesson Prompts</div>
              {demoLessons[selectedDemo].map((prompt, idx) => (
                <div key={`lesson-${selectedDemo}-${idx}`} style={{ fontSize: 12, marginBottom: 4 }}>• {prompt}</div>
              ))}
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <button onClick={exportAst}>Export AST</button>
            <button onClick={() => fileRef.current?.click()}>Import AST</button>
            <button onClick={addObject}>+ Add Object</button>
            <input ref={fileRef} type="file" accept="application/json" style={{ display: "none" }} onChange={(e) => onImportFile(e.target.files?.[0])} />
            <button onClick={runDemoScript}>Run DataTune Demo Mode</button>
            <button onClick={() => setPresentationMode((v) => !v)}>{presentationMode ? "Exit Presentation" : "Presentation Mode"}</button>
            <button onClick={() => { setShowPresenterGuide((v) => !v); setPresentationMode(true); }}>
              {showPresenterGuide ? "Hide Presenter Guide" : "Show Presenter Guide"}
            </button>
          </div>

          <button onClick={() => runDeterministicValidation()}>Run Deterministic Validation</button>
          <button onClick={injectValidationExample}>Inject Violation Example</button>
          <button onClick={() => runDeterministicImpact()}>Run Deterministic Impact</button>
          <button onClick={runProbabilisticValidation}>Run Probabilistic Validation</button>
          <button onClick={runProbabilisticImpact}>Run Probabilistic Impact</button>
          <button onClick={applyAiModelSuggestions}>Apply AI Modeling Suggestions (PK/FK)</button>
        </div>

        <h4>Selected Node Editor</h4>
        {selected ? (
          <div className="card" style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Table</label>
            <input style={{ width: "100%", marginTop: 4, marginBottom: 8, border: "1px solid var(--panel-border)", borderRadius: 8, padding: 8 }} value={String(selectedData.label ?? "")} onChange={(e) => renameSelectedNode(e.target.value)} />
            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Schema</label>
            <input style={{ width: "100%", marginTop: 4, marginBottom: 8, border: "1px solid var(--panel-border)", borderRadius: 8, padding: 8 }} value={String(selectedData.schema ?? "demo")} onChange={(e) => renameSchema(e.target.value)} />

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong>Columns</strong>
              <button onClick={addColumn}>+ Add</button>
            </div>
            {selectedColumns.map((c, idx) => (
              <div key={`col-${idx}`} className="card" style={{ marginTop: 6 }}>
                <input style={{ width: "100%", marginBottom: 4, border: "1px solid var(--panel-border)", borderRadius: 6, padding: 6 }} value={c.name} onChange={(e) => updateColumn(idx, "name", e.target.value)} />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                  <select value={c.dataType} onChange={(e) => updateColumn(idx, "dataType", e.target.value)}>
                    {["string", "int", "bigint", "decimal", "boolean", "date", "timestamp", "json", "array", "struct"].map((dt) => (
                      <option key={dt} value={dt}>{dt}</option>
                    ))}
                  </select>
                  <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
                    <input type="checkbox" checked={!!c.isPrimaryKey} onChange={(e) => updateColumn(idx, "isPrimaryKey", e.target.checked)} /> PK
                  </label>
                </div>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, marginTop: 4 }}>
                  <input type="checkbox" checked={c.nullable} onChange={(e) => updateColumn(idx, "nullable", e.target.checked)} /> Nullable
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, marginTop: 4 }}>
                  <input type="checkbox" checked={!!c.isForeignKey} onChange={(e) => updateColumn(idx, "isForeignKey", e.target.checked)} /> FK
                </label>
                <button style={{ marginTop: 6 }} onClick={() => removeColumn(idx)}>Remove</button>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "var(--color-text-muted)" }}>Click a node to edit table/schema/columns.</div>
        )}

        <h4>Relationship Editor</h4>
        {selectedEdge ? (
          <div className="card" style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 4 }}>Edge ID: {selectedEdge.id}</div>
            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Source</label>
            <select value={String(selectedEdge.source)} onChange={(e) => updateSelectedEdge("source", e.target.value)}>
              {nodes.map((n) => <option key={n.id} value={n.id}>{n.id}</option>)}
            </select>
            <label style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>Target</label>
            <select value={String(selectedEdge.target)} onChange={(e) => updateSelectedEdge("target", e.target.value)}>
              {nodes.map((n) => <option key={n.id} value={n.id}>{n.id}</option>)}
            </select>
            <label style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>Relationship Type</label>
            <select value={String(selectedEdge.label ?? "many_to_one")} onChange={(e) => updateSelectedEdge("label", e.target.value as RelType)}>
              <option value="one_to_one">one_to_one</option>
              <option value="one_to_many">one_to_many</option>
              <option value="many_to_one">many_to_one</option>
              <option value="many_to_many">many_to_many</option>
            </select>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
              <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Join Field Pairs</label>
              <button onClick={addSelectedEdgeJoinPair}>+ Add Pair</button>
            </div>
            {getSelectedEdgeJoinColumns().map((j, idx) => (
              <div key={`join-${selectedEdge.id}-${idx}`} style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 6, marginTop: 6 }}>
                <input
                  style={{ border: "1px solid var(--panel-border)", borderRadius: 8, padding: 8 }}
                  placeholder="from column"
                  value={j.fromColumn}
                  onChange={(e) => updateSelectedEdgeJoinPair(idx, "fromColumn", e.target.value)}
                />
                <input
                  style={{ border: "1px solid var(--panel-border)", borderRadius: 8, padding: 8 }}
                  placeholder="to column"
                  value={j.toColumn}
                  onChange={(e) => updateSelectedEdgeJoinPair(idx, "toColumn", e.target.value)}
                />
                <button className="btn-danger" onClick={() => removeSelectedEdgeJoinPair(idx)}>x</button>
              </div>
            ))}
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button onClick={addEdgeManual}>+ Add Edge</button>
              <button className="btn-danger" onClick={removeSelectedEdge}>Remove Edge</button>
            </div>
          </div>
        ) : (
          <div className="card" style={{ marginBottom: 10 }}>
            <div style={{ color: "var(--color-text-muted)", marginBottom: 6 }}>No edge selected.</div>
            <button onClick={addEdgeManual}>+ Add Edge</button>
          </div>
        )}

        <h4>Login</h4>
        <div className="card card-auth" style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 6 }}>
            Authenticate to run checks, persist runs, and push AST to git.
          </div>
          <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Username</label>
          <input style={{ width: "100%", marginTop: 4, marginBottom: 8, border: "1px solid var(--panel-border)", borderRadius: 8, padding: 8 }} value={username} onChange={(e) => setUsername(e.target.value)} />
          <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Password</label>
          <input type="password" style={{ width: "100%", marginTop: 4, marginBottom: 8, border: "1px solid var(--panel-border)", borderRadius: 8, padding: 8 }} value={password} onChange={(e) => setPassword(e.target.value)} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <button className="btn-primary" onClick={login}>Login</button>
            <span className={`badge ${activeUser ? "success" : "warning"}`}>{activeUser ? `Signed in: ${activeUser}` : "Not signed in"}</span>
          </div>
        </div>

        <h4>Backend Bootstrap Status</h4>
        <div className="card card-backend" style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 6 }}>
            Quick health/status for LakeBase backend tables.
          </div>
          <button onClick={loadBootstrapStatus} style={{ marginBottom: 8 }}>Refresh Status</button>
          {bootstrapStatus ? (
            <>
              <div style={{ fontSize: 12 }}>
                <strong>Backend:</strong> {bootstrapStatus.lakebase.backend}
              </div>
              {bootstrapStatus.lakebase.duckdb_path && (
                <div style={{ fontSize: 12 }}>
                  <strong>DuckDB:</strong> {bootstrapStatus.lakebase.duckdb_path}
                </div>
              )}
              <div style={{ fontSize: 12, marginBottom: 6 }}>
                <strong>Configured:</strong> {bootstrapStatus.lakebase.configured ? "Yes" : "No"}
              </div>
              <div style={{ display: "grid", gap: 4 }}>
                {Object.entries(bootstrapStatus.lakebase.tables).map(([name, info]) => (
                  <div key={name} style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <span>{name}</span>
                    <span className={`badge ${info.present ? "success" : "error"}`}>
                      {info.present ? `rows: ${info.row_count ?? 0}` : "missing"}
                    </span>
                  </div>
                ))}
              </div>
              {!!bootstrapStatus.lakebase.errors.length && (
                <div style={{ marginTop: 8, fontSize: 12, color: "var(--color-text-muted)" }}>
                  {bootstrapStatus.lakebase.errors.join(" | ")}
                </div>
              )}
            </>
          ) : (
            <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>No status loaded yet.</div>
          )}
        </div>

        <h4>Git AST Versioning</h4>
        <div className="card card-git" style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 6 }}>
            Configure git per workspace, then save current AST as a versioned JSON snapshot.
          </div>
          <div style={{ fontSize: 12, marginBottom: 6 }}><strong>Workspace:</strong> {ast.workspaceId}</div>
          <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Repo Path</label>
          <input style={{ width: "100%", marginTop: 4, marginBottom: 8, border: "1px solid var(--panel-border)", borderRadius: 8, padding: 8 }} value={gitRepoPath} onChange={(e) => setGitRepoPath(e.target.value)} placeholder="E:\\gde_git\\ai-data-modeling-ide" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
            <div>
              <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Branch</label>
              <input style={{ width: "100%", marginTop: 4, border: "1px solid var(--panel-border)", borderRadius: 8, padding: 8 }} value={gitBranch} onChange={(e) => setGitBranch(e.target.value)} placeholder="main" />
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Remote</label>
              <input style={{ width: "100%", marginTop: 4, border: "1px solid var(--panel-border)", borderRadius: 8, padding: 8 }} value={gitRemote} onChange={(e) => setGitRemote(e.target.value)} placeholder="origin" />
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <button className="btn-primary" onClick={saveGitConfig}>Save Git Config</button>
            <button onClick={loadGitStatus}>Refresh Git Status</button>
            <button className="btn-success" onClick={pushAstToGit}>Commit + Push AST</button>
          </div>
          {gitStatus ? (
            <>
              <div style={{ fontSize: 12 }}><strong>Configured:</strong> {gitStatus.configured ? "Yes" : "No"}</div>
              {gitStatus.message && <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{gitStatus.message}</div>}
              {gitStatus.repo_path && <div style={{ fontSize: 12 }}><strong>Repo:</strong> {gitStatus.repo_path}</div>}
              {gitStatus.branch && <div style={{ fontSize: 12 }}><strong>Target Branch:</strong> {gitStatus.branch}</div>}
              {gitStatus.current_branch && <div style={{ fontSize: 12 }}><strong>Current Branch:</strong> {gitStatus.current_branch}</div>}
              {gitStatus.remote && <div style={{ fontSize: 12 }}><strong>Remote:</strong> {gitStatus.remote}</div>}
            </>
          ) : (
            <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>No git status loaded yet.</div>
          )}
        </div>

        <h4>Connections & Sources</h4>
        <div className="card" style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 6 }}>
            Configure customer-specific connection settings for lineage + integrations.
          </div>
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 6 }}>
            Workspace ID: <strong style={{ color: "var(--color-text)" }}>{ast.workspaceId}</strong>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
            <button onClick={refreshDemoReadiness}>Demo Readiness Check</button>
            {demoReadiness && (
              <span className={`badge ${demoReadiness.ready ? "success" : "warning"}`}>
                {demoReadiness.ready ? "READY" : `BLOCKED (${demoReadiness.blockers.length})`}
              </span>
            )}
          </div>
          {demoReadiness && (
            <div className="card" style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 12 }}>Connections: {demoReadiness.summary?.connections_configured ?? 0}</div>
              <div style={{ fontSize: 12 }}>Policy Docs: {demoReadiness.summary?.policy_documents ?? 0}</div>
              <div style={{ fontSize: 12 }}>Validation Runs: {demoReadiness.summary?.validation_runs ?? 0}</div>
              <div style={{ fontSize: 12 }}>Impact Runs: {demoReadiness.summary?.impact_runs ?? 0}</div>
              {!!demoReadiness.blockers?.length && (
                <div style={{ marginTop: 6 }}>
                  {demoReadiness.blockers.map((b, i) => <div key={`blk-${i}`} style={{ fontSize: 12, color: "var(--danger)" }}>• {b}</div>)}
                </div>
              )}
            </div>
          )}
          <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Connection Type</label>
          <select value={connType} onChange={(e) => setConnType(e.target.value as "databricks_uc" | "information_schema" | "git" | "power_bi")}>
            <option value="databricks_uc">Databricks / Unity Catalog</option>
            <option value="information_schema">information_schema</option>
            <option value="git">Git</option>
            <option value="power_bi">Power BI</option>
          </select>
          {connType === "databricks_uc" && (
            <div className="card" style={{ marginTop: 8 }}>
              <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 6 }}>Databricks Required Fields</div>
              <input value={String(databricksDraft.host ?? "")} onChange={(e) => updateDatabricksField("host", e.target.value)} placeholder="host (https://...)" />
              <input style={{ marginTop: 6 }} value={String(databricksDraft.http_path ?? "")} onChange={(e) => updateDatabricksField("http_path", e.target.value)} placeholder="http_path (/sql/1.0/warehouses/...)" />
              <input style={{ marginTop: 6 }} value={String(databricksDraft.warehouse_id ?? "")} onChange={(e) => updateDatabricksField("warehouse_id", e.target.value)} placeholder="warehouse_id" />
              <input style={{ marginTop: 6 }} value={String(databricksDraft.catalog ?? "")} onChange={(e) => updateDatabricksField("catalog", e.target.value)} placeholder="catalog" />
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, marginTop: 6 }}>
                <select value={String(databricksDraft.schema ?? "*")} onChange={(e) => updateDatabricksField("schema", e.target.value)}>
                  <option value="*">* (all schemas)</option>
                  {databricksSchemas.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <button onClick={loadDatabricksSchemas}>Load Schemas</button>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
                <input
                  type={showToken ? "text" : "password"}
                  value={String(databricksDraft.token ?? "")}
                  onChange={(e) => updateDatabricksField("token", e.target.value)}
                  placeholder="token"
                  style={{ flex: 1 }}
                />
                <button onClick={() => setShowToken((v) => !v)}>{showToken ? "Hide" : "Show"}</button>
              </div>
            </div>
          )}
          <label style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 8 }}>Settings JSON (advanced)</label>
          <textarea
            value={connPayload}
            onChange={(e) => setConnPayload(e.target.value)}
            style={{ width: "100%", minHeight: 140, marginTop: 4, border: "1px solid var(--panel-border)", borderRadius: 8, padding: 8, background: "var(--control-bg)", color: "var(--color-text)" }}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button className="btn-primary" onClick={saveConnectionSettings}>Save Connection</button>
            <button onClick={loadConnectionSettings}>Refresh</button>
            <button onClick={async () => { const t = await api.connectionTemplates(); setConnPayload(JSON.stringify(t.templates[connType] ?? {}, null, 2)); }}>Load Template</button>
          </div>
          {connType === "databricks_uc" && (
            <div style={{ marginTop: 6, display: "grid", gap: 6 }}>
              <button onClick={testDatabricksConnectionLive}>Test Databricks Connection (Live)</button>
              <button onClick={syncDatabricksSchemaToCanvas}>Import Databricks Tables/Fields</button>
              {databricksValidationMsg && <div style={{ fontSize: 12, marginTop: 4, color: "var(--color-text-muted)" }}>{databricksValidationMsg}</div>}
              {!!importedDatabricksObjects.length && (
                <div style={{ marginTop: 6, maxHeight: 120, overflowY: "auto", border: "1px solid var(--panel-border)", borderRadius: 8, padding: 6 }}>
                  <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: 4 }}>Imported Objects ({importedDatabricksObjects.length})</div>
                  {importedDatabricksObjects.slice(0, 50).map((name, idx) => (
                    <div key={`dbo-${idx}`} style={{ fontSize: 12 }}>{name}</div>
                  ))}
                  {importedDatabricksObjects.length > 50 && (
                    <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>...and {importedDatabricksObjects.length - 50} more</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <h4>Standards / Regulatory</h4>
        <div className="card" style={{ marginBottom: 10 }}>
          <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Template Pack</label>
          <select value={selectedTemplateKey} onChange={(e) => setSelectedTemplateKey(e.target.value)}>
            <option value="">Select template</option>
            {Object.keys(standardsTemplates).map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <button style={{ marginTop: 6 }} onClick={() => {
            if (!selectedTemplateKey) return;
            setPolicyDocName(`${selectedTemplateKey}.json`);
            setPolicyDocType(selectedTemplateKey.includes("regulatory") ? "regulatory" : "standards");
            setPolicyDocContent(JSON.stringify(standardsTemplates[selectedTemplateKey] ?? {}, null, 2));
          }}>Load to Editor</button>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 6 }}>
            <input value={standardsTemplateVersion} onChange={(e) => setStandardsTemplateVersion(e.target.value)} placeholder="standards version" />
            <input value={regulatoryTemplateVersion} onChange={(e) => setRegulatoryTemplateVersion(e.target.value)} placeholder="regulatory version" />
          </div>
          <button style={{ marginTop: 6 }} onClick={savePolicyConfig}>Pin Template Versions</button>
          <label style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 8 }}>Document Name</label>
          <input value={policyDocName} onChange={(e) => setPolicyDocName(e.target.value)} />
          <label style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 8 }}>Type</label>
          <select value={policyDocType} onChange={(e) => setPolicyDocType(e.target.value)}>
            <option value="standards">standards</option>
            <option value="regulatory">regulatory</option>
            <option value="custom">custom</option>
          </select>
          <textarea value={policyDocContent} onChange={(e) => setPolicyDocContent(e.target.value)} style={{ width: "100%", minHeight: 110, marginTop: 6 }} placeholder="Paste policy text or JSON" />
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
            <button className="btn-primary" onClick={uploadPolicyDocument}>Upload Policy Doc</button>
            <span className="badge info">Docs: {policyDocsCount}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
            <button onClick={refreshRunHistory}>Refresh Run History</button>
            <span className="badge success">Runs: {runHistoryCount}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
            <button onClick={runStandardsEvaluation}>Run Standards Evaluation</button>
            <span className="badge warning">Findings: {filteredStandardsFindings.length}</span>
          </div>
          <label style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 8 }}>Findings Severity Filter</label>
          <select value={findingsSeverityFilter} onChange={(e) => setFindingsSeverityFilter(e.target.value as "ALL" | "HIGH" | "MED" | "LOW")}>
            <option value="ALL">ALL</option>
            <option value="HIGH">HIGH</option>
            <option value="MED">MED</option>
            <option value="LOW">LOW</option>
          </select>
          <label style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 8 }}>Findings Search</label>
          <input value={findingsSearch} onChange={(e) => setFindingsSearch(e.target.value)} placeholder="search table/finding/source" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 6 }}>
            <button onClick={exportStandardsFindings}>Export Findings JSON</button>
            <button onClick={exportStandardsFindingsCsv}>Export Findings CSV</button>
            <button onClick={exportRunHistory}>Export Run History JSON</button>
            <button onClick={exportRunHistoryCsv}>Export Run History CSV</button>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
            <button onClick={copyReportSummary}>Copy Report Summary</button>
            <button onClick={copyPrSummary}>Copy PR Summary</button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 6 }}>
            <button onClick={() => setFilteredFindingsStatus("accepted-risk")}>Mark Filtered as accepted-risk</button>
            <button onClick={() => setFilteredFindingsStatus("remediated")}>Mark Filtered as remediated</button>
          </div>
          <label style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 8 }}>PR Webhook URL (Generic)</label>
          <input value={prWebhookUrl} onChange={(e) => setPrWebhookUrl(e.target.value)} placeholder="https://..." />
          <button style={{ marginTop: 6 }} onClick={postPrSummaryWebhook}>Post PR Summary to Webhook</button>

          <label style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 8 }}>Provider PR Comment</label>
          <select value={prProvider} onChange={(e) => setPrProvider(e.target.value as "github" | "gitlab")}>
            <option value="github">github</option>
            <option value="gitlab">gitlab</option>
          </select>
          <input value={prApiUrl} onChange={(e) => setPrApiUrl(e.target.value)} placeholder="API URL" style={{ marginTop: 6 }} />
          <input type="password" value={prToken} onChange={(e) => setPrToken(e.target.value)} placeholder="Provider token" style={{ marginTop: 6 }} />
          {prProvider === "github" ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 6 }}>
              <input value={prRepo} onChange={(e) => setPrRepo(e.target.value)} placeholder="owner/repo" />
              <input value={prNumber} onChange={(e) => setPrNumber(e.target.value)} placeholder="PR #" />
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 6 }}>
              <input value={gitlabProjectId} onChange={(e) => setGitlabProjectId(e.target.value)} placeholder="project id" />
              <input value={gitlabMrIid} onChange={(e) => setGitlabMrIid(e.target.value)} placeholder="MR iid" />
            </div>
          )}
          <button style={{ marginTop: 6 }} onClick={postProviderPrComment}>Post Provider PR Comment</button>
          {prProvider === "github" && (
            <>
              <label style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 8 }}>GitHub Artifacts Path</label>
              <input value={githubArtifactsPath} onChange={(e) => setGithubArtifactsPath(e.target.value)} placeholder="governance-reports" />
              <button style={{ marginTop: 6 }} onClick={postGithubArtifacts}>Post AST + Findings to GitHub</button>
            </>
          )}
        </div>

        {resultsTab === "impact" && <h4>Impact Mapping (Pipelines/Notebooks/PBI)</h4>}
        {resultsTab === "impact" && (
        <div className="card" style={{ marginBottom: 10 }}>
          <input value={impactSourceObject} onChange={(e) => setImpactSourceObject(e.target.value)} placeholder="source object" />
          <input value={impactTargetObject} onChange={(e) => setImpactTargetObject(e.target.value)} placeholder="target object" style={{ marginTop: 6 }} />
          <button style={{ marginTop: 8 }} onClick={addImpactMapping}>Add Mapping + Re-run Impact</button>
        </div>
        )}

        {loading && <p className="badge info">Running: {loading}</p>}
        {error && <p className="badge error">{error}</p>}

        <h4>Results Panel</h4>
        <div className="card" style={{ marginBottom: 10 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <button onClick={() => setResultsTab("impact")}>Impact</button>
            <button onClick={() => setResultsTab("violations")}>Violations</button>
            <button onClick={() => setResultsTab("findings")}>Standards Findings</button>
            <button onClick={() => setResultsTab("audit")}>Finding Audit</button>
            <button onClick={() => setResultsTab("ast")}>AST Preview</button>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
            <input type="checkbox" checked={performanceMode} onChange={(e) => setPerformanceMode(e.target.checked)} />
            Performance Mode (compact large graph rendering)
          </label>
        </div>

        {resultsTab === "violations" && <h4>Violations ({violations.length})</h4>}
        {resultsTab === "violations" && (
        <div style={{ display: "grid", gap: 6 }}>
          {violations.map((v, idx) => (
            <div key={`${v.code}-${idx}`} className="card card-violation">
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <strong>{v.code}</strong>
                <span className={`badge ${v.severity === "HIGH" ? "error" : v.severity === "MED" ? "warning" : "info"}`}>{v.severity}</span>
              </div>
              <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>{v.message}</div>
            </div>
          ))}
        </div>
        )}

        {resultsTab === "impact" && <h4 style={{ marginTop: 14 }}>Dependencies ({dependencies.length})</h4>}
        {resultsTab === "impact" && (
        <div style={{ display: "grid", gap: 6 }}>
          {dependencies.map((d, idx) => (
            <div key={`${d.object_name}-${idx}`} className="card card-dependency">
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <strong>{d.object_name}</strong>
                <span className={`badge ${d.color === "green" ? "success" : d.color === "yellow" ? "warning" : "error"}`}>{d.confidence}%</span>
              </div>
              <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>{d.source} · {d.dependency_type}</div>
            </div>
          ))}
        </div>
        )}

        {resultsTab === "findings" && <h4 style={{ marginTop: 14 }}>Standards Findings ({filteredStandardsFindings.length})</h4>}
        {resultsTab === "findings" && (
        <div style={{ display: "grid", gap: 6 }}>
          {filteredStandardsFindings.slice(0, 12).map((f, idx) => (
            <div key={`sf-${idx}`} className="card">
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <strong>{f.table}</strong>
                <span className={`badge ${f.severity === "HIGH" ? "error" : f.severity === "MED" ? "warning" : "info"}`}>{f.severity ?? "LOW"}</span>
              </div>
              <div style={{ fontSize: 12 }}>{f.finding}</div>
              <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{f.source_ref}</div>
              <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 6 }}>
                <span style={{ fontSize: 11 }}>Status:</span>
                <select value={f.status ?? "open"} onChange={(e) => setFindingLifecycleStatus(String(f.finding_key || ""), e.target.value)}>
                  <option value="open">open</option>
                  <option value="accepted-risk">accept risk</option>
                  <option value="remediated">remediated</option>
                  <option value="false-positive">false positive</option>
                </select>
              </div>
            </div>
          ))}
        </div>
        )}

        {resultsTab === "audit" && <h4 style={{ marginTop: 14 }}>Run History ({runHistoryRows.length})</h4>}
        {resultsTab === "audit" && (
        <>
        <div style={{ display: "grid", gap: 6 }}>
          {runHistoryRows.slice(0, 12).map((r, idx) => (
            <div key={`rh-${idx}`} className="card" style={{ fontSize: 12 }}>
              <strong>{r.run_type}</strong> · {r.pass_type} · {r.actor_user}
              <div style={{ color: "var(--color-text-muted)" }}>{r.run_at}</div>
            </div>
          ))}
        </div>

        <h4 style={{ marginTop: 14 }}>Finding Status Audit ({findingAuditRows.length})</h4>
        <div style={{ display: "grid", gap: 6 }}>
          {findingAuditRows.slice(0, 12).map((a, idx) => (
            <div key={`fa-${idx}`} className="card" style={{ fontSize: 12 }}>
              <strong>{a.new_status}</strong> ← {a.old_status ?? "(none)"}
              <div style={{ color: "var(--color-text-muted)" }}>{a.finding_key}</div>
              <div style={{ color: "var(--color-text-muted)" }}>{a.updated_by} · {a.updated_at}</div>
            </div>
          ))}
        </div>
        </>
        )}

        {resultsTab === "ast" && <h4 style={{ marginTop: 14 }}>AST Preview</h4>}
        {resultsTab === "ast" && <pre style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>{JSON.stringify(ast, null, 2)}</pre>}
      </div>
      </div>
      <div className="splitter" onMouseDown={() => setDraggingSplit(true)} />
      <div className="canvas-pane" style={{ position: "relative" }}>
        {showPresenterGuide && (
          <div className="presenter-overlay">
            <div className="presenter-title">DataTune Presenter Guide</div>
            <div className="presenter-step">{presenterStep + 1}. {DATATUNE_STEPS[presenterStep].title}</div>
            <div style={{ fontSize: 14, lineHeight: 1.45 }}>{DATATUNE_STEPS[presenterStep].prompt}</div>
            <div className="presenter-controls">
              <button onClick={prevPresenterStep}>Back</button>
              <button onClick={nextPresenterStep}>Next</button>
            </div>
          </div>
        )}
        <ReactFlow
          nodes={displayNodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => setSelectedNodeId(node.id)}
          onNodeDoubleClick={(_, node) => { setSelectedNodeId(node.id); setInlineEditNodeId(node.id); }}
          onEdgeClick={(_, edge) => setSelectedEdgeId(edge.id)}
        >
          <Background color={themeMode === "dark-premium" ? "#1f2d45" : "#cbd5e1"} gap={18} size={1.2} />
          <MiniMap
            nodeColor={themeMode === "dark-premium" ? "#334155" : "#93c5fd"}
            maskColor={themeMode === "dark-premium" ? "rgba(2,6,23,0.45)" : "rgba(226,232,240,0.55)"}
            style={{ background: themeMode === "dark-premium" ? "#0b1220" : "#ffffff", border: "1px solid var(--panel-border)" }}
          />
          <Controls />
        </ReactFlow>
      </div>
    </div>
    </>
  );
}
