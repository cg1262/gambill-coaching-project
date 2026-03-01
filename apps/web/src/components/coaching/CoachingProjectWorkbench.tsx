"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type CoachingIntakeSubmission } from "../../lib/api";

type IntakeStepId = "resume" | "selfAssessment" | "jobLinks" | "preferences";
type StageId = "intakeParsed" | "sowGenerated" | "validated";

type IntakeDraft = {
  workspaceId: string;
  candidateName: string;
  candidateEmail: string;
  targetRole: string;
  resumeFileName: string;
  selfAssessment: string;
  jobLinksText: string;
  preferredStack: string;
  timelineWeeks: string;
};

type Milestone = {
  title: string;
  outcome: string;
  deliverables: string[];
};

type ProjectScaffold = {
  title: string;
  candidateSnapshot: string;
  businessOutcome: string;
  architecture: {
    bronze: string;
    silver: string;
    gold: string;
  };
  milestones: Milestone[];
  roiRequirements: string[];
  recommendedResources: { title: string; type: "course" | "article" | "video"; url: string; reason: string }[];
  mentoringCta: {
    offer: string;
    pricing: string;
    timeline: string;
    ctaText: string;
  };
};

const STEP_ORDER: IntakeStepId[] = ["resume", "selfAssessment", "jobLinks", "preferences"];

const STEP_LABELS: Record<IntakeStepId, string> = {
  resume: "1) Resume",
  selfAssessment: "2) Self-Assessment",
  jobLinks: "3) Job Links",
  preferences: "4) Stack + Timeline",
};

const DEFAULT_DRAFT: IntakeDraft = {
  workspaceId: "demo-workspace",
  candidateName: "",
  candidateEmail: "",
  targetRole: "Senior Data Engineer",
  resumeFileName: "",
  selfAssessment: "",
  jobLinksText: "",
  preferredStack: "Databricks + dbt + Power BI",
  timelineWeeks: "8",
};

function buildProjectScaffold(draft: IntakeDraft): ProjectScaffold {
  const parsedJobLinks = draft.jobLinksText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const candidateName = draft.candidateName.trim() || "Candidate";
  const targetRole = draft.targetRole.trim() || "Data Engineer";

  return {
    title: `${targetRole} Coaching Project Blueprint`,
    candidateSnapshot: `${candidateName} targeting ${targetRole}. Intake includes ${parsedJobLinks.length || 0} job posting references and stack preference of ${draft.preferredStack}.`,
    businessOutcome: "Design and implement a medallion-aligned analytics platform initiative that demonstrates measurable delivery impact to hiring managers.",
    architecture: {
      bronze: "Raw ingest from source systems into immutable bronze layer with ingestion observability and SLA tracking.",
      silver: "Conformed silver transformations with quality checks, schema evolution handling, and tested business logic.",
      gold: "Curated gold marts with KPI definitions, stakeholder-ready semantic models, and dashboard-ready outputs.",
    },
    milestones: [
      {
        title: "Milestone 1: Intake-to-Model Plan",
        outcome: "Translate resume/job signals into a technical scope and risk assumptions.",
        deliverables: ["Skill gap matrix", "System context diagram", "Delivery plan draft"],
      },
      {
        title: "Milestone 2: Medallion Build Sprint",
        outcome: "Ship working bronze/silver/gold data product with tests and lineage.",
        deliverables: ["Pipeline implementation", "Data quality checks", "Lineage + runbook"],
      },
      {
        title: "Milestone 3: Business Readout",
        outcome: "Present architecture decisions, KPI lift, and operational readiness.",
        deliverables: ["ROI dashboard spec", "Executive walkthrough", "Interview narrative assets"],
      },
    ],
    roiRequirements: [
      "Define baseline KPI and target KPI with explicit formula.",
      "Map at least one cost metric and one speed metric to pipeline outcomes.",
      "Include instrumentation plan for 30/60/90 day tracking.",
    ],
    recommendedResources: [
      {
        title: "Databricks Medallion Architecture Reference",
        type: "article",
        url: "https://docs.databricks.com/en/lakehouse/medallion.html",
        reason: "Aligns project architecture with interview-ready patterns.",
      },
      {
        title: "dbt Fundamentals",
        type: "course",
        url: "https://courses.getdbt.com/courses/fundamentals",
        reason: "Strengthens transformation and testing delivery for Milestone 2.",
      },
      {
        title: "Storytelling With Data",
        type: "video",
        url: "https://www.youtube.com/@storytellingwithdata",
        reason: "Improves executive readout and ROI narrative quality.",
      },
    ],
    mentoringCta: {
      offer: "1:1 Mentoring Sprint (4 weeks)",
      pricing: "$1,200 flat",
      timeline: "Weekly 60-min sessions + async reviews",
      ctaText: "Book mentoring kickoff",
    },
  };
}

