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
  read-only network-time管理者確認はgeneration-bound operation `25_network_time`としてhost/KILLより先に
  完了し、operation `30_host_kill`はそのpassed証拠を必須predecessorとしてGUI認証を再実行せずKILL試験だけを
  行う。operation 25/30のstarted marker作成後に結果不明となった場合は同generationで再試行しない。
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
  各1回だけGETしてよい。final quoteはsheetのreference midpointから5.0pips以内、spread 2.0pips以下、
  age 5秒以内を必須とし、各pairは異なる目的のone-use operationであって再取得retryにはしない。
- 新しいreviewed-files digestとG013 generation artifactを作り、完全test、独立review、commit/push後の
  clean mainで外部準備を最初から一度だけ行う。
- G013 monitor-only LaunchAgentはgeneration-bound preparation ledgerの`60_monitor_launchagent`へ固定する。
  operation marker作成前に`gui/<uid>`がlogin/Aquaかつauxiliary bootstrapper completeの安定domainであることを
  read-only確認する。不安定domainは固定safe statusでretry-safe拒否し、marker、plist、launchdを変更しない。
  exact labelの既存serviceがload済みの場合だけ`bootout`を最大1 attempt行い、その後`RunAtLoad` plistの
  `bootstrap`を最大1 attempt行う。`kickstart`は使用せず、新generation pathのfresh heartbeatが
  credential/broker read/writeなし、POST count 0であることを50秒以内に確認した場合だけ完了とする。
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
- operatorが明示的に有限監視を授権した場合、既存のM1 Public preview候補に限り、同一foreground
  processでfresh H1を一度だけ追加Public GETし、正式ATR(24)入力がmemory内で成立するかを確認する
  formal-aware observerを最大20 completed M1 slot、60秒間隔で実行してよい。M1候補なしではH1を
  取得しない。H1入力不成立はterminal safe failureとし、same-slot retryをしない。observerはactual
  candle cache／actual public ledgerを書き換えず、actual-canaryのimport／起動、Private API、Keychain、
  Pushover/SMTP、permit、broker transport、order actionを持たない。方向、確率、価格、raw candle、注文sheet、
  challengeを出力・保存せず、formal候補時だけ固定macOS soundを最大1回再生してsanitized通知後に停止する。
  formal候補はauthorizationではなく、operatorが新規actual-canaryを起動し独立fresh formal inputを取得する。

### G013でも禁止し続けること

- preview結果を正式signal、注文方向、注文sheet、preflight、permit、allow値、actual preparation証拠として
  流用すること。`candidate_actionable=true`もauthorization、live-ready、performance proofを意味せず、
  actual canaryはexternal preparation後にfresh M1+H1から正式signalを独立生成しなければならない。
- previewのscheduler、polling loop、LaunchAgent、same-slot retry、alternate-date fallback、H1/status/ticker、
  Private API、Keychain、通知、broker write、preview結果の永続化。
  ただしoperatorが明示的に有限監視を授権した場合だけ、Codex automationから、reviewed G013 generationに
  bindした専用foreground observerを最大20 completed M1 slot、60秒間隔で起動してよい。observerは各起動で
  既存のnon-authorizing Public previewを1回だけ呼び、成功以外または`candidate_actionable=true`で直ちに
  停止する。候補時は固定macOS built-in soundを最大1回再生し、Codexへsanitized notificationを返してよい。
  observerはLaunchAgent、cron、常駐process、background loop、Pushover/SMTP、Private API、Keychain、permit、
  broker transportを持たず、direction/probability/price/raw candleを出力・保存しない。候補通知は正式signal、
  注文sheet、authorizationではなく、actual canaryはoperator起動後にfresh formal M1+H1を独立取得する。
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

## H-11 v4 G013 post-canary reconciliation 限定例外

operatorが明示的にgeneration-bound post-canary reconciliationを依頼した場合だけ、既存のentry/exit経路を使わない専用laneを実装・実行してよい。対象は既存G013 canaryの自然OCO後のsanitized状態確認だけであり、新規entry、取消、決済、OCO変更、既存generation markerの変更を一切許可しない。

### この例外で限定的に許可すること

