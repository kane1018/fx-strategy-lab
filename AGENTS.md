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
  対話承認を最大300秒待つ
  access rehearsalを1回だけ行う。読み取った値は即座破棄し、表示・ログ・永続化しない。
- Pushoverへの準備試験メッセージを1回だけ送信し、emergency receiptを5秒未満の間隔でpollせず、
  preparation専用operationではoperator acknowledgementを最大15分以内でsanitized確認する。
  application側から同じメッセージを再送しない。
- Pushoverとは別のSMTP operationでemail準備試験メッセージを1回だけ送信する。宛先は
  `SMTP usernameと同じaddress`に固定し、account文字列を表示・保存しない。失敗時はcredential、
  provider responseを出さず、接続／EHLO／TLS／認証／送信／宛先／session終了の固定分類だけを返す。
- GMO FX Private GETを、`latestExecutions`、`openPositions`、`activeOrders`の各1回、合計3回だけ
  0.00/0.25/0.50秒以上の間隔で実行する。結果は成功可否、件数、flat/zero-active判定等のsanitized
  aggregateだけに限定する。
- current hostのread-only状態確認、有限なdisposable subprocessのKILL試験、persistent HALT／lock確認を
  行う。実運用processをkillせず、sleep、reboot、network遮断、clock変更、Keychain lock、launchd install、
  cron追加、常駐化は別途明示承認なしに行わない。
- operatorが当該generationについて明示承認した場合に限り、network time設定確認だけを目的として
  macOS標準の管理者認証画面から固定read-only `systemsetup -getusingnetworktime`を1回実行してよい。
  管理者passwordはOS認証画面だけで扱い、Python stdin／stdout、report、marker、ログへ渡さない。
  その他のprivileged command、設定変更、時刻変更へこの例外を拡張しない。
- actual host/KILL rehearsalは、当該generationのfresh operator承認後、引数なしの固定CLIを
  GUI-capableかつescalatedなCodex実行contextから1回だけ起動する。通常sandboxから起動して管理者認証を
  不明にしたgenerationは失効とし、started marker／HALTを保持して新reviewed-files digestへ進む。
  新generationのexternal preparationはoperation `00_presence`から全件freshに再実行し、旧email確認、
  Keychain、notification、host、Public／Private GET証拠を流用しない。
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
- 同じSMTP operationでのemail再送、またはPushover失敗後にSMTPを同一operation内で続行すること。
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

## H-11 v4 G012 actual canary直前準備限定例外（broker POST禁止）

通常作業、Step 6G、v4 adapter実装Step、v4 activation準備Stepの境界は引き続き有効とする。ただし、
operatorが明示的に`H-11 v4 G012をbroker POST直前まで進める`と依頼した場合に限り、G012 reviewed
generation専用のactual canary runtimeを、broker POST直前で停止する範囲まで実装・有限検証してよい。
この例外はG012の初回10,000通貨canary専用であり、v3、他仮説、手動UI、汎用broker経路には適用しない。

### G012 canary直前準備で限定的に許可すること

- `AGENTS.md`本節、G012専用docs、tests、actual runtime binding、generation-bound one-use permit型を
  実装する。permit発行条件には、exact generation/request binding、永続one-use marker、fresh current-turn
  operator confirmation、major-incident resume proofを必須とする。permitでruntimeを一度だけbindした後も、
  broker POSTにはfresh reconciliationとDB-backed one-use action proofを別途必須とし、過去confirmationや
  G011 evidenceを再利用できない設計とする。
- actual transportのGET/POST実装を作る。ただし本Stepでは実generationのpermitを発行せず、実client／networkで
  hard guardへ`True`を渡さず、broker POSTを実行しない。fake credential/fake httpx clientの専用testに限り、
  generation/cycle/action-bound one-use permit消費後のhard guard通過とPOST形状を検証してよい。
