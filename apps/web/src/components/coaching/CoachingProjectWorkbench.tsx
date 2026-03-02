"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type CoachingIntakeSubmission, type CoachingIntakeSubmissionDetail } from "../../lib/api";

type TimelineEvent = { id: string; at?: string; label: string; detail?: string; tone?: "info" | "success" | "warning" | "error" };

type IntakeStepId = "resume" | "selfAssessment" | "jobLinks" | "preferences";
type StageId = "intakeParsed" | "sowGenerated" | "validated";
type CoachingAuthState = "signedOut" | "authenticated";
type SubscriptionStatus = "unknown" | "inactive" | "active";
type PlanTier = "starter" | "pro" | "elite";
type MemberLaunchState = "memberHome" | "launchRequested" | "handoffPending" | "landed";
type ExportFormat = "markdown" | "json";

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

type ResourceLink = { title: string; type: "course" | "article" | "video" | "doc"; url: string; reason: string };

type ProjectScaffold = {
  title: string;
  executiveSummary: string;
  candidateSnapshot: string;
  businessOutcome: string;
  dataSources: { name: string; type: "system" | "document" | "job-posting"; link?: string; note: string }[];
  architecture: {
    bronze: string;
    silver: string;
    gold: string;
  };
  milestones: Milestone[];
  storyNarrative: string[];
  roiRequirements: string[];
  resourceLinksByStep: { stepTitle: string; resources: ResourceLink[] }[];
  recommendedResources: ResourceLink[];
  mentoringCta: {
    offer: string;
    pricing: string;
    timeline: string;
    rationale?: string;
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

const PLAN_DETAILS: Record<PlanTier, { label: string; monthly: string; upgradeCta: string; includes: string[] }> = {
  starter: {
    label: "Starter",
    monthly: "$49/mo",
    upgradeCta: "Upgrade to Pro",
    includes: ["Intake + scaffold", "Resource package export"],
  },
  pro: {
    label: "Pro",
    monthly: "$149/mo",
    upgradeCta: "Upgrade to Elite Mentoring",
    includes: ["Everything in Starter", "Coach review queue", "Priority feedback"],
  },
  elite: {
    label: "Elite Mentoring",
    monthly: "$399/mo",
    upgradeCta: "Top tier active",
    includes: ["Everything in Pro", "1:1 mentoring sessions", "Interview narrative support"],
  },
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
    executiveSummary: `${candidateName} will deliver a business-first, medallion-aligned project targeted to ${targetRole}, with measurable KPI impact and a hiring-manager-ready narrative.`,
    candidateSnapshot: `${candidateName} targeting ${targetRole}. Intake includes ${parsedJobLinks.length || 0} job posting references and stack preference of ${draft.preferredStack}.`,
    businessOutcome: "Design and implement a medallion-aligned analytics platform initiative that demonstrates measurable delivery impact to hiring managers.",
    dataSources: [
      { name: "Resume intake", type: "document", note: "Used to map existing strengths and experience claims." },
      ...parsedJobLinks.map((url, idx) => ({ name: `Target Job Posting ${idx + 1}`, type: "job-posting" as const, link: url, note: "Used to align skills and project language with role expectations." })),
      { name: "Source operational system", type: "system", note: "Primary system of record used for ingestion and medallion modeling." },
    ],
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
    storyNarrative: [
      "Set the business context: what pain exists today and why it matters now.",
      "Show the technical intervention: architecture choices and delivery trade-offs.",
      "Close with impact: KPI lift, operational readiness, and next-step roadmap.",
    ],
    roiRequirements: [
      "Define baseline KPI and target KPI with explicit formula.",
      "Map at least one cost metric and one speed metric to pipeline outcomes.",
      "Include instrumentation plan for 30/60/90 day tracking.",
    ],
    resourceLinksByStep: [
      {
        stepTitle: "Milestone 1: Intake-to-Model Plan",
        resources: [
          { title: "Architecture Diagramming Guide", type: "doc", url: "https://c4model.com/", reason: "Improves system context clarity." },
          { title: "STAR Story Framework", type: "doc", url: "https://www.themuse.com/advice/star-interview-method", reason: "Supports interview-ready narrative framing." },
        ],
      },
      {
        stepTitle: "Milestone 2: Medallion Build Sprint",
        resources: [
          { title: "Databricks Medallion Architecture Reference", type: "article", url: "https://docs.databricks.com/en/lakehouse/medallion.html", reason: "Aligns implementation to common lakehouse standards." },
          { title: "dbt Fundamentals", type: "course", url: "https://courses.getdbt.com/courses/fundamentals", reason: "Strengthens testing and transformation practices." },
        ],
      },
      {
        stepTitle: "Milestone 3: Business Readout",
        resources: [
          { title: "Storytelling With Data", type: "video", url: "https://www.youtube.com/@storytellingwithdata", reason: "Improves executive communication quality." },
        ],
      },
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
      rationale: "Recommended when delivery confidence and interview storytelling both need structured support.",
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

function normalizeJobLinks(value?: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

export default function CoachingProjectWorkbench() {
  const [authState, setAuthState] = useState<CoachingAuthState>("signedOut");
  const [subscriptionStatus, setSubscriptionStatus] = useState<SubscriptionStatus>("unknown");
  const [planTier, setPlanTier] = useState<PlanTier>("starter");
  const [memberLaunchState, setMemberLaunchState] = useState<MemberLaunchState>("memberHome");
  const [acceptedLaunchTerms, setAcceptedLaunchTerms] = useState(false);

  const [activeStep, setActiveStep] = useState<IntakeStepId>("resume");
  const [draft, setDraft] = useState<IntakeDraft>(DEFAULT_DRAFT);
  const [scaffold, setScaffold] = useState<ProjectScaffold | null>(null);
  const [viewerTab, setViewerTab] = useState<"summary" | "dataSources" | "architecture" | "milestones" | "story" | "roi" | "resources">("summary");
  const [stageState, setStageState] = useState<Record<StageId, boolean>>({
    intakeParsed: false,
    sowGenerated: false,
    validated: false,
  });

  const [submissions, setSubmissions] = useState<CoachingIntakeSubmission[]>([]);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<string | null>(null);
  const [selectedSubmission, setSelectedSubmission] = useState<CoachingIntakeSubmissionDetail | null>(null);
  const [submissionDetailLoading, setSubmissionDetailLoading] = useState(false);
  const [submissionDetailError, setSubmissionDetailError] = useState<string | null>(null);
  const [selectedSubmissionRuns, setSelectedSubmissionRuns] = useState<Record<string, any>[]>([]);
  const [selectedSubmissionStatus, setSelectedSubmissionStatus] = useState<string>("submitted");
  const [coachNotes, setCoachNotes] = useState<string>("");
  const [currentSubmissionId, setCurrentSubmissionId] = useState<string | null>(null);
  const [generationState, setGenerationState] = useState<{ running: boolean; message?: string; sourceMode?: "llm" | "fallback"; qualityFlags?: Record<string, any>; generationMeta?: Record<string, any> }>({ running: false });
  const [exportStatus, setExportStatus] = useState<{ format: ExportFormat | null; state: "idle" | "exporting" | "success" | "error"; message?: string }>({
    format: null,
    state: "idle",
  });

  const completion = useMemo(() => ({
    resume: Boolean(draft.resumeFileName.trim()),
    selfAssessment: draft.selfAssessment.trim().length > 40,
    jobLinks: draft.jobLinksText.trim().length > 0,
    preferences: Boolean(draft.preferredStack.trim()) && Boolean(draft.timelineWeeks.trim()),
  }), [draft]);

  const completedCount = Object.values(completion).filter(Boolean).length;
  const hasActiveSubscription = authState === "authenticated" && subscriptionStatus === "active";
  const canAccessWorkbench = hasActiveSubscription;
  const canAccessReviewQueue = hasActiveSubscription && planTier !== "starter";
  const canAccessMentoringRecommendation = hasActiveSubscription;
  const canBookMentoring = hasActiveSubscription && planTier === "elite";
  const currentPlan = PLAN_DETAILS[planTier];

  const qualityBadges = useMemo(() => {
    if (!scaffold) return [] as { label: string; pass: boolean }[];
    return [
      { label: "Has data source links", pass: scaffold.dataSources.some((source) => Boolean(source.link)) },
      { label: "Has ROI requirements", pass: scaffold.roiRequirements.length > 0 },
      {
        label: "Resources mapped per milestone",
        pass: scaffold.milestones.every((milestone) => scaffold.resourceLinksByStep.some((step) => step.stepTitle === milestone.title && step.resources.length > 0)),
      },
      { label: "Executive summary present", pass: scaffold.executiveSummary.trim().length > 0 },
      { label: "Story narrative included", pass: scaffold.storyNarrative.length > 0 },
    ];
  }, [scaffold]);

  const submissionTimeline = useMemo(() => {
    const events: TimelineEvent[] = [];
    if (selectedSubmission) {
      events.push({ id: `intake-${selectedSubmission.submission_id}`, at: selectedSubmission.created_at, label: "Intake submitted", detail: selectedSubmission.applicant_name || "Candidate", tone: "info" });
    }
    selectedSubmissionRuns.forEach((run: any) => {
      const status = String(run.run_status || "unknown");
      events.push({
        id: String(run.run_id || run.id || Math.random()),
        at: String(run.created_at || run.run_at || ""),
        label: `Generation run (${status})`,
        detail: String((run.validation_json || {}).auto_revised ? "Auto-revised once" : "No auto-revision"),
        tone: status === "completed" ? "success" : status.includes("review") ? "warning" : "info",
      });
    });
    return events;
  }, [selectedSubmission, selectedSubmissionRuns]);

  async function loadSubmissions() {
    if (!canAccessWorkbench) return;
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
    if (!canAccessWorkbench) return;
    loadSubmissions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canAccessWorkbench]);

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

  function mapSowToScaffold(sow: Record<string, any>): ProjectScaffold {
    const businessOutcome = sow.business_outcome || {};
    const projectStory = sow.project_story || {};
    const medallion = (sow.solution_architecture || {}).medallion_plan || {};
    const milestones = Array.isArray(sow.milestones) ? sow.milestones : [];
    const resourcePlan = sow.resource_plan || {};
    const mentoring = sow.mentoring_cta || {};

    return {
      title: String(sow.project_title || "Coaching Project Blueprint"),
      executiveSummary: String(projectStory.executive_summary || ""),
      candidateSnapshot: `${draft.candidateName || "Candidate"} targeting ${draft.targetRole || "Data Engineer"}.`,
      businessOutcome: String(businessOutcome.problem_statement || ""),
      dataSources: (businessOutcome.data_sources || []).map((source: any) => ({
        name: String(source.name || "Data source"),
        type: "document" as const,
        link: String(source.url || ""),
        note: String(source.ingestion_doc_url || "Ingestion doc not provided"),
      })),
      architecture: {
        bronze: String(medallion.bronze || ""),
        silver: String(medallion.silver || ""),
        gold: String(medallion.gold || ""),
      },
      milestones: milestones.map((m: any) => ({
        title: String(m.name || "Milestone"),
        outcome: `Duration: ${String(m.duration_weeks || "?")} weeks`,
        deliverables: Array.isArray(m.deliverables) ? m.deliverables.map((d: any) => String(d)) : [],
      })),
      storyNarrative: [String(projectStory.challenge || ""), String(projectStory.approach || ""), String(projectStory.impact_story || "")].filter(Boolean),
      roiRequirements: [
        ...(Array.isArray((sow.roi_dashboard_requirements || {}).required_dimensions) ? (sow.roi_dashboard_requirements || {}).required_dimensions : []),
        ...(Array.isArray((sow.roi_dashboard_requirements || {}).required_measures) ? (sow.roi_dashboard_requirements || {}).required_measures : []),
      ].map((x: any) => String(x)),
      resourceLinksByStep: milestones.map((m: any) => ({
        stepTitle: String(m.name || "Milestone"),
        resources: (Array.isArray(m.resources) ? m.resources : []).map((r: any) => ({
          title: String(r.title || "Resource"),
          type: "doc" as const,
          url: String(r.url || ""),
          reason: "Mapped from generation output",
        })),
      })),
      recommendedResources: [...(resourcePlan.required || []), ...(resourcePlan.recommended || [])].map((r: any) => ({
        title: String(r.title || "Resource"),
        type: "doc" as const,
        url: String(r.url || ""),
        reason: String(r.reason || "Recommended by generation pipeline."),
      })),
      mentoringCta: {
        offer: String(mentoring.recommended_tier || "Mentoring recommendation available"),
        pricing: String(mentoring.pricing || "See plan"),
        timeline: String(mentoring.timeline || "Flexible"),
        rationale: String(mentoring.reason || "Recommendation based on milestone tags and current skill gap profile."),
        ctaText: String(mentoring.cta_text || "Book mentoring kickoff"),
      },
    };
  }

  async function submitIntake() {
    if (!canAccessWorkbench) return;

    const jobLinks = draft.jobLinksText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    const intakeResult = await api.coachingIntake({
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

    setCurrentSubmissionId(intakeResult.submission_id || null);
    setStageState((prev) => ({ ...prev, intakeParsed: true }));
    await loadSubmissions();
  }

  async function generateSow(useImprovements = false) {
    if (!canAccessWorkbench) return;
    if (!currentSubmissionId) {
      setScaffold(buildProjectScaffold(draft));
      setStageState((prev) => ({ ...prev, sowGenerated: true }));
      setGenerationState({ running: false, message: "Built local scaffold (submit intake to enable server generation).", sourceMode: "fallback" });
      return;
    }

    try {
      setGenerationState({ running: true, message: useImprovements ? "Regenerating with improvements..." : "Generating SOW..." });
      const out = await api.coachingGenerateSow({ workspace_id: draft.workspaceId, submission_id: currentSubmissionId, parsed_jobs: [] });
      if (!out.ok || !out.sow) {
        setGenerationState({ running: false, message: out.message || "Generation failed." });
        return;
      }
      setScaffold(mapSowToScaffold(out.sow));
      setStageState((prev) => ({ ...prev, sowGenerated: true, validated: Boolean(out.valid) }));
      const fallbackUsed = Boolean(out.quality_flags?.fallback_used);
      setGenerationState({
        running: false,
        message: useImprovements ? "Regeneration complete." : "Generation complete.",
        sourceMode: fallbackUsed ? "fallback" : "llm",
        qualityFlags: out.quality_flags || {},
        generationMeta: out.generation_meta || {},
      });
    } catch (e: any) {
      const msg = e?.message || "Generation failed.";
      setGenerationState({ running: false, message: msg.includes("403") ? "Upgrade required: active subscription needed for generation." : msg });
    }
  }

  function markValidated() {
    setStageState((prev) => ({ ...prev, validated: true }));
  }

  async function openSubmission(submissionId: string) {
    setSelectedSubmissionId(submissionId);
    setSubmissionDetailError(null);
    setSubmissionDetailLoading(true);

    try {
      const out = await api.coachingIntakeSubmissionDetail(submissionId);
      const runsOut = await api.coachingReviewSubmissionRuns(submissionId, 20);
      if (!out.ok || !out.submission) {
        setSelectedSubmission(null);
        setSubmissionDetailError(out.message || "Unable to load submission details.");
        return;
      }
      setSelectedSubmission(out.submission);
      setCurrentSubmissionId(out.submission.submission_id);
      setSelectedSubmissionStatus(String(out.submission.status || "submitted"));
      setCoachNotes(String((out.latest_generation_run || {}).coach_notes || ""));
      setSelectedSubmissionRuns(runsOut.runs || []);
      if (out.latest_generation_run) {
        setStageState({
          intakeParsed: true,
          sowGenerated: true,
          validated: String(out.latest_generation_run.run_status || "").toLowerCase() === "completed",
        });
      }
    } catch (e: any) {
      setSelectedSubmission(null);
      setSubmissionDetailError(e?.message || "Unable to load submission details.");
    } finally {
      setSubmissionDetailLoading(false);
    }
  }

  function loadSubmissionIntoDraft() {
    if (!selectedSubmission) return;
    const parsedJobLinks = normalizeJobLinks(selectedSubmission.job_links_json);
    const preferences = selectedSubmission.preferences_json || {};

    setDraft((prev) => ({
      ...prev,
      candidateName: selectedSubmission.applicant_name || prev.candidateName,
      candidateEmail: selectedSubmission.applicant_email || prev.candidateEmail,
      targetRole: String(preferences.target_role || prev.targetRole),
      resumeFileName: selectedSubmission.resume_text || prev.resumeFileName,
      selfAssessment: selectedSubmission.self_assessment_text || prev.selfAssessment,
      jobLinksText: parsedJobLinks.length ? parsedJobLinks.join("\n") : prev.jobLinksText,
      preferredStack: String(preferences.preferred_stack || prev.preferredStack),
      timelineWeeks: String(preferences.timeline_weeks || prev.timelineWeeks),
    }));

    setStageState((prev) => ({ ...prev, intakeParsed: true }));
    setActiveStep("resume");
  }

  function exportStudentPackage(format: ExportFormat) {
    if (!scaffold) return;

    const timestamp = new Date().toISOString().slice(0, 10);
    const safeName = (draft.candidateName || "candidate").toLowerCase().replace(/\s+/g, "-");

    try {
      setExportStatus({ format, state: "exporting", message: `Preparing ${format.toUpperCase()} package...` });

      if (format === "json") {
        downloadText(JSON.stringify(scaffold, null, 2), `${safeName}-coaching-package-${timestamp}.json`, "application/json");
        setExportStatus({ format, state: "success", message: `JSON package exported (${timestamp}).` });
        return;
      }

      const markdown = [
        `# ${scaffold.title}`,
        "",
        "## Executive Summary",
        scaffold.executiveSummary,
        "",
        "## Candidate Snapshot",
        scaffold.candidateSnapshot,
        "",
        "## Business Outcome",
        scaffold.businessOutcome,
        "",
        "## Data Sources",
        ...scaffold.dataSources.flatMap((source) => [
          `- ${source.name} (${source.type})${source.link ? ` — [Link](${source.link})` : ""}`,
          `  - Note: ${source.note}`,
        ]),
        "",
        "## Architecture",
        `- Bronze: ${scaffold.architecture.bronze}`,
        `- Silver: ${scaffold.architecture.silver}`,
        `- Gold: ${scaffold.architecture.gold}`,
        "",
        "## Milestones",
        ...scaffold.milestones.flatMap((m) => [
          `### ${m.title}`,
          `- Outcome: ${m.outcome}`,
          ...m.deliverables.map((d) => `- Deliverable: ${d}`),
        ]),
        "",
        "## Story Narrative",
        ...scaffold.storyNarrative.map((line) => `- ${line}`),
        "",
        "## ROI Dashboard Requirements",
        ...scaffold.roiRequirements.map((item) => `- ${item}`),
        "",
        "## Resource Links by Step",
        ...scaffold.resourceLinksByStep.flatMap((step) => [
          `### ${step.stepTitle}`,
          ...step.resources.map((resource) => `- [${resource.title}](${resource.url}) (${resource.type}) — ${resource.reason}`),
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
      setExportStatus({ format, state: "success", message: `Markdown package exported (${timestamp}).` });
    } catch (e: any) {
      setExportStatus({ format, state: "error", message: e?.message || "Export failed. Try again." });
    }
  }

  function gateMessage(): string {
    if (authState !== "authenticated") return "Please sign in to your coaching app account to continue.";
    if (subscriptionStatus !== "active") return "An active subscription is required to access intake and project generation.";
    return "";
  }

  function launchStateLabel(): string {
    if (memberLaunchState === "memberHome") return "Member page ready";
    if (memberLaunchState === "launchRequested") return "Launch requested";
    if (memberLaunchState === "handoffPending") return "Token/session handoff pending";
    return "Arrived at coaching app";
  }

  function launchStep() {
    setMemberLaunchState((prev) => {
      if (prev === "memberHome") return "launchRequested";
      if (prev === "launchRequested") return "handoffPending";
      if (prev === "handoffPending") return "landed";
      return "landed";
    });
  }

  function resetLaunchFlow() {
    setMemberLaunchState("memberHome");
  }

  function upgradeTier() {
    if (planTier === "starter") setPlanTier("pro");
    if (planTier === "pro") setPlanTier("elite");
  }

  return (
    <div className="coaching-shell">
      <div className="coaching-hero">
        <div>
          <h2>Gambill Coaching Project Builder</h2>
          <p>Generate portfolio-ready, business-outcome-driven data engineering projects from resume + job targets.</p>
        </div>
        <span className="badge info">Coaching App</span>
      </div>

      <h4>Squarespace Member Launch Flow</h4>
      <div className="card coaching-card" style={{ marginBottom: 10 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
          <span className={authState === "authenticated" ? "badge success" : "badge warning"}>Auth: {authState}</span>
          <span className={subscriptionStatus === "active" ? "badge success" : subscriptionStatus === "inactive" ? "badge error" : "badge warning"}>
            Subscription: {subscriptionStatus}
          </span>
          <span className={memberLaunchState === "landed" ? "badge success" : "badge info"}>{launchStateLabel()}</span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginBottom: 8 }}>
          <button onClick={() => setAuthState("signedOut")}>Set Signed Out</button>
          <button onClick={() => setAuthState("authenticated")}>Set Authenticated</button>
          <button onClick={() => setSubscriptionStatus("inactive")}>Set Inactive Sub</button>
          <button onClick={() => setSubscriptionStatus("active")}>Set Active Sub</button>
          <button onClick={() => setSubscriptionStatus("unknown")}>Set Unknown Sub</button>
          <button onClick={resetLaunchFlow}>Reset Launch</button>
        </div>

        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginBottom: 8 }}>
          <input type="checkbox" checked={acceptedLaunchTerms} onChange={(e) => setAcceptedLaunchTerms(e.target.checked)} />
          I accepted the member launch terms (scaffolded Squarespace handoff check)
        </label>

        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <button
            className="btn-primary"
            onClick={launchStep}
            disabled={authState !== "authenticated" || !acceptedLaunchTerms || memberLaunchState === "landed"}
          >
            {memberLaunchState === "memberHome" ? "Launch Project Builder" : memberLaunchState === "launchRequested" ? "Continue handoff" : memberLaunchState === "handoffPending" ? "Enter coaching app" : "In coaching app"}
          </button>
          {memberLaunchState !== "memberHome" && <button onClick={resetLaunchFlow}>Start over</button>}
        </div>
        <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 8 }}>
          {authState !== "authenticated"
            ? "Sign in first so launch can hand off to your app session."
            : !acceptedLaunchTerms
              ? "Accept launch terms to continue from Squarespace member page."
              : memberLaunchState === "handoffPending"
                ? "Scaffolded token exchange in progress (next: backend verification)."
                : memberLaunchState === "landed"
                  ? "Landing complete. Coaching workbench is ready."
                  : "This simulates the Squarespace member-to-app launch journey."}
        </div>
      </div>

      <h4>Plan + Tier</h4>
      <div className="card" style={{ marginBottom: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          <strong>{currentPlan.label}</strong>
          <span className={planTier === "starter" ? "badge warning" : planTier === "pro" ? "badge info" : "badge success"}>{currentPlan.monthly}</span>
        </div>
        <ul style={{ margin: "0 0 8px 18px", padding: 0, fontSize: 12 }}>
          {currentPlan.includes.map((item) => <li key={item}>{item}</li>)}
        </ul>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
          <span className={canAccessReviewQueue ? "badge success" : "badge warning"}>Coach review queue: {canAccessReviewQueue ? "unlocked" : "Pro+ required"}</span>
          <span className={canBookMentoring ? "badge success" : "badge info"}>Live mentoring booking: {canBookMentoring ? "included" : "Elite required"}</span>
        </div>
        {planTier !== "elite" && (
          <div className="card" style={{ padding: 8, border: "1px solid var(--color-border-strong)" }}>
            <div style={{ fontSize: 12, marginBottom: 6 }}>
              {planTier === "starter"
                ? "Pro unlocks coach review visibility and faster feedback cycles."
                : "Elite adds 1:1 mentoring sessions and interview narrative support."}
            </div>
            <button className="btn-primary" onClick={upgradeTier}>{currentPlan.upgradeCta}</button>
          </div>
        )}
      </div>

      {!canAccessWorkbench && (
        <>
          <h4>Coaching Access Gate</h4>
          <div className="card" style={{ marginBottom: 10 }}>
            <span className="badge warning">Subscription-required state</span>
            <div style={{ marginTop: 8, fontSize: 12, color: "var(--color-text-muted)" }}>{gateMessage()}</div>
            {subscriptionStatus !== "active" && (
              <button style={{ marginTop: 8 }} onClick={() => setSubscriptionStatus("active")}>Simulate successful upgrade/renewal</button>
            )}
          </div>
        </>
      )}

      {canAccessWorkbench && (
        <>
          <h4>Coach Review Queue</h4>
          <div className="card" style={{ marginBottom: 10 }}>
            {!canAccessReviewQueue ? (
              <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                Coach review queue details are available on <strong>Pro</strong> and <strong>Elite</strong> plans.
              </div>
            ) : (
              <>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
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

                <div style={{ overflowX: "auto", marginBottom: 8 }}>
                  <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                    <thead>
                      <tr>
                        <th align="left">Applicant</th>
                        <th align="left">Email</th>
                        <th align="left">Status</th>
                        <th align="left">Submitted By</th>
                        <th align="left">Created</th>
                        <th align="left">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {submissions.length === 0 ? (
                        <tr>
                          <td colSpan={6} style={{ color: "var(--color-text-muted)", padding: "8px 0" }}>
                            No submissions yet for this workspace.
                          </td>
                        </tr>
                      ) : (
                        submissions.map((s) => (
                          <tr key={s.submission_id} style={selectedSubmissionId === s.submission_id ? { background: "rgba(120,120,255,0.08)" } : undefined}>
                            <td>{s.applicant_name || "—"}</td>
                            <td>{s.applicant_email || "—"}</td>
                            <td>
                              <span className={`badge ${String(s.status || "submitted").toLowerCase().includes("review") ? "warning" : "info"}`}>
                                {s.status || "submitted"}
                              </span>
                            </td>
                            <td>{s.submitted_by || "—"}</td>
                            <td>{s.created_at ? String(s.created_at) : "—"}</td>
                            <td>
                              <button onClick={() => openSubmission(s.submission_id)}>Open submission</button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="card" style={{ padding: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <strong>Submission Detail</strong>
                    {selectedSubmission && <button onClick={loadSubmissionIntoDraft}>Load into intake form</button>}
                  </div>
                  {submissionDetailLoading && <span className="badge info">Loading detail…</span>}
                  {submissionDetailError && <span className="badge error">{submissionDetailError}</span>}
                  {!submissionDetailLoading && !submissionDetailError && !selectedSubmission && (
                    <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                      Open a row above to review a specific intake submission.
                    </div>
                  )}
                  {!submissionDetailLoading && selectedSubmission && (
                    <div style={{ fontSize: 12, display: "grid", gap: 6 }}>
                      <div><strong>Applicant:</strong> {selectedSubmission.applicant_name || "—"} ({selectedSubmission.applicant_email || "no email"})</div>
                      <div><strong>Status:</strong> {selectedSubmission.status || "submitted"}</div>
                      <div><strong>Resume:</strong> {selectedSubmission.resume_text || "—"}</div>
                      <div><strong>Self-Assessment:</strong> {selectedSubmission.self_assessment_text || "—"}</div>
                      <div>
                        <strong>Job Links:</strong>
                        <ul style={{ margin: "4px 0 0 18px", padding: 0 }}>
                          {normalizeJobLinks(selectedSubmission.job_links_json).map((link) => (
                            <li key={link}><a href={link} target="_blank" rel="noreferrer">{link}</a></li>
                          ))}
                          {normalizeJobLinks(selectedSubmission.job_links_json).length === 0 && <li>—</li>}
                        </ul>
                      </div>
                      <div>
                        <strong>Preferences:</strong>{" "}
                        {selectedSubmission.preferences_json
                          ? `${String(selectedSubmission.preferences_json.target_role || "n/a")} | ${String(selectedSubmission.preferences_json.preferred_stack || "n/a")} | ${String(selectedSubmission.preferences_json.timeline_weeks || "n/a")} weeks`
                          : "—"}
                      </div>

                      <div className="card" style={{ padding: 8 }}>
                        <strong>Coach Status + Notes</strong>
                        <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
                          <select value={selectedSubmissionStatus} onChange={(e) => setSelectedSubmissionStatus(e.target.value)}>
                            <option value="submitted">submitted</option>
                            <option value="in_review">in_review</option>
                            <option value="needs_revision">needs_revision</option>
                            <option value="ready">ready</option>
                          </select>
                          <span className="badge info">Local UI workflow (save endpoint pending)</span>
                        </div>
                        <textarea
                          value={coachNotes}
                          onChange={(e) => setCoachNotes(e.target.value)}
                          placeholder="Add coaching notes, feedback highlights, and next actions..."
                          style={{ width: "100%", minHeight: 80, marginTop: 6 }}
                        />
                      </div>

                      <div className="card" style={{ padding: 8 }}>
                        <strong>Submission Timeline</strong>
                        <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                          {submissionTimeline.map((evt) => (
                            <div key={evt.id} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12 }}>
                              <span className={`badge ${evt.tone || "info"}`}>{evt.label}</span>
                              <span style={{ color: "var(--color-text-muted)" }}>{evt.at || "time n/a"}</span>
                              {evt.detail && <span>{evt.detail}</span>}
                            </div>
                          ))}
                          {submissionTimeline.length === 0 && <div style={{ color: "var(--color-text-muted)" }}>No timeline events yet.</div>}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          <h4>Coaching Project Intake</h4>
          <div className="card" style={{ marginBottom: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <div style={{ fontSize: 12 }}>
                Active tier: <strong>{currentPlan.label}</strong>
              </div>
              <span className={planTier === "starter" ? "badge warning" : planTier === "pro" ? "badge info" : "badge success"}>{currentPlan.monthly}</span>
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

            <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
              <span className={stageBadgeClass(stageState.intakeParsed)}>Intake Parsed</span>
              <span className={stageBadgeClass(stageState.sowGenerated)}>SOW Generated</span>
              <span className={stageBadgeClass(stageState.validated)}>Validated</span>
              {generationState.sourceMode && (
                <span className={`badge ${generationState.sourceMode === "llm" ? "success" : "warning"}`}>
                  Source: {generationState.sourceMode === "llm" ? "LLM generated" : "Scaffold fallback"}
                </span>
              )}
            </div>
            {generationState.message && <div style={{ fontSize: 12, marginBottom: 8, color: "var(--color-text-muted)" }}>{generationState.message}</div>}

            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Candidate Name</label>
            <input value={draft.candidateName} onChange={(e) => setDraft((prev) => ({ ...prev, candidateName: e.target.value }))} placeholder="Chris Gambill" style={{ marginBottom: 6 }} />

            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Candidate Email</label>
            <input value={draft.candidateEmail} onChange={(e) => setDraft((prev) => ({ ...prev, candidateEmail: e.target.value }))} placeholder="candidate@email.com" style={{ marginBottom: 6 }} />

            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Target Role</label>
            <input value={draft.targetRole} onChange={(e) => setDraft((prev) => ({ ...prev, targetRole: e.target.value }))} placeholder="Senior Data Engineer" style={{ marginBottom: 8 }} />

            {activeStep === "resume" && (
              <>
                <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Resume Upload (name-only scaffold)</label>
                <input value={draft.resumeFileName} onChange={(e) => setDraft((prev) => ({ ...prev, resumeFileName: e.target.value }))} placeholder="resume.pdf" />
              </>
            )}

            {activeStep === "selfAssessment" && (
              <>
                <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Self-Assessment</label>
                <textarea value={draft.selfAssessment} onChange={(e) => setDraft((prev) => ({ ...prev, selfAssessment: e.target.value }))} placeholder="Current strengths, gaps, and confidence areas..." style={{ width: "100%", minHeight: 90, marginTop: 4 }} />
              </>
            )}

            {activeStep === "jobLinks" && (
              <>
                <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Job Posting URLs (one per line)</label>
                <textarea value={draft.jobLinksText} onChange={(e) => setDraft((prev) => ({ ...prev, jobLinksText: e.target.value }))} placeholder="https://company.com/jobs/123" style={{ width: "100%", minHeight: 90, marginTop: 4 }} />
              </>
            )}

            {activeStep === "preferences" && (
              <>
                <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Preferred Stack</label>
                <input value={draft.preferredStack} onChange={(e) => setDraft((prev) => ({ ...prev, preferredStack: e.target.value }))} placeholder="Databricks + dbt + Power BI" style={{ marginBottom: 6 }} />
                <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Timeline (weeks)</label>
                <input value={draft.timelineWeeks} onChange={(e) => setDraft((prev) => ({ ...prev, timelineWeeks: e.target.value }))} placeholder="8" />
              </>
            )}

            <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
              <button onClick={() => moveStep("back")}>Back</button>
              <button onClick={() => moveStep("next")}>Next</button>
              <button onClick={submitIntake}>Submit Intake</button>
              <button className="btn-success" onClick={() => generateSow(false)} disabled={generationState.running}>Generate SOW</button>
              <button onClick={() => generateSow(true)} disabled={generationState.running || !stageState.sowGenerated}>Regenerate with improvements</button>
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
                    <button onClick={() => exportStudentPackage("markdown")} disabled={exportStatus.state === "exporting"}>Export Markdown</button>
                    <button onClick={() => exportStudentPackage("json")} disabled={exportStatus.state === "exporting"}>Export JSON</button>
                  </div>
                </div>

                {exportStatus.state !== "idle" && (
                  <div style={{ marginBottom: 8 }}>
                    <span className={`badge ${exportStatus.state === "success" ? "success" : exportStatus.state === "error" ? "error" : "info"}`}>
                      {exportStatus.state === "exporting" ? "Exporting" : exportStatus.state === "success" ? "Export complete" : "Export failed"}
                    </span>
                    <span style={{ marginLeft: 6, fontSize: 12, color: "var(--color-text-muted)" }}>{exportStatus.message}</span>
                  </div>
                )}

                <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
                  <button onClick={() => setViewerTab("summary")}>Executive Summary</button>
                  <button onClick={() => setViewerTab("dataSources")}>Data Sources</button>
                  <button onClick={() => setViewerTab("architecture")}>Architecture</button>
                  <button onClick={() => setViewerTab("milestones")}>Milestones</button>
                  <button onClick={() => setViewerTab("story")}>Story Narrative</button>
                  <button onClick={() => setViewerTab("roi")}>ROI Dashboard</button>
                  <button onClick={() => setViewerTab("resources")}>Resource Links by Step</button>
                </div>

                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
                  {qualityBadges.map((badge) => (
                    <span key={badge.label} className={`badge ${badge.pass ? "success" : "warning"}`}>
                      {badge.pass ? "✓" : "!"} {badge.label}
                    </span>
                  ))}
                </div>

                {viewerTab === "summary" && (
                  <div className="card" style={{ padding: 10, background: "rgba(120,120,255,0.05)" }}>
                    <div style={{ fontSize: 14, marginBottom: 8, lineHeight: 1.5 }}>{scaffold.executiveSummary}</div>
                    <div style={{ fontSize: 13, marginBottom: 6 }}><strong>Candidate Snapshot:</strong> {scaffold.candidateSnapshot}</div>
                    <div style={{ fontSize: 13 }}><strong>Business Outcome:</strong> {scaffold.businessOutcome}</div>
                  </div>
                )}

                {viewerTab === "dataSources" && (
                  <div style={{ display: "grid", gap: 8 }}>
                    {scaffold.dataSources.map((source) => (
                      <div key={`${source.name}-${source.link || "nolink"}`} className="card" style={{ padding: 8 }}>
                        <div style={{ fontSize: 13 }}>
                          <strong>{source.name}</strong> <span style={{ color: "var(--color-text-muted)" }}>({source.type})</span>
                        </div>
                        <div style={{ fontSize: 12, marginTop: 4 }}>{source.note}</div>
                        <div style={{ fontSize: 12, marginTop: 4 }}>
                          {source.link ? <a href={source.link} target="_blank" rel="noreferrer">{source.link}</a> : <span style={{ color: "var(--color-text-muted)" }}>No external link provided</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {viewerTab === "milestones" && (
                  <div style={{ display: "grid", gap: 8 }}>
                    {scaffold.milestones.map((m) => (
                      <div key={m.title} className="card" style={{ padding: 10 }}>
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
                  <div style={{ display: "grid", gap: 8, fontSize: 12 }}>
                    <div className="card" style={{ padding: 8 }}><strong>Bronze</strong><div style={{ marginTop: 4 }}>{scaffold.architecture.bronze}</div></div>
                    <div className="card" style={{ padding: 8 }}><strong>Silver</strong><div style={{ marginTop: 4 }}>{scaffold.architecture.silver}</div></div>
                    <div className="card" style={{ padding: 8 }}><strong>Gold</strong><div style={{ marginTop: 4 }}>{scaffold.architecture.gold}</div></div>
                  </div>
                )}

                {viewerTab === "story" && (
                  <ol style={{ margin: "0 0 0 18px", padding: 0, fontSize: 12, display: "grid", gap: 6 }}>
                    {scaffold.storyNarrative.map((item) => <li key={item}>{item}</li>)}
                  </ol>
                )}

                {viewerTab === "roi" && (
                  <div className="card" style={{ padding: 8 }}>
                    <strong>ROI Dashboard Requirements</strong>
                    <ul style={{ margin: "6px 0 0 18px", padding: 0, fontSize: 12 }}>
                      {scaffold.roiRequirements.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                )}

                {viewerTab === "resources" && (
                  <div style={{ display: "grid", gap: 8 }}>
                    {scaffold.resourceLinksByStep.map((step) => (
                      <div key={step.stepTitle} className="card" style={{ padding: 8 }}>
                        <strong>{step.stepTitle}</strong>
                        <ul style={{ margin: "6px 0 0 18px", padding: 0, fontSize: 12 }}>
                          {step.resources.map((resource) => (
                            <li key={resource.url}>
                              <a href={resource.url} target="_blank" rel="noreferrer">{resource.title}</a> ({resource.type}) — {resource.reason}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}

                    {canAccessMentoringRecommendation && (
                      <div className="card" style={{ padding: 8, border: "1px solid var(--color-border-strong)" }}>
                        <strong>Mentoring Recommendation</strong>
                        <div style={{ fontSize: 12, marginTop: 4 }}>
                          Recommended path: <strong>{scaffold.mentoringCta.offer}</strong>
                        </div>
                        <div style={{ fontSize: 12 }}><strong>Pricing:</strong> {scaffold.mentoringCta.pricing}</div>
                        <div style={{ fontSize: 12 }}><strong>Timeline:</strong> {scaffold.mentoringCta.timeline}</div>
                        {scaffold.mentoringCta.rationale && <div style={{ fontSize: 12, marginTop: 4 }}><strong>Rationale:</strong> {scaffold.mentoringCta.rationale}</div>}
                        {!canBookMentoring && <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>Upgrade to Elite to unlock live booking and 1:1 mentoring sessions.</div>}
                        <button className="btn-primary" style={{ marginTop: 8 }} disabled={!canBookMentoring}>{canBookMentoring ? scaffold.mentoringCta.ctaText : "Elite required"}</button>
                      </div>
                    )}
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
      )}
    </div>
  );
}
