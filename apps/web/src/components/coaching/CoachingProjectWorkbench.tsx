"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, api, type CoachingIntakeSubmission, type CoachingIntakeSubmissionDetail } from "../../lib/api";
import { trackConversionEvent } from "../../lib/conversion";
import {
  DEFAULT_RATE_LIMIT_UI_CONFIG,
  type RateLimitUiConfig,
  loadRateLimitUiConfig,
  saveRateLimitUiConfig,
} from "../../lib/rateLimitConfig";

type TimelineEvent = { id: string; at?: string; label: string; detail?: string; tone?: "info" | "success" | "warning" | "error" };

type IntakeStepId = "resume" | "selfAssessment" | "jobLinks" | "preferences";
type StageId = "intakeParsed" | "sowGenerated" | "validated";
type CoachingAuthState = "signedOut" | "authenticated";
type SubscriptionStatus = "unknown" | "inactive" | "active";
type PlanTier = "starter" | "pro" | "elite";
type MemberLaunchState = "memberHome" | "launchRequested" | "handoffPending" | "landed";
type ExportFormat = "markdown" | "json";
type ViewerTabId = "charter" | "summary" | "dataSources" | "architecture" | "milestones" | "story" | "roi" | "resources" | "interview";

type QualityActionableReason = {
  code: string;
  field: string;
  reason: string;
  suggested_fix: string;
};

type IntakeDraft = {
  workspaceId: string;
  candidateName: string;
  candidateEmail: string;
  targetRole: string;
  resumeFileName: string;
  resumeHighlights: string[];
  selfAssessment: string;
  questionnaire: {
    careerGoal: string;
    roleTimeline: string;
    currentBackground: string;
    deliveryExamples: string;
    confidenceSql: string;
    confidenceModeling: string;
    confidenceOrchestration: string;
    confidenceStakeholder: string;
    platformExposure: string[];
    toolExposure: string[];
    platformExposureOther: string;
    toolExposureOther: string;
    portfolioReadiness: string;
    interviewReadiness: string;
    weeklyHours: string;
    timelineWeeks: string;
    supportNeeded: string;
  };
  jobLinks: string[];
  selectedPlatforms: string[];
  selectedTools: string[];
  timelineWeeks: string;
};

type Milestone = {
  title: string;
  outcome: string;
  expectations: string[];
  deliverables: string[];
  acceptanceChecks: string[];
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
  interviewArtifacts: {
    starStories: { situation: string; task: string; action: string; result: string }[];
    portfolioChecklist: string[];
    recruiterMapping: { requirement: string; evidence: string }[];
  };
};

const STEP_ORDER: IntakeStepId[] = ["resume", "selfAssessment", "jobLinks", "preferences"];

const STEP_LABELS: Record<IntakeStepId, string> = {
  resume: "1) Resume",
  selfAssessment: "2) Self-Assessment",
  jobLinks: "3) Job Links",
  preferences: "4) Stack + Timeline",
};

const PLATFORM_OPTIONS = ["Databricks", "Snowflake", "BigQuery", "Azure Synapse", "Redshift"];
const TOOL_OPTIONS = ["dbt", "Airflow", "Power BI", "Tableau", "Python", "Spark"];
const PLATFORM_EXPOSURE_OPTIONS = ["Databricks", "Snowflake", "BigQuery", "Azure", "AWS", "GCP"];
const TOOL_EXPOSURE_OPTIONS = ["dbt", "Airflow", "Power BI", "Tableau", "Looker", "Spark", "Python"];
const COACH_FEEDBACK_TAG_OPTIONS = ["scope_clarity", "business_alignment", "architecture_depth", "storytelling", "portfolio_gap", "execution_risk"];
const FEEDBACK_TAG_LABELS: Record<string, string> = {
  scope_clarity: "Scope clarity",
  business_alignment: "Business alignment",
  architecture_depth: "Architecture depth",
  storytelling: "Storytelling",
  portfolio_gap: "Portfolio gap",
  execution_risk: "Execution risk",
};

const QUICK_FEEDBACK_TEMPLATES: Array<{ id: string; label: string; tags: string[]; body: string }> = [
  {
    id: "revision-scope",
    label: "Needs revision — tighten scope",
    tags: ["scope_clarity", "execution_risk"],
    body: "Your scope is promising, but it is currently too broad for the target timeline. Reduce to one measurable business KPI, one primary data source path, and one interview-ready milestone artifact per week.",
  },
  {
    id: "revision-architecture",
    label: "Needs revision — architecture depth",
    tags: ["architecture_depth", "business_alignment"],
    body: "Please add deeper architecture rationale: clarify bronze/silver/gold responsibilities, quality checks by layer, and why this path improves business decision confidence.",
  },
  {
    id: "ready-approve",
    label: "Ready — approve with evidence check",
    tags: ["storytelling"],
    body: "Strong revision. Before final send, verify each milestone includes one concrete deliverable, one success metric, and one evidence link for portfolio/interview narration.",
  },
];

const REGENERATE_RECIPES: Array<{ id: string; label: string; guidance: string; tags: string[] }> = [
  {
    id: "scope-repair",
    label: "Scope repair",
    guidance: "Regenerate with narrower scope: enforce one KPI, one domain problem statement, and explicit timeline guardrails.",
    tags: ["scope_clarity", "execution_risk"],
  },
  {
    id: "architecture-repair",
    label: "Architecture repair",
    guidance: "Regenerate with stronger architecture detail: require medallion layer responsibilities, data contracts, and acceptance checks.",
    tags: ["architecture_depth"],
  },
  {
    id: "story-repair",
    label: "Storytelling + portfolio repair",
    guidance: "Regenerate with interview story improvements: tighten STAR evidence, milestone outcomes, and recruiter mapping language.",
    tags: ["storytelling", "portfolio_gap"],
  },
];

const RESUME_CONFIDENCE_BANDS = [
  { min: 85, label: "High confidence", tone: "success" as const, guidance: "Highlights look clean. Tighten wording, then continue." },
  { min: 60, label: "Medium confidence", tone: "warning" as const, guidance: "Review each highlight for metrics and role relevance before submit." },
  { min: 0, label: "Low confidence", tone: "error" as const, guidance: "Parser confidence is low. Add/replace highlights manually before generating." },
];

const DISCORD_COMMUNITY_URL = "https://discord.gg/gambillcoaching";

const DEFAULT_DRAFT: IntakeDraft = {
  workspaceId: "demo-workspace",
  candidateName: "",
  candidateEmail: "",
  targetRole: "Senior Data Engineer",
  resumeFileName: "",
  resumeHighlights: [""],
  selfAssessment: "",
  questionnaire: {
    careerGoal: "",
    roleTimeline: "",
    currentBackground: "",
    deliveryExamples: "",
    confidenceSql: "Intermediate",
    confidenceModeling: "Intermediate",
    confidenceOrchestration: "Intermediate",
    confidenceStakeholder: "Intermediate",
    platformExposure: ["Databricks"],
    toolExposure: ["dbt", "Python"],
    platformExposureOther: "",
    toolExposureOther: "",
    portfolioReadiness: "In progress",
    interviewReadiness: "Practicing",
    weeklyHours: "6",
    timelineWeeks: "8",
    supportNeeded: "Weekly architecture and storytelling feedback",
  },
  jobLinks: Array.from({ length: 8 }, () => ""),
  selectedPlatforms: ["Databricks"],
  selectedTools: ["dbt", "Power BI"],
  timelineWeeks: "8",
};

function deriveResumeHighlights(rawText: string): string[] {
  const lines = rawText
    .split(/\r?\n/)
    .map((line) => line.replace(/[\u2022\-\*]+/g, "").trim())
    .filter((line) => line.length > 24);

  const ranked = lines
    .map((line) => {
      const lower = line.toLowerCase();
      const score = ["built", "delivered", "led", "%", "$", "pipeline", "dashboard", "data"].reduce((acc, token) => acc + (lower.includes(token) ? 1 : 0), 0);
      return { line, score };
    })
    .sort((a, b) => b.score - a.score)
    .map((item) => item.line);

  return Array.from(new Set(ranked)).slice(0, 6);
}

function deriveResumeSignalSummary(rawText: string, highlights: string[]) {
  const tokens = rawText.toLowerCase();
  const strengthCandidates = highlights.filter((line) => /\d|%|\$|led|built|launched|migrat|automated|reduced|improved/.test(line.toLowerCase()));
  const gapCandidates = [
    !tokens.includes("stakeholder") ? "Add one stakeholder communication win" : "",
    !tokens.includes("impact") && !tokens.includes("reduced") && !tokens.includes("improved") ? "Add one measurable business impact metric" : "",
    !tokens.includes("airflow") && !tokens.includes("dbt") && !tokens.includes("spark") ? "Add one tooling detail (dbt/Airflow/Spark/etc.)" : "",
  ].filter(Boolean);

  const confidence = Math.max(15, Math.min(98, Math.round((highlights.length * 14) + (strengthCandidates.length * 11) + (gapCandidates.length ? 0 : 12))));

  return {
    confidence,
    strengths: (strengthCandidates.length ? strengthCandidates : highlights).slice(0, 4),
    gaps: gapCandidates.slice(0, 3),
  };
}

function buildCombinedProfile(draft: IntakeDraft): string {
  const highlights = draft.resumeHighlights.map((item) => item.trim()).filter(Boolean);
  const summaryBits = [
    draft.questionnaire.currentBackground.trim() && `Background: ${draft.questionnaire.currentBackground.trim()}`,
    draft.questionnaire.careerGoal.trim() && `Goal: ${draft.questionnaire.careerGoal.trim()}`,
    highlights.length ? `Resume signals: ${highlights.join(" | ")}` : "",
  ].filter(Boolean);
  return summaryBits.join("\n");
}

function failReasonPriority(reason: QualityActionableReason): number {
  const code = String(reason.code || "").toUpperCase();
  if (code.includes("MISSING") || code.includes("SECTION") || code.includes("MILESTONE")) return 1;
  if (code.includes("DATA_SOURCE") || code.includes("INGESTION") || code.includes("ARCHITECTURE")) return 2;
  if (code.includes("RESOURCE") || code.includes("NARRATIVE") || code.includes("STYLE")) return 3;
  return 4;
}

function mapFailReasonToViewerTab(reason: QualityActionableReason): ViewerTabId {
  const code = String(reason.code || "").toUpperCase();
  const field = String(reason.field || "").toLowerCase();

  if (code.includes("MILESTONE") || field.includes("milestone")) return "milestones";
  if (code.includes("DATA_SOURCE") || code.includes("INGESTION") || field.includes("data_source")) return "dataSources";
  if (code.includes("RESOURCE") || field.includes("resource")) return "resources";
  if (code.includes("CHARTER") || code.includes("SECTION") || field.includes("project_charter")) return "charter";
  if (code.includes("STYLE") || code.includes("NARRATIVE") || field.includes("story")) return "story";
  return "summary";
}

function viewerTabCtaLabel(tab: ViewerTabId): string {
  if (tab === "milestones") return "Open milestone cards";
  if (tab === "dataSources") return "Open data sources";
  if (tab === "resources") return "Open resource links";
  if (tab === "charter") return "Open project charter";
  if (tab === "story") return "Open story narrative";
  return "Open executive summary";
}