- 新reviewed-files digestとtarget generation digest、immutable origin generation digestに同時bindされた、entry-disabled target generationを作る。
- fresh external preparationをoperation `00_presence`から`50_private_get`まで完了したtarget generationに限り、`latestExecutions`、`openPositions`、`activeOrders`を固定順で各1回だけGETする。entry-disabled one-shot laneはresident runtimeを持たないため、`60_monitor_launchagent`を要求・実行しない。
- origin cycle referenceはorigin coordinator stateからmemory内で導出し、表示・保存しない。結果はsubject observed、account flat、active orders zero、result known、broker read count、broker write attempt countのsanitized aggregateだけとする。
- target generation state rootにstarted markerとterminal sanitized markerを各1回だけ作る。origin generationのHALT、OCO、coordinator、monitor、no-retry markerを変更しない。

### この例外でも禁止し続けること

- `order`、`cancelOrders`、`closeOrder`、OCOその他すべてのbroker write、generic request surface、actual canary、permit、action plan、exit dispatcherのimportまたは呼出し。
- result unknown/non-flat後のretry、同一target generationでの再実行、origin generationのmarker reset・削除・上書き。
- credential、raw request/response、header、signature、実ID、cycle reference、損益値の表示・保存。
- reconciliation-only target generationでの新規entry。entry-disabled contractが存在する間、actual canaryはformal signal取得前に拒否する。

## H-11 v4 unattended shadow controller no-POST実装限定例外

operatorが明示的に完全自動売買へ向けたno-POST controllerとshadow modeの実装を依頼した場合に限り、
H-11 v4の凍結signal／risk contractを使う、broker非依存の共通判断controllerとshadow専用永続ledgerを
実装してよい。この例外は設計・fake test・有限shadow cycle専用であり、live activation、resident運転、
broker read/write、credential、外部通知を許可しない。

### この例外で限定的に許可すること

- `SHORT_V1`、30分、`USD_JPY`、1,000通貨、`MARKET`、1日最大1 entryの既存凍結条件を変更せず、
  caller-suppliedのformal signalとsanitized preflight snapshotから非認可shadow intentを生成する。
- market OPEN、signal／quote age、spread、reference deviation、account flat、active orders zero、process lock、
  notification readiness、clock、risk stop、HALT、entry windowをすべてfail-closedで評価する。
- 同一signalの再処理と同一JST日の2件目をSQLite transactionで拒否し、sticky HALTをclear/resetするAPIを
  持たないshadow ledgerを`backend/shadow_exports/`配下で使用する。
- fake/synthetic入力だけのtest、設計文書、専用contractを追加する。shadow resultは
  `broker_post_authorized=false`、`actual_post_count=0`、`live_ready=false`、
  `unattended_live_supported=false`を固定する。

### この例外でも禁止し続けること

- Private API、Keychain、credential、broker transport、hard guard、permit、actual coordinator、
  `order`／`cancelOrders`／`closeOrder`／OCO write経路のimport、呼出し、接続。
- shadow判定booleanをhard guardの`allow`へ接続するgeneric allow bridge、env／`.env`によるlive解除、
  `LIVE=true`型のmode switch。
- scheduler、polling loop、LaunchAgent、cron、resident process、Public／Private network access、
  Pushover／SMTP送信。
- shadow intent、preview、過去canary confirmation、旧generation evidenceをlive authorizationへ流用すること。
- `live_ready`、`unattended_live_supported`、`actual_post_authorized`のtrue化。live化は独立review、
  新reviewed generation、fresh external preparation、固定小額contractを必須とする別Stepで扱う。

## H-11 v4 unattended Public-only finite shadow adapter/runner 限定例外

上記no-POST shadow controller例外の境界は維持する。ただしoperatorが明示的に、完全自動売買へ向けた
Public-only有限shadow adapterとbounded runnerの実装を依頼した場合に限り、既存の凍結signal／risk
contractとno-POST controllerへ、GMO **Public** read-only市場データだけを供給するnetwork adapterと
有限cycle runnerを実装してよい。この例外は設計・fake test・有限Public shadow専用であり、live
activation、resident運転、Private API、credential、broker read/write、外部通知を許可しない。

### この例外で限定的に許可すること

