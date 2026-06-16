import { describe, expect, it } from "vitest";

import type { ReportIndexItem } from "@/types/reports";
import { fetchReports, fmtNum, fmtText, safetyBadge } from "./reports";

const okItem: ReportIndexItem = {
  run_id: "run_a",
  read_only_confirmed: true,
  safety_complete: true,
  safety_conflicts: [],
  has_error: false
};

describe("safetyBadge", () => {
  it("returns SAFE_READ_ONLY only when confirmed and no conflicts", () => {
    const badge = safetyBadge(okItem);
    expect(badge.id).toBe("SAFE_READ_ONLY");
    expect(badge.safe).toBe(true);
  });

  it("error rows are never safe", () => {
    expect(safetyBadge({ ...okItem, has_error: true }).id).toBe("ERROR");
    expect(safetyBadge({ ...okItem, has_error: true }).safe).toBe(false);
  });

  it("conflict beats incomplete/unconfirmed and is not safe", () => {
    const badge = safetyBadge({
      ...okItem,
      read_only_confirmed: false,
      safety_complete: false,
      safety_conflicts: ["real_order"]
    });
    expect(badge.id).toBe("SAFETY_CONFLICT");
    expect(badge.safe).toBe(false);
  });

  it("incomplete safety is not safe", () => {
    expect(safetyBadge({ ...okItem, safety_complete: false }).id).toBe(
      "SAFETY_INCOMPLETE"
    );
  });

  it("unconfirmed read-only is not safe", () => {
    expect(safetyBadge({ ...okItem, read_only_confirmed: false }).id).toBe(
      "UNCONFIRMED"
    );
  });
});

describe("fmtNum / fmtText", () => {
  it("formats numbers to fixed decimals", () => {
    expect(fmtNum(0.123456, 4)).toBe("0.1235");
    expect(fmtNum(1.2, 2)).toBe("1.20");
  });

  it("renders missing values as dash", () => {
    expect(fmtNum(null, 4)).toBe("-");
    expect(fmtNum(undefined, 2)).toBe("-");
    expect(fmtText(null)).toBe("-");
    expect(fmtText("")).toBe("-");
    expect(fmtText("rsi_reversal")).toBe("rsi_reversal");
  });
});

describe("fetchReports", () => {
  const jsonResponse = (body: unknown, status = 200) =>
    ({
      status,
      ok: status >= 200 && status < 300,
      json: async () => body
    }) as Response;

  it("maps a successful response to success", async () => {
    const fake = async () =>
      jsonResponse({ items: [okItem], count: 1 });
    const result = await fetchReports(fake as typeof fetch);
    expect(result.status).toBe("success");
    if (result.status === "success") {
      expect(result.data.count).toBe(1);
    }
  });

  it("maps 503 to unavailable", async () => {
    const fake = async () => jsonResponse({ detail: {} }, 503);
    const result = await fetchReports(fake as typeof fetch);
    expect(result.status).toBe("unavailable");
  });

  it("maps other failures to error", async () => {
    const fake = async () => jsonResponse({ detail: "boom" }, 500);
    const result = await fetchReports(fake as typeof fetch);
    expect(result.status).toBe("error");
  });

  it("maps a network throw to error", async () => {
    const fake = async () => {
      throw new Error("network down");
    };
    const result = await fetchReports(fake as typeof fetch);
    expect(result.status).toBe("error");
    if (result.status === "error") {
      expect(result.message).toContain("network down");
    }
  });
});
