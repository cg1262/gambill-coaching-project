export type RateLimitUiConfig = {
  defaultRetrySeconds: number;
  helperMessage: string;
};

export const RATE_LIMIT_CONFIG_STORAGE_KEY = "coaching.rateLimitUiConfig.v1";

export const DEFAULT_RATE_LIMIT_UI_CONFIG: RateLimitUiConfig = {
  defaultRetrySeconds: 30,
  helperMessage: "If retries keep failing, wait a minute, then try again or contact support with the exact action.",
};

export function loadRateLimitUiConfig(): RateLimitUiConfig {
  if (typeof window === "undefined") return DEFAULT_RATE_LIMIT_UI_CONFIG;
  try {
    const raw = window.localStorage.getItem(RATE_LIMIT_CONFIG_STORAGE_KEY);
    if (!raw) return DEFAULT_RATE_LIMIT_UI_CONFIG;
    const parsed = JSON.parse(raw) as Partial<RateLimitUiConfig>;
    return {
      defaultRetrySeconds:
        Number.isFinite(parsed.defaultRetrySeconds) && Number(parsed.defaultRetrySeconds) > 0
          ? Number(parsed.defaultRetrySeconds)
          : DEFAULT_RATE_LIMIT_UI_CONFIG.defaultRetrySeconds,
      helperMessage:
        typeof parsed.helperMessage === "string" && parsed.helperMessage.trim().length > 0
          ? parsed.helperMessage.trim()
          : DEFAULT_RATE_LIMIT_UI_CONFIG.helperMessage,
    };
  } catch {
    return DEFAULT_RATE_LIMIT_UI_CONFIG;
  }
}

export function saveRateLimitUiConfig(config: RateLimitUiConfig): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(RATE_LIMIT_CONFIG_STORAGE_KEY, JSON.stringify(config));
}
