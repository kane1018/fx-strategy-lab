import { describe, expect, it } from "vitest";

import type { ReportIndexItem } from "@/types/reports";
import {
  fetchReportDetail,
  fetchReportDetailMarkdown,
  fetchReports,
  fmtCompact,
  fmtNum,
  fmtText,
  safetyBadge
} from "./reports";

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

describe("fmtCompact", () => {
  it("renders missing values as dash", () => {
    expect(fmtCompact(null)).toBe("-");
    expect(fmtCompact(undefined)).toBe("-");
    expect(fmtCompact("")).toBe("-");
  });

  it("renders dict/list as compact JSON", () => {
    expect(fmtCompact({ median_expectancy: 0.1 })).toBe(
      '{"median_expectancy":0.1}'
    );
    expect(fmtCompact(["a", "b"])).toBe('["a","b"]');
  });

  it("renders scalars as strings", () => {
    expect(fmtCompact(9)).toBe("9");
    expect(fmtCompact(true)).toBe("true");
  });
});

describe("fetchReportDetail", () => {
  const jsonResponse = (body: unknown, status = 200) =>
    ({
      status,
      ok: status >= 200 && status < 300,
      json: async () => body
    }) as Response;

  it("maps a successful response to success", async () => {
    const fake = async () => jsonResponse({ run_id: "run_a", files: [] });
    const result = await fetchReportDetail("run_a", fake as typeof fetch);
    expect(result.status).toBe("success");
    if (result.status === "success") {
      expect(result.data.run_id).toBe("run_a");
    }
  });

  it("maps 400 to invalid", async () => {
    const fake = async () => jsonResponse({ detail: {} }, 400);
    expect((await fetchReportDetail("bad", fake as typeof fetch)).status).toBe(
      "invalid"
    );
  });

  it("maps 404 to not_found", async () => {
    const fake = async () => jsonResponse({ detail: {} }, 404);
    expect((await fetchReportDetail("x", fake as typeof fetch)).status).toBe(
      "not_found"
    );
  });

  it("maps 422 to broken", async () => {
    const fake = async () => jsonResponse({ detail: {} }, 422);
    expect((await fetchReportDetail("x", fake as typeof fetch)).status).toBe(
      "broken"
    );
  });

  it("maps 500 to error", async () => {
    const fake = async () => jsonResponse({ detail: "boom" }, 500);
    expect((await fetchReportDetail("x", fake as typeof fetch)).status).toBe(
      "error"
    );
  });

  it("maps a network throw to error", async () => {
    const fake = async () => {
      throw new Error("offline");
    };
    const result = await fetchReportDetail("x", fake as typeof fetch);
    expect(result.status).toBe("error");
  });

  it("URL-encodes the run_id in the request path", async () => {
    let calledWith = "";
    const fake = async (url: string | URL | Request) => {
      calledWith = String(url);
      return jsonResponse({ run_id: "a b", files: [] });
    };
    await fetchReportDetail("a b/c", fake as unknown as typeof fetch);
    expect(calledWith).toContain("/api/reports/a%20b%2Fc");
  });
});

describe("fetchReportDetailMarkdown", () => {
  const jsonResponse = (body: unknown, status = 200) =>
    ({
      status,
      ok: status >= 200 && status < 300,
      json: async () => body
    }) as Response;

  it("returns markdown string on success", async () => {
    const fake = async () => jsonResponse({ markdown: "# FX Report Detail: run_a" });
    const result = await fetchReportDetailMarkdown("run_a", fake as typeof fetch);
    expect(result.status).toBe("success");
    if (result.status === "success") {
      expect(result.markdown).toContain("FX Report Detail");
    }
  });

  it("maps 400 to invalid", async () => {
    const fake = async () => jsonResponse({ detail: {} }, 400);
    expect((await fetchReportDetailMarkdown("x", fake as typeof fetch)).status).toBe(
      "invalid"
    );
  });

  it("maps 404 to not_found", async () => {
    const fake = async () => jsonResponse({ detail: {} }, 404);
    expect((await fetchReportDetailMarkdown("x", fake as typeof fetch)).status).toBe(
      "not_found"
    );
  });

  it("maps 422 to broken", async () => {
    const fake = async () => jsonResponse({ detail: {} }, 422);
    expect((await fetchReportDetailMarkdown("x", fake as typeof fetch)).status).toBe(
      "broken"
    );
  });

  it("maps 500 to error", async () => {
    const fake = async () => jsonResponse({ detail: "boom" }, 500);
    expect((await fetchReportDetailMarkdown("x", fake as typeof fetch)).status).toBe(
      "error"
    );
  });

  it("maps a network throw to error", async () => {
    const fake = async () => {
      throw new Error("offline");
    };
    expect((await fetchReportDetailMarkdown("x", fake as typeof fetch)).status).toBe(
      "error"
    );
  });

  it("URL-encodes the run_id and targets /markdown", async () => {
    let calledWith = "";
    const fake = async (url: string | URL | Request) => {
      calledWith = String(url);
      return jsonResponse({ markdown: "ok" });
    };
    await fetchReportDetailMarkdown("a b/c", fake as unknown as typeof fetch);
    expect(calledWith).toContain("/api/reports/a%20b%2Fc/markdown");
  });
});
