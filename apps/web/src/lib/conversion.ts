export type ConversionEventName =
  | "launch_path_viewed"
  | "launch_step_advanced"
  | "upgrade_cta_viewed"
  | "upgrade_cta_clicked"
  | "intake_submitted"
  | "sow_generate_clicked"
  | "sow_generate_completed"
  | "sow_regenerate_clicked"
  | "export_clicked"
  | "export_completed"
  | "mentoring_cta_clicked";

export type ConversionEvent = {
  name: ConversionEventName;
  workspaceId?: string;
  submissionId?: string;
  planTier?: string;
  source?: string;
  details?: Record<string, unknown>;
  at?: string;
};

const STORAGE_KEY = "coaching.conversion.events";

export function trackConversionEvent(event: ConversionEvent) {
  const payload = { ...event, at: event.at || new Date().toISOString() };
  if (typeof window === "undefined") return;
  try {
    const prior = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]");
    const next = Array.isArray(prior) ? [...prior, payload].slice(-300) : [payload];
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // no-op: telemetry should never break UX
  }
  // Keep console visibility for pilot launch verification.
  // eslint-disable-next-line no-console
  console.info("[conversion]", payload);
}
