# Phase 3C: Live Verification Mode design

Phase 3Cでは、Phase 3Dの極小実資金検証へ進む前に、Live Verification Modeの安全設計をdocs化する。

今回は **設計のみ** である。Live Verification Mode実装、broker実装、注文API実装、OrderRequest実装、
実注文、実資金検証、自動売買、本番公開API追加には進まない。

## 1. Phase 3Cの目的

- Live Verification Modeを設計する。
- Phase 3D極小実資金検証前の安全設計を固定する。
- 注文前、注文時、注文後の確認条件と停止条件を明確にする。
- read-only precheck、risk decision、order intent、ID相関を1つの手順として整理する。
- 100通貨固定、`USD_JPY`のみ、1回限定、manual onlyを明文化する。
- Phase 3Dへ進むためのレビュー条件を定義する。

Phase 3Cは実装ではない。実注文ではない。実資金検証ではない。自動売買ではない。

## 2. Live Verification Modeの定義

Live Verification Modeとは、実資金検証へ進む直前に、read-only確認、risk decision、注文候補、
注文前チェック、停止条件を1つの安全な実行フローとして固定するモードである。

ただし、Phase 3Cでは設計のみを行う。実行コード、broker、注文API、OrderRequest、実注文payloadは作らない。

Live Verification Modeの役割:

- Phase 2Eで確認したcandidate / risk decisionの安全境界を、将来の実注文直前フローに接続する。
- Phase 3B-4で確認したPrivate API read-only 3 endpointを、注文前の必須precheckにする。
- 注文可能状態へ進む前に、fail closed条件を明確にする。
- 「発注するかどうか」ではなく、「発注してよい状態かを設計上判定できるか」を確認する。

## 3. Live Verification Modeで許可する範囲

許可する範囲:

```text
USD_JPYのみ
100通貨固定
1回限定
manual only
local only
read-only確認必須
risk decision必須
kill switch必須
明示承認必須
raw response保存なし
headers保存なし
signature保存なし
APIキー / secret表示なし
```

実行環境の前提:

- productionではなくlocal only。
- Render / Vercel / backend公開API / frontendから実行しない。
- `backend/app/main_readonly.py` へ追加しない。
- cron、schedule、常駐botから実行しない。
- 実行する場合も、将来Phase 3Dでユーザーの明示承認を得た1回だけに限定する。

## 4. Live Verification Modeで禁止する範囲

禁止する範囲:

```text
自動売買
常駐bot
cron / schedule
複数回注文
複数通貨
100通貨超
ナンピン
マーチンゲール
損失回復目的の追加注文
retryによる再注文
loop
同時複数ポジション
未約定注文がある状態での新規注文
既存建玉がある状態での新規注文
```

禁止する実装・導線:

```text
broker実装
OrderRequest実装
注文API実装
注文変更API実装
注文取消API実装
決済API実装
OrderCandidateからOrderRequestへの変換
submit / send / place / cancel / amend
ENABLE_LIVE_TRADING
本番公開API追加
frontend実行画面
```

## 5. 注文前read-onlyチェック

Phase 3B-4で確認済みのPrivate API read-only endpointを、将来の注文前precheckとして必須にする。

必須endpoint:

```text
GET /private/v1/account/assets
GET /private/v1/openPositions
GET /private/v1/activeOrders
```

必須チェック:

- `account/assets` が取得できる。
- `openPositions` が取得できる。
- `activeOrders` が取得できる。
- 既存建玉なし。
- 未約定注文なし。
- read-only結果がsanitizedされている。
- raw response保存なし。
- headers保存なし。
- signature保存なし。
- credential表示なし。
- error時にretryしない。
- error時に注文系へ進まない。

合格条件:

```text
account_assets: success
open_positions: success
active_orders: success
open_positions_count: 0
active_orders_count: 0
has_open_positions: false
has_active_orders: false
raw_response_saved: false
headers_saved: false
credentials_printed: false
retry_attempted: false
```

補足:

- 口座資産の金額詳細はorder intentや最終報告へ保存しない。
- 建玉詳細、注文ID詳細、約定ID詳細は保存しない。
- Phase 3Cではprecheckの設計だけを行い、追加接続は行わない。

## 6. risk decision / candidate / order intent相関

Phase 2E / Phase 3Bの成果を踏まえ、将来のLive Verification Modeでは次の順序を固定する。

```text
signal
candidate
risk decision
read-only precheck
order intent
live verification run
```

ID相関:

| ID | 役割 | 必須条件 |
| --- | --- | --- |
| `candidate_id` | signalから作られる注文候補の識別子 | 1つのcandidateに対してrisk decisionは1つだけ |
| `decision_id` | risk decisionの識別子 | `candidate_id` と同じrun文脈に属する |
| `order_intent_id` | 実注文直前の意思決定記録 | `candidate_id` と `decision_id` を必ず参照する |
| `verification_run_id` | Live Verification Modeの1回限りの実行単位 | read-only precheck、risk decision、order intentを束ねる |

