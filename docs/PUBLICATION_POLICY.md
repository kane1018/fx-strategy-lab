# 公開・アクセス制御ポリシー（PUBLICATION_POLICY）

FX Strategy Lab の **一般公開可否・認証/アクセス制御の要否・公開してよい/してはいけない情報** の方針。
本書は方針定義であり、認証実装・コード変更・外部設定変更は含まない。今後 Codex / Claude Code に依頼する際の
**安全制約の単一参照点**として使う。安全実装の詳細は [SAFETY.md](SAFETY.md)、現在地は
[PROJECT_STATUS.md](PROJECT_STATUS.md)、デプロイ実績は [DEPLOYMENT_RESULT.md](DEPLOYMENT_RESULT.md)。

## 1. 現時点の公開判断（暫定：一般公開可）

現在の本番は以下をすべて満たすため、**暫定的に一般公開可**とする。
**この「一般公開可」は、現在のサンプル read-only MVP に限る**（条件が1つでも変われば §2 で再判断）。

- 公開対象は **read-only reports のみ**（`/`＝案内ランディング、`/reports`、`/reports/[run_id]`、Markdown コピー）。
- backend は **`app.main_readonly:app`**（`/health` ＋ `/api/reports*` の GET のみ）。
- 注文系など他 API は未登録（`GET /api/orders`・`/api/paper/sessions`・`/api/automation/status` → 404、
  `POST /api/reports` → 405）。
- 実注文なし / 実資金なし / APIキー・secret なし / Private API なし / 実データなし。
- 公開レポートは **無害な E2E サンプルのみ**（`e2e_*` run）。
- CSV 本文返却・CSV ダウンロードなし（files は name/kind/size_bytes のメタのみ）。

## 2. 認証 / アクセス制御が必要になる条件（いずれか1つでも該当したら必須化を再判断）

- 実取引由来レポートを表示する。
- 実資金の損益・建玉・取引履歴・約定履歴を表示する。
- APIキー / API 利用状況に関係する情報を扱う。
- GMO / OANDA の Private API を扱う。
- strategy の詳細ロジックや独自優位性を含むレポートを公開する。
- 個人メモ・資金計画・運用ルール・心理ログなどを表示する。
- CSV 本文返却 / CSV ダウンロードを有効にする。
- paper trading / shadow trading のセッション情報を表示する。
- 注文候補・売買シグナル・ポジション情報を表示する。
- 管理画面・設定画面・実行ボタンが存在する。
- 第三者に見られると不利益がある情報を扱う。

→ 上記に1つでも触れる時点で、**公開前に「認証/アクセス制御の要否」を必ず再判断**し、必要なら実装する。

## 3. 公開してよい情報（現時点）

- 無害な E2E サンプルレポート（`e2e_*`）。
- read-only で加工済みのサンプルメタ情報（run_id / kind / strategy / timeframe / verdict / 集計値など）。
- 実取引に由来しない検証サンプル。
- APIキー・個人情報・実資金情報を含まない Markdown 概要。
- CSV 本文を含まないファイルメタ情報（name / kind / size_bytes）。

## 4. 公開してはいけない情報（公開禁止）

- `.env` / APIキー / secret / token / PRIVATE_KEY / パスワード。
- GMO / OANDA の Private API 情報・接続情報。
- 実資金の残高 / 建玉 / 注文履歴 / 約定履歴。
- 個人の資金計画 / 運用ルール / 心理ログ等の私的メモ。
- 実取引由来レポート / 実データ CSV 本文 / 本番 DB の中身。
- broker 接続情報 / 実注文可能なエンドポイント / 管理者用操作。
- live trading 設定、`ENABLE_LIVE_TRADING=true` を前提にした情報。

## 5. 今後の推奨方針（フェーズ別）

- **現在**: read-only sample reports は一般公開可（§1）。
- **次に検討**: 本番 URL smoke E2E、認証要否の再確認。
- **実データを扱う前**: 認証必須 / アクセス制限必須 / 公開範囲レビュー必須。
- **GMO Public API / shadow 検証**: まずローカル or 非公開環境で実施。公開 UI に出す前に本書の方針確認＋安全レビュー。
- **GMO Private API / 実資金**: 一般公開 UI に直接つながない。APIキーを Vercel/Render に安易に入れない。
  read-only 確認 → 手動承認 → 少額実資金 → 緊急停止、の順で**別フェーズ・別環境**として管理。

## 6. 将来の認証候補（比較・実装はしない）

| 候補 | 実装の軽さ | セキュリティ | 運用しやすさ | 個人MVPとの相性 | 現 read-only 公開との相性 |
| --- | --- | --- | --- | --- | --- |
| Vercel Protection / Deployment Protection | ◎（設定のみ） | ○（frontend 前段で保護。backend 直叩きは別途要） | ◎ | ◎ | △（公開デモには制限が強い） |
| Basic 認証（frontend/backend 前段） | ○ | ○（共有資格情報。漏洩時弱い） | ○ | ○ | △（誰でも閲覧の公開デモには不向き） |
| NextAuth 等アプリ認証 | △（実装コスト） | ◎ | △（ユーザー管理） | △（MVP には重い） | △ |
| IP 制限 | ○ | ○（固定IP前提） | △（IP 変動に弱い） | ○ | △ |
| 管理画面のみ認証（reports は公開、実データ系のみ非公開） | ○ | ◎（境界が明確） | ○ | ◎ | ◎ |
| reports は公開・実データ系のみ非公開（=現状の設計思想） | ◎（現状維持） | ◎（公開面が read-only に限定） | ◎ | ◎ | ◎ |
| 全体非公開（社内/個人限定） | ◎ | ◎ | ○ | ○ | △（公開の意味が薄れる） |

**結論**: 現時点では **認証実装は不要**（公開面が read-only サンプルに限定され、危険導線が無いため）。
ただし **実データ・実取引・Private API・設定/実行画面へ進む前に、認証/アクセス制御の必須化を再判断**する。
進める場合の第一候補は「**reports は公開・実データ系のみ非公開（管理画面のみ認証）**」＝現在の設計思想の延長。

## 7. 本書の範囲（今回やらないこと）

- 認証実装 / login 画面 / middleware / Basic 認証 / DB 追加。
- Vercel/Render の環境変数・設定変更、`app.main_readonly:app` の変更、`app.main:app` の公開。
- APIキー/secret/Private API の追加・参照・表示、実注文・自動売買の有効化。
- 実データ・個人情報の docs 記載。
