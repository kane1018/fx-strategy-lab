# FX Strategy Lab — Codex 作業ルール

このリポジトリでは、目的達成に必要な最小限の変更だけを行う。

## 作業手順

1. 作業前に既存コード、関連 docs、テスト、`git status`、最新 commit を確認する。
2. 変更対象と触らない箇所を整理する。不要な機能追加や大規模リファクタリングはしない。
3. `package.json`、`pyproject.toml`、`requirements*.txt` 等を確認し、実在する検証コマンドだけを実行する。
4. エラー時は根本原因を特定して最小限に修正する。修正と再検証は最大5回までとする。
5. 指定された検証に成功したら停止し、明示依頼なしに次フェーズへ進まない。
6. 最終報告は ChatGPT へそのまま貼れる Markdown 形式で出力する。

## 絶対に行わないこと

- Private API、APIキー、実注文、実資金を扱わない。
- 残高、建玉、注文履歴、約定を取得しない。注文、注文変更、注文取消を行わない。
- `.env` / secret を表示、変更、commit しない。`ENABLE_LIVE_TRADING=true` にしない。
- 本番公開 API を追加せず、`backend/app/main_readonly.py` を変更しない。
- Render / Vercel の設定変更、DB 本番化、認証実装を行わない。
- `shadow_exports/`、実 API レスポンス、集計出力を commit しない。
- `analysis_exports/` に実データを混入させず、生成物を commit しない。

上記に近づく変更は、実装前に必ず ChatGPT または Claude Code を含む事前レビューを行い、明示承認を得る。

## 重要な注意（2026-07-06 監査で確認・重大インシデント扱い）

`backend/app/live_verification/` 配下の "Step 6G-PC-OX-R-...controlled" 系モジュール
（130ファイル中ほぼ全て）は、dataclassの固定デフォルト値によるシミュレーションであり、
実ブローカー・実HTTP・実credentialとは接続されていない。一方で、以下は**実際にGMO FX本番
Private APIへ実HMAC署名付きHTTP POSTを送信できる実装済みコード**であり、シミュレーションでは
ない。

- `backend/app/live_verification/live_order_once.py`
  （`execute_one_shot_live_order` / `post_live_order_with_httpx`）
- `backend/app/live_verification/live_order_real_official_settlement_actual_transport_no_post_controlled.py`
  （`OfficialSettlementActualTransportHttpxClient`）
- `backend/app/live_verification/live_order_real_one_shot_post_real_delegate_controlled.py`
  （`make_live_order_real_one_shot_post_real_delegate` が上記の実POST関数を解決・呼び出す橋渡し）

これらは現状、明示的な `transport`・実credential・`allow_live_http_post=True` 等をすべて
呼び出し側が渡さない限り発火せず、Step 6G の "controlled/safe" 系モジュールの既定
（zero-arg）エントリポイントからは到達できないことを
`backend/app/tests/test_live_verification_real_post_capability_isolation.py` で固定している。
ただし「実POSTが不可能」であることを意味する命名（`_no_post_controlled` 等）は誤解を招くため、
このファイル名だけを根拠に安全と判断してはならない。新しい "controlled" モジュールを追加する際は、
上記3ファイルをimport・呼び出しに追加しないこと。追加した場合は
`test_live_verification_real_post_capability_isolation.py` が失敗する設計にしてある。

**追記（Step 6G-PC-OX-R-REAL-POST-HARD-GUARD-MINIMAL-NO-POST-C 完了）**: 上記3経路の実POST/実送信
直前に、共通の default-deny ハードガード（`assert_real_broker_post_allowed(*, allow: bool)`）を
追加した。`allow` に明示的な `True` を渡さない限り（`False`/`None`/未設定/その他の truthy値
いずれも）例外で拒否し、env/`.env`による解除経路は存在しない。既存の `allow_live_http_post` 等の
個別フラグと合わせた多層防御であり、`test_live_verification_real_post_capability_isolation.py` に
source scanと専用回帰テストを追加済み。