function buildProjectScaffold(draft: IntakeDraft): ProjectScaffold {
  const parsedJobLinks = draft.jobLinks.map((line) => line.trim()).filter(Boolean);

  const candidateName = draft.candidateName.trim() || "Candidate";
  const targetRole = draft.targetRole.trim() || "Data Engineer";

  return {
    title: `${targetRole} Coaching Project Blueprint`,
    executiveSummary: `${candidateName} will deliver a business-first, medallion-aligned project targeted to ${targetRole}, with measurable KPI impact and a hiring-manager-ready narrative.`,
    candidateSnapshot: `${candidateName} targeting ${targetRole}. Intake includes ${parsedJobLinks.length || 0} job posting references, ${draft.resumeHighlights.filter(Boolean).length} resume highlights, and stack preference of ${[...draft.selectedPlatforms, ...draft.selectedTools].join(" + ") || "Not specified"}.`,
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
        expectations: ["Scope ties to top hiring criteria", "Data source assumptions are explicit"],
        deliverables: ["Skill gap matrix", "System context diagram", "Delivery plan draft"],
        acceptanceChecks: ["At least 3 role requirements mapped", "Risk register includes mitigation owner"],
      },
      {
        title: "Milestone 2: Medallion Build Sprint",
        outcome: "Ship working bronze/silver/gold data product with tests and lineage.",
        expectations: ["Pipeline is production-like and reproducible", "Quality checks cover core tables"],
        deliverables: ["Pipeline implementation", "Data quality checks", "Lineage + runbook"],
        acceptanceChecks: ["Critical tests pass in run log", "Runbook includes on-call recovery steps"],
      },
      {
        title: "Milestone 3: Business Readout",
        outcome: "Present architecture decisions, KPI lift, and operational readiness.",
        expectations: ["Business narrative is concise and evidence-backed", "Trade-offs are communicated clearly"],
        deliverables: ["ROI dashboard spec", "Executive walkthrough", "Interview narrative assets"],
        acceptanceChecks: ["Before/after KPI math is shown", "One STAR story tied to measurable impact"],
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
    interviewArtifacts: {
      starStories: [
        {
          situation: "Legacy reporting took multiple days and metrics were inconsistent.",
          task: "Design a reliable medallion pipeline and shared KPI layer.",
          action: "Implemented tested bronze/silver/gold transformations with KPI contracts and observability.",
          result: "Reduced reporting lag from days to hours and improved stakeholder trust in published metrics.",
        },
      ],
      portfolioChecklist: [
        "Architecture diagram with bronze/silver/gold and trade-off notes",
        "Before/after KPI table with clear definitions",
        "GitHub repo or project writeup with reproducible steps",
        "Short executive summary version for recruiter screens",
      ],
      recruiterMapping: [
        { requirement: "End-to-end pipeline delivery", evidence: "Milestone 2 deliverables + lineage/runbook artifacts" },
        { requirement: "Business impact communication", evidence: "Business readout narrative + ROI dashboard requirements" },
      ],
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

function isPrivateIpv4Host(host: string): boolean {
  const m = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!m) return false;
  const parts = m.slice(1).map((x) => Number(x));
  if (parts.some((n) => Number.isNaN(n) || n < 0 || n > 255)) return true;
  const [a, b] = parts;
  if (a === 10) return true;
  if (a === 127) return true;
  if (a === 169 && b === 254) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  if (a === 0) return true;
  return false;
}

function safeExternalUrl(url?: string): { safe: boolean; reason?: string; normalized?: string } {
  const raw = String(url || "").trim();
  if (!raw) return { safe: false, reason: "empty" };
  try {
    const parsed = new URL(raw);
    if (!["http:", "https:"].includes(parsed.protocol)) return { safe: false, reason: "blocked_scheme" };
    const host = parsed.hostname.toLowerCase();
    if (["localhost", "127.0.0.1", "0.0.0.0", "::1"].includes(host) || host.endsWith(".local") || isPrivateIpv4Host(host)) {
      return { safe: false, reason: "blocked_private_host" };
    }
    const blocked = ["example.com", "placeholder", "your-link", "tbd"];
    if (blocked.some((term) => raw.toLowerCase().includes(term))) return { safe: false, reason: "placeholder_or_blocked" };
    return { safe: true, normalized: parsed.toString() };
  } catch {
    return { safe: false, reason: "invalid_url" };
  }
}

function isUnauthorizedError(message?: string): boolean {
  const text = String(message || "").toLowerCase();
  return text.includes("401") || text.includes("unauthorized") || text.includes("invalid token") || text.includes("expired");
}

function formatRetryWindow(seconds?: number): string {
  if (!seconds || seconds <= 0) return "about 30 seconds";
  if (seconds < 60) return `${seconds} seconds`;
  const mins = Math.ceil(seconds / 60);
  return mins === 1 ? "about 1 minute" : `about ${mins} minutes`;
}

function isRateLimitError(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 429;
}

function uiErrorMessage(error: unknown, rateLimitConfig: RateLimitUiConfig): string {
  const message = error instanceof Error ? error.message : String(error || "");
  if (isUnauthorizedError(message)) return "Your session expired. Please sign in again.";
  if (isRateLimitError(error)) {
    const waitFor = error.retryAfterSeconds ?? rateLimitConfig.defaultRetrySeconds;
    return `You have hit a temporary request limit. Wait ${formatRetryWindow(waitFor)}, then retry.`;
  }
  return "We hit a request issue. Please retry.";
}

function toggleOption(items: string[], value: string, checked: boolean): string[] {
  if (checked) return items.includes(value) ? items : [...items, value];
  return items.filter((x) => x !== value);
}

function parseCoachTagsFromNotes(notes?: string): string[] {
  const text = String(notes || "");
  const match = text.match(/\[tags:([^\]]+)\]/i);
  if (!match) return [];
  return match[1].split(",").map((s) => s.trim()).filter(Boolean);
}

function composeCoachNotesWithTags(notes: string, tags: string[]): string {
  const body = String(notes || "").replace(/\s*\[tags:[^\]]+\]\s*/gi, "").trim();
  if (!tags.length) return body;
  return `${body}\n\n[tags: ${tags.join(", ")}]`.trim();
}

function buildStructuredAssessment(draft: IntakeDraft): string {
  const q = draft.questionnaire;
  return [
    "Career Goals",
    `- Goal: ${q.careerGoal || ""}`,
    `- Target timeline: ${q.roleTimeline || ""}`,
    "",
    "Background + Experience",
    `- Current background: ${q.currentBackground || ""}`,
    `- Delivery examples: ${q.deliveryExamples || ""}`,
    "",
    "Skills Confidence",
    `- SQL: ${q.confidenceSql || ""}`,
    `- Data modeling: ${q.confidenceModeling || ""}`,
    `- Orchestration: ${q.confidenceOrchestration || ""}`,
    `- Stakeholder communication: ${q.confidenceStakeholder || ""}`,
    "",
    "Tools + Platform Exposure",
    `- Platforms used: ${[...q.platformExposure, q.platformExposureOther ? `Other: ${q.platformExposureOther}` : ""].filter(Boolean).join(", ")}`,
    `- Tools used: ${[...q.toolExposure, q.toolExposureOther ? `Other: ${q.toolExposureOther}` : ""].filter(Boolean).join(", ")}`,
    "",
    "Portfolio + Interview Readiness",
    `- Portfolio: ${q.portfolioReadiness || ""}`,
    `- Interview readiness: ${q.interviewReadiness || ""}`,
    "",
    "Constraints + Support",
    `- Weekly commitment (hours/week): ${q.weeklyHours || ""}`,
    `- Timeline target (weeks): ${q.timelineWeeks || ""}`,
    `- Support needed: ${q.supportNeeded || ""}`,
  ].join("\n");
}

type WorkbenchRouteMode = "all" | "intake" | "review" | "project";

type CoachingProjectWorkbenchProps = {
  mode?: WorkbenchRouteMode;
  projectId?: string;
};