- GMO Public read-only endpoint（`/public/v1/status`、`/public/v1/ticker`、`/public/v1/klines`の
  M1／H1）だけを、既存の`GmoPublicMarketDataClient`経由で、完了済みM1 slotごとに有限回GETする。
  same completed slotは`backend/shadow_exports/`配下のO_EXCL markerで一度だけclaimし、retryしない。
- 凍結SHORT_V1／30分方向推論と、official H1だけからのATR(24)（`build_g013_formal_canary_input`と
  同一結果をcross-check testで固定）を再利用し、caller非依存のformal signalとsanitized market
  snapshotをメモリ内で作る。account flat／active orders／boot reconciliation／fresh broker snapshotは
  Private GETなしに観測できないため、preflightでfail-closed（未観測=block）とする。よって
  Public-only cycleは`SHADOW_WOULD_ENTER`へ到達せず、常にsafe blockに留まる。
- no-POST controllerを1 cycle呼び、generation非依存のSQLite shadow ledgerへ非認可決定を記録する。
- 有限のbounded runner（最大cycle数または固定interval。resident化・常駐loop・自動再起動なし）で
  上記を駆動し、sanitized aggregateだけを出力する。direction、probability、price、raw candle、
  実IDを表示・保存しない。
- 上記adapter／runner／fake test／設計docを必要最小限で追加する。shadow結果は
  `broker_post_authorized=false`、`actual_post_count=0`、`live_ready=false`、
  `unattended_live_supported=false`を固定する。

### この例外でも禁止し続けること

- Private API、Keychain、credential、broker transport、hard guard、permit、actual coordinator／
  transport／adapter、`order`／`cancelOrders`／`closeOrder`／OCO write経路のimport、呼出し、接続。
- Public結果からaccount flat等を推測すること。account／position／order／risk stopの観測は
  credential＋Private GETを使う別phaseで扱う。
- scheduler、cron、LaunchAgent、launchd、resident process、background loop、自動再起動、
  Pushover／SMTP送信。
- shadow判定booleanをhard guardの`allow`へ接続するgeneric allow bridge、env／`.env`／`LIVE=true`に
  よるlive解除。
- shadow observation、intent、preview、過去canary confirmation、旧generation evidenceを
  live authorization、live-ready、performance proofへ流用すること。
- `live_ready`、`unattended_live_supported`、`actual_post_authorized`、`broker_post_authorized`の
  true化。live化は独立review、新reviewed generation、fresh external preparation、固定小額contractを
  必須とする別Stepで扱う。
- 既存G013 canary／post-canary markerの変更・reset・削除・上書き、またはそれらの証拠流用。

## H-11 v4 unattended shadow Private-GET account/order preflight 限定例外（slice 1・fake-only）

上記Public-only shadow例外の境界は維持する。ただしoperatorが明示的に、Private GETを使う
full operational read-only shadowへの着手を依頼した場合に限り、shadow preflightのうち
`broker_snapshot_fresh`／`boot_reconciled`／`position_count`／`active_order_count`を
`latestExecutions`／`openPositions`／`activeOrders`のsanitized Private GETから導出する型・
snapshot・合成関数を実装してよい。この例外はslice 1（account/order観測のみ）専用であり、
notification送信、daily／monthly／consecutive-loss stop追跡、host／dead-man状態、
operator persistent HALT配線、runnerへの実結線は含まない。

### この例外で限定的に許可すること

- `latestExecutions`／`openPositions`／`activeOrders`用の、shadow専用・generation非依存の
  read-only GET Protocolと、sanitized件数（`latest_executions_count`／`open_positions_count`／
  `active_orders_count`／`account_flat`／`active_orders_zero`）だけを返すsnapshot型を実装する。
- Phase 1のfail-closed preflightのうち`broker_snapshot_fresh`／`boot_reconciled`／
  `position_count`／`active_order_count`だけを上記snapshotへ差し替える合成関数を実装する。
  `notification_path_ready`、daily／monthly／consecutive-loss stop、`operator_halt_clear`は
  この合成対象に含めず、Phase 1の値のまま変更しない。
- HMAC署名ヘッダ生成には既存の純粋関数`app.private_api.auth.build_auth_headers`（呼び出し側が
  渡した値だけを使い、credential store・env・fileを読まない）だけを再利用してよい。