- monitor-only resident supervisor、generation-bound runtime dispatcher、土曜03:45 exit-sequence dispatch、
  土曜04:00 flat-target monitorを実装する。supervisor自身はcredential、Private API、broker writeを扱わず、
  actual dispatcherの未発効時はsafe marker／通知／persistent HALTだけを行う。
- G012専用LaunchAgentをinstall/bootstrap/kickstartし、有限restart試験を行う。cronは使用しない。
  plistにcredential、operator confirmation、broker payloadを含めない。
- 全実装・独立review・commit/push後のclean mainで、G012 external preparationを固定順序で1回だけ行う。
  sealed Keychain read、Pushover 1回、SMTP 1回、Public GET、`latestExecutions`／`openPositions`／
  `activeOrders`のPrivate GET各1回を許可する。safe aggregate以外は表示・保存しない。
- major-incident resume declarationの発効直前まで準備し、broker POST直前のgo/no-go sheetを提示する。

### G012 canary直前準備でも禁止し続けること

- brokerへのHTTP POST、実注文、OCO、取消、変更、決済、`order`／`cancelOrders`／`closeOrder`の実呼出し。
- permitの実発行、actual POST transportの実有効化、hard guardへ`allow=True`を渡すこと。
- generic allow bridge、複数booleanから再利用可能なlive許可値を作ること、env／`.env`による解除、
  hard guardの削除・弱化、既存Step 6G real-POST経路への接続。
- retry、repost、second attempt、same-action再送、結果不明後のwrite、自動resume。
- credential値・長さ・hash・fingerprint・先頭末尾、raw request/response、header/signature/token、
  実order/execution/position/clientOrder ID、final confirmation全文の表示・ログ・永続化・Git保存。
- CodexによるBUY/SELL、symbol、size、executionTypeの推測・変更。正式30分signalがStay/期限切れなら停止する。
- final current-turn confirmationの代行、生成、再利用、保存。confirmationは別のactual canary Stepでのみ扱う。
- canary broker POST。全gateがclearでもPOST count=0のまま停止する。

### G012 canary直前準備の停止条件

- dirty tree、`HEAD != origin/main`、digest不一致、review VETO、test/ruff/danger scan失敗。
- generation-bound permit／runtime／supervisorのone-use、no-retry、unknown-HALT契約を証明できない。
- LaunchAgent restart後のmonitor heartbeat、single-process lock、persistent HALTを確認できない。
- notification、host、Keychain、Private GETの有限operationが失敗または結果不明。
- account flat/zero-active、market OPEN、fresh quote/spread、正式30分BUY/SELL、operator専有を確認できない。
- major-incident resumeが未発効、residual risk未承認、final current-turn confirmationが未入力。
- 少しでもraw/secret/ID非表示またはPOST count=0を保証できない。

この限定例外の完了はlive-ready、performance proof、unattended live support、broker POST許可を意味しない。

## H-11 v4 G013 corrective actual canary限定例外

通常境界とG012のno-retry停止は維持する。ただしoperatorが明示的にG012失敗後のcorrective generationを
授権し、`実ポストまで進める`と依頼した場合に限り、G013専用の修正、完全review、外部準備、fresh
current-turn確認後の初回actual canaryを実行してよい。この例外はG013、`SHORT_V1`、30分、`USD_JPY`、
1,000通貨に限定し、他generation、他strategy、手動UI、汎用broker経路へ適用しない。
（2026-07-17 operator改定: 初回canary数量を10,000通貨から1,000通貨へ縮小。証拠金所要と
1トレード損失感応度を1/10にするための保守方向の変更であり、予算上限・1 entry/日・その他の
安全条件は不変。G013世代digest・protection/policy hashは新数量で再凍結済み。）

### G013で限定的に許可すること

