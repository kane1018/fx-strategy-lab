// Pure presentation/data helpers for the read-only reports list UI (docs §15).
// Kept free of JSX/DOM so they are unit-testable under the existing node-env Vitest.

import type { ReportIndexItem, ReportsResponse } from "@/types/reports";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type SafetyBadgeId =
  | "SAFE_READ_ONLY"
  | "ERROR"
  | "SAFETY_CONFLICT"
  | "SAFETY_INCOMPLETE"
  | "UNCONFIRMED";

export type SafetyBadge = {
  id: SafetyBadgeId;
  label: string;
  safe: boolean;
};

// docs §15-7 priority: ERROR > CONFLICT > INCOMPLETE > UNCONFIRMED > SAFE_READ_ONLY.
// Only SAFE_READ_ONLY is treated as safe; unknown/partial state is never "safe".
export function safetyBadge(item: ReportIndexItem): SafetyBadge {
  if (item.has_error) {
    return { id: "ERROR", label: "Error", safe: false };
  }
  if (item.safety_conflicts && item.safety_conflicts.length > 0) {
    return { id: "SAFETY_CONFLICT", label: "Safety conflict", safe: false };
  }
  if (item.safety_complete === false) {
    return { id: "SAFETY_INCOMPLETE", label: "Safety incomplete", safe: false };
  }
  if (item.read_only_confirmed !== true) {
    return { id: "UNCONFIRMED", label: "Unconfirmed", safe: false };
  }
  return { id: "SAFE_READ_ONLY", label: "Read-only確認済み", safe: true };
}

// Fixed-decimal display for headline metrics; "-" for null/undefined/NaN.
export function fmtNum(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(digits);
}

export function fmtText(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return value;
}

export type FetchReportsResult =
  | { status: "success"; data: ReportsResponse }
  | { status: "unavailable" } // 503: reports root not configured / missing
  | { status: "error"; message: string };

// Read-only fetch of the run list. Maps 503 to a distinct "unavailable" state so
// the UI can show the "reports root not set" message (docs §15-4).
export async function fetchReports(
  fetchImpl: typeof fetch = fetch
): Promise<FetchReportsResult> {
  try {
    const response = await fetchImpl(`${API_BASE}/api/reports`, {
      headers: { "Content-Type": "application/json" }
    });
    if (response.status === 503) {
      return { status: "unavailable" };
    }
    if (!response.ok) {
      return { status: "error", message: `API error: ${response.status}` };
    }
    const data = (await response.json()) as ReportsResponse;
    return { status: "success", data };
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown error";
    return { status: "error", message };
  }
}