- fake credential pair、fake HTTP transportだけを使うtestを追加する。実Keychain reader関数は
  このモジュールへ実装しない（＝defaultからの実credential到達経路を作らない）。
- 設計docとtestを必要最小限で追加する。

### この例外でも禁止し続けること

- 実Keychain read、実credential値の読込・表示・保存。このモジュールへ実Keychain reader
  （`security find-generic-password`等）を実装・importしないこと。
- 実Private API endpointへの実HTTP呼出し、実broker read。testは常にfake transportだけを使う。
- 本snapshot／合成関数をshadow runner CLIへ実結線すること。実結線は別途明示依頼と別reviewを
  必須とする独立Stepとして扱う。
- Pushover／SMTP送信、notification transportのimport・呼出し。
- daily／monthly／consecutive-loss stop、host／dead-man状態、operator persistent HALTの実装・
  claim。これらは別phaseで扱う。
- broker write endpoint（`order`／`cancelOrders`／`closeOrder`／OCO）のimport・呼出し・接続。
- `broker_post_authorized`、`live_ready`、`unattended_live_supported`のtrue化。
- 既存G013 canary／post-canary marker、`h11_v4_gmo_readonly_preflight.py`等の既存G013専用
  preparation-gated moduleの変更、またはそれらのgate／permitへの結合。

## H-11 v4 unattended shadow 通知判断layer 限定例外（slice 2・fake-only）

上記slice 1の境界は維持する。ただしoperatorが明示的に、shadow cycleの結果を通知すべきか判断する
layerの実装を依頼した場合に限り、既存の汎用・fake-only強制済み`H11V4DisabledDualRouteNotifier`
（`app/services/h11_v4_notification_binding_no_post.py`）を再利用し、shadow controller報告から
通知要否を判定する純粋関数を実装してよい。実Pushover/SMTP送信、runnerへの結線は含まない。

### この例外で限定的に許可すること

- `H11V4NotificationEvent`へ`SHADOW_ACTIONABLE_OBSERVED`（非critical）と`SHADOW_HALT_ENGAGED`
  （critical、sticky HALTはclear/resetパスがないため）の2値を追加専用で追記する（既存値・既存
  `CRITICAL_EVENTS`メンバーは変更しない）。
- shadow controller の`V4ShadowControllerReport.status`と直前statusから、通知要否と
  重複排除（同一statusが連続する限り再通知しない）を行う純粋関数を実装する。I/Oを持たない。
- 送信自体は既存の`H11V4DisabledDualRouteNotifier.notify_once`をそのまま呼ぶだけとし、
  新しいtransport実装、新しいPushover/SMTP接続コードは一切追加しない。
- fake transport（`H11V4FakePushoverTransport`／`H11V4FakeEmailTransport`）だけを使うtestを
  追加する。default（Refusing）transportでは送信不能であることも確認する。

### この例外でも禁止し続けること

- 実Pushover/SMTP transportの実装・接続、`H11V4DisabledDualRouteNotifier`のfake_only強制の
  弱体化・迂回。
- shadow runner CLIへの結線（別途明示依頼が必要な独立Step）。
- daily／monthly／consecutive-loss stop、host／dead-man状態、operator persistent HALTの実装・
  claim。
- broker write endpoint、Private API、Keychain、credentialのimport・呼出し・接続。
- `broker_post_authorized`、`live_ready`、`unattended_live_supported`のtrue化。

## H-11 v4 unattended live adapter 設計限定例外（design-only・コード実装なし）

上記slice群の境界は維持する。ただしoperatorが明示的に、unattended live adapter（将来の実発注経路）の
全体設計を依頼した場合に限り、**文書（design doc）とAGENTS.md本体の更新だけ**を行ってよい。
このStepはPythonコードを一切書かない。既存のG012/G013 permit／action-proof／coordinator／
exit dispatcher／hard guardコードを一切変更しない。実credential・実Private API・実broker write・
scheduler・resident processへは一切接続しない。

### この例外で限定的に許可すること