- costlyなexternal preparationを開始する前の手動判断補助に限り、G013 reviewed generation専用の
  non-authorizing Public signal previewを実行してよい。previewはclean main、reviewed-files digest、
  generation digestにbindし、完了済みM1 slotごとにPublic `klines`の`USD_JPY`／`BID`／`M1`を
  最大1回だけGETする。same-slot retryは禁止し、後続の完了済みM1 slotは別観測として扱う。
- previewはfresh Public M1だけから、exact completed slotで終わる重複なし・1分連続のexact 31本を
  メモリ内で作り、凍結`SHORT_V1`／30分閾値で`candidate_actionable`だけを判定してよい。legacy local M1は
  preview推論に使わない。direction、probability、price、raw candleは表示・保存せず、candle CSV、
  actual preparation state、actual runtime state、formal-candles markerを変更しない。
- 公式tickerの全銘柄list schemaへ対応するsanitized one-use Public preflightを実装し、Public operationを
  generation-bound no-retry ledgerへ追加する。
- actual sessionのfresh正式30分signalと凍結risk幅を作るため、Public `klines`の当日M1とH1を各1回だけ
  GETしてよい。正式30分signalのM1推論もfresh response内のexact completed 31本だけを使い、legacy
  local M1を使わない。credential／Private API／broker writeを使わず、same-request retryを行わない。
- exact注文sheet用のreference status+tickerを各1回、confirmation後かつPOST前のfinal status+tickerを
  各1回だけGETしてよい。final quoteはsheetのreference midpointから5.0pips以内、spread 0.5pips以下、
  age 5秒以内を必須とし、各pairは異なる目的のone-use operationであって再取得retryにはしない。
- 新しいreviewed-files digestとG013 generation artifactを作り、完全test、独立review、commit/push後の
  clean mainで外部準備を最初から一度だけ行う。
- G013 monitor-only LaunchAgentはgeneration-bound preparation ledgerの`60_monitor_launchagent`へ固定する。
  exact labelの既存serviceがload済みの場合だけ`bootout`を最大1 attempt行い、その後`RunAtLoad` plistの
  `bootstrap`を最大1 attempt行う。`kickstart`は使用せず、新generation pathのfresh heartbeatが
  credential/broker read/writeなし、POST count 0であることを20秒以内に確認した場合だけ完了とする。
- plistはexpected reviewed-files digestとexpected generation digestを非秘密引数として固定する。
  monitor entrypointは両digestをruntime state root作成前に再計算結果と照合し、不一致なら
  heartbeatやbroker read/writeを行わず終了する。
- LaunchAgentは`KeepAlive=false`とし、digest mismatchやprocess exit後の自動再起動を行わない。
  operation 60はbootstrap開始後に更新されたheartbeatとpost-bootstrap exact service stateの両方を
  要求し、`launchctl print`のnot-found以外のnonzero結果はunknownとしてfail-closedする。
- monitorが読み込むlocal application moduleはreviewed-files digest対象とし、stdlib-only digest module以外の
  application importは初回digest照合後に行う。import後も同digestを再照合してからsupervisorを作成する。
- fresh正式30分signalが`BUY`または`SELL`で期限内の場合だけ、そのexact方向、`USD_JPY`、1,000、
  `MARKET`を注文sheetへ固定する。
- fresh major-incident resume phraseと、表示したexact注文sheetに対するfresh current-turn challengeを
  operatorが完全一致入力した場合だけ、generation-bound one-use permitを発行しactual runtimeをbindする。
- fresh current-turn challengeは当該turnでoperatorへ1回だけ表示してよい。入力値はhidden readとし、echo、
  file保存、再利用をしない。
- entry `order`を最大1 attempt実行し、結果既知の約定量をfresh reconciliationで確認後、同量のexact
  protection OCOを最大1 attempt実行する。entryとOCOは別actionであり、同一actionのretry/repostではない。