相関ルール:

- `candidate_id` がない場合は停止。
- `decision_id` がない場合は停止。
- `order_intent_id` がない場合は停止。
- `order_intent_id` が複数ある場合は停止。
- `candidate_id` と `decision_id` のrun文脈が一致しない場合は停止。
- `order_intent_id` が参照する `candidate_id` / `decision_id` が一致しない場合は停止。
- risk decisionが `ALLOW` 相当でない場合は停止。
- read-only precheckがorder intent作成より前に成功していない場合は停止。

Phase 3Cではorder intentまでを設計する。OrderRequestや実注文APIはまだ作らない。

## 7. order intent設計

order intentは、実注文リクエストではなく、注文直前の意思決定記録である。

order intentに含める候補:

```text
order_intent_id
candidate_id
decision_id
verification_run_id
symbol
side
units
mode
manual_confirmation_required
readonly_precheck_passed
created_at
expires_at
```

制約:

```text
unitsは100固定
symbolはUSD_JPYのみ
modeはlive_verificationのみ
manual_confirmation_requiredはtrue固定
readonly_precheck_passedはtrue必須
expires_atを過ぎたintentは無効
```

order intentがしてはいけないこと:

- 実注文payloadではない。
- brokerへ渡さない。
- API endpointへ送らない。
- request headersを持たない。
- signatureを持たない。
- APIキー / secretを持たない。
- 注文ID、約定ID、残高詳細、建玉詳細を持たない。

Phase 3Cでの扱い:

- docs設計のみ。
- schema実装なし。
- DB保存なし。
- JSONL writer追加なし。
- CLI追加なし。

## 8. kill switch / STOP / fail closed条件

次のいずれかに該当する場合は即停止する。

```text
APIキー / secretが表示された
raw responseが保存された
headersが保存された
signatureが保存された
read-only precheck失敗
account/assets取得失敗
openPositions取得失敗
activeOrders取得失敗
既存建玉あり
未約定注文あり
risk decisionがALLOW以外
candidate / decision / order intent相関不整合
unitsが100以外
symbolがUSD_JPY以外
manual confirmationなし
kill switch active
safety violation
Git差分にsecret混入
```

追加のfail closed条件:

- `.env` またはcredentialファイルがtracking対象になった。
- `.env.example` に実値が入った。
- backend testsが失敗した。
- private_readonly testsが失敗した。
- no-order-import guardが失敗した。
- forbidden endpoint guardが失敗した。
- broker importが混入した。
- `OrderRequest` が混入した。
- `submit` / `send` / `place` / `cancel` / `amend` が実行可能導線として混入した。
- retryやloopによる再注文導線が入った。
- 本番公開APIまたはfrontendから実行できる導線が入った。

停止時の扱い:

- 追加接続しない。
- 注文系へ進まない。
- 実装を急がない。
- docsレビュー、mocked tests、境界確認へ戻る。

## 9. 実注文前チェックリスト

Phase 3Dで実注文に近づく前に、最低限次をすべて満たす必要がある。

```text
git working tree clean
backend tests pass
ruff pass
private_readonly tests pass
no-order-import guard pass
forbidden endpoint guard pass
read-only endpoint 3件成功
APIキー / secret非表示
.envがgit管理対象でない
raw response保存なし
headers保存なし
signature保存なし
既存建玉なし
未約定注文なし
risk decision ALLOW
candidate / decision / order intent相関あり
symbol USD_JPY
units 100
1回限定
manual confirmationあり
kill switch inactive
safety violation 0
```

チェックリストの運用:

- 1項目でも未確認なら停止。
- 1項目でもNGなら停止。
- 「たぶん大丈夫」で進めない。
- Phase 3D直前に再確認する。

## 10. 実行後チェックリスト

Phase 3Dで将来、明示承認のもと実注文を1回だけ出した場合、直後に次を確認して停止する。

```text
注文を出した場合は即停止
追加注文しない
retryしない
loopしない
約定確認をread-onlyで行う
建玉確認をread-onlyで行う
未約定注文確認をread-onlyで行う
raw response保存なし
headers保存なし
credentials表示なし
Git差分にsecretなし
実データをcommitしない
```

実行後の禁止:

- 連続検証へ進まない。
- 損益確認を理由に追加注文しない。
- 未約定を理由に自動取消や再注文へ進まない。
- 建玉が残っている状態で新規注文しない。
- 実データや実APIレスポンスをfixture化しない。

## 11. Phase 3Cの合格条件

Phase 3Cの合格条件:

```text
Live Verification Mode設計docs完了
order intent設計完了
read-only precheck設計完了
kill switch / STOP条件整理済み
実注文前チェックリスト整理済み
実行後チェックリスト整理済み
まだ実装していない
まだ実注文していない
```

追加条件:

- Phase 3C docsがPhase 3B-4結果と矛盾していない。
- Phase 3Dへ進む条件が明文化されている。
- broker、OrderRequest、注文API、実注文をまだ作っていない。
- `.env` / `.env.example` を変更していない。
- raw response、headers、signature、credentialを保存していない。

## 12. Phase 3Dへ進む条件

Phase 3Dへ進むには、最低限次が必要である。

```text
Phase 3C設計レビュー完了
Phase 3C実装設計レビュー完了
order intent実装レビュー完了
broker / order API実装前レビュー完了
100通貨・1回限定の明示承認
read-only precheckが直前に成功
実注文前チェックリスト全項目OK
```

Phase 3Dの初回条件案:

```text
symbol = USD_JPY
units = 100
orders_count = 1
execution = manual only
frequency = one-time verification
max_open_positions = 1
auto_retry = false
auto_reentry = false
schedule / cron / bot = false
```

Phase 3Dへ進まない条件:

- Phase 3C設計レビューが未完了。
- 実装設計レビューが未完了。
- order intent実装レビューが未完了。
- broker / order API実装前レビューが未完了。
- 100通貨・1回限定の明示承認がない。
- read-only precheckが直前に成功していない。
- 実注文前チェックリストに未確認またはNGがある。

追記:

- Phase 3C実装設計レビューは完了済み。詳細は
  [PHASE3C_IMPLEMENTATION_DESIGN_REVIEW.md](PHASE3C_IMPLEMENTATION_DESIGN_REVIEW.md)。
- Phase 3C-1 mocked core実装も後続タスクで完了済み。order intent、read-only precheck result、
  live verification state、errors、mocked tests、no-order-import guardをlocal-only / mocked範囲で追加した。
- Phase 3C-2 ID相関テストも後続タスクで完了済み。signal、candidate、risk decision、
  readonly precheck、order intent、verification runの相関、同一run内2件目intent拒否、
  READY_FOR_ORDER_REVIEW停止をpure mocked testsで確認した。
- Phase 3C-3 dry-run統合テストも後続タスクで完了済み。read-only precheck、risk decision、
  ID correlation、order intent、state transitionを1本のpure mocked flowで確認し、
  READY_FOR_ORDER_REVIEWまで到達して停止すること、失敗条件ではfail closedすることを確認した。
- Phase 3D前 broker / order API実装前レビューも後続タスクで完了済み。詳細は
  [PHASE3D_PRE_ORDER_API_REVIEW.md](PHASE3D_PRE_ORDER_API_REVIEW.md)。
  判定は **A: Phase 3D-0 公式仕様・危険endpoint再レビューへ進んでよい**。
- ただし、実注文可能なLive Verification Mode、broker、OrderRequest、注文API、実注文、実資金検証には
  進んでいない。

## 13. まだ進まない範囲

Phase 3Cでは次へ進まない。

```text
Live Verification Mode実装
order intent実装
broker実装
OrderRequest実装
注文API実装
注文変更API実装
注文取消API実装
決済API実装
実注文
実資金検証
自動売買
本番公開API
frontend変更
backend/app/main_readonly.py変更
DB本番化
認証実装
cron / schedule / 常駐bot
```

## 14. 変更していない重要箇所

- backend code: 変更しない。
- private read-only client: 変更しない。
- connection script: 変更しない。
- tests: 変更しない。
- `.env` / `.env.example`: 表示・変更しない。
- backend公開API: 変更しない。
- `backend/app/main_readonly.py`: 変更しない。
- frontend: 変更しない。
- broker: 変更しない。
- 注文API: 変更しない。
- 実注文: 行わない。
- 実資金検証: 行わない。
- `shadow_exports/` / 実APIレスポンス: commitしない。

## 15. 結論

Phase 3Cでは、Live Verification ModeをPhase 3D極小実資金検証前の安全設計として定義した。

結論:

- Live Verification Modeは、read-only precheck、risk decision、order intent、停止条件を束ねる設計である。
- Phase 3Dへ進むには、Phase 3C設計レビューに加え、実装設計レビュー、order intent実装レビュー、
  broker / order API実装前レビュー、100通貨・1回限定の明示承認が必要である。
- Phase 3C実装設計レビュー、Phase 3C-1 mocked core実装、Phase 3C-2 ID相関テスト、
  Phase 3C-3 dry-run統合テスト、Phase 3D前 broker / order API実装前レビューは後続タスクで
  完了済みだが、Phase 3D-0以降はまだ未実施である。
- Phase 3C-3時点では、実注文可能なLive Verification Mode、broker、注文API、OrderRequest、
  実注文、実資金検証、自動売買には進まない。