- 既存のgeneration-bound one-use permit型（`v4_gmo_canary_activation.py`）、persisted action-proof
  chain（`v4_gmo_persisted_authorization.py`）、real coordinator／coordinated-path
  （`v4_gmo_actual_coordinator.py`／`h11_v4_gmo_coordinated_actual_path.py`）、pure OCO計算
  （`build_exact_fill_oco_plan_no_post`）、exit dispatcher（`h11_v4_gmo_exit_dispatcher.py`）、
  hard guard（`assert_real_broker_post_allowed`）を**読み取り調査**し、unattended文脈での再利用可否を
  設計docへ記述する。
- G013の人間確認2種（major-incident resume phrase、current-turn challenge）を置き換える、
  unattended向けpermit発行判断の**設計案**（構造要件・複数の独立した安全条件・operatorレビュー
  ポイント）を文書化する。この設計案自体はpermitを発行する実装ではない。
- Phase 5昇格基準（機械判定可能なchecklist）を文書化する。
- 新しいAGENTS.md本体限定例外（次の実装slice用）の草案を、実装前提を明記した上でこのdocへ含めてよい。

### この例外でも禁止し続けること

- 実装コード（Python）を一切書かない。型定義・関数実装・permit発行実装はすべて次の別Step。
- 既存のG012/G013 permit／coordinator／transport／hard guardコードの変更。
- 実credential、実Private API、実broker write、scheduler、resident processへの接続。
- unattended permit発行判断の設計案を、実際のpermit発行や活性化として扱うこと。設計docの完成は
  live-ready、performance proof、実装承認を意味しない。

## H-11 v4 unattended live activation components 実装限定例外（fake-only・未結線）

上記design-only例外の設計docをoperatorがレビューし、§3.2の6条件構造と§3.4の決定値
（authorized window=1 JST営業日・authorization 1件あたり最大1 entry・cold-startはそのまま許容）を
明示承認した場合に限り、その設計に対応する以下のcomponent群を、fake-only／未結線で実装してよい。
この例外はPhase 4 component実装専用であり、実credential・実Private API・実broker write・
実通知送信・scheduler・resident process・既存G012/G013コードの変更を一切含まない。

### この例外で限定的に許可すること

- (a) realized P&L risk ledger: 当初は専用SQLite台帳の新設を想定したが、調査の結果、既存の
  reviewed済み`app/h11_auto/runtime_safety.py`（`PhaseBRiskPolicy/State/Store`・
  `evaluate_risk_before_entry`・`record_closed_result_once`・JST日/月rollover・
  cycle_refごとのdedup・凍結risk値5,000円/trade・10,000円/日・50,000円/月・5連敗）が
  この要件を既に満たすため、**変更なしで再利用**する（重複実装によるdrift回避。2026-07-24
  operator承認済みの設計doc §9に記録）。新規台帳は実装しない。既知の制約: `PhaseBRiskStore`は
  state file欠損時に新規ACTIVE stateを生成するため、wiring時に「file欠損=起動拒否」の
  bootstrap規律を別途必須とする（設計doc §9.2-1）。
- (b) supervisor health/dead-man check: 既存`DeadManPolicy/Store`（recency）を再利用し、
  新規moduleは「直前N秒間の連続健全性」（continuity chain）判定だけを追加する。
  read-onlyのhost状態観測を含んでよいが、process kill・sleep・reboot・設定変更は行わない。
- (c) operator authorization artifact型: operator-write-onlyの事前授権artifact
  （1 JST営業日window・最大1 entry・O_EXCL one-use消費marker）。自動化側から
  window延長・cap引き上げ・再発行を行うAPIを構造的に持たない。
- (d) unattended live専用のoperator persistent HALT: 既存`engage_risk_kill`＋
  `AutoRiskStopState.KILLED`（un-kill APIなし・auto-clearなし）を**変更なしで再利用**する
  （(a)と同じ理由・同じ2026-07-24記録）。state rootはshadow ledgerと別であることをwiring時に
  必須とし、(a)のbootstrap規律（file欠損=起動拒否）がHALTの永続性保証の前提となる。
- (e) permit発行orchestration: (a)〜(d)と既存fail-closed gate群の全条件成立時だけ、
  既存の**無変更**`issue_v4_gmo_actual_activation_permit`へ渡すproof objectを組み立てる
  純粋な判断layer。ただし本例外の実装・testではpermitの実発行はfake state rootに対する
  test内でのみ行い、実runtime state root・実coordinator・実transportへは接続しない。