function downloadText(content: string, fileName: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

function stageBadgeClass(done: boolean): string {
  return done ? "badge success" : "badge warning";
}

export default function CoachingProjectWorkbench() {
  const [activeStep, setActiveStep] = useState<IntakeStepId>("resume");
  const [draft, setDraft] = useState<IntakeDraft>(DEFAULT_DRAFT);
  const [scaffold, setScaffold] = useState<ProjectScaffold | null>(null);
  const [viewerTab, setViewerTab] = useState<"overview" | "milestones" | "architecture" | "roi" | "resources">("overview");
  const [stageState, setStageState] = useState<Record<StageId, boolean>>({
    intakeParsed: false,
    sowGenerated: false,
    validated: false,
  });

  const [submissions, setSubmissions] = useState<CoachingIntakeSubmission[]>([]);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const completion = useMemo(() => ({
    resume: Boolean(draft.resumeFileName.trim()),
    selfAssessment: draft.selfAssessment.trim().length > 40,
    jobLinks: draft.jobLinksText.trim().length > 0,
    preferences: Boolean(draft.preferredStack.trim()) && Boolean(draft.timelineWeeks.trim()),
  }), [draft]);

  const completedCount = Object.values(completion).filter(Boolean).length;

  async function loadSubmissions() {
    try {
      setReviewLoading(true);
      setReviewError(null);
      const out = await api.listCoachingIntakeSubmissions(draft.workspaceId || "demo-workspace", 50);
      setSubmissions(out.submissions || []);
    } catch (e: any) {
      setReviewError(e?.message || "Failed to load submissions");
    } finally {
      setReviewLoading(false);
    }
  }

  useEffect(() => {
    loadSubmissions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function moveStep(direction: "next" | "back") {
    const current = STEP_ORDER.indexOf(activeStep);
    if (direction === "next") {
      const next = STEP_ORDER[Math.min(STEP_ORDER.length - 1, current + 1)];
      setActiveStep(next);
      return;
    }
    const previous = STEP_ORDER[Math.max(0, current - 1)];
    setActiveStep(previous);
  }

  async function submitIntake() {
    const jobLinks = draft.jobLinksText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    await api.coachingIntake({
      workspace_id: draft.workspaceId,
      applicant_name: draft.candidateName || "Candidate",
      applicant_email: draft.candidateEmail || undefined,
      resume_text: draft.resumeFileName,
      self_assessment_text: draft.selfAssessment,
      job_links: jobLinks,
      preferences: {
        target_role: draft.targetRole,
        preferred_stack: draft.preferredStack,
        timeline_weeks: draft.timelineWeeks,
      },
    });

    setStageState((prev) => ({ ...prev, intakeParsed: true }));
    await loadSubmissions();
  }

  function buildScaffoldAndAdvance() {
    setScaffold(buildProjectScaffold(draft));
    setStageState((prev) => ({ ...prev, sowGenerated: true }));
  }

  function markValidated() {
    setStageState((prev) => ({ ...prev, validated: true }));
  }

  function exportStudentPackage(format: "markdown" | "json") {
    if (!scaffold) return;

    const timestamp = new Date().toISOString().slice(0, 10);
    const safeName = (draft.candidateName || "candidate").toLowerCase().replace(/\s+/g, "-");

    if (format === "json") {
      downloadText(JSON.stringify(scaffold, null, 2), `${safeName}-coaching-package-${timestamp}.json`, "application/json");
      return;
    }

    const markdown = [
      `# ${scaffold.title}`,
      "",
      `## Candidate Snapshot`,
      scaffold.candidateSnapshot,
      "",
      `## Business Outcome`,
      scaffold.businessOutcome,
      "",
      "## Milestones",
      ...scaffold.milestones.flatMap((m) => [
        `### ${m.title}`,
        `- Outcome: ${m.outcome}`,
        ...m.deliverables.map((d) => `- Deliverable: ${d}`),
      ]),
      "",
      "## Recommended Resources",
      ...scaffold.recommendedResources.map((r) => `- [${r.title}](${r.url}) — ${r.reason}`),
      "",
      "## Mentoring Offer",
      `- Offer: ${scaffold.mentoringCta.offer}`,
      `- Pricing: ${scaffold.mentoringCta.pricing}`,
      `- Timeline: ${scaffold.mentoringCta.timeline}`,
      `- CTA: ${scaffold.mentoringCta.ctaText}`,
    ].join("\n");

    downloadText(markdown, `${safeName}-coaching-package-${timestamp}.md`, "text/markdown");
  }

  return (
    <>
      <h4>Coach Review Queue</h4>
      <div className="card" style={{ marginBottom: 10 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
          <input
            value={draft.workspaceId}
            onChange={(e) => setDraft((prev) => ({ ...prev, workspaceId: e.target.value }))}
            placeholder="workspace id"
            style={{ maxWidth: 220 }}
          />
          <button onClick={loadSubmissions}>Refresh submissions</button>
          {reviewLoading && <span className="badge info">Loading…</span>}
          {reviewError && <span className="badge error">{reviewError}</span>}
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th align="left">Applicant</th>
                <th align="left">Email</th>
                <th align="left">Status</th>
                <th align="left">Submitted By</th>
                <th align="left">Created</th>
              </tr>
            </thead>
            <tbody>
              {submissions.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ color: "var(--color-text-muted)", padding: "8px 0" }}>
                    No submissions yet for this workspace.
                  </td>
                </tr>
              ) : (
                submissions.map((s) => (
                  <tr key={s.submission_id}>
                    <td>{s.applicant_name || "—"}</td>
                    <td>{s.applicant_email || "—"}</td>
                    <td>
                      <span className={`badge ${String(s.status || "submitted").toLowerCase().includes("review") ? "warning" : "info"}`}>
                        {s.status || "submitted"}
                      </span>
                    </td>
                    <td>{s.submitted_by || "—"}</td>
                    <td>{s.created_at ? String(s.created_at) : "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <h4>Coaching Project Intake</h4>
      <div className="card" style={{ marginBottom: 10 }}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
          {STEP_ORDER.map((step) => (
            <button
              key={step}
              onClick={() => setActiveStep(step)}
              className={activeStep === step ? "btn-primary" : undefined}
              style={{ fontSize: 12, padding: "6px 8px" }}
            >
              {STEP_LABELS[step]} {completion[step] ? "✓" : ""}
            </button>
          ))}
        </div>

        <div style={{ fontSize: 12, marginBottom: 8 }}>
          Completion: <strong>{completedCount}/4</strong>
        </div>

        <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
          <span className={stageBadgeClass(stageState.intakeParsed)}>Intake Parsed</span>
          <span className={stageBadgeClass(stageState.sowGenerated)}>SOW Generated</span>
          <span className={stageBadgeClass(stageState.validated)}>Validated</span>
        </div>

        <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Candidate Name</label>
        <input
          value={draft.candidateName}
          onChange={(e) => setDraft((prev) => ({ ...prev, candidateName: e.target.value }))}
          placeholder="Chris Gambill"
          style={{ marginBottom: 6 }}
        />

        <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Candidate Email</label>
        <input
          value={draft.candidateEmail}
          onChange={(e) => setDraft((prev) => ({ ...prev, candidateEmail: e.target.value }))}
          placeholder="candidate@email.com"
          style={{ marginBottom: 6 }}
        />

        <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Target Role</label>
        <input
          value={draft.targetRole}
          onChange={(e) => setDraft((prev) => ({ ...prev, targetRole: e.target.value }))}
          placeholder="Senior Data Engineer"
          style={{ marginBottom: 8 }}
        />

        {activeStep === "resume" && (
          <>
            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Resume Upload (name-only scaffold)</label>
            <input
              value={draft.resumeFileName}
              onChange={(e) => setDraft((prev) => ({ ...prev, resumeFileName: e.target.value }))}
              placeholder="resume.pdf"
            />
          </>
        )}

        {activeStep === "selfAssessment" && (
          <>
            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Self-Assessment</label>
            <textarea
              value={draft.selfAssessment}
              onChange={(e) => setDraft((prev) => ({ ...prev, selfAssessment: e.target.value }))}
              placeholder="Current strengths, gaps, and confidence areas..."
              style={{ width: "100%", minHeight: 90, marginTop: 4 }}
            />
          </>
        )}

        {activeStep === "jobLinks" && (
          <>
            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Job Posting URLs (one per line)</label>
            <textarea
              value={draft.jobLinksText}
              onChange={(e) => setDraft((prev) => ({ ...prev, jobLinksText: e.target.value }))}
              placeholder="https://company.com/jobs/123"
              style={{ width: "100%", minHeight: 90, marginTop: 4 }}
            />
          </>
        )}

        {activeStep === "preferences" && (
          <>
            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Preferred Stack</label>
            <input
              value={draft.preferredStack}
              onChange={(e) => setDraft((prev) => ({ ...prev, preferredStack: e.target.value }))}
              placeholder="Databricks + dbt + Power BI"
              style={{ marginBottom: 6 }}
            />
            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Timeline (weeks)</label>
            <input
              value={draft.timelineWeeks}
              onChange={(e) => setDraft((prev) => ({ ...prev, timelineWeeks: e.target.value }))}
              placeholder="8"
            />
          </>
        )}

        <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
          <button onClick={() => moveStep("back")}>Back</button>
          <button onClick={() => moveStep("next")}>Next</button>
          <button onClick={submitIntake}>Submit Intake</button>
          <button className="btn-success" onClick={buildScaffoldAndAdvance}>Build Project Scaffold</button>
          <button onClick={markValidated}>Mark Validated</button>
        </div>
      </div>

      <h4>Project Output Viewer</h4>
      <div className="card" style={{ marginBottom: 10 }}>
        {scaffold ? (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <strong>{scaffold.title}</strong>
              <div style={{ display: "flex", gap: 6 }}>
                <button onClick={() => exportStudentPackage("markdown")}>Export Markdown</button>
                <button onClick={() => exportStudentPackage("json")}>Export JSON</button>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginBottom: 8 }}>
              <button onClick={() => setViewerTab("overview")}>Overview</button>
              <button onClick={() => setViewerTab("milestones")}>Milestones</button>
              <button onClick={() => setViewerTab("architecture")}>Architecture</button>
              <button onClick={() => setViewerTab("roi")}>ROI</button>
              <button onClick={() => setViewerTab("resources")}>Resources + Mentoring</button>
            </div>

            {viewerTab === "overview" && (
              <div style={{ fontSize: 13 }}>
                <div style={{ marginBottom: 6 }}><strong>Candidate Snapshot:</strong> {scaffold.candidateSnapshot}</div>
                <div><strong>Business Outcome:</strong> {scaffold.businessOutcome}</div>
              </div>
            )}

            {viewerTab === "milestones" && (
              <div style={{ display: "grid", gap: 6 }}>
                {scaffold.milestones.map((m) => (
                  <div key={m.title} className="card" style={{ padding: 8 }}>
                    <strong>{m.title}</strong>
                    <div style={{ fontSize: 12, marginTop: 4 }}>{m.outcome}</div>
                    <ul style={{ margin: "6px 0 0 18px", padding: 0, fontSize: 12 }}>
                      {m.deliverables.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                ))}
              </div>
            )}

            {viewerTab === "architecture" && (
              <div style={{ display: "grid", gap: 6, fontSize: 12 }}>
                <div><strong>Bronze:</strong> {scaffold.architecture.bronze}</div>
                <div><strong>Silver:</strong> {scaffold.architecture.silver}</div>
                <div><strong>Gold:</strong> {scaffold.architecture.gold}</div>
              </div>
            )}

            {viewerTab === "roi" && (
              <ul style={{ margin: "0 0 0 18px", padding: 0, fontSize: 12 }}>
                {scaffold.roiRequirements.map((item) => <li key={item}>{item}</li>)}
              </ul>
            )}

            {viewerTab === "resources" && (
              <div style={{ display: "grid", gap: 8 }}>
                <div className="card" style={{ padding: 8 }}>
                  <strong>Recommended Resources</strong>
                  <ul style={{ margin: "6px 0 0 18px", padding: 0, fontSize: 12 }}>
                    {scaffold.recommendedResources.map((resource) => (
                      <li key={resource.url}>
                        <a href={resource.url} target="_blank" rel="noreferrer">{resource.title}</a> ({resource.type}) — {resource.reason}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="card" style={{ padding: 8, border: "1px solid var(--color-border-strong)" }}>
                  <strong>{scaffold.mentoringCta.offer}</strong>
                  <div style={{ fontSize: 12, marginTop: 4 }}><strong>Pricing:</strong> {scaffold.mentoringCta.pricing}</div>
                  <div style={{ fontSize: 12 }}><strong>Timeline:</strong> {scaffold.mentoringCta.timeline}</div>
                  <button className="btn-primary" style={{ marginTop: 8 }}>{scaffold.mentoringCta.ctaText}</button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
            Submit intake and build a scaffold to preview SOW output, resources, and student package export.
          </div>
        )}
      </div>
    </>
  );
}