**追記（Step 6G-PC-OX-R-REAL-BROKER-HARD-GUARD-RELOCATION-NO-POST-C 完了）**: 上記ハードガードは
`backend/app/live_verification/real_broker_post_hard_guard.py` から
`backend/app/security/real_broker_post_hard_guard.py` へ移設した（挙動・default-denyは無変更）。
理由は、production broker/service経路が`app.live_verification`を一切importしないという
分離原則（`test_gmo_fx_broker_live_verification_isolation.py`）と、将来の`GmoFxBroker`実装が
このハードガードを参照する必要性を両立させるため。新しい `app.security` パッケージは
production-safeな共有安全プリミティブ専用とし、Step 6G controlled/simulation系のコードは
置かない。実POST可能3経路（`live_order_once.py`等）は新しいimport path
（`app.security.real_broker_post_hard_guard`）を参照するよう更新済み。旧パスは削除した
（互換shimは残していない。参照箇所は今回すべて更新したため不要と判断）。

docs/CODEX_HANDOFF.md の過去の "Step 6G" 記録（entry POST accepted、settlement POST rejected、
runtime safe read の position count 等）は、実ブローカー検証済みの事実ではなく、大半が
上記シミュレーション層の出力または運用者の申告（docs claim）であり、コード監査だけでは
真偽を確認できない。詳細は同ファイル冒頭のインシデント記録を参照。

**追記（Step 6G-PC-OX-R-POST-INCIDENT-LIVE-ALLOW-BRIDGE-NO-POST-C: allow bridge実装を却下）**:
上記hard guardの`allow`を安全boolean群から自動算出する「allow bridge」（例:
`build_real_broker_post_allow_decision_no_post_controlled`のような、複数のsafe boolean/labelを
AND結合して`allow_real_broker_post_safe_boolean`を返す再利用可能な判定関数）は、no-POST設計であっても
**実装しない**と判断した。理由は、これが将来hard guardを機械的に解除するための唯一の欠けていた
接続点になり得るためで、重大インシデント直後の安全方針に反する。live再開の可否は、こうした
再利用可能なboolean判定器ではなく、運営者による明示的な重大インシデント解除宣言と、その時点の
fresh gate（新しいruntime読み取り・新しい6行confirmation）でのみ扱う。previous confirmationや
過去のsafe labelは再利用しない。新しいエージェント/セッションは、同種の allow bridge を再提案・
再実装しないこと。実POST再開の是非は、別途専用の再開方針Stepでのみ判断する。

## Step 6G Controlled one-shot POST 限定例外

通常作業では、Private API、APIキー、実注文、実資金、残高・建玉・注文照会、HTTP POST、broker/order endpoint、`live_order_once` は引き続き禁止する。

ただし、ユーザーが明示的に `Step 6G Controlled one-shot POST` または同等のStep 6G実行タスクを依頼した場合に限り、以下の限定例外を認める。この例外はStep 6G専用であり、他の通常作業・調査・実装・docs更新には適用しない。

### Step 6Gで限定的に許可すること

- credential presenceを `PRESENT` / `MISSING` のみで確認する。
- credential値、長さ、hash、fingerprint、先頭末尾、headers、signature、token、secretは表示しない。
- `.env` は表示・変更しない。env一覧表示や `printenv` は行わない。
- Step 6Gのfresh preflight目的に限り、public status/ticker GETを実行してよい。
- Step 6Gのfresh preflight目的に限り、Private API read-only GETで以下だけをsanitized取得してよい。
  - `account/assets`: account status / account asset check pass flag
  - `openPositions`: open positions count / pass flag
  - `activeOrders`: active orders count / pass flag
- fresh read-only preflightは、final confirmation前に最大1回、final confirmation後のPOST直前に最大1回だけ許可する。
- final confirmation gateでは、非秘密・非rawのgo/no-go checklistのみ表示してよい。
- ユーザーがCodex画面で指定されたfinal confirmation phraseを完全一致入力した場合に限り、既存の承認済みone-shot経路で最大1回だけHTTP POSTしてよい。
- POST後は、sanitized fieldsだけのread-only reconciliationを最大1回行ってよい。
- Step 6G中も永続設定としての `allowed_for_live=true` 保存は禁止する。最終状態は `allowed_for_live=false` とする。

### Step 6Gでも禁止し続けること

