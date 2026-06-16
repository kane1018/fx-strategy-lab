"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  fetchReportDetail,
  fetchReportDetailMarkdown,
  fmtCompact,
  fmtNum,
  fmtText,
  safetyBadge,
  type FetchReportDetailResult
} from "@/lib/reports";
import type { ReportDetail, ReportIndexItem } from "@/types/reports";

function num(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function Kv({ rows }: { rows: [string, string][] }) {
  return (
    <table className="detail-kv">
      <tbody>
        {rows.map(([key, value]) => (
          <tr key={key}>
            <th>{key}</th>
            <td>{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Overview({ detail }: { detail: ReportDetail }) {
  const index = detail.index ?? ({} as ReportIndexItem);
  return (
    <section data-testid="detail-section" data-testid-section="overview">
      <h2 data-testid="detail-overview">Overview</h2>
      <Kv
        rows={[
          ["run_id", fmtText(detail.run_id)],
          ["kind", fmtText(index.kind)],
          ["strategy", fmtText(index.strategy)],
          ["timeframe", fmtText(index.timeframe)],
          ["cost_scenario", fmtText(index.cost_scenario)],
          ["verdict", fmtText(index.verdict)],
          ["created_at", fmtText(index.created_at)]
        ]}
      />
    </section>
  );
}

function Safety({ detail }: { detail: ReportDetail }) {
  const index = detail.index ?? ({} as ReportIndexItem);
  const safety = index.safety ?? {};
  const badge = safetyBadge(index);
  return (
    <section data-testid="detail-section" data-testid-section="safety">
      <h2 data-testid="detail-safety">Safety</h2>
      <p>
        <span
          data-testid="safety-badge"
          data-safe={badge.safe}
          className="safety-badge"
        >
          {badge.label}
        </span>
      </p>
      <Kv
        rows={[
          ["read_only_confirmed", String(index.read_only_confirmed ?? "-")],
          ["safety_complete", String(index.safety_complete ?? "-")],
          ["safety_conflicts", fmtCompact(index.safety_conflicts)],
          ["real_order", String(safety.real_order ?? "-")],
          ["private_api_used", String(safety.private_api_used ?? "-")],
          ["api_key_used", String(safety.api_key_used ?? "-")],
          ["gmo_readonly", String(safety.gmo_readonly ?? "-")],
          ["gmo_order_enabled", String(safety.gmo_order_enabled ?? "-")],
          ["no_order_execution", String(safety.no_order_execution ?? "-")]
        ]}
      />
    </section>
  );
}

function Metrics({ detail }: { detail: ReportDetail }) {
  const s = detail.summary ?? {};
  return (
    <section data-testid="detail-section" data-testid-section="metrics">
      <h2 data-testid="detail-metrics">Metrics Summary</h2>
      <Kv
        rows={[
          ["median_expectancy", fmtNum(num(s.median_expectancy), 4)],
          ["median_pf", fmtNum(num(s.median_pf), 3)],
          ["total_pnl", fmtNum(num(s.total_pnl), 2)],
          ["max_drawdown_max", fmtNum(num(s.max_drawdown_max), 2)],
          ["positive_windows", fmtCompact(s.positive_windows)],
          ["negative_windows", fmtCompact(s.negative_windows)],
          ["group_prior10", fmtCompact(s.group_prior10)],
          ["group_oos5", fmtCompact(s.group_oos5)],
          ["verdict", fmtCompact(s.verdict)]
        ]}
      />
    </section>
  );
}

function Cost({ detail }: { detail: ReportDetail }) {
  const index = detail.index ?? ({} as ReportIndexItem);
  const manifest = detail.manifest ?? {};
  return (
    <section data-testid="detail-section" data-testid-section="cost">
      <h2 data-testid="detail-cost">Cost / Execution</h2>
      <Kv
        rows={[
          ["cost_scenario", fmtText(index.cost_scenario)],
          ["timeframe", fmtText(index.timeframe)],
          ["spread_pips", fmtCompact(manifest.spread_pips)],
          ["slippage_pips", fmtCompact(manifest.slippage_pips)],
          ["stop_loss_pips", fmtCompact(manifest.stop_loss_pips)],
          ["take_profit_pips", fmtCompact(manifest.take_profit_pips)],
          ["symbols", fmtCompact(manifest.symbols)]
        ]}
      />
    </section>
  );
}

function Files({ detail }: { detail: ReportDetail }) {
  const files = detail.files ?? [];
  return (
    <section data-testid="detail-section" data-testid-section="files">
      <h2 data-testid="detail-files">Files</h2>
      {files.length === 0 ? (
        <p>ファイルがありません</p>
      ) : (
        <table className="detail-files">
          <thead>
            <tr>
              <th>name</th>
              <th>kind</th>
              <th>size_bytes</th>
            </tr>
          </thead>
          <tbody>
            {files.map((f) => (
              <tr key={f.name}>
                <td>{fmtText(f.name)}</td>
                <td>{fmtText(f.kind)}</td>
                <td>{fmtCompact(f.size_bytes)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function MarkdownBlock({
  testId,
  title,
  body
}: {
  testId: string;
  title: string;
  body: string | null | undefined;
}) {
  return (
    <section data-testid="detail-section" data-testid-section={testId}>
      <h2 data-testid={testId}>{title}</h2>
      <pre className="detail-markdown">{body && body.trim() ? body : "-"}</pre>
    </section>
  );
}

function DetailBody({ detail }: { detail: ReportDetail }) {
  return (
    <>
      <Overview detail={detail} />
      <Safety detail={detail} />
      <Metrics detail={detail} />
      <Cost detail={detail} />
      <Files detail={detail} />
      <MarkdownBlock
        testId="detail-summary-markdown"
        title="Summary Markdown"
        body={detail.summary_markdown}
      />
      <MarkdownBlock
        testId="detail-final-decision"
        title="Final Decision"
        body={detail.final_decision_markdown}
      />
    </>
  );
}

export default function ReportDetailPage() {
  const params = useParams<{ run_id: string }>();
  const runId = Array.isArray(params.run_id) ? params.run_id[0] : params.run_id;
  const [result, setResult] = useState<FetchReportDetailResult | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) {
      return;
    }
    let active = true;
    fetchReportDetail(runId).then((r) => {
      if (active) {
        setResult(r);
      }
    });
    return () => {
      active = false;
    };
  }, [runId]);

  // Read-only copy aid: fetch the run's Markdown and write it to the clipboard.
  // Only runs on explicit button click; never auto-copies; never mutates anything.
  async function handleCopyMarkdown() {
    if (!runId) {
      return;
    }
    setCopyStatus(null);
    const md = await fetchReportDetailMarkdown(runId);
    if (md.status !== "success") {
      setCopyStatus("Markdownのコピーに失敗しました");
      return;
    }
    try {
      await navigator.clipboard.writeText(md.markdown);
      setCopyStatus("Markdownをコピーしました");
    } catch {
      setCopyStatus("Markdownのコピーに失敗しました");
    }
  }

  return (
    <main data-testid="report-detail-page" className="report-detail-page">
      <p>
        <Link href="/reports" data-testid="back-to-reports">
          ← 一覧へ戻る
        </Link>
      </p>
      <h1>Run: {fmtText(runId)}</h1>

      <p className="report-actions">
        <button
          type="button"
          data-testid="copy-detail-markdown"
          className="report-copy-button"
          onClick={handleCopyMarkdown}
        >
          Markdownをコピー
        </button>
        {copyStatus && (
          <span data-testid="copy-detail-markdown-status" className="report-copy-status">
            {copyStatus}
          </span>
        )}
      </p>

      {result === null && (
        <p data-testid="report-detail-loading">詳細読み込み中...</p>
      )}

      {result?.status === "invalid" && (
        <p data-testid="report-detail-error" role="alert">
          run_idが不正です
        </p>
      )}

      {result?.status === "not_found" && (
        <p data-testid="report-detail-error" role="alert">
          runが見つかりません
        </p>
      )}

      {result?.status === "broken" && (
        <p data-testid="report-detail-error" role="alert">
          run構造が壊れています
        </p>
      )}

      {result?.status === "error" && (
        <p data-testid="report-detail-error" role="alert">
          詳細取得に失敗しました
        </p>
      )}

      {result?.status === "success" && <DetailBody detail={result.data} />}
    </main>
  );
}