- 各componentのfake-only test、設計doc更新、AGENTS.md本体の必要最小限更新。
- shadow系moduleと同様のimport-graph isolation test（actual transport・credential・
  notification実送信・G013 canary orchestrationへの到達を拒否）。

### この例外でも禁止し続けること

- 実credential、実Keychain read、実Private API、実broker write、実Pushover/SMTP送信。
- scheduler、cron、LaunchAgent、resident process、background loopの追加・install。
- 既存G012/G013 permit／coordinator／transport／exit dispatcher／hard guardコードの変更。
- (c)のauthorization artifactを自動化側から作成・延長・再発行するAPIの実装。artifactの
  作成はoperator自身の明示的なCLI/手動操作として別Stepで設計する。
- (e)から実coordinator・実transport・実runtime state rootへの結線。結線は全component
  review完了後の別Step・別明示承認とする。
- `broker_post_authorized`、`live_ready`、`unattended_live_supported`のtrue化。
- 本例外下の実装・test完了をlive-ready、performance proof、activation承認として扱うこと。

## H-11 v4 unattended live daily authorization artifact作成CLI 限定例外（operator手動実行専用）

上記component例外は、authorization artifactの作成を「operator自身の明示的なCLI／手動操作として
別Stepで設計する」と明記して先送りした。operatorが明示的にこのCLIの実装を依頼した場合に限り、
その別Stepとして以下を実装してよい。artifactのconsume（消費）は既存の
`h11_v4_unattended_live_authorization.py`のままとし、本例外はcreateだけを対象とする。

### この例外で限定的に許可すること

- generation-bound canonical path helper（`v4_gmo_runtime_paths.py`と同型のdigest検証、
  `backend/market_data/h11_v4_unattended_live/generation-{digest}/`配下）を新設する。
  既存のgitignore済み`backend/market_data/`配下に限定する。
- operatorが手動実行するCLIスクリプト（`backend/scripts/`配下）を新設する。実行時のJST日付は
  常に「実行時点の今日」固定とし、operatorによる日付指定・過去日・未来日オーバーライドを
  受け付けない。`--generation-digest`は明示必須引数とし、暗黙のdefaultやfallback推定を持たない。
  既存artifactが当日分で存在する場合は`--force`なしで上書きしない。
- 生成したartifactに対して、既存の`check_operator_daily_authorization`をそのまま呼び、結果を
  sanitizedに表示する（値の解釈・判断ロジックの新規実装はしない）。
- 各componentのfake-only／ローカルfilesystemだけを使うtest、設計doc更新、AGENTS.md本体の
  必要最小限更新。

### この例外でも禁止し続けること

- このCLIをscheduler、cron、LaunchAgent、resident process、他のCodex/Claude自動実行から
  呼び出すこと。呼出しは常にoperatorの手動実行に限る。
- `h11_v4_unattended_live_authorization.py`の公開関数（check／consume）を変更・拡張すること。
  本例外はcreate専用の別スクリプトとし、既存モジュールの「read-and-consume only」設計を
  変更しない。
- 実credential、実Private API、実broker write、実Pushover/SMTP送信、G012/G013コードの変更。
- artifactの自動再発行・自動延長・cap自動引き上げの実装。
- `broker_post_authorized`、`live_ready`、`unattended_live_supported`のtrue化。
- 本例外下の実装完了をlive-ready、performance proof、activation承認として扱うこと。

## H-11 v4 unattended proof constructor 設計限定例外（design-only・コード実装なし）

これは、Phase 4設計docが「G013 permit moduleのprivate-token規律内に追加する、別途明示承認・別review
必須の唯一のG013コード変更」として明示的に先送りした項目である。operatorが明示的にこの設計を
依頼した場合に限り、**文書（design doc addendum）とAGENTS.md本体の更新だけ**を行ってよい。
このStepはPythonコードを一切書かない。`v4_gmo_canary_activation.py`を含む既存G012/G013コードは
一切変更しない。

### この例外で限定的に許可すること

- `v4_gmo_canary_activation.py`の`_RESUME_TOKEN`／`_CONFIRMATION_TOKEN`によるprivate-token規律を
  読み取り調査し、unattended文脈でのproof発行に必要な新規関数の**設計**（シグネチャ・検証順序・
  「decision.allowedをproof構築に流用しない」ための一次state再検証方針）を文書化する。