- final confirmation前のHTTP POST。
- HTTP POSTを2回以上実行すること。
- retry、loop、追加注文、決済注文、取消、注文変更。
- `closeOrder`、`cancelOrders`、`changeOrder`。
- 新しいorder endpoint経路の作成、新しいpayload組み立てロジックの作成。
- CodexによるBUY/SELL、symbol、size、executionTypeの推測または変更。
- order payload全文の表示・保存。
- raw request / raw response の表示・保存。
- headers値、signature値、API key値、secret値、token値、credentials値の表示・保存。
- credentialの長さ、hash、fingerprint、先頭末尾の表示。
- `.env`表示・変更、env一覧表示、`printenv`。
- order ID、execution ID、position ID、clientOrderIdの表示。
- approval command全文表示、copyable approval command表示、pbcopy、approval commandファイル保存。
- ledger reset、ledger削除、ledger変更。
- 実API結果、raw request、raw response、headers、signature、credential、real ID、approval command全文のGit保存。
- commit / push。ただし別タスクでAGENTS.md変更自体を明示依頼された場合を除く。

### Step 6Gの停止条件

以下のいずれかに該当する場合、CodexはHTTP POSTせず停止する。

- working treeがdirty。
- HEADがorigin/mainと一致しない。
- credential presenceが不足。
- tests / ruff / danger scanが失敗。
- approval artifact / exact validation / order intent exact matchが確認できない。
- fresh preflightが失敗。
- market closed / unknown、broker maintenance、holiday / special close。
- open positions countが0ではない。
- active orders countが0ではない。
- ticker stale、spread上限超過。
- permission / IP binding / previous result checkが不明または失敗。
- raw/secret/ID非表示を保証できない。
- final confirmation phraseが完全一致しない。
- 少しでも安全に判断できない。

この限定例外は、Codexに投資判断を委ねるものではない。Codexは注文方向、数量、銘柄、executionTypeを推測せず、既存の承認済みartifactおよびユーザーの明示入力と完全一致する場合だけ処理を続行する。

## H-11 GMO relaxed v4 actual adapter 実装限定例外

通常作業および上記Step 6Gの境界は引き続き有効とする。ただし、operatorが明示的に
`H-11 GMO relaxed v4 actual adapter実装`を依頼した場合に限り、実ブローカーへの送信・activationを
行わない実装／fake検証Stepとして、次の限定例外を認める。この例外はH-11 GMO relaxed v4専用であり、
v3、他仮説、手動シグナルUI、汎用broker経路には適用しない。

### v4 adapter実装Stepで限定的に許可すること

- GMO FX Private APIの型付きadapter、request builder、HMAC署名境界、注入点を実装する。
- 対象endpointは、v4凍結契約に必要な`order`、`cancelOrders`、OCO、position-specific
  `closeOrder`、`latestExecutions`、`openPositions`、`activeOrders`に限定する。
- macOS Keychainからsealed credentialを読むloaderを実装する。ただし、このStepの実行・testでは
  fake loaderだけを使用し、実Keychain itemや実credential値は読まない。
- actual reconciliation、clientOrderIdによる所有権追跡、positionIdのメモリ内限定処理を実装する。
- fake HTTP client、fake credential、synthetic IDだけを使って先行testを実行する。
- `AGENTS.md`、v4専用docs、v4専用adapter／testを必要最小限で変更する。

### v4 adapter実装Stepでも禁止し続けること

- 実GMO endpointへのPrivate GET/POST、broker read/write、実注文、取消、決済、変更。
- activation token／permitの発行、actual transportの有効化、hard guardの解除、allow bridgeの実装。
- 実Keychain credentialのread/write、credential値・長さ・hash・fingerprint・先頭末尾の表示または保存。
- raw request／raw response、header、signature、token、実order/execution/position/clientOrder IDの
  表示、ログ、永続化、Git保存。
- `.env`／process envからの解除、`ENABLE_LIVE_TRADING=true`、`main_readonly.py`変更。
- retry、repost、second attempt、generic opposite close、v4凍結risk/spec/config hashの変更。
- actual broker送信・activation。これらは実装とレビュー完了後の別Step・別承認を必須とする。
- commit／push（別途明示授権がある場合を除く）。

v4 actual-capableコードはfake-onlyの`app.h11_auto`エンジン本体から分離し、既定では構造的に
refuseする。実装完了はlive可、performance proof、activation済みを意味しない。

## H-11 GMO relaxed v4 actual activation準備限定例外（canary POST直前停止）

通常作業、Step 6G、v4 adapter実装Stepの境界は引き続き有効とする。ただし、operatorが明示的に
`H-11 v4 actual activation準備`を依頼した場合に限り、canaryのbroker POST直前までの有限な証拠取得
Stepとして次を認める。この例外はH-11 v4専用であり、v3、他仮説、手動シグナルUI、汎用broker経路
には適用しない。