- MARKETが部分約定またはpendingで結果既知の場合に限り、fresh reconciliationで確認した未約定残数量を
  `cancelOrders`で最大1 attempt取消してよい。これはentryの再送ではなく、未約定riskを減らす独立actionで
  あり、取消後のfresh reconciliationが既知かつpending=0の場合だけ実約定量のOCOへ進む。
- OCO成立を`activeOrders`とposition ownership/sizeで15秒以内にsanitized確認し、成立後はforeground
  driverとmonitor-only LaunchAgentを継続する。
- actual write後のread-only reconciliationは各fixed action後に一度だけ許可する。safe aggregate以外を
  表示・保存しない。exact OCO確認後のforeground driverは5秒heartbeatとone-use exit marker監視だけを
  行い、Private GETを一切pollしない。自然な利確／損切りによるflatの認識は、別途scheduleされた
  exit sequenceの固定actionに伴うreconciliationでのみ行う。

### G013でも禁止し続けること

- preview結果を正式signal、注文方向、注文sheet、preflight、permit、allow値、actual preparation証拠として
  流用すること。`candidate_actionable=true`もauthorization、live-ready、performance proofを意味せず、
  actual canaryはexternal preparation後にfresh M1+H1から正式signalを独立生成しなければならない。
- previewのscheduler、polling loop、LaunchAgent、same-slot retry、alternate-date fallback、H1/status/ticker、
  Private API、Keychain、通知、broker write、preview結果の永続化。
- operatorのfresh major-incident resume入力またはfresh current-turn challenge完全一致前のbroker POST。
- Codexによる方向、数量、symbol、execution type、損切り／利確値の推測・変更。
- same-action retry、repost、second attempt、結果不明後のwrite、自動resume、generic allow bridge。
- LaunchAgentのbootout、bootstrap、heartbeat確認が失敗または結果不明の場合の同generation再実行、
  marker削除、変更、reset。
- review中またはdigest変更中のmutable worktreeに追従する未固定LaunchAgentを稼働させること。
  この状態が検出されたgenerationは失効とし、stateやmarkerを保持して新しいreviewed-files
  digestへ進む。
- 未約定残取消の結果不明、拒否、または取消後もpendingが残る状態でのOCO／追加write。
- hard guardの汎用解除、env／`.env`解除、既存Step 6G real-POST経路への接続。
- protected状態での継続的Private GET polling（定期reconciliationを含む。許可されるread-only
  reconciliationは各fixed write後の一度だけ）。
- credential、raw request/response、header/signature/token、実order/execution/position/clientOrder ID、
  operatorが入力したcurrent-turn confirmationのecho・ログ・永続化・Git保存。
- protection未成立、結果不明、HALT後の追加注文、generic opposite close。
- G012 markerの削除、変更、reset、またはG013への証拠流用。

### G013 actual canary停止条件

- dirty tree、`HEAD != origin/main`、digest不一致、review VETO、test/ruff/danger scan失敗。
- Keychain/notification/host/exclusivity/Public/Private GET/LaunchAgentのfresh G013 operationが未clear。
- market非OPEN、quote stale、spread条件未確定または上限超過、正式30分signalがStay/期限切れ。
- account非flat、active order非0、unowned exposure、risk/dead-man/process lock不clear。
- major-incident resume未入力、exact current-turn confirmation不一致、permit期限切れ。
- entry結果不明、未約定残取消の結果不明、OCOが15秒以内にexact-size確認不能、credential/raw/実ID非表示を
  保証できない。

この例外は利益、edge、live-ready、unattended liveの証明ではない。初回canaryの各actual writeはoperatorが
確認したexact sheetとcurrent-turn challengeに限定される。

## 最初に読む文書

- `docs/CODEX_HANDOFF.md`
- `docs/PROJECT_STATUS.md`
- `docs/SHADOW_RUNBOOK.md`
- `docs/PUBLICATION_POLICY.md`
- `docs/GMO_PUBLIC_API_PLAN.md`
- `docs/PHASE2_SHADOW_TRADING_PLAN.md`