export default function CoachingProjectWorkbench({ mode = "all", projectId }: CoachingProjectWorkbenchProps) {
  const searchParams = useSearchParams();
  const showInternalAdminPanel = searchParams.get("internal") === "1" || searchParams.get("admin") === "1";

  const [authState, setAuthState] = useState<CoachingAuthState>("signedOut");
  const [subscriptionStatus, setSubscriptionStatus] = useState<SubscriptionStatus>("unknown");
  const [planTier, setPlanTier] = useState<PlanTier>("starter");
  const [memberLaunchState, setMemberLaunchState] = useState<MemberLaunchState>("memberHome");
  const [acceptedLaunchTerms, setAcceptedLaunchTerms] = useState(false);

  const [activeStep, setActiveStep] = useState<IntakeStepId>("resume");
  const [draft, setDraft] = useState<IntakeDraft>(DEFAULT_DRAFT);
  const [resumeUploadState, setResumeUploadState] = useState<{ phase: "idle" | "uploading" | "parsing" | "ready" | "error"; progress: number; message?: string }>({ phase: "idle", progress: 0 });
  const [resumeParseConfidence, setResumeParseConfidence] = useState<number>(0);
  const [resumeStrengthSignals, setResumeStrengthSignals] = useState<string[]>([]);
  const [resumeGapSignals, setResumeGapSignals] = useState<string[]>([]);
  const resumeFileInputRef = useRef<HTMLInputElement | null>(null);
  const [scaffold, setScaffold] = useState<ProjectScaffold | null>(null);
  const [viewerTab, setViewerTab] = useState<ViewerTabId>("charter");
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
  const [selectedSubmissionIds, setSelectedSubmissionIds] = useState<string[]>([]);
  const [batchReviewState, setBatchReviewState] = useState<{ running: boolean; message?: string; error?: string }>({ running: false });
  const [batchRegenerateState, setBatchRegenerateState] = useState<{ running: boolean; message?: string; error?: string }>({ running: false });
  const [coachNotes, setCoachNotes] = useState<string>("");
  const [coachFeedbackTags, setCoachFeedbackTags] = useState<string[]>([]);
  const [queueStatusFilter, setQueueStatusFilter] = useState<string>("all");
  const [reviewSaveState, setReviewSaveState] = useState<{ saving: boolean; message?: string; error?: string }>({ saving: false });
  const [quickActionState, setQuickActionState] = useState<{ running: boolean; message?: string; error?: string; launchToken?: string }>({ running: false });
  const [currentSubmissionId, setCurrentSubmissionId] = useState<string | null>(null);
  const [generationState, setGenerationState] = useState<{ running: boolean; message?: string; sourceMode?: "llm" | "fallback"; qualityFlags?: Record<string, any>; generationMeta?: Record<string, any>; quality?: Record<string, any> }>({ running: false });
  const [readinessState, setReadinessState] = useState<{ loading: boolean; error?: string; readiness?: Record<string, any> }>({ loading: false });
  const [exportStatus, setExportStatus] = useState<{ format: ExportFormat | null; state: "idle" | "exporting" | "success" | "error"; message?: string }>({
    format: null,
    state: "idle",
  });
  const [sessionBanner, setSessionBanner] = useState<string | null>(null);
  const [rateLimitConfig, setRateLimitConfig] = useState<RateLimitUiConfig>(DEFAULT_RATE_LIMIT_UI_CONFIG);
  const [rateLimitConfigSaved, setRateLimitConfigSaved] = useState<string>("");

  const submissionsLoadRef = useRef(0);
  const submissionDetailReqRef = useRef(0);
  const readinessReqRef = useRef(0);

  useEffect(() => {
    setRateLimitConfig(loadRateLimitUiConfig());
  }, []);

  const completion = useMemo(() => ({
    resume: Boolean(draft.resumeFileName.trim()),
    selfAssessment: Boolean(draft.questionnaire.careerGoal.trim()) && Boolean(draft.questionnaire.currentBackground.trim()) && Boolean(draft.questionnaire.supportNeeded.trim()),
    jobLinks: draft.jobLinks.some((link) => link.trim().length > 0),
    preferences: (draft.selectedPlatforms.length + draft.selectedTools.length) > 0 && Boolean(draft.timelineWeeks.trim()),
  }), [draft]);

  const completedCount = Object.values(completion).filter(Boolean).length;

  useEffect(() => {
    setSelectedSubmissionIds((prev) => prev.filter((id) => submissions.some((row) => row.submission_id === id)));
  }, [submissions]);

  const resumeConfidenceBand = useMemo(() => {
    return RESUME_CONFIDENCE_BANDS.find((band) => resumeParseConfidence >= band.min) || RESUME_CONFIDENCE_BANDS[RESUME_CONFIDENCE_BANDS.length - 1];
  }, [resumeParseConfidence]);
  const hasActiveSubscription = authState === "authenticated" && subscriptionStatus === "active";
  const canAccessWorkbench = hasActiveSubscription;
  const canAccessReviewQueue = hasActiveSubscription && planTier !== "starter";
  const canAccessMentoringRecommendation = hasActiveSubscription;
  const canBookMentoring = hasActiveSubscription && planTier === "elite";

  const showLaunchAndAccess = mode === "all" || mode === "intake";
  const showReadiness = mode !== "project";
  const showReviewQueue = mode === "all" || mode === "review";
  const showIntake = mode === "all" || mode === "intake";
  const showOutputViewer = mode === "all" || mode === "project" || mode === "intake";

  function clearAuthStaleState() {
    setSessionBanner(null);
    setReadinessState((prev) => ({ ...prev, error: undefined }));
  }

  function markAuthenticatedApiSuccess() {
    clearAuthStaleState();
  }

  function handleProtectedApiError(error: unknown): string {
    const msg = error instanceof Error ? error.message : "Request failed";
    if (isUnauthorizedError(msg)) {
      setSessionBanner("Session expired. Please sign back in to continue.");
    }
    if (isRateLimitError(error)) {
      const waitFor = error.retryAfterSeconds ?? rateLimitConfig.defaultRetrySeconds;
      setSessionBanner(`Rate limit reached. Please wait ${formatRetryWindow(waitFor)} before retrying.`);
    }
    return uiErrorMessage(error, rateLimitConfig);
  }

  useEffect(() => {
    if (authState === "authenticated" || subscriptionStatus === "active") {
      clearAuthStaleState();
    }
  }, [authState, subscriptionStatus]);

  useEffect(() => {
    if (showLaunchAndAccess) {
      trackConversionEvent({ name: "launch_path_viewed", workspaceId: draft.workspaceId, planTier, details: { authState, subscriptionStatus } });
    }
    if (!canAccessWorkbench) {
      trackConversionEvent({ name: "upgrade_cta_viewed", workspaceId: draft.workspaceId, planTier, details: { authState, subscriptionStatus } });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showLaunchAndAccess, canAccessWorkbench]);

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

  const qualityGuidance = useMemo(() => {
    const q = generationState.quality || {};
    const diagnostics = q.quality_diagnostics || {};
    const missing = Array.isArray(q.missing_sections) ? q.missing_sections : [];
    const sectionOrderValid = q.section_order_valid !== false;
    const actions: string[] = [];

    if (missing.length > 0) {
      actions.push(`Missing sections detected: ${missing.join(", ")}. Regenerate with improvements to force section completion.`);
    }
    if (!sectionOrderValid) {
      actions.push("Section order mismatch detected. Regenerate with improvements to restore canonical section flow.");
    }
    if (Number(diagnostics.deficiency_count || 0) > 0) {
      actions.push("Use top deficiency messages below to tighten milestone execution detail, expected deliverable quality, and business rationale.");
    }
    if ((q.band || "").toString().toLowerCase().includes("low")) {
      actions.push("Quality band is low. Re-run regeneration, then review data source links and milestone resources before export.");
    }
    return actions;
  }, [generationState.quality]);

  const qualityFailureReasons = useMemo(() => {
    const q = generationState.quality || {};
    const diagnostics = (q.quality_diagnostics || {}) as Record<string, any>;
    const reasons: string[] = [];

    if (Array.isArray(q.missing_sections) && q.missing_sections.length > 0) {
      reasons.push(`Missing required sections: ${q.missing_sections.join(", ")}`);
    }
    if (q.section_order_valid === false) {
      reasons.push("Section order invalid for expected coaching template.");
    }
    if (Array.isArray(diagnostics.top_deficiencies) && diagnostics.top_deficiencies.length > 0) {
      reasons.push(...diagnostics.top_deficiencies.slice(0, 3).map((msg: any) => String(msg)));
    }

    return reasons.slice(0, 5);
  }, [generationState.quality]);

  const qualityActionableReasons = useMemo((): Array<QualityActionableReason & { targetTab: ViewerTabId }> => {
    const diagnostics = ((generationState.quality || {}).quality_diagnostics || {}) as Record<string, any>;
    const rows = Array.isArray(diagnostics.actionable_fail_reasons) ? diagnostics.actionable_fail_reasons : [];
    return rows
      .slice(0, 8)
      .map((row: any) => {
        const normalized: QualityActionableReason = {
          code: String(row?.code || "UNKNOWN"),
          field: String(row?.field || "sow"),
          reason: String(row?.reason || "Quality issue requires correction."),
          suggested_fix: String(row?.suggested_fix || "Address this issue and regenerate."),
        };
        return { ...normalized, targetTab: mapFailReasonToViewerTab(normalized), priority: failReasonPriority(normalized) };
      })
      .sort((a, b) => a.priority - b.priority)
      .slice(0, 6);
  }, [generationState.quality]);

  const suggestedFeedbackTags = useMemo(() => {
    const q = generationState.quality || {};
    const diagnostics = (q.quality_diagnostics || {}) as Record<string, any>;
    const tags = new Set<string>();
    const missing = Array.isArray(q.missing_sections) ? q.missing_sections.length : 0;
    const deficiencyCount = Number(diagnostics.deficiency_count || 0);
    const codes = Array.isArray(diagnostics.deficiency_codes) ? diagnostics.deficiency_codes.map((x: string) => String(x).toLowerCase()) : [];

    if (missing > 0 || codes.some((c: string) => c.includes("scope") || c.includes("section"))) tags.add("scope_clarity");
    if (codes.some((c: string) => c.includes("business") || c.includes("roi"))) tags.add("business_alignment");
    if (codes.some((c: string) => c.includes("architecture") || c.includes("data_source") || c.includes("structure"))) tags.add("architecture_depth");
    if (codes.some((c: string) => c.includes("story") || c.includes("narrative") || c.includes("interview"))) tags.add("storytelling");
    if (codes.some((c: string) => c.includes("portfolio") || c.includes("artifact"))) tags.add("portfolio_gap");
    if (deficiencyCount >= 3 || (q.band || "").toString().toLowerCase().includes("low")) tags.add("execution_risk");

    return Array.from(tags).filter((tag) => COACH_FEEDBACK_TAG_OPTIONS.includes(tag)).slice(0, 4);
  }, [generationState.quality]);

  const reviewPromptDraft = useMemo(() => {
    if (!suggestedFeedbackTags.length) return "";
    const labels = suggestedFeedbackTags.map((t) => FEEDBACK_TAG_LABELS[t] || t).join(", ");
    return `Coach focus: ${labels}. Ask for one concrete milestone-level correction per flagged area and require evidence links before approve/send.`;
  }, [suggestedFeedbackTags]);

  const reviewProfileSnapshot = useMemo(() => {
    const prefs = ((selectedSubmission?.preferences_json || {}) as Record<string, any>) || {};
    const resumeProfile = ((prefs.resume_profile || {}) as Record<string, any>) || {};
    const highlights = Array.isArray(resumeProfile.highlights) ? resumeProfile.highlights.map((x: any) => String(x)).filter(Boolean) : [];
    const strengths = Array.isArray(resumeProfile.strengths) ? resumeProfile.strengths.map((x: any) => String(x)).filter(Boolean) : [];
    const gaps = Array.isArray(resumeProfile.gaps) ? resumeProfile.gaps.map((x: any) => String(x)).filter(Boolean) : [];
    const confidence = Number(resumeProfile.confidence || 0);
    const combinedProfile = String(prefs.combined_profile || "").trim();
    return { highlights, strengths, gaps, confidence, combinedProfile };
  }, [selectedSubmission]);

  const selectedSubmissionStatusSummary = useMemo(() => {
    const selected = submissions.filter((row) => selectedSubmissionIds.includes(row.submission_id));
    const statusCounts = selected.reduce((acc, row) => {
      const key = String(row.status || "submitted").toLowerCase();
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return Object.entries(statusCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([status, count]) => `${status}: ${count}`);
  }, [submissions, selectedSubmissionIds]);

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
    const reqId = ++submissionsLoadRef.current;
    try {
      setReviewLoading(true);
      setReviewError(null);
      if (queueStatusFilter !== "all") {
        const out = await api.coachingReviewOpenSubmissions(draft.workspaceId || "demo-workspace", 50, queueStatusFilter);
        if (reqId !== submissionsLoadRef.current) return;
        setSubmissions((out.open_submissions || []).map((row) => ({ ...row.submission, status: row.coach_review_status || row.submission.status })));
      } else {
        const out = await api.listCoachingIntakeSubmissions(draft.workspaceId || "demo-workspace", 50);
        if (reqId !== submissionsLoadRef.current) return;
        setSubmissions(out.submissions || []);
      }
      markAuthenticatedApiSuccess();
    } catch (e: any) {
      if (reqId !== submissionsLoadRef.current) return;
      setReviewError(handleProtectedApiError(e));
    } finally {
      if (reqId === submissionsLoadRef.current) {
        setReviewLoading(false);
      }
    }
  }

  useEffect(() => {
    if (!canAccessWorkbench) return;
    loadSubmissions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canAccessWorkbench, queueStatusFilter]);

  async function loadReadiness() {
    if (!canAccessWorkbench) return;
    const reqId = ++readinessReqRef.current;
    try {
      setReadinessState({ loading: true });
      const out = await api.coachingHealthReadiness(draft.workspaceId || "demo-workspace");
      if (reqId !== readinessReqRef.current) return;
      setReadinessState({ loading: false, readiness: out.readiness, error: undefined });
      markAuthenticatedApiSuccess();
    } catch (e: any) {
      if (reqId !== readinessReqRef.current) return;
      setReadinessState({ loading: false, error: handleProtectedApiError(e) });
    }
  }

  useEffect(() => {
    if (!canAccessWorkbench) return;
    loadReadiness();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canAccessWorkbench, draft.workspaceId]);

  useEffect(() => {
    if (!projectId || !canAccessWorkbench) return;
    openSubmission(projectId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, canAccessWorkbench]);

  async function saveCoachReview() {
    if (!selectedSubmissionId) return;
    try {
      setReviewSaveState({ saving: true });
      const out = await api.coachingReviewStatusUpdate({
        workspace_id: draft.workspaceId || "demo-workspace",
        submission_id: selectedSubmissionId,
        coach_review_status: selectedSubmissionStatus,
        coach_notes: composeCoachNotesWithTags(coachNotes, coachFeedbackTags),
      });
      markAuthenticatedApiSuccess();
      if (!out.ok) {
        setReviewSaveState({ saving: false, error: out.message || "Failed to save review." });
        return;
      }
      setReviewSaveState({ saving: false, message: "Review status + notes saved." });
      if (out.submission) {
        setSelectedSubmission(out.submission);
      }
      await loadSubmissions();
    } catch (e: any) {
      setReviewSaveState({ saving: false, error: handleProtectedApiError(e) });
    }
  }

  async function runQuickReviewAction(action: "in_review" | "needs_revision" | "ready") {
    if (!selectedSubmissionId || quickActionState.running) return;
    try {
      setQuickActionState({ running: true });
      const out = await api.coachingReviewStatusUpdate({
        workspace_id: draft.workspaceId || "demo-workspace",
        submission_id: selectedSubmissionId,
        coach_review_status: action,
        coach_notes: composeCoachNotesWithTags(coachNotes, coachFeedbackTags),
      });
      markAuthenticatedApiSuccess();
      if (!out.ok) {
        setQuickActionState({ running: false, error: out.message || "Quick action failed." });
        return;
      }
      if (out.submission) {
        setSelectedSubmission(out.submission);
        setSelectedSubmissionStatus(String((out.submission as any).coach_review_status || out.submission.status || action));
      } else {
        setSelectedSubmissionStatus(action);
      }
      setQuickActionState({ running: false, message: `Status updated to ${action}.` });
      await loadSubmissions();
    } catch (e: any) {
      setQuickActionState({ running: false, error: handleProtectedApiError(e) });
    }
  }

  async function approveAndSend() {
    if (!selectedSubmissionId || quickActionState.running) return;
    try {
      setQuickActionState({ running: true, message: "Approving and preparing handoff token..." });
      const out = await api.coachingReviewApproveSend({
        workspace_id: draft.workspaceId || "demo-workspace",
        submission_id: selectedSubmissionId,
        coach_notes: composeCoachNotesWithTags(coachNotes, coachFeedbackTags),
      });
      markAuthenticatedApiSuccess();
      if (!out.ok) {
        setQuickActionState({ running: false, error: out.message || "Approve/send failed." });
        return;
      }
      setSelectedSubmissionStatus("approved_sent");
      setQuickActionState({
        running: false,
        message: "Approved and marked sent. Launch handoff token is ready.",
        launchToken: out.handoff?.launch_token,
      });
      await openSubmission(selectedSubmissionId);
      await loadSubmissions();
    } catch (e: any) {
      setQuickActionState({ running: false, error: handleProtectedApiError(e) });
    }
  }

  function applyFeedbackTemplate(templateId: string, mode: "append" | "replace" = "append") {
    const template = QUICK_FEEDBACK_TEMPLATES.find((item) => item.id === templateId);
    if (!template) return;
    setCoachNotes((prev) => {
      if (mode === "replace") return template.body;
      return prev.trim() ? `${prev.trim()}\n\n${template.body}` : template.body;
    });
    setCoachFeedbackTags((prev) => Array.from(new Set([...prev, ...template.tags])));
  }

  function applyRegenerateRecipe(recipeId: string) {
    const recipe = REGENERATE_RECIPES.find((item) => item.id === recipeId);
    if (!recipe) return;
    const guidance = `Regenerate recipe (${recipe.label}): ${recipe.guidance}`;
    setCoachNotes((prev) => (prev.trim() ? `${prev.trim()}\n\n${guidance}` : guidance));
    setCoachFeedbackTags((prev) => Array.from(new Set([...prev, ...recipe.tags])));
    void generateSow(true);
  }

  async function runBatchReviewAction(action: "in_review" | "needs_revision" | "ready") {
    if (!selectedSubmissionIds.length || batchReviewState.running || batchRegenerateState.running) return;

    try {
      setBatchReviewState({ running: true, message: `Applying ${action} to ${selectedSubmissionIds.length} submissions...` });
      const ids = [...selectedSubmissionIds];
      let success = 0;
      let failure = 0;

      for (const submissionId of ids) {
        try {
          const out = await api.coachingReviewStatusUpdate({
            workspace_id: draft.workspaceId || "demo-workspace",
            submission_id: submissionId,
            coach_review_status: action,
            coach_notes: composeCoachNotesWithTags(coachNotes, coachFeedbackTags),
          });
          if (out.ok) {
            success += 1;
          } else {
            failure += 1;
          }
        } catch {
          failure += 1;
        }
      }

      await loadSubmissions();
      setBatchReviewState({ running: false, message: `Batch complete: ${success} updated, ${failure} failed.` });
      if (failure === 0) {
        setSelectedSubmissionIds([]);
      }
    } catch (e: any) {
      setBatchReviewState({ running: false, error: handleProtectedApiError(e) });
    }
  }

  async function runBatchRegenerateSelected() {
    if (!selectedSubmissionIds.length || batchRegenerateState.running || batchReviewState.running) return;

    try {
      setBatchRegenerateState({ running: true, message: `Regenerating ${selectedSubmissionIds.length} selected submissions...` });
      const ids = [...selectedSubmissionIds];
      let success = 0;
      let failure = 0;

      for (const submissionId of ids) {
        try {
          const out = await api.coachingGenerateSow({
            workspace_id: draft.workspaceId || "demo-workspace",
            submission_id: submissionId,
            parsed_jobs: [],
            regenerate_with_improvements: true,
          });
          if (out.ok && out.sow) {
            success += 1;
          } else {
            failure += 1;
          }
        } catch {
          failure += 1;
        }
      }

      await loadSubmissions();
      setBatchRegenerateState({ running: false, message: `Batch regenerate complete: ${success} regenerated, ${failure} failed.` });
    } catch (e: any) {
      setBatchRegenerateState({ running: false, error: handleProtectedApiError(e) });
    }
  }

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

  function setTimelineWeeks(value: string) {
    setDraft((prev) => ({
      ...prev,
      timelineWeeks: value,
      questionnaire: {
        ...prev.questionnaire,
        timelineWeeks: value,
      },
    }));
  }

  function applyActionableFixAndRegenerate(reason: QualityActionableReason & { targetTab: ViewerTabId }) {
    setViewerTab(reason.targetTab);
    const fixLine = `Actionable fix (${reason.code}): ${reason.suggested_fix}`;
    setCoachNotes((prev) => (prev.trim() ? `${prev.trim()}\n\n${fixLine}` : fixLine));
    void generateSow(true);
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
        expectations: Array.isArray(m.expectations) ? m.expectations.map((d: any) => String(d)) : ["Scope reviewed with coach"],
        deliverables: Array.isArray(m.deliverables) ? m.deliverables.map((d: any) => String(d)) : [],
        acceptanceChecks: Array.isArray(m.acceptance_checks) ? m.acceptance_checks.map((d: any) => String(d)) : ["Coach and learner both confirm milestone completion"],
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
      interviewArtifacts: {
        starStories: Array.isArray((sow.interview_ready || {}).star_stories) && (sow.interview_ready || {}).star_stories.length
          ? (sow.interview_ready || {}).star_stories.map((s: any) => ({
              situation: String(s.situation || ""),
              task: String(s.task || ""),
              action: String(s.action || ""),
              result: String(s.result || ""),
            }))
          : [{
              situation: "Business stakeholders lacked trusted KPI visibility.",
              task: "Deliver an interview-ready analytics initiative with measurable impact.",
              action: "Built medallion data model + quality gates + KPI dashboard contract.",
              result: "Reduced reporting lag and improved KPI confidence for decision-making.",
            }],
        portfolioChecklist: Array.isArray((sow.interview_ready || {}).portfolio_checklist)
          ? (sow.interview_ready || {}).portfolio_checklist.map((x: any) => String(x))
          : ["Architecture diagram", "KPI before/after metrics", "README with delivery narrative"],
        recruiterMapping: Array.isArray((sow.interview_ready || {}).recruiter_mapping)
          ? (sow.interview_ready || {}).recruiter_mapping.map((r: any) => ({ requirement: String(r.requirement || ""), evidence: String(r.evidence || "") }))
          : [{ requirement: "Data platform delivery", evidence: "Milestone deliverables and runbook" }],
      },
    };
  }

  async function processResumeFile(file: File) {
    setResumeUploadState({ phase: "uploading", progress: 8, message: `Uploading ${file.name}...` });
    setDraft((prev) => ({ ...prev, resumeFileName: file.name }));

    const timer = window.setInterval(() => {
      setResumeUploadState((prev) => ({ ...prev, progress: Math.min(92, prev.progress + 12) }));
    }, 120);

    try {
      const rawText = await file.text();
      setResumeUploadState({ phase: "parsing", progress: 95, message: "Parsing resume for highlights..." });
      const highlights = deriveResumeHighlights(rawText);
      const resolvedHighlights = highlights.length ? highlights : ["Add one achievement highlight from your resume"];
      const signalSummary = deriveResumeSignalSummary(rawText, resolvedHighlights);
      setDraft((prev) => ({ ...prev, resumeHighlights: resolvedHighlights }));
      setResumeParseConfidence(signalSummary.confidence);
      setResumeStrengthSignals(signalSummary.strengths);
      setResumeGapSignals(signalSummary.gaps);
      setResumeUploadState({ phase: "ready", progress: 100, message: `Parsed ${highlights.length || 1} highlight${highlights.length === 1 ? "" : "s"}.` });
      trackConversionEvent({ name: "resume_parse_completed", workspaceId: draft.workspaceId, details: { confidence: signalSummary.confidence, highlights: resolvedHighlights.length } });
    } catch (e: any) {
      setResumeUploadState({ phase: "error", progress: 100, message: e?.message || "Could not parse that file. Try .txt, .md, .docx, or paste highlights manually." });
      setResumeParseConfidence(0);
      setResumeStrengthSignals([]);
      setResumeGapSignals(["Paste at least 3 achievement highlights manually to continue."]);
      trackConversionEvent({ name: "resume_parse_failed", workspaceId: draft.workspaceId, details: { reason: e?.message || "parse_error" } });
    } finally {
      window.clearInterval(timer);
    }
  }

  async function submitIntake() {
    if (!canAccessWorkbench) return;

    const jobLinks = draft.jobLinks.map((line) => line.trim()).filter(Boolean);
    const preferredStack = [...draft.selectedPlatforms, ...draft.selectedTools].join(" + ");
    const structuredAssessment = buildStructuredAssessment(draft);
    const combinedProfile = buildCombinedProfile(draft);

    try {
      const intakeResult = await api.coachingIntake({
        workspace_id: draft.workspaceId,
        applicant_name: draft.candidateName || "Candidate",
        applicant_email: draft.candidateEmail || undefined,
        resume_text: draft.resumeFileName,
        self_assessment_text: [
          structuredAssessment,
          "",
          "Resume-Derived Highlights",
          ...draft.resumeHighlights.map((item) => `- ${item.trim()}`).filter((line) => line !== "-"),
          "",
          "Resume strengths",
          ...resumeStrengthSignals.map((item) => `- ${item.trim()}`).filter((line) => line !== "-"),
          "",
          "Resume gaps to close",
          ...resumeGapSignals.map((item) => `- ${item.trim()}`).filter((line) => line !== "-"),
          "",
          "Combined Profile",
          combinedProfile,
        ].join("\n"),
        job_links: jobLinks,
        preferences: {
          target_role: draft.targetRole,
          preferred_stack: preferredStack,
          timeline_weeks: draft.questionnaire.timelineWeeks || draft.timelineWeeks,
          selected_platforms: draft.selectedPlatforms,
          selected_tools: draft.selectedTools,
          resume_profile: {
            file_name: draft.resumeFileName,
            confidence: resumeParseConfidence,
            highlights: draft.resumeHighlights.map((item) => item.trim()).filter(Boolean),
            strengths: resumeStrengthSignals.map((item) => item.trim()).filter(Boolean),
            gaps: resumeGapSignals.map((item) => item.trim()).filter(Boolean),
          },
          combined_profile: combinedProfile,
        },
      });

      markAuthenticatedApiSuccess();
      setDraft((prev) => ({ ...prev, selfAssessment: structuredAssessment }));
      setCurrentSubmissionId(intakeResult.submission_id || null);
      trackConversionEvent({ name: "intake_submitted", workspaceId: draft.workspaceId, submissionId: intakeResult.submission_id, planTier, details: { jobLinks: jobLinks.length } });
      setStageState((prev) => ({ ...prev, intakeParsed: true }));
      await loadSubmissions();
    } catch (e: any) {
      setGenerationState({ running: false, message: handleProtectedApiError(e) });
    }
  }

  async function generateSow(useImprovements = false) {
    if (!canAccessWorkbench || generationState.running) return;
    if (!currentSubmissionId) {
      setScaffold(buildProjectScaffold(draft));
      setStageState((prev) => ({ ...prev, sowGenerated: true }));
      setGenerationState({ running: false, message: "Built local scaffold (submit intake to enable server generation).", sourceMode: "fallback" });
      return;
    }

    try {
      trackConversionEvent({ name: useImprovements ? "sow_regenerate_clicked" : "sow_generate_clicked", workspaceId: draft.workspaceId, submissionId: currentSubmissionId, planTier });
      setGenerationState({ running: true, message: useImprovements ? "Regenerating with improvements..." : "Generating SOW..." });
      const out = await api.coachingGenerateSow({ workspace_id: draft.workspaceId, submission_id: currentSubmissionId, parsed_jobs: [], regenerate_with_improvements: useImprovements });
      markAuthenticatedApiSuccess();
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
        quality: out.quality || {},
      });
      trackConversionEvent({ name: "sow_generate_completed", workspaceId: draft.workspaceId, submissionId: currentSubmissionId, source: fallbackUsed ? "fallback" : "llm", details: { valid: Boolean(out.valid), score: out.quality?.score } });
    } catch (e: any) {
      const msg = e?.message || "Generation failed.";
      setGenerationState({ running: false, message: msg.includes("403") ? "Upgrade required: active subscription needed for generation." : handleProtectedApiError(e) });
    }
  }

  function markValidated() {
    setStageState((prev) => ({ ...prev, validated: true }));
  }

  async function openSubmission(submissionId: string) {
    const reqId = ++submissionDetailReqRef.current;
    setSelectedSubmissionId(submissionId);
    setSubmissionDetailError(null);
    setSubmissionDetailLoading(true);
    setQuickActionState({ running: false });

    try {
      const out = await api.coachingIntakeSubmissionDetail(submissionId);
      const runsOut = await api.coachingReviewSubmissionRuns(submissionId, 20);
      if (reqId !== submissionDetailReqRef.current) return;
      markAuthenticatedApiSuccess();
      if (!out.ok || !out.submission) {
        setSelectedSubmission(null);
        setSubmissionDetailError(out.message || "Unable to load submission details.");
        return;
      }
      setSelectedSubmission(out.submission);
      setCurrentSubmissionId(out.submission.submission_id);
      setSelectedSubmissionStatus(String((out.submission as any).coach_review_status || out.submission.status || "submitted"));
      const loadedNotes = String((out.submission as any).coach_notes || (out.latest_generation_run || {}).coach_notes || "");
      setCoachNotes(loadedNotes.replace(/\s*\[tags:[^\]]+\]\s*/gi, "").trim());
      setCoachFeedbackTags(parseCoachTagsFromNotes(loadedNotes));
      setReviewSaveState({ saving: false });
      setSelectedSubmissionRuns(runsOut.runs || []);
      const recs = ((out.latest_generation_run || {}) as any).recommendations || {};
      if (recs.platforms || recs.tools || recs.timeline_weeks) {
        setDraft((prev) => ({
          ...prev,
          selectedPlatforms: Array.isArray(recs.platforms) && recs.platforms.length ? recs.platforms.map((x: any) => String(x)) : prev.selectedPlatforms,
          selectedTools: Array.isArray(recs.tools) && recs.tools.length ? recs.tools.map((x: any) => String(x)) : prev.selectedTools,
          timelineWeeks: recs.timeline_weeks ? String(recs.timeline_weeks) : prev.timelineWeeks,
          questionnaire: {
            ...prev.questionnaire,
            timelineWeeks: recs.timeline_weeks ? String(recs.timeline_weeks) : prev.questionnaire.timelineWeeks,
          },
        }));
      }
      if (out.latest_generation_run) {
        setStageState({
          intakeParsed: true,
          sowGenerated: true,
          validated: String(out.latest_generation_run.run_status || "").toLowerCase() === "completed",
        });
      }
    } catch (e: any) {
      if (reqId !== submissionDetailReqRef.current) return;
      setSelectedSubmission(null);
      setSubmissionDetailError(handleProtectedApiError(e));
    } finally {
      if (reqId === submissionDetailReqRef.current) {
        setSubmissionDetailLoading(false);
      }
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
      resumeHighlights: Array.isArray((preferences as any).resume_profile?.highlights) && (preferences as any).resume_profile.highlights.length
        ? (preferences as any).resume_profile.highlights.map((x: any) => String(x))
        : prev.resumeHighlights,
      selfAssessment: selectedSubmission.self_assessment_text || prev.selfAssessment,
      jobLinks: parsedJobLinks.length ? [...parsedJobLinks, ...Array.from({ length: Math.max(0, 8 - parsedJobLinks.length) }, () => "")].slice(0, 10) : prev.jobLinks,
      selectedPlatforms: Array.isArray((preferences as any).selected_platforms) ? (preferences as any).selected_platforms.map((x: any) => String(x)) : prev.selectedPlatforms,
      selectedTools: Array.isArray((preferences as any).selected_tools) ? (preferences as any).selected_tools.map((x: any) => String(x)) : prev.selectedTools,
      timelineWeeks: String(preferences.timeline_weeks || prev.timelineWeeks),
      questionnaire: {
        ...prev.questionnaire,
        timelineWeeks: String(preferences.timeline_weeks || prev.questionnaire.timelineWeeks || prev.timelineWeeks),
      },
    }));

    const resumeProfile = (preferences as any).resume_profile || {};
    setResumeParseConfidence(Number(resumeProfile.confidence || 0));
    setResumeStrengthSignals(Array.isArray(resumeProfile.strengths) ? resumeProfile.strengths.map((x: any) => String(x)) : []);
    setResumeGapSignals(Array.isArray(resumeProfile.gaps) ? resumeProfile.gaps.map((x: any) => String(x)) : []);

    setStageState((prev) => ({ ...prev, intakeParsed: true }));
    setActiveStep("resume");
  }

  function exportStudentPackage(format: ExportFormat) {
    if (!scaffold) return;

    const timestamp = new Date().toISOString().slice(0, 10);
    const safeName = (draft.candidateName || "candidate").toLowerCase().replace(/\s+/g, "-");

    try {
      trackConversionEvent({ name: "export_clicked", workspaceId: draft.workspaceId, submissionId: currentSubmissionId || undefined, details: { format } });
      setExportStatus({ format, state: "exporting", message: `Preparing ${format.toUpperCase()} package...` });

      if (format === "json") {
        downloadText(JSON.stringify(scaffold, null, 2), `${safeName}-coaching-package-${timestamp}.json`, "application/json");
        setExportStatus({ format, state: "success", message: `JSON package exported (${timestamp}).` });
        trackConversionEvent({ name: "export_completed", workspaceId: draft.workspaceId, submissionId: currentSubmissionId || undefined, details: { format } });
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
          ...m.expectations.map((d) => `- Expectation: ${d}`),
          ...m.deliverables.map((d) => `- Deliverable: ${d}`),
          ...m.acceptanceChecks.map((d) => `- Acceptance check: ${d}`),
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
        "## Interview Artifacts",
        "### STAR Stories",
        ...scaffold.interviewArtifacts.starStories.flatMap((s, idx) => [
          `#### Story ${idx + 1}`,
          `- Situation: ${s.situation}`,
          `- Task: ${s.task}`,
          `- Action: ${s.action}`,
          `- Result: ${s.result}`,
        ]),
        "",
        "### Portfolio Checklist",
        ...scaffold.interviewArtifacts.portfolioChecklist.map((item) => `- ${item}`),
        "",
        "### Recruiter Mapping",
        ...scaffold.interviewArtifacts.recruiterMapping.map((row) => `- ${row.requirement}: ${row.evidence}`),
        "",
        "## Mentoring Offer",
        `- Offer: ${scaffold.mentoringCta.offer}`,
        `- Pricing: ${scaffold.mentoringCta.pricing}`,
        `- Timeline: ${scaffold.mentoringCta.timeline}`,
        `- CTA: ${scaffold.mentoringCta.ctaText}`,
      ].join("\n");

      downloadText(markdown, `${safeName}-coaching-package-${timestamp}.md`, "text/markdown");
      setExportStatus({ format, state: "success", message: `Markdown package exported (${timestamp}).` });
      trackConversionEvent({ name: "export_completed", workspaceId: draft.workspaceId, submissionId: currentSubmissionId || undefined, details: { format } });
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
      const next = prev === "memberHome" ? "launchRequested" : prev === "launchRequested" ? "handoffPending" : "landed";
      trackConversionEvent({ name: "launch_step_advanced", workspaceId: draft.workspaceId, planTier, details: { from: prev, to: next } });
      return next;
    });
  }

  function resetLaunchFlow() {
    setMemberLaunchState("memberHome");
  }


  return (
    <div className="coaching-shell">
      <div className="coaching-hero">
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <img src="/brand/logo.png" alt="Gambill Coaching" style={{ width: 44, height: 44, objectFit: "contain", borderRadius: 8 }} />
          <div>
            <h2>Gambill Coaching Project Builder</h2>
            <p>Generate portfolio-ready, business-outcome-driven data engineering projects from resume + job targets.</p>
          </div>
        </div>
        <span className="badge info">Coaching App</span>
      </div>
      {sessionBanner && <div className="card" style={{ border: "1px solid #f59e0b", background: "#fffbeb", color: "#92400e" }}>{sessionBanner}</div>}
      {(reviewError || readinessState.error || (generationState.message && generationState.message.toLowerCase().includes("retry"))) && (
        <div className="card" style={{ border: "1px solid #f59e0b", background: "#fff7ed", marginBottom: 10 }}>
          <strong style={{ fontSize: 12 }}>Issue response guide</strong>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            We hit a live issue. Retry first. If it persists, use fallback mode (local scaffold/export) and capture coach notes for follow-up.
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
            <button onClick={loadSubmissions}>Retry queue load</button>
            <button onClick={loadReadiness}>Retry readiness check</button>
            <button onClick={() => generateSow(false)} disabled={generationState.running}>Retry generation</button>
          </div>
          <div style={{ fontSize: 12, marginTop: 8 }}>
            Rate-limit fallback: wait <strong>{rateLimitConfig.defaultRetrySeconds}s</strong> when no Retry-After header is returned.
          </div>
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 4 }}>{rateLimitConfig.helperMessage}</div>
        </div>
      )}

      {showInternalAdminPanel && (
        <div className="card" style={{ border: "1px dashed #94a3b8", marginBottom: 10 }}>
          <strong style={{ fontSize: 12 }}>Internal Admin: Rate-Limit UX Config (local scaffold)</strong>
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 4 }}>
            This panel is intentionally hidden behind <code>?internal=1</code> or <code>?admin=1</code>.
          </div>
          <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
            <label style={{ fontSize: 12 }}>
              Default retry seconds
              <input
                type="number"
                min={1}
                value={rateLimitConfig.defaultRetrySeconds}
                onChange={(e) => setRateLimitConfig((prev) => ({ ...prev, defaultRetrySeconds: Math.max(1, Number(e.target.value || 1)) }))}
              />
            </label>
            <label style={{ fontSize: 12 }}>
              Helper message
              <textarea
                style={{ width: "100%", minHeight: 60 }}
                value={rateLimitConfig.helperMessage}
                onChange={(e) => setRateLimitConfig((prev) => ({ ...prev, helperMessage: e.target.value }))}
              />
            </label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                onClick={() => {
                  saveRateLimitUiConfig(rateLimitConfig);
                  setRateLimitConfigSaved("Saved locally for this browser.");
                }}
              >
                Save local config
              </button>
              <button
                onClick={() => {
                  setRateLimitConfig(DEFAULT_RATE_LIMIT_UI_CONFIG);
                  saveRateLimitUiConfig(DEFAULT_RATE_LIMIT_UI_CONFIG);
                  setRateLimitConfigSaved("Reset to defaults.");
                }}
              >
                Reset defaults
              </button>
              {rateLimitConfigSaved && <span className="badge success">{rateLimitConfigSaved}</span>}
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Link href="/intake"><button className={mode === "intake" ? "btn-primary" : undefined}>Intake</button></Link>
        <Link href="/review"><button className={mode === "review" ? "btn-primary" : undefined}>Review</button></Link>
        <Link href={currentSubmissionId ? `/project/${currentSubmissionId}` : "/project/demo"}><button className={mode === "project" ? "btn-primary" : undefined}>Project</button></Link>
      </div>

      {showLaunchAndAccess && (
      <>
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
          <button onClick={() => { setAuthState("authenticated"); clearAuthStaleState(); }}>Set Authenticated</button>
          <button onClick={() => setSubscriptionStatus("inactive")}>Set Inactive Sub</button>
          <button onClick={() => { setSubscriptionStatus("active"); clearAuthStaleState(); }}>Set Active Sub</button>
          <button onClick={() => setSubscriptionStatus("unknown")}>Set Unknown Sub</button>
          <button onClick={resetLaunchFlow}>Reset Launch</button>
        </div>

        <label style={{ display: "grid", gap: 4, fontSize: 12, marginBottom: 8, maxWidth: 220 }}>
          Plan tier
          <select value={planTier} onChange={(e) => setPlanTier(e.target.value as PlanTier)}>
            <option value="starter">starter</option>
            <option value="pro">pro</option>
            <option value="elite">elite</option>
          </select>
        </label>

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

      <div className="card" style={{ marginBottom: 10 }}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <span className={canAccessReviewQueue ? "badge success" : "badge warning"}>Coach review: {canAccessReviewQueue ? "enabled" : "locked"}</span>
          <span className={canBookMentoring ? "badge success" : "badge info"}>Live mentoring: {canBookMentoring ? "enabled" : "locked"}</span>
        </div>
      </div>
      </>
      )}

      {!canAccessWorkbench && (
        <>
          <h4>Coaching Access Gate</h4>
          <div className="card" style={{ marginBottom: 10 }}>
            <span className="badge warning">Subscription-required state</span>
            <div style={{ marginTop: 8, fontSize: 12, color: "var(--color-text-muted)" }}>{gateMessage()}</div>
            {subscriptionStatus !== "active" && (
              <>
                <div style={{ fontSize: 12, marginTop: 8 }}><strong>Upgrade message:</strong> Upgrade to Pro/Elite to unlock generation, exports, and coach review workflow.</div>
                <button style={{ marginTop: 8 }} onClick={() => { trackConversionEvent({ name: "upgrade_cta_clicked", workspaceId: draft.workspaceId, planTier }); setSubscriptionStatus("active"); clearAuthStaleState(); }}>Simulate successful upgrade/renewal</button>
              </>
            )}
          </div>
        </>
      )}

      {canAccessWorkbench && (
        <>
          {showReadiness && (
          <>
          <h4>Readiness Health</h4>
          <div className="card" style={{ marginBottom: 10 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}>
              <button onClick={loadReadiness} disabled={readinessState.loading}>{readinessState.loading ? "Checking..." : "Refresh readiness"}</button>
              {readinessState.readiness && (
                <span className={`badge ${readinessState.readiness.ready ? "success" : "warning"}`}>
                  {readinessState.readiness.ready ? "Ready" : "Action needed"}
                </span>
              )}
              {readinessState.error && <span className="badge error">{readinessState.error}</span>}
            </div>
            {readinessState.readiness && (
              <div style={{ display: "grid", gap: 6, fontSize: 12 }}>
                <div>LLM key: <strong>{readinessState.readiness.llm_key_present ? "present" : "missing"}</strong></div>
                <div>Lakebase: <strong>{readinessState.readiness.lakebase_ok ? "healthy" : "unhealthy"}</strong></div>
                <div style={{ color: "var(--color-text-muted)" }}>{readinessState.readiness.lakebase_message || "No lakebase details."}</div>
              </div>
            )}
          </div>
          </>
          )}

          {showReviewQueue && (
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
                  <select value={queueStatusFilter} onChange={(e) => setQueueStatusFilter(e.target.value)}>
                    <option value="all">All statuses</option>
                    <option value="new">new</option>
                    <option value="submitted">submitted</option>
                    <option value="in_review">in_review</option>
                    <option value="needs_revision">needs_revision</option>
                    <option value="ready">ready</option>
                  </select>
                  <button onClick={loadSubmissions}>Refresh submissions</button>
                  {reviewLoading && <span className="badge info">Loading…</span>}
                  {reviewError && <span className="badge error">{reviewError}</span>}
                </div>

                <div className="card" style={{ padding: 8, marginBottom: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <strong style={{ fontSize: 12 }}>Batch review actions</strong>
                    <span className="badge info">Selected: {selectedSubmissionIds.length}/{submissions.length}</span>
                    <button
                      type="button"
                      onClick={() => setSelectedSubmissionIds(submissions.slice(0, 10).map((row) => row.submission_id))}
                      disabled={batchReviewState.running || batchRegenerateState.running || submissions.length === 0}
                    >
                      Select first 10
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedSubmissionIds(submissions.map((row) => row.submission_id))}
                      disabled={batchReviewState.running || batchRegenerateState.running || submissions.length === 0}
                    >
                      Select all loaded
                    </button>
                    <button type="button" onClick={() => runBatchReviewAction("in_review")} disabled={batchReviewState.running || selectedSubmissionIds.length === 0}>Batch → in_review</button>
                    <button type="button" onClick={() => runBatchReviewAction("needs_revision")} disabled={batchReviewState.running || selectedSubmissionIds.length === 0}>Batch → needs_revision</button>
                    <button type="button" className="btn-success" onClick={() => runBatchReviewAction("ready")} disabled={batchReviewState.running || batchRegenerateState.running || selectedSubmissionIds.length === 0}>Batch → ready</button>
                    <button type="button" className="btn-primary" onClick={runBatchRegenerateSelected} disabled={batchReviewState.running || batchRegenerateState.running || selectedSubmissionIds.length === 0}>{batchRegenerateState.running ? "Regenerating..." : "Batch regenerate"}</button>
                    <button type="button" onClick={() => setSelectedSubmissionIds([])} disabled={batchReviewState.running || batchRegenerateState.running || selectedSubmissionIds.length === 0}>Clear selection</button>
                  </div>
                  {selectedSubmissionStatusSummary.length > 0 && (
                    <div style={{ marginTop: 6, fontSize: 12, color: "var(--color-text-muted)" }}>
                      Status mix: {selectedSubmissionStatusSummary.join(" | ")}
                    </div>
                  )}
                  {batchReviewState.message && <div style={{ marginTop: 6 }}><span className="badge success">{batchReviewState.message}</span></div>}
                  {batchReviewState.error && <div style={{ marginTop: 6 }}><span className="badge error">{batchReviewState.error}</span></div>}
                  {batchRegenerateState.message && <div style={{ marginTop: 6 }}><span className="badge success">{batchRegenerateState.message}</span></div>}
                  {batchRegenerateState.error && <div style={{ marginTop: 6 }}><span className="badge error">{batchRegenerateState.error}</span></div>}
                </div>

                <div style={{ overflowX: "auto", marginBottom: 8 }}>
                  <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                    <thead>
                      <tr>
                        <th align="left">
                          <input
                            type="checkbox"
                            checked={submissions.length > 0 && selectedSubmissionIds.length === submissions.length}
                            onChange={(e) => setSelectedSubmissionIds(e.target.checked ? submissions.map((row) => row.submission_id) : [])}
                            aria-label="Select all submissions"
                          />
                        </th>
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
                          <td colSpan={7} style={{ color: "var(--color-text-muted)", padding: "8px 0" }}>
                            No submissions yet for this workspace.
                          </td>
                        </tr>
                      ) : (
                        submissions.map((s) => (
                          <tr key={s.submission_id} style={selectedSubmissionId === s.submission_id ? { background: "rgba(120,120,255,0.08)" } : undefined}>
                            <td>
                              <input
                                type="checkbox"
                                checked={selectedSubmissionIds.includes(s.submission_id)}
                                onChange={(e) => setSelectedSubmissionIds((prev) => e.target.checked ? Array.from(new Set([...prev, s.submission_id])) : prev.filter((id) => id !== s.submission_id))}
                                aria-label={`Select ${s.applicant_name || s.submission_id}`}
                              />
                            </td>
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
                          {normalizeJobLinks(selectedSubmission.job_links_json).map((link) => {
                            const safety = safeExternalUrl(link);
                            return (
                              <li key={link}>
                                {safety.safe ? <a href={safety.normalized} target="_blank" rel="noreferrer">{link}</a> : <span>{link} <span className="badge warning">Blocked unsafe link ({safety.reason})</span></span>}
                              </li>
                            );
                          })}
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
                        <strong>Resume/Profile Mapping Snapshot</strong>
                        <div style={{ marginTop: 6, fontSize: 12 }}>
                          Parse confidence: <span className={`badge ${reviewProfileSnapshot.confidence >= 85 ? "success" : reviewProfileSnapshot.confidence >= 60 ? "warning" : "error"}`}>{reviewProfileSnapshot.confidence || 0}%</span>
                        </div>
                        <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                          <div>
                            <strong>Highlights ({reviewProfileSnapshot.highlights.length})</strong>
                            <ul style={{ margin: "4px 0 0 18px", padding: 0 }}>
                              {reviewProfileSnapshot.highlights.slice(0, 5).map((item, idx) => <li key={`review-highlight-${idx}`}>{item}</li>)}
                              {reviewProfileSnapshot.highlights.length === 0 && <li style={{ color: "var(--color-text-muted)" }}>No highlights saved in intake preferences.</li>}
                            </ul>
                          </div>
                          <div>
                            <strong>Strengths → role evidence ({reviewProfileSnapshot.strengths.length})</strong>
                            <ul style={{ margin: "4px 0 0 18px", padding: 0 }}>
                              {reviewProfileSnapshot.strengths.slice(0, 4).map((item, idx) => <li key={`review-strength-${idx}`}>{item}</li>)}
                              {reviewProfileSnapshot.strengths.length === 0 && <li style={{ color: "var(--color-text-muted)" }}>No mapped strengths captured.</li>}
                            </ul>
                          </div>
                          <div>
                            <strong>Gaps to close ({reviewProfileSnapshot.gaps.length})</strong>
                            <ul style={{ margin: "4px 0 0 18px", padding: 0 }}>
                              {reviewProfileSnapshot.gaps.slice(0, 4).map((item, idx) => <li key={`review-gap-${idx}`}>{item}</li>)}
                              {reviewProfileSnapshot.gaps.length === 0 && <li style={{ color: "var(--color-text-muted)" }}>No explicit gaps captured.</li>}
                            </ul>
                          </div>
                          {reviewProfileSnapshot.combinedProfile && (
                            <div>
                              <strong>Combined profile narrative</strong>
                              <div style={{ marginTop: 4, whiteSpace: "pre-wrap", color: "var(--color-text-muted)" }}>{reviewProfileSnapshot.combinedProfile}</div>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="card" style={{ padding: 8 }}>
                        <strong>Coach Status + Notes</strong>
                        <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap", alignItems: "center" }}>
                          <select value={selectedSubmissionStatus} onChange={(e) => setSelectedSubmissionStatus(e.target.value)}>
                            <option value="submitted">submitted</option>
                            <option value="in_review">in_review</option>
                            <option value="needs_revision">needs_revision</option>
                            <option value="ready">ready</option>
                            <option value="approved_sent">approved_sent</option>
                          </select>
                          <button onClick={saveCoachReview} disabled={reviewSaveState.saving || !selectedSubmissionId || quickActionState.running}>{reviewSaveState.saving ? "Saving..." : "Save review"}</button>
                          <button onClick={() => runQuickReviewAction("in_review")} disabled={!selectedSubmissionId || quickActionState.running}>Quick: Mark in review</button>
                          <button onClick={() => runQuickReviewAction("needs_revision")} disabled={!selectedSubmissionId || quickActionState.running}>Quick: Needs revision</button>
                          <button className="btn-success" onClick={() => runQuickReviewAction("ready")} disabled={!selectedSubmissionId || quickActionState.running}>Quick: Mark ready</button>
                          <button className="btn-primary" onClick={approveAndSend} disabled={!selectedSubmissionId || quickActionState.running}>Approve + Send</button>
                          {reviewSaveState.message && <span className="badge success">{reviewSaveState.message}</span>}
                          {reviewSaveState.error && <span className="badge error">{reviewSaveState.error}</span>}
                        </div>
                        <div style={{ marginTop: 8, fontSize: 12 }}>
                          <strong>Quick feedback templates</strong>
                          <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                            {QUICK_FEEDBACK_TEMPLATES.map((template) => (
                              <button key={template.id} type="button" onClick={() => applyFeedbackTemplate(template.id)}>
                                + {template.label}
                              </button>
                            ))}
                            <button type="button" onClick={() => setCoachNotes("")}>Clear notes</button>
                          </div>
                        </div>

                        <div style={{ marginTop: 8, fontSize: 12 }}>
                          <strong>Feedback tags</strong>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
                            {COACH_FEEDBACK_TAG_OPTIONS.map((tag) => (
                              <label key={tag} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                                <input
                                  type="checkbox"
                                  checked={coachFeedbackTags.includes(tag)}
                                  onChange={(e) => setCoachFeedbackTags((prev) => toggleOption(prev, tag, e.target.checked))}
                                />
                                {FEEDBACK_TAG_LABELS[tag] || tag}
                              </label>
                            ))}
                          </div>
                          {suggestedFeedbackTags.length > 0 && (
                            <div style={{ marginTop: 6 }}>
                              <span className="badge info">Suggested from diagnostics: {suggestedFeedbackTags.map((t) => FEEDBACK_TAG_LABELS[t] || t).join(", ")}</span>
                              <button style={{ marginLeft: 8 }} onClick={() => setCoachFeedbackTags((prev) => Array.from(new Set([...prev, ...suggestedFeedbackTags])))}>Apply suggested tags</button>
                            </div>
                          )}
                        </div>
                        {reviewPromptDraft && <div style={{ marginTop: 6, fontSize: 11, color: "var(--color-text-muted)" }}><strong>Prompt draft:</strong> {reviewPromptDraft}</div>}
                        <div style={{ marginTop: 8, fontSize: 12 }}>
                          <strong>Regenerate recipes</strong>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
                            {REGENERATE_RECIPES.map((recipe) => (
                              <button key={recipe.id} type="button" className="btn-primary" onClick={() => applyRegenerateRecipe(recipe.id)} disabled={generationState.running}>
                                {generationState.running ? "Regenerating..." : recipe.label}
                              </button>
                            ))}
                          </div>
                        </div>
                        <textarea
                          value={coachNotes}
                          onChange={(e) => setCoachNotes(e.target.value)}
                          placeholder={reviewPromptDraft || "Add coaching notes, feedback highlights, and next actions..."}
                          style={{ width: "100%", minHeight: 80, marginTop: 6 }}
                        />
                        {quickActionState.running && <div style={{ marginTop: 6 }}><span className="badge info">Running quick action…</span></div>}
                        {quickActionState.message && <div style={{ marginTop: 6 }}><span className="badge success">{quickActionState.message}</span></div>}
                        {quickActionState.error && <div style={{ marginTop: 6 }}><span className="badge error">{quickActionState.error}</span></div>}
                        {quickActionState.launchToken && (
                          <div style={{ marginTop: 6, fontSize: 11, color: "var(--color-text-muted)" }}>
                            Launch token (preview): <code>{quickActionState.launchToken.slice(0, 24)}…</code>
                          </div>
                        )}
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

          </>
          )}

          {showIntake && (
          <>
          <h4>Coaching Project Intake</h4>
          <div className="card" style={{ marginBottom: 10 }}>
            <div style={{ marginBottom: 8, fontSize: 12, color: "var(--color-text-muted)" }}>
              Complete each section to generate a coaching-ready project package.
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
            {(generationState.sourceMode || generationState.quality) && (
              <div className="card" style={{ padding: 8, marginBottom: 8, fontSize: 12 }}>
                {generationState.sourceMode === "fallback" && (
                  <div style={{ marginBottom: 4 }}>
                    Fallback explanation: LLM provider was unavailable or returned an invalid payload, so a safe scaffold was used.
                  </div>
                )}
                {generationState.quality && (
                  <div style={{ display: "grid", gap: 4 }}>
                    <div>Quality score: <strong>{String(generationState.quality.score ?? "n/a")}</strong></div>
                    <div>Quality band: <strong>{String(generationState.quality.band ?? "n/a")}</strong></div>
                    <div>Structure score: <strong>{String(generationState.quality.structure_score ?? "n/a")}</strong></div>
                    <div>Section order valid: <strong>{generationState.quality.section_order_valid === false ? "no" : "yes"}</strong></div>
                    <div>
                      Regenerate delta: <strong>{String(generationState.quality.quality_delta ?? "n/a")}</strong>
                      {typeof generationState.quality.score === "number" && typeof generationState.quality.quality_delta === "number" && (
                        <span> (before {generationState.quality.score - generationState.quality.quality_delta} → after {generationState.quality.score})</span>
                      )}
                    </div>
                    {generationState.quality?.quality_diagnostics && (
                      <>
                        <div>Quality floor: <strong>{String(generationState.quality.quality_diagnostics.floor_score ?? "n/a")}</strong></div>
                        <div>Auto-regenerated for floor: <strong>{generationState.quality.quality_diagnostics.auto_regenerated ? "yes" : "no"}</strong></div>
                        <div>Deficiency count: <strong>{String(generationState.quality.quality_diagnostics.deficiency_count ?? 0)}</strong></div>
                        {qualityFailureReasons.length > 0 && (
                          <div>
                            Clear fail reasons:
                            <ul style={{ margin: "4px 0 0 18px" }}>
                              {qualityFailureReasons.map((reason, idx) => (
                                <li key={`quality-fail-reason-${idx}`}>{reason}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {qualityActionableReasons.length > 0 && (
                          <div style={{ marginTop: 6 }}>
                            Actionable fixes (one-click):
                            <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                              {qualityActionableReasons.map((item, idx) => (
                                <div key={`quality-actionable-${idx}`} className="card" style={{ padding: 8, border: "1px solid var(--color-border-strong)" }}>
                                  <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                                    <span className="badge warning">{item.code}</span>
                                    <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Field: {item.field}</span>
                                  </div>
                                  <div style={{ marginTop: 4 }}>{item.reason}</div>
                                  <div style={{ marginTop: 4, fontSize: 12, color: "var(--color-text-muted)" }}><strong>Suggested fix:</strong> {item.suggested_fix}</div>
                                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                                    <button type="button" onClick={() => setViewerTab(item.targetTab)}>{viewerTabCtaLabel(item.targetTab)}</button>
                                    <button type="button" className="btn-primary" onClick={() => applyActionableFixAndRegenerate(item)} disabled={generationState.running}>
                                      {generationState.running ? "Regenerating..." : `Apply fix + regenerate (${item.code})`}
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {Array.isArray(generationState.quality.missing_sections) && generationState.quality.missing_sections.length > 0 && (
                          <div>
                            Missing sections:
                            <ul style={{ margin: "4px 0 0 18px" }}>
                              {generationState.quality.missing_sections.map((section: string, idx: number) => (
                                <li key={`missing-section-${idx}`}>{section}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {Array.isArray(generationState.quality.quality_diagnostics.deficiency_codes) && generationState.quality.quality_diagnostics.deficiency_codes.length > 0 && (
                          <div>
                            Deficiency codes: {generationState.quality.quality_diagnostics.deficiency_codes.slice(0, 6).map((code: string) => (
                              <span key={code} className="badge warning" style={{ marginLeft: 6 }}>{code}</span>
                            ))}
                          </div>
                        )}
                        {Array.isArray(generationState.quality.quality_diagnostics.top_deficiencies) && generationState.quality.quality_diagnostics.top_deficiencies.length > 0 && (
                          <div>
                            Top deficiencies:
                            <ul style={{ margin: "4px 0 0 18px" }}>
                              {generationState.quality.quality_diagnostics.top_deficiencies.slice(0, 3).map((msg: string, idx: number) => (
                                <li key={`quality-def-${idx}`}>{msg}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {qualityGuidance.length > 0 && (
                          <div>
                            Regenerate guidance:
                            <ul style={{ margin: "4px 0 0 18px" }}>
                              {qualityGuidance.map((msg, idx) => (
                                <li key={`quality-guidance-${idx}`}>{msg}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            )}

            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Candidate Name</label>
            <input value={draft.candidateName} onChange={(e) => setDraft((prev) => ({ ...prev, candidateName: e.target.value }))} placeholder="Chris Gambill" style={{ marginBottom: 6 }} />

            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Candidate Email</label>
            <input value={draft.candidateEmail} onChange={(e) => setDraft((prev) => ({ ...prev, candidateEmail: e.target.value }))} placeholder="candidate@email.com" style={{ marginBottom: 6 }} />

            <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Target Role</label>
            <input value={draft.targetRole} onChange={(e) => setDraft((prev) => ({ ...prev, targetRole: e.target.value }))} placeholder="Senior Data Engineer" style={{ marginBottom: 8 }} />

            {activeStep === "resume" && (
              <div style={{ display: "grid", gap: 8 }}>
                <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Resume upload + highlights</label>
                <div
                  className="resume-dropzone"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const file = e.dataTransfer.files?.[0];
                    if (file) processResumeFile(file);
                  }}
                >
                  <div style={{ fontWeight: 600 }}>Drag and drop resume here</div>
                  <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>or</div>
                  <button type="button" onClick={() => resumeFileInputRef.current?.click()}>Choose file</button>
                  <input
                    ref={resumeFileInputRef}
                    type="file"
                    accept=".txt,.md,.doc,.docx,.pdf"
                    style={{ display: "none" }}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) processResumeFile(file);
                    }}
                  />
                  <div style={{ fontSize: 12 }}>Selected: <strong>{draft.resumeFileName || "none"}</strong></div>
                </div>

                <div style={{ display: "grid", gap: 4 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <span>Upload + parse status</span>
                    <span>{resumeUploadState.progress}%</span>
                  </div>
                  <div className="resume-progress-track"><span style={{ width: `${resumeUploadState.progress}%` }} /></div>
                  {resumeUploadState.message && <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{resumeUploadState.message}</div>}
                </div>

                {(resumeUploadState.phase === "ready" || draft.resumeHighlights.some((h) => h.trim())) && (
                  <div className="card" style={{ padding: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                      <strong style={{ fontSize: 12 }}>Resume parse confidence</strong>
                      <span className={`badge ${resumeConfidenceBand.tone}`}>{resumeConfidenceBand.label} ({resumeParseConfidence}%)</span>
                    </div>
                    <div style={{ marginTop: 6, fontSize: 11, color: "var(--color-text-muted)" }}>{resumeConfidenceBand.guidance}</div>
                    <div style={{ marginTop: 6, fontSize: 11, color: "var(--color-text-muted)" }}>
                      Confidence factors: highlights ({draft.resumeHighlights.filter((x) => x.trim()).length}) + strengths ({resumeStrengthSignals.filter((x) => x.trim()).length}) + gaps penalty ({resumeGapSignals.filter((x) => x.trim()).length > 0 ? "applied" : "none"}).
                    </div>
                    <div className="coaching-input-grid" style={{ marginTop: 8 }}>
                      <div>
                        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: 4 }}><strong>Editable strengths</strong></div>
                        <div style={{ display: "grid", gap: 6 }}>
                          {resumeStrengthSignals.length ? resumeStrengthSignals.map((signal, idx) => (
                            <div key={`resume-strength-${idx}`} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 6 }}>
                              <input
                                value={signal}
                                onChange={(e) => setResumeStrengthSignals((prev) => prev.map((item, i) => i === idx ? e.target.value : item))}
                              />
                              <button type="button" onClick={() => setResumeStrengthSignals((prev) => prev.filter((_, i) => i !== idx))}>Remove</button>
                            </div>
                          )) : <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>No strengths extracted yet.</div>}
                          <button type="button" onClick={() => setResumeStrengthSignals((prev) => [...prev, ""])}>Add strength signal</button>
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: 4 }}><strong>Editable gaps to close</strong></div>
                        <div style={{ display: "grid", gap: 6 }}>
                          {resumeGapSignals.length ? resumeGapSignals.map((signal, idx) => (
                            <div key={`resume-gap-${idx}`} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 6 }}>
                              <input
                                value={signal}
                                onChange={(e) => setResumeGapSignals((prev) => prev.map((item, i) => i === idx ? e.target.value : item))}
                              />
                              <button type="button" onClick={() => setResumeGapSignals((prev) => prev.filter((_, i) => i !== idx))}>Remove</button>
                            </div>
                          )) : <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>No obvious gaps detected.</div>}
                          <button type="button" onClick={() => setResumeGapSignals((prev) => [...prev, ""])}>Add gap to close</button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                <div className="card" style={{ padding: 10, border: "1px solid var(--color-border-strong)" }}>
                  <strong style={{ fontSize: 12 }}>Intake mapping preview</strong>
                  <div style={{ marginTop: 4, fontSize: 11, color: "var(--color-text-muted)" }}>What reviewers will see from your resume profile payload.</div>
                  <div style={{ marginTop: 6, fontSize: 12 }}><strong>Strength signals:</strong> {resumeStrengthSignals.filter((x) => x.trim()).length || 0}</div>
                  <div style={{ marginTop: 2, fontSize: 12 }}><strong>Gap signals:</strong> {resumeGapSignals.filter((x) => x.trim()).length || 0}</div>
                  <div style={{ marginTop: 2, fontSize: 12 }}><strong>Highlight bullets:</strong> {draft.resumeHighlights.filter((x) => x.trim()).length || 0}</div>
                  {buildCombinedProfile(draft) && <div style={{ marginTop: 6, fontSize: 11, color: "var(--color-text-muted)", whiteSpace: "pre-wrap" }}>{buildCombinedProfile(draft)}</div>}
                </div>

                <div className="card" style={{ padding: 10 }}>
                  <strong style={{ fontSize: 12 }}>Editable parsed highlights</strong>
                  <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4 }}>Tune these before submit so reviewers see the strongest evidence.</div>
                  <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
                    {draft.resumeHighlights.map((highlight, idx) => (
                      <div key={`resume-highlight-${idx}`} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 6 }}>
                        <input
                          value={highlight}
                          onChange={(e) => setDraft((prev) => ({ ...prev, resumeHighlights: prev.resumeHighlights.map((item, i) => i === idx ? e.target.value : item) }))}
                          placeholder="Led migration to lakehouse and reduced latency by 38%"
                        />
                        <button
                          type="button"
                          onClick={() => setDraft((prev) => ({ ...prev, resumeHighlights: prev.resumeHighlights.length <= 1 ? [""] : prev.resumeHighlights.filter((_, i) => i !== idx) }))}
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                  <button type="button" style={{ marginTop: 8 }} onClick={() => setDraft((prev) => ({ ...prev, resumeHighlights: [...prev.resumeHighlights, ""] }))}>Add highlight</button>
                </div>
              </div>
            )}

            {activeStep === "selfAssessment" && (
              <div style={{ display: "grid", gap: 8 }}>
                <div className="card" style={{ padding: 8 }}>
                  <strong style={{ fontSize: 12 }}>Career Goals</strong>
                  <div className="coaching-input-grid" style={{ marginTop: 6 }}>
                    <input value={draft.questionnaire.careerGoal} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, careerGoal: e.target.value } }))} placeholder="Target role and outcome in the next 6-12 months" />
                    <input value={draft.questionnaire.roleTimeline} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, roleTimeline: e.target.value } }))} placeholder="Promotion/job-switch timeline" />
                  </div>
                </div>

                <div className="card" style={{ padding: 8 }}>
                  <strong style={{ fontSize: 12 }}>Background</strong>
                  <div className="coaching-input-grid" style={{ marginTop: 6 }}>
                    <input value={draft.questionnaire.currentBackground} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, currentBackground: e.target.value } }))} placeholder="Current role + years of experience" />
                    <input value={draft.questionnaire.deliveryExamples} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, deliveryExamples: e.target.value } }))} placeholder="Recent projects you shipped" />
                  </div>
                </div>

                <div className="card" style={{ padding: 8 }}>
                  <strong style={{ fontSize: 12 }}>Skills Confidence</strong>
                  <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                    <label style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 8, alignItems: "center", fontSize: 12 }}><span>SQL confidence</span><select value={draft.questionnaire.confidenceSql} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, confidenceSql: e.target.value } }))}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label>
                    <label style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 8, alignItems: "center", fontSize: 12 }}><span>Data modeling confidence</span><select value={draft.questionnaire.confidenceModeling} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, confidenceModeling: e.target.value } }))}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label>
                    <label style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 8, alignItems: "center", fontSize: 12 }}><span>Orchestration confidence</span><select value={draft.questionnaire.confidenceOrchestration} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, confidenceOrchestration: e.target.value } }))}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label>
                    <label style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 8, alignItems: "center", fontSize: 12 }}><span>Stakeholder comms confidence</span><select value={draft.questionnaire.confidenceStakeholder} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, confidenceStakeholder: e.target.value } }))}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label>
                  </div>
                </div>

                <div className="card" style={{ padding: 8 }}>
                  <strong style={{ fontSize: 12 }}>Tools + Platform Exposure</strong>
                  <div style={{ display: "grid", gap: 8, marginTop: 6, fontSize: 12 }}>
                    <div>
                      <div style={{ marginBottom: 4, color: "var(--color-text-muted)" }}>Platforms used</div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        {PLATFORM_EXPOSURE_OPTIONS.map((option) => <label key={`platform-exp-${option}`} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><input type="checkbox" checked={draft.questionnaire.platformExposure.includes(option)} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, platformExposure: toggleOption(prev.questionnaire.platformExposure, option, e.target.checked) } }))} />{option}</label>)}
                        <label style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><input type="checkbox" checked={draft.questionnaire.platformExposure.includes("Other")} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, platformExposure: toggleOption(prev.questionnaire.platformExposure, "Other", e.target.checked), platformExposureOther: e.target.checked ? prev.questionnaire.platformExposureOther : "" } }))} />Other</label>
                      </div>
                      {draft.questionnaire.platformExposure.includes("Other") && <input style={{ marginTop: 6 }} value={draft.questionnaire.platformExposureOther} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, platformExposureOther: e.target.value } }))} placeholder="Other platform(s)" />}
                    </div>
                    <div>
                      <div style={{ marginBottom: 4, color: "var(--color-text-muted)" }}>Tools used</div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        {TOOL_EXPOSURE_OPTIONS.map((option) => <label key={`tool-exp-${option}`} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><input type="checkbox" checked={draft.questionnaire.toolExposure.includes(option)} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, toolExposure: toggleOption(prev.questionnaire.toolExposure, option, e.target.checked) } }))} />{option}</label>)}
                        <label style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><input type="checkbox" checked={draft.questionnaire.toolExposure.includes("Other")} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, toolExposure: toggleOption(prev.questionnaire.toolExposure, "Other", e.target.checked), toolExposureOther: e.target.checked ? prev.questionnaire.toolExposureOther : "" } }))} />Other</label>
                      </div>
                      {draft.questionnaire.toolExposure.includes("Other") && <input style={{ marginTop: 6 }} value={draft.questionnaire.toolExposureOther} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, toolExposureOther: e.target.value } }))} placeholder="Other tool(s)" />}
                    </div>
                  </div>
                </div>

                <div className="card" style={{ padding: 8 }}>
                  <strong style={{ fontSize: 12 }}>Portfolio + Interview Readiness</strong>
                  <div className="coaching-input-grid" style={{ marginTop: 6 }}>
                    <select value={draft.questionnaire.portfolioReadiness} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, portfolioReadiness: e.target.value } }))}><option>Not started</option><option>In progress</option><option>Ready to showcase</option></select>
                    <select value={draft.questionnaire.interviewReadiness} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, interviewReadiness: e.target.value } }))}><option>Not started</option><option>Practicing</option><option>Interview ready</option></select>
                  </div>
                </div>

                <div className="card" style={{ padding: 8 }}>
                  <strong style={{ fontSize: 12 }}>Constraints + Support</strong>
                  <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4 }}>Use concrete numbers so coaching plans and milestones are scoped realistically.</div>
                  <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                    <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Hours available per week</label>
                    <input value={draft.questionnaire.weeklyHours} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, weeklyHours: e.target.value } }))} placeholder="e.g., 6" />
                    <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Target timeline (weeks)</label>
                    <input value={draft.questionnaire.timelineWeeks} onChange={(e) => setTimelineWeeks(e.target.value)} placeholder="e.g., 8" />
                    <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Support needed from coach</label>
                    <input value={draft.questionnaire.supportNeeded} onChange={(e) => setDraft((prev) => ({ ...prev, questionnaire: { ...prev.questionnaire, supportNeeded: e.target.value } }))} placeholder="e.g., architecture reviews, interview drills, accountability" />
                  </div>
                </div>
              </div>
            )}

            {activeStep === "jobLinks" && (
              <>
                <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Job Posting URLs (5-10 links)</label>
                <div className="coaching-input-grid" style={{ marginTop: 4 }}>
                  {draft.jobLinks.map((link, idx) => {
                    const safety = safeExternalUrl(link);
                    return <div key={idx}><input value={link} onChange={(e) => setDraft((prev) => ({ ...prev, jobLinks: prev.jobLinks.map((v, i) => i === idx ? e.target.value : v) }))} placeholder={`https://company.com/jobs/${idx + 1}`} />{link.trim() && !safety.safe && <div style={{ fontSize: 11, color: "#b45309" }}>Use full http/https URL.</div>}</div>;
                  })}
                </div>
              </>
            )}

            {activeStep === "preferences" && (
              <>
                <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Platforms</label>
                <div>{PLATFORM_OPTIONS.map((option) => <label key={option} style={{ display: "inline-flex", marginRight: 8 }}><input type="checkbox" checked={draft.selectedPlatforms.includes(option)} onChange={(e) => setDraft((prev) => ({ ...prev, selectedPlatforms: e.target.checked ? [...prev.selectedPlatforms, option] : prev.selectedPlatforms.filter((x) => x !== option) }))} />{option}</label>)}</div>
                <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Tools</label>
                <div>{TOOL_OPTIONS.map((option) => <label key={option} style={{ display: "inline-flex", marginRight: 8 }}><input type="checkbox" checked={draft.selectedTools.includes(option)} onChange={(e) => setDraft((prev) => ({ ...prev, selectedTools: e.target.checked ? [...prev.selectedTools, option] : prev.selectedTools.filter((x) => x !== option) }))} />{option}</label>)}</div>
                <label style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Timeline target</label>
                <select value={draft.timelineWeeks} onChange={(e) => setTimelineWeeks(e.target.value)}><option value="4">4 weeks</option><option value="6">6 weeks</option><option value="8">8 weeks</option><option value="12">12 weeks</option></select>
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

          </>
          )}

          {showOutputViewer && (
          <>
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

                <div className="card" style={{ padding: 10, marginBottom: 10 }}>
                  <div style={{ fontSize: 13, marginBottom: 6 }}><strong>Executive Summary</strong>: {scaffold.executiveSummary}</div>
                  <div style={{ fontSize: 12, marginBottom: 6 }}><strong>Business Outcome</strong>: {scaffold.businessOutcome}</div>
                  <div style={{ fontSize: 12 }}><strong>Milestones</strong>: {scaffold.milestones.map((m) => m.title).join(" • ")}</div>
                </div>

                <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
                  <button onClick={() => setViewerTab("charter")}>Project Charter</button>
                  <button onClick={() => setViewerTab("summary")}>Executive Summary</button>
                  <button onClick={() => setViewerTab("dataSources")}>Data Sources + Ingestion</button>
                  <button onClick={() => setViewerTab("architecture")}>Architecture</button>
                  <button onClick={() => setViewerTab("milestones")}>Milestone Cards</button>
                  <button onClick={() => setViewerTab("story")}>Story Narrative</button>
                  <button onClick={() => setViewerTab("roi")}>ROI Dashboard</button>
                  <button onClick={() => setViewerTab("resources")}>Resource Links by Step</button>
                  <button onClick={() => setViewerTab("interview")}>Interview Artifacts</button>
                </div>

                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
                  {qualityBadges.map((badge) => (
                    <span key={badge.label} className={`badge ${badge.pass ? "success" : "warning"}`}>
                      {badge.pass ? "✓" : "!"} {badge.label}
                    </span>
                  ))}
                </div>

                {viewerTab === "charter" && (
                  <div style={{ display: "grid", gap: 10 }}>
                    <div className="card" style={{ padding: 12, border: "1px solid var(--color-border-strong)" }}>
                      <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--color-text-muted)" }}>Business story</div>
                      <div style={{ fontSize: 15, lineHeight: 1.65, marginTop: 4 }}>{scaffold.storyNarrative[0] || scaffold.executiveSummary}</div>
                      <div style={{ fontSize: 13, marginTop: 8 }}><strong>Why now:</strong> {scaffold.storyNarrative[1] || scaffold.businessOutcome}</div>
                      <div style={{ fontSize: 13, marginTop: 4 }}><strong>What success looks like:</strong> {scaffold.storyNarrative[2] || scaffold.businessOutcome}</div>
                    </div>
                    <div className="coaching-input-grid">
                      <div className="card" style={{ padding: 12 }}>
                        <div style={{ fontSize: 11, textTransform: "uppercase", color: "var(--color-text-muted)" }}>Candidate profile</div>
                        <div style={{ marginTop: 4, fontSize: 13, lineHeight: 1.5 }}>{scaffold.candidateSnapshot}</div>
                      </div>
                      <div className="card" style={{ padding: 12 }}>
                        <div style={{ fontSize: 11, textTransform: "uppercase", color: "var(--color-text-muted)" }}>Business outcome</div>
                        <div style={{ marginTop: 4, fontSize: 13, lineHeight: 1.5 }}>{scaffold.businessOutcome}</div>
                      </div>
                    </div>
                  </div>
                )}

                {viewerTab === "summary" && (
                  <div className="card" style={{ padding: 10, background: "rgba(120,120,255,0.05)" }}>
                    <div style={{ fontSize: 14, marginBottom: 8, lineHeight: 1.5 }}>{scaffold.executiveSummary}</div>
                    <div style={{ fontSize: 13, marginBottom: 6 }}><strong>Candidate Snapshot:</strong> {scaffold.candidateSnapshot}</div>
                    <div style={{ fontSize: 13 }}><strong>Business Outcome:</strong> {scaffold.businessOutcome}</div>
                  </div>
                )}

                {viewerTab === "dataSources" && (
                  <div style={{ display: "grid", gap: 10 }}>
                    <div className="card" style={{ padding: 10, border: "1px solid var(--color-border-strong)", background: "color-mix(in srgb, var(--panel-bg) 88%, #10b981 12%)" }}>
                      <strong>Ingestion instruction block</strong>
                      <div style={{ fontSize: 12, marginTop: 6 }}>For each source, clarify why it exists + exactly how it enters Bronze so reviewers can validate feasibility fast.</div>
                    </div>
                    {scaffold.dataSources.map((source, idx) => (
                      <div key={`${source.name}-${source.link || "nolink"}`} className="card" style={{ padding: 10 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap", fontSize: 13 }}>
                          <strong>{idx + 1}. {source.name}</strong>
                          <span className="badge info">{source.type}</span>
                        </div>
                        <div style={{ fontSize: 12, marginTop: 6 }}><strong>Why this source matters:</strong> {source.note}</div>
                        <div style={{ fontSize: 12, marginTop: 8 }}><strong>Ingestion steps:</strong></div>
                        <ol style={{ margin: "4px 0 0 18px", padding: 0, fontSize: 12, display: "grid", gap: 2 }}>
                          <li>Confirm source owner + access method.</li>
                          <li>Document cadence + SLA target.</li>
                          <li>Land raw payload in Bronze with schema drift handling.</li>
                          <li>Route failures to alert channel and runbook owner.</li>
                        </ol>
                        <div style={{ fontSize: 12, marginTop: 6 }}>
                          {source.link ? (() => { const safety = safeExternalUrl(source.link); return safety.safe ? <a href={safety.normalized} target="_blank" rel="noreferrer">{source.link}</a> : <span>{source.link} <span className="badge warning">Blocked unsafe link ({safety.reason})</span></span>; })() : <span style={{ color: "var(--color-text-muted)" }}>No external link provided</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {viewerTab === "milestones" && (
                  <div style={{ display: "grid", gap: 10 }}>
                    {scaffold.milestones.map((m, idx) => (
                      <div key={m.title} className="card milestone-card" style={{ padding: 12 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                          <strong>{m.title}</strong>
                          <span className="badge info">Step {idx + 1} of {scaffold.milestones.length}</span>
                        </div>
                        <div style={{ fontSize: 13, marginTop: 6, lineHeight: 1.5 }}>{m.outcome}</div>
                        <div style={{ marginTop: 8, fontSize: 12 }}><strong>Expectations</strong></div>
                        <ul style={{ margin: "4px 0 0 18px", padding: 0, fontSize: 12 }}>
                          {m.expectations.map((item, expIdx) => <li key={`${m.title}-exp-${expIdx}`}>{item}</li>)}
                        </ul>
                        <div style={{ marginTop: 8, fontSize: 12 }}><strong>Deliverables</strong></div>
                        <ul style={{ margin: "4px 0 0 18px", padding: 0, fontSize: 12 }}>
                          {m.deliverables.map((item) => <li key={item}>{item}</li>)}
                        </ul>
                        <div style={{ marginTop: 8, fontSize: 12 }}><strong>Acceptance checks</strong></div>
                        <ul style={{ margin: "4px 0 0 18px", padding: 0, fontSize: 12 }}>
                          {m.acceptanceChecks.map((item, accIdx) => <li key={`${m.title}-acc-${accIdx}`}>{item}</li>)}
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

                {viewerTab === "interview" && (
                  <div style={{ display: "grid", gap: 8 }}>
                    <div className="card" style={{ padding: 8 }}>
                      <strong>STAR Stories</strong>
                      <div style={{ display: "grid", gap: 6, marginTop: 6, fontSize: 12 }}>
                        {scaffold.interviewArtifacts.starStories.map((s, idx) => (
                          <div key={`star-${idx}`} style={{ borderLeft: "2px solid var(--color-border-strong)", paddingLeft: 8 }}>
                            <div><strong>S:</strong> {s.situation}</div>
                            <div><strong>T:</strong> {s.task}</div>
                            <div><strong>A:</strong> {s.action}</div>
                            <div><strong>R:</strong> {s.result}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="card" style={{ padding: 8 }}>
                      <strong>Portfolio Checklist</strong>
                      <ul style={{ margin: "6px 0 0 18px", padding: 0, fontSize: 12 }}>
                        {scaffold.interviewArtifacts.portfolioChecklist.map((item) => <li key={item}>{item}</li>)}
                      </ul>
                    </div>
                    <div className="card" style={{ padding: 8 }}>
                      <strong>Recruiter Mapping</strong>
                      <ul style={{ margin: "6px 0 0 18px", padding: 0, fontSize: 12 }}>
                        {scaffold.interviewArtifacts.recruiterMapping.map((row, idx) => <li key={`map-${idx}`}><strong>{row.requirement}:</strong> {row.evidence}</li>)}
                      </ul>
                    </div>
                  </div>
                )}

                {viewerTab === "resources" && (
                  <div style={{ display: "grid", gap: 8 }}>
                    {scaffold.resourceLinksByStep.map((step) => (
                      <div key={step.stepTitle} className="card" style={{ padding: 8 }}>
                        <strong>{step.stepTitle}</strong>
                        <ul style={{ margin: "6px 0 0 18px", padding: 0, fontSize: 12 }}>
                          {step.resources.map((resource) => {
                            const safety = safeExternalUrl(resource.url);
                            return (
                              <li key={resource.url}>
                                {safety.safe ? <a href={safety.normalized} target="_blank" rel="noreferrer">{resource.title}</a> : <span>{resource.title} <span className="badge warning">Blocked unsafe link ({safety.reason})</span></span>} ({resource.type}) — {resource.reason}
                              </li>
                            );
                          })}
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
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                          <button
                            className="btn-primary"
                            disabled={!canBookMentoring}
                            onClick={() => {
                              trackConversionEvent({ name: "mentoring_cta_clicked", workspaceId: draft.workspaceId, submissionId: currentSubmissionId || undefined, planTier });
                              trackConversionEvent({ name: "coaching_plan_checkout_clicked", workspaceId: draft.workspaceId, submissionId: currentSubmissionId || undefined, planTier, details: { offer: scaffold.mentoringCta.offer } });
                            }}
                          >
                            {canBookMentoring ? scaffold.mentoringCta.ctaText : "Elite required"}
                          </button>
                          <a
                            href={DISCORD_COMMUNITY_URL}
                            target="_blank"
                            rel="noreferrer"
                            onClick={() => trackConversionEvent({ name: "discord_cta_clicked", workspaceId: draft.workspaceId, submissionId: currentSubmissionId || undefined, planTier, details: { location: "mentoring_recommendation" } })}
                            style={{ alignSelf: "center", fontSize: 12 }}
                          >
                            Join Discord coaching channel
                          </a>
                        </div>
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
        </>
      )}
    </div>
  );
}