### v4 actual activation準備Stepで限定的に許可すること

- v4専用Keychain item 6件について、値を外部へ出さないpresence確認と、下記の有限試験に必要な
  sealed internal readを行う。
  - service `fx-strategy-lab-h11-v4-actual`: `gmo-fx-api-key` / `gmo-fx-api-secret`
  - service `fx-strategy-lab-h11-v4-notify`: `pushover-api-token` / `pushover-user-key` /
    `smtp-username` / `smtp-app-password`
- presence後、通知送信前に6件を値非表示でinternal readし、Keychain access operation全体で
  対話承認を最大120秒待つ
  access rehearsalを1回だけ行う。読み取った値は即座破棄し、表示・ログ・永続化しない。
- Pushoverへの準備試験メッセージを1回だけ送信し、emergency receiptを5秒未満の間隔でpollせず、
  operator acknowledgementを有限時間内でsanitized確認する。application側から同じメッセージを再送しない。
- emailへ準備試験メッセージを1回だけ送信する。宛先は`SMTP usernameと同じaddress`に固定し、
  account文字列を表示・保存しない。
- GMO FX Private GETを、`latestExecutions`、`openPositions`、`activeOrders`の各1回、合計3回だけ
  0.00/0.25/0.50秒以上の間隔で実行する。結果は成功可否、件数、flat/zero-active判定等のsanitized
  aggregateだけに限定する。
- current hostのread-only状態確認、有限なdisposable subprocessのKILL試験、persistent HALT／lock確認を
  行う。実運用processをkillせず、sleep、reboot、network遮断、clock変更、Keychain lock、launchd install、
  cron追加、常駐化は別途明示承認なしに行わない。
- 上記の準備専用adapter、notification sender、finite rehearsal、test、docs、safe reportを必要最小限で
  実装する。POST可能transport・fake-only engine・`main_readonly.py`とは分離する。
- Pushover／SMTP送信のための外部通信は通知経路に限り許可する。この通知送信はbroker POST countに
  含めないが、external notification send countとして別記する。

### v4 actual activation準備Stepでも禁止し続けること

- brokerへのHTTP POST、実注文、取消、変更、決済、OCO作成、canary実行。
- `order`、`cancelOrders`、`closeOrder`その他のbroker write endpoint呼出し。
- actual activation token／permitの発行、POST transportの有効化、hard guardの解除・弱化、allow bridge、
  env／`.env`による解除。
- credential、raw request／raw response、header、signature、token、receipt、実order/execution/position/
  clientOrder IDの表示、ログ、永続化、Git保存。credentialの長さ、hash、fingerprint、先頭末尾も扱わない。
- Pushover emergency messageのapplication再送、broker GET/POSTのretry、repost、second attempt。
- 同じreviewed-files digestに属する失敗済みpreparation operationの再試行、markerの削除・変更。
- `main_readonly.py`変更、resident process、launchd install、cron追加。
- canary POST。全準備と独立レビューがclearでも、fresh最終確認を提示してoperatorの別承認を待つ。
- commit／push（別途明示授権がある場合を除く）。

### v4 actual activation準備Stepの外部試験停止条件

以下のいずれかに該当する場合、実Keychain read、外部通知送信、Private GETを開始しない。

- working treeがdirty。
- HEADが`origin/main`と一致しない。
- focused／related tests、ruff、`git diff --check`、danger scan、独立レビューがclearでない。
- 完全generation manifestまたはactual準備専用のexact artifact整合が未確認。
- raw／secret／ID非表示を保証できない。

IP制限を使用しないoperator判断は`OPERATOR_ACCEPTED_RESIDUAL_RISK`として記録し、safety PASSとは扱わない。
修正後の再試行は、新しいreviewed-files digestに結び付く新規generationでのみ許可する。
旧generationのno-retry markerは保持し、reset・削除・上書きしない。
この準備Stepの完了もactual activation、performance proof、live ready、unattended live supportを意味しない。

## 最初に読む文書

- `docs/CODEX_HANDOFF.md`
- `docs/PROJECT_STATUS.md`
- `docs/SHADOW_RUNBOOK.md`
- `docs/PUBLICATION_POLICY.md`
- `docs/GMO_PUBLIC_API_PLAN.md`
- `docs/PHASE2_SHADOW_TRADING_PLAN.md`
