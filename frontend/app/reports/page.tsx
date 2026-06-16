"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  fetchReports,
  fetchReportsMarkdown,
  fmtNum,
  fmtText,
  safetyBadge,
  type FetchReportsResult
} from "@/lib/reports";
import type { ReportIndexItem } from "@/types/reports";

const COLUMNS = [
  "status",
  "run_id",
  "kind",
  "strategy",
  "timeframe",
  "cost_scenario",
  "verdict",
  "median_expectancy",
  "median_pf",
  "total_pnl",
  "max_drawdown_max",
  "safety",
  "warnings",
  "created_at",
  "error"
];

function SafetyBadge({ item }: { item: ReportIndexItem }) {
  const badge = safetyBadge(item);
  return (
    <span data-testid="safety-badge" data-safe={badge.safe} className="safety-badge">
      {badge.label}
    </span>
  );
}

function ReportRow({ item }: { item: ReportIndexItem }) {
  const isError = item.has_error === true;
  const warnings = item.warnings_count ?? (item.has_warnings ? "yes" : 0);
  return (
    <tr
      data-testid={isError ? "error-row" : "report-row"}
      data-run-id={item.run_id}
      className={isError ? "report-row report-row-error" : "report-row"}
    >
      <td>{fmtText(item.status)}</td>
      <td>
        <Link href={`/reports/${item.run_id}`}>{item.run_id}</Link>
      </td>
      <td>{fmtText(item.kind)}</td>
      <td>{fmtText(item.strategy)}</td>
      <td>{fmtText(item.timeframe)}</td>
      <td>{fmtText(item.cost_scenario)}</td>
      <td>{fmtText(item.verdict)}</td>
      <td>{fmtNum(item.median_expectancy, 4)}</td>
      <td>{fmtNum(item.median_pf, 3)}</td>
      <td>{fmtNum(item.total_pnl, 2)}</td>
      <td>{fmtNum(item.max_drawdown_max, 2)}</td>
      <td>
        <SafetyBadge item={item} />
      </td>
      <td>{String(warnings)}</td>
      <td>{fmtText(item.created_at)}</td>
      <td>{isError ? fmtText(item.error) : "-"}</td>
    </tr>
  );
}

export default function ReportsPage() {
  const [result, setResult] = useState<FetchReportsResult | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchReports().then((r) => {
      if (active) {
        setResult(r);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  // Read-only copy aid: fetch the list Markdown and write it to the clipboard.
  // Only runs on explicit button click; never auto-copies; never mutates anything.
  async function handleCopyMarkdown() {
    setCopyStatus(null);
    const md = await fetchReportsMarkdown();
    if (md.status === "unavailable") {
      setCopyStatus("レポート保存先が未設定または存在しないためコピーできません");
      return;
    }
    if (md.status !== "success") {
      setCopyStatus("一覧Markdownのコピーに失敗しました");
      return;
    }
    try {
      await navigator.clipboard.writeText(md.markdown);
      setCopyStatus("一覧Markdownをコピーしました");
    } catch {
      setCopyStatus("一覧Markdownのコピーに失敗しました");
    }
  }

  return (
    <main data-testid="reports-page" className="reports-page">
      <h1>FX Reports</h1>

      <p className="report-actions">
        <button
          type="button"
          data-testid="copy-reports-markdown"
          className="report-copy-button"
          onClick={handleCopyMarkdown}
        >
          一覧Markdownをコピー
        </button>
        {copyStatus && (
          <span data-testid="copy-reports-markdown-status" className="report-copy-status">
            {copyStatus}
          </span>
        )}
      </p>

      {result === null && (
        <p data-testid="reports-loading">読み込み中...</p>
      )}

      {result?.status === "unavailable" && (
        <p data-testid="reports-error" role="alert">
          レポート保存先が未設定または存在しません
        </p>
      )}

      {result?.status === "error" && (
        <p data-testid="reports-error" role="alert">
          レポート一覧を取得できません
        </p>
      )}

      {result?.status === "success" && result.data.count === 0 && (
        <p data-testid="reports-empty">レポートがありません</p>
      )}

      {result?.status === "success" && result.data.count > 0 && (
        <>
          <p data-testid="reports-count">Reports: {result.data.count}</p>
          <div style={{ overflowX: "auto" }}>
            <table data-testid="reports-table" className="reports-table">
              <thead>
                <tr>
                  {COLUMNS.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.data.items.map((item) => (
                  <ReportRow key={item.run_id} item={item} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
