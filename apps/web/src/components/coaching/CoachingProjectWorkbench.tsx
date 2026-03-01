"use client";

import { useMemo, useState } from "react";

type IntakeStepId = "resume" | "selfAssessment" | "jobLinks" | "preferences";

type IntakeDraft = {
  candidateName: string;
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
};

const STEP_ORDER: IntakeStepId[] = ["resume", "selfAssessment", "jobLinks", "preferences"];

const STEP_LABELS: Record<IntakeStepId, string> = {
  resume: "1) Resume",
  selfAssessment: "2) Self-Assessment",
  jobLinks: "3) Job Links",
  preferences: "4) Stack + Timeline",
};

const DEFAULT_DRAFT: IntakeDraft = {
  candidateName: "",
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
  };
}

export default function CoachingProjectWorkbench() {
  const [activeStep, setActiveStep] = useState<IntakeStepId>("resume");
  const [draft, setDraft] = useState<IntakeDraft>(DEFAULT_DRAFT);
  const [scaffold, setScaffold] = useState<ProjectScaffold | null>(null);
  const [viewerTab, setViewerTab] = useState<"overview" | "milestones" | "architecture" | "roi">("overview");

  const completion = useMemo(() => ({
    resume: Boolean(draft.resumeFileName.trim()),
    selfAssessment: draft.selfAssessment.trim().length > 40,
    jobLinks: draft.jobLinksText.trim().length > 0,
    preferences: Boolean(draft.preferredStack.trim()) && Boolean(draft.timelineWeeks.trim()),
  }), [draft]);

  const completedCount = Object.values(completion).filter(Boolean).length;

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

  return (
    <>
      <h4>Coaching Project Intake (Scaffold)</h4>
      <div className="card" style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 8 }}>
          Multi-step UX scaffold for coaching project creation (Master Plan items 1-2).
        </div>

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

        <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Candidate Name</label>
        <input
          value={draft.candidateName}
          onChange={(e) => setDraft((prev) => ({ ...prev, candidateName: e.target.value }))}
          placeholder="Chris Gambill"
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

        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button onClick={() => moveStep("back")}>Back</button>
          <button onClick={() => moveStep("next")}>Next</button>
          <button className="btn-success" onClick={() => setScaffold(buildProjectScaffold(draft))}>
            Build Project Scaffold
          </button>
        </div>
      </div>

      <h4>Project Output Viewer (Scaffold)</h4>
      <div className="card" style={{ marginBottom: 10 }}>
        {scaffold ? (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <strong>{scaffold.title}</strong>
              <span className="badge info">Draft</span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 8 }}>
              <button onClick={() => setViewerTab("overview")}>Overview</button>
              <button onClick={() => setViewerTab("milestones")}>Milestones</button>
              <button onClick={() => setViewerTab("architecture")}>Architecture</button>
              <button onClick={() => setViewerTab("roi")}>ROI</button>
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
          </>
        ) : (
          <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
            Build a project scaffold from intake to preview SOW rendering modules.
          </div>
        )}
      </div>
    </>
  );
}