- 既存の`issue_v4_gmo_actual_activation_permit`／`consume_v4_gmo_actual_activation_permit`／
  `confirm_v4_major_incident_resume_exact`／`confirm_v4_current_turn_exact`を変更しないことを
  設計の前提として明記する。
- 「6条件評価を繰り返し呼んでも、同一JST日にresume/current-turn proofのペアを2回以上mintできない」
  ことを保証する具体的な順序（authorization artifactの消費を、6条件クリア後の最初の書き込みとして
  行う）を設計に含める。
- この設計案自体はproofを発行する実装ではない。

### この例外でも禁止し続けること

- 実装コード（Python）を一切書かない。
- `v4_gmo_canary_activation.py`を含む既存G012/G013コード（permit／coordinator／transport／
  exit dispatcher／hard guard）の変更。
- この設計案を、実際のproof発行やactivationとして扱うこと。設計doc完成はlive-ready、
  performance proof、実装承認を意味しない。

## H-11 v4 unattended proof constructor 実装限定例外（唯一のG012/G013コード追記・未結線）

上記design-only例外で承認された設計（§10、Option A、consume-first順序、§9.2項目3の解決済み state
root）をoperatorが実装承認した場合に限り、`v4_gmo_canary_activation.py`へ**追加専用**で新関数を
実装してよい。これは本トラック全体で唯一のG012/G013コード変更である。既存関数
（`V4GmoCanaryIntent`／`V4CurrentTurnChallenge`／`confirm_v4_major_incident_resume_exact`／
`confirm_v4_current_turn_exact`／`issue_v4_gmo_actual_activation_permit`／
`consume_v4_gmo_actual_activation_permit`）は一切変更しない。

### この例外で限定的に許可すること

- `v4_gmo_canary_activation.py`へ、`app.h11_auto.runtime_safety`（同一package。既存の
  `v4_host_rehearsal.py`が`app.services`をimportしている前例に倣い、`app.services`のunattended
  live moduleも直接importしてよい）を使い、authorization／risk／dead-man／heartbeat
  continuityを**呼び出しの瞬間に新鮮読み込みし直す**新関数を1つ追加する。
  `notification_ready`・`entry_gate_blocked_reasons`は呼び出し側供給のまま（§10.2の意図的な
  scope境界）。
- 新関数は既存の`decide_unattended_permit_issuance`（変更しない）を呼び、`allowed`なら
  **真っ先に**`consume_operator_daily_authorization_once`を呼んでから（これが今回の評価での
  最初の書き込み）、resume proofとcurrent-turn proofの両方を同一評価から同時にmintして返す。
  consume呼び出し前にはいかなるproofもmintしない。
- fake-only test（fake store／tmp pathだけを使う）に加え、consume-then-mintの順序を**真の並行
  プロセス／スレッド**でレースさせ、同一JST日に2組目のproof pairが絶対にmintされないことを
  検証する、実際に並行させるconcurrency testを追加する（設計doc §10.3/§10.4が要求する、
  従来のsequential呼び出しだけのtestでは代替できない項目）。
- 新関数のdocstringに、「既存の`confirm_v4_major_incident_resume_exact`／
  `confirm_v4_current_turn_exact`をunattended経路から直接呼び出してこの新関数をバイパスしては
  ならない」旨を明記する。orchestration moduleがまだ存在しないため、import-graph isolation
  によるbypass防止の強制は、orchestration実装時の別Stepで扱う（本Stepでは文書化と、新関数
  自体の閉じたtestまでとする）。
- 設計doc §10.4の該当項目の更新、AGENTS.md本体の必要最小限更新。

### この例外でも禁止し続けること

- 既存のG012/G013関数（上記6関数）の変更。新関数は追加専用。
- 実credential、実Private API、実broker write、実Pushover/SMTP送信。
- 新関数を実coordinator／実transport／実runtime state root／scheduler／resident processへ
  結線すること。結線は別途明示承認が必要な独立Stepとする。
- `broker_post_authorized`、`live_ready`、`unattended_live_supported`のtrue化。
- 本例外下の実装完了をlive-ready、performance proof、activation承認として扱うこと。
