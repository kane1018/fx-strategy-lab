import Link from "next/link";

// Read-only public landing. The full TradingDashboard (backtest / paper / signals /
// demo orders) hits backend APIs that are NOT exposed by the deployed read-only
// entrypoint (app.main_readonly:app), so it is not rendered here to avoid "Failed to
// fetch" on the public site. The dashboard component is kept for local dev / future
// phases. Public version offers read-only report viewing only.
export default function Home() {
  return (
    <main data-testid="landing-page" className="reports-page">
      <h1>FX Strategy Lab</h1>

      <p data-testid="landing-scope">
        現在の公開版は <strong>read-only レポート閲覧</strong> のみ対応しています。
        バックテスト・ペーパートレード・シグナル通知・注文関連機能は未公開です。
      </p>

      <p>
        <Link href="/reports" data-testid="to-reports" className="landing-cta">
          レポート一覧を見る →
        </Link>
      </p>

      <section className="landing-note" data-testid="landing-unavailable">
        <h2>未公開の機能</h2>
        <p>
          バックテスト / ペーパートレード / シグナル通知 / デモ注文・安全設定 は、現在の公開版では
          未提供です（次フェーズで安全確認後に公開予定）。実注文・実資金取引・Private API・自動売買は
          公開していません。
        </p>
      </section>
    </main>
  );
}
