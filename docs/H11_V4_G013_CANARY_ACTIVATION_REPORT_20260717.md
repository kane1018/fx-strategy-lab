# H-11 v4 G013 Corrective Canary Activation Report

Date: 2026-07-17

Status: `IMPLEMENTED_VALIDATED_PRE_EXTERNAL_PREPARATION_NO_BROKER_POST`

## 1. Purpose

G012のno-retry証拠を保持したまま、公式GMO FX ticker schemaへ対応するcorrective generationを
G013として新設する。Public GETをone-use preparation ledgerへ追加し、完全review・commit/push・
clean main後に外部準備を最初から実行する。

### 1.1 2026-07-20 host rehearsal corrective generation

旧G013 generationのexternal preparationは、`30_host_kill`で
`READ_ONLY_HOST_CHECK_FAILED`となった。旧generationのstarted/passed markerは削除、変更、resetせず、
以降のKeychain、notification、Public/Private GET、broker POSTへ進まない。

sanitized read-only調査では`pmset -g batt`、直接の
`systemsetup -getusingnetworktime`、`sntp -t 2 time.apple.com`を分離した。直接の`systemsetup`は
想定どおり管理者権限不足を返し、管理者read-only fallbackは別の120秒timeout契約である。一方、
非管理者command wrapperはすべて5秒固定で、DNS/接続時間を含むSNTPだけが内部2秒制限とは別に
wrapper timeoutへ到達し得た。safe markerは失敗commandを永続化しないため事後の一意特定はできないが、
観測可能な契約上の最小correctiveとしてSNTP wrapperだけを有限15秒へ変更する。`pmset`と直接
`systemsetup`の5秒、管理者fallbackの120秒、fail-closed、same-generation no-retryは維持する。

修正後は新しいreviewed-files digestとgeneration digestを焼成し、旧generationの外部証拠を一切
流用しない。generation labelは本限定例外の`H11_AUTO_30M_20260717_G013`を維持するが、digestで分離された
新規generationとして完全reviewと外部準備を最初から要求する。

### 1.2 2026-07-20 host runner CLI corrective generation

前項の新generationは、operatorのfresh email confirmation後、host runnerへ`--help`を渡した際に
runnerが引数をparseせず`30_host_kill.started.json`を作成したため停止した。passed markerは作成されず、
後続のexclusivity、Public/Private GET、LaunchAgent、permit、broker writeへは進んでいない。この失敗markerも
削除、変更、resetせず保持し、同generationでhost operationを再実行しない。

corrective runnerはargparseをclean-main確認、external gate load、ledger構築より前に実行する。`--help`は
exit 0、不正引数はexit 2で終了し、どちらもpreparation operationを開始しない。正式な引数なし実行だけが
one-use host operationへ進む。月曜から木曜は既存policyどおりblocked hoursの05:00-09:00 JSTを除いて
entry可能であり、本日2026-07-20月曜のために曜日/risk/order contractを緩和しない。Fridayの09:00-21:00
制限、1,000通貨、SHORT_V1、USD_JPY、30分、MARKET、全no-retry条件も維持する。

### 1.3 2026-07-20 LaunchAgent lifecycle corrective generation

前項generationは`60 monitor-only LaunchAgent`でplist installとbootstrap後、`launchctl kickstart -k`が
15秒以内にreturnせず停止した。read-only reconciliationではservice runningとfresh
`WAITING_FOR_CANONICAL_RUNTIME` heartbeatを確認したが、同generationは結果不明のため再実行せず、
markerとserviceを変更せず保持する。

corrective lifecycleは`60_monitor_launchagent`をgeneration-bound preparation ledgerの必須最終operationへ
追加し、外部mutation前にno-retry started markerを確定する。exact labelの既存serviceが存在する場合だけ
bootoutを最大1 attempt、その後RunAtLoad plistのbootstrapを最大1 attempt実行する。kickstartは使用しない。
新generation専用runtime pathのheartbeatが50秒以内にfreshとなり、generation digest一致、
`WAITING_FOR_CANONICAL_RUNTIME`、broker read/write false、POST count 0の場合だけpassed markerを作る。
timeout、bootout/bootstrap失敗、heartbeat不一致・staleはpersistent stopとし、同generationで再試行しない。

review中の2026-07-20 12:20:44 JSTに新generation runtime rootが予期せず生成され、
12:29:34 JSTに既存serviceが同generation digestのheartbeatを生成した。sanitized確認で
broker read/writeはfalse、broker POST countは0だった。exact labelへのcontainment `bootout`初回は
`Operation not permitted`で失敗したため、同generationでは再試行せず、runtime stateを削除・変更・
resetしない。次generationのplistはexpected reviewed-files digestとgeneration digestを固定し、
entrypointは両者をruntime root作成前に検証する。

初回の独立reviewは、automatic `KeepAlive`、pre-bootstrap heartbeat受理、monitorのtransitive dependencyの
digest漏れ、`launchctl print`のunknownをabsent扱いする点をVETOした。correctiveで`KeepAlive=false`、
bootstrap開始後のheartbeat更新とpost-bootstrap service確認、not-found以外のnonzero fail-closed、
stdlib-only pre-import digest照合とtransitive monitor dependencyのdigest追加を実装した。
二回目の独立reviewはdigest module自体が`app.h11_auto`配下にあり、初回照合前にpackage initializerが
実行される点をVETOした。correctiveでdigest moduleをbackend top-levelへ移し、初回照合前のproject
importをstdlib-only moduleだけに限定した。後段で実行されるpackage initializerとfake boundaryも
reviewed-files digestへ追加し、application import後の再照合を維持する。

### 1.4 2026-07-20 Pushover acknowledgement timeout corrective generation

前項generationのfresh external preparationはpresence 6/6とsealed Keychain access 6/6を完了後、
Pushover preparation messageを1回だけ送信したが、有限15分以内にoperator acknowledgementを確認できず
`PUSHOVER_ACK_NOT_CONFIRMED_NO_RETRY`で停止した。`10_pushover.started.json`は保持し、passed markerはなく、
SMTP、Public/Private GET、LaunchAgent、signal、quote、permit、broker writeへ進んでいない。broker POST countは0。

operatorはPushover notificationを受信してacknowledgeできる状態へ戻した。これはmajor-incident resume、
current-turn confirmation、注文承認ではなく、次generationのpreparation operation 10を実行可能にする運用上の
correctiveだけとして扱う。旧markerを削除、変更、resetせず、新しいreviewed-files digestとgeneration digestへ
分離し、presenceから全operationをfreshに実行する。Pushover送信は新generationでも最大1回、application再送なし、
15分以内にacknowledgementを確認できなければ再びno-retry停止する。

### 1.5 2026-07-20 GUI administrator context corrective generation

active-M1 corrective generationのexternal preparationは、fresh presence、Keychain、Pushover acknowledgement、
SMTP、email receipt confirmationを完了後、`30_host_kill`で`network_time_enabled=null`となり停止した。
sanitized reportでは管理者fallbackが使用され、AC power、disk、SNTP skew、disposable KILL、persistent HALTは
clearだった。broker GET/POSTは0で、exclusivity、Public/Private GET、LaunchAgent、formal signal、quote、permitへ
進んでいない。failed markerとHALTは削除、変更、resetしない。

host CLIはCodexの通常sandboxから起動され、固定read-only `osascript`管理者fallbackをGUI-capable contextで
完了できなかった。strict `Network Time: On/Off` parser、fixed command、timeout、fail-closed条件は正しく、
codeや判定条件を緩和しない。次generationでは、fresh generation-specific operator承認後、引数なしhost CLIを
GUI-capable escalated contextから1回だけ実行する。external preparationは`00_presence`から全operationをfreshに
再実行し、今回のemail確認を含む旧generation証拠は一切流用しない。

実装前の独立reviewは、operation 10からの再開案をVETOした。corrective手順はledgerの固定順序どおり
operation 00から再開する。Architecture/SafetyはCLEARで、code変更不要、procedure-only reviewed changeは
この修正条件で許容との判定だった。

### 1.6 2026-07-22 GUI login-domain transition corrective generation

daily one-shot/spread corrective generationのoperation 60は、bootstrap success後もserviceが`xpcproxy`、
`execs=0`のままPython supervisorへ遷移せず、50秒以内にheartbeatを生成しなかった。sanitized unified logは
同時刻に多数のApple/third-party agentを含む`gui/501` domain全体がon-demand-only transition中だったことを
示した。G013 broker read/writeはfalse、broker POST countは0で、`60_monitor_launchagent.started`を保持し、
同generationでは再実行しない。

correctiveはoperation marker作成前に`launchctl print gui/<uid>`をread-onlyで1回確認し、このhostで実測した
`type=login`、`session=Aqua`、auxiliary bootstrapper complete、`gui login` propertiesをすべて要求する。
不安定・timeout・欠落は固定`GUI_DOMAIN_NOT_READY_RETRY_SAFE`で拒否し、ledger、plist、launchdを変更しない。
domain transitionが確認後に始まるTOCTOUは残るため、bootstrap後50秒heartbeat gateは最終検出器として維持する。
bootout/bootstrap各最大1 attempt、kickstart禁止、KeepAlive=false、credential/broker非接続は変更しない。

## 2. Official ticker contract correction

- `GET /public/v1/ticker`はsymbol queryを送らず、全銘柄listを返す。
- list内から`symbol == USD_JPY`の行がexactly oneであることを要求する。
- status、bid、ask、timestampはprocess memory内だけで検証する。
- 永続reportはmarket open、quote fresh、spread pips等のsanitized aggregateに限定する。
- status 1回+ticker 1回の合計2 GETで、retry、second attemptを持たない。
- actual sessionでは正式signal生成用に当日M1とH1のPublic klinesを各1回だけ取得する。M1から凍結済み
  `SHORT_V1`の30分方向を再計算し、H1の最新24本のcompleted true range平均をATR(24)として固定する。
- activeな未完成M1/H1 barはfail-closedで拒否する。使用したcompleted M1/H1 OHLC列とmodel config hashから
  `input_provenance_digest`を生成し、exact注文sheetとcurrent-turn challengeへ結合する。Public candle本体は
  gitignore済み`backend/market_data/`だけに保存し、report、Git、chatには出さない。
- final entry quoteは5秒以内、USD/JPY spreadは0.5pips以下を必須とする。
- exact注文sheet作成時にreference status+tickerを各1回取得し、表示したreference BID/ASKもsheet digestへ
  結合する。confirmation後のfinal status+tickerも各1回だけ取得し、reference midpointから5.0pipsを超えて
  動いていた場合はPOSTせず停止する。
- formal M1/H1、reference quote、final quoteは別々のgeneration-bound operationとして、各I/O前に
  `O_EXCL` markerを確定する。同generationで同じpurposeのGETを再試行できない。

## 3. Corrective preparation sequence

```text
00 presence
05 sealed Keychain access
10 Pushover send + acknowledgement
15 SMTP send
20 fresh email receipt confirmation
30 current-host / disposable KILL
40 fresh account exclusivity confirmation
45 Public status+ticker GET
50 latestExecutions/openPositions/activeOrders GET
60 monitor-only LaunchAgent install/restart evidence
```

各operationはexternal I/O前にgeneration-bound started markerを`O_EXCL`で保存する。失敗・不明時は
同generationで再試行しない。

## 4. Frozen canary contract

```text
generation=H11_AUTO_30M_20260717_G013
strategy=SHORT_V1
horizon=30m
symbol=USD_JPY
size=1000
entry=MARKET
entry_window_jst=Monday_to_Thursday_except_05:00_to_09:00;Friday_09:00_inclusive_to_21:00_exclusive
exit_sequence=minimum(entry_plus_23h,Saturday_03:45_JST)
weekend_flat_target=Saturday_04:00_JST
maximum_unprotected_seconds=15
maximum_entry_spread_pips=0.5
maximum_reference_deviation_pips=5.0
atr_24=latest_24_completed_H1_true_range_mean
same_action_retry=false
same_action_repost=false
```

正式signalが`BUY`/`SELL`かつ期限内の場合だけ、方向をそのままexact intentへ固定する。Codexは方向、
数量、symbol、execution typeを推測・変更しない。

## 5. Actual canary boundary

外部準備、fresh Public/Private preflight、risk/dead-man/process lock、major-incident resumeのfresh入力、
exact注文sheet確認後のfresh current-turn challengeがすべてclearの場合だけ、generation-bound permitを
一度発行できる。entry MARKETとexact-size protection OCOは別actionであり、各action最大1 attemptとする。
operator入力の直前状態を信頼せず、permit発行直前にclean main、`HEAD == origin/main`、reviewed-files digest、
generation digest、completed preparation evidenceを再読込・再照合する。不一致時はconfirmationを消費せず停止する。
正式30分signalは準備時だけでなくPOST直前にも観測から300秒以内であることを再検査する。
MARKETが結果既知の部分約定/pendingの場合は、fresh reconciliationで確認した未約定残だけを
`cancelOrders`で最大1 attempt取消する。取消結果が既知かつpending=0の場合だけ、実約定量と同じOCOへ
進む。結果不明、取消拒否、pending残存、または15秒以内にexact OCO確認不能の場合はpersistent HALTとし、
追加writeを行わない。

各fixed write後のPrivate reconciliationは1 sequenceだけとする。その同じsnapshotからtransport結果を確定し、
次actionのexact数量を作り、one-use evidenceを引き渡す。追加GETで同じ状態を取り直さない。POST直前には
weekday-specific entry windowも再確認し、Fridayは21:00 JST到達後、signalが期限内でもentryを拒否する。注文sheetはfrozen
session内で保持し、permit発行前とfinal quote前にsheet SHA-256、formal signal、reference quote、risk幅を
再照合する。

保護成立後のforeground driverは5秒heartbeatとone-use exit marker監視だけを行い、Private GETをpollしない。
各fixed write後のauthoritative reconciliationは1回だけで、その同じevidenceをclassificationと永続記録へ渡す。
自然なOCO決済によるflatの認識は、別途scheduleされたexit sequenceの固定actionに伴うreconciliationでのみ
行う（継続的なscheduled observationはoperator授権のG013例外「各fixed write後1回」を超えるため実装しない）。

actual canary runnerは`python -m scripts.h11_auto_v4_g013_actual_canary`で、exact注文sheetを表示後、fresh
major-incident resume phraseとfresh current-turn challengeの完全一致入力を同一process内で要求する。
challengeはside/size/symbol/execution typeだけでなく、表示したexact注文sheet全体のSHA-256 digestにも
結合される。operator入力はhidden readでecho・保存しない。
challengeは通常stdoutやファイルに出さず、非表示入力プロンプト内に一時表示する。

## 6. Current safety flags

```text
actual_post=false
broker_write=false
broker_post_count=0
activation_permit_issued=false
major_incident_resume_effective=false
current_turn_confirmation_consumed=false
credential_value_exposure=false
raw_response_exposure=false
real_id_exposure=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```

### 1.5 2026-07-20 Public candle refresh corrective generation

- The prior generation completed external preparation through operation 60, then stopped with `G013_PUBLIC_CANDLE_REFRESH_FAILED_NO_RETRY` before a formal signal, exact order sheet, permit, or broker write existed.
- Its `formal-candles` attempt marker and all earlier no-retry markers remain immutable. The Mac subsequently stopped; no old runtime, LaunchAgent state, signal, quote, Private GET, notification result, or operator confirmation is reusable.
- Read-only investigation found that the prior implementation collapsed both Public M1 and H1 failures into one code and made the two GETs without an explicit cadence boundary. The retained sanitized marker cannot establish which request or safe failure class occurred.
- The corrective implementation keeps exactly one M1 GET and one H1 GET, adds one fixed 0.25-second gap between them, and emits interval-specific sanitized no-retry failures. It does not add retry, fallback date, credential use, Private API access, or broker write.
- The order contract remains `H11_AUTO_30M_20260717_G013`, `SHORT_V1`, `USD_JPY`, `30m`, 1,000 units, `MARKET`. Broker POST count remains zero.
# 2026-07-20 Public-only non-authorizing signal preview improvement

- The prior G013 formal signal operation stopped safely at `G013_FORMAL_SIGNAL_STAY`.
- Its no-retry marker remains preserved; no permit, order sheet, or broker POST was produced.
- A separate manual preview lane now uses exactly one Public M1 request per completed slot.
- Preview output is limited to an actionable-candidate boolean and freshness/safety fields.
- Preview does not expose or persist direction, probability, prices, candles, raw responses, or IDs.
- Preview never reads credentials or Private API and never touches notifications, LaunchAgent, permit,
  actual preparation state, actual runtime state, or the formal-candles operation.
- A positive preview is not authorization and cannot be reused by the actual canary. The actual path still
  requires fresh external preparation and independently obtains M1+H1 for its formal 30-minute signal.
- Historical local aggregate observation motivating the change: actionable frequency was 25.54% over all
  eligible rows and 15.07% over the latest 1,440 eligible rows. This is workflow evidence only, not
  performance or profitability evidence.

## 2026-07-22 finite Public observer and local alert

- An operator-authorized Codex automation may invoke the new foreground observer for at most 20 distinct,
  completed M1 slots at a fixed 60-second cadence. It invokes the existing reviewed Public-only preview once
  per wake and stops on any non-success or actionable candidate; a claimed slot remains immutable and is not
  retried.
- The observer directly imports only the Public preview. It has no Private API, Keychain, permit, broker
  transport, Pushover, SMTP, resident process, LaunchAgent, cron, background loop, or actual-canary import.
- A candidate may cause exactly one local attempt to play the fixed macOS `Glass.aiff` sound. The emitted
  result remains sanitized and never includes direction, probability, price, candle, credential, raw response,
  identifier, order sheet, or authorization.
- The alert is workflow-only. It does not create a formal signal, order intent, preparation evidence, permit,
  or broker POST authority. After an alert, the operator starts a new actual-canary process, which obtains its
  own fresh M1/H1 signal and all normal current-turn gates.

## 2026-07-22 Pushover receipt propagation corrective generation

- The prior generation completed Keychain presence and sealed access, then its one Pushover send stopped at the
  first receipt lookup with the fixed safe label `PUSHOVER_RECEIPT_REJECTED_NO_RETRY`. Its started marker is
  retained; neither the message nor the receipt lookup is retried in that generation.
- The accepted send had already produced a receipt, so a receipt endpoint `404` is treated as bounded
  propagation-pending state within the existing 15-minute acknowledgement window. It does not cause an
  additional application send, credential read, broker action, or result persistence. Any non-404 receipt
  failure, malformed success response, network failure, expiry, or acknowledgement timeout remains terminal
  and no-retry.
- This changes only the Pushover preparation classification. It does not alter the frozen trade intent, actual
  canary, permit, broker transport, Keychain contract, SMTP path, or any historical marker.

## 2026-07-22 host GUI-context unknown-stop corrective generation

- The prior generation completed operations 00 through 20, then created only
  `30_host_kill.started`; no passed marker or sanitized terminal report was produced. The generation-specific
  host rehearsal directory remained empty, so the coordinator/KILL persistence stage was not reached. Broker
  GET/POST counts remained zero and no later preparation operation was started.
- The elevated Codex execution bridge returned no stdout and did not prove that the macOS administrator dialog
  completed in the logged-in Aqua session. The retained evidence cannot safely distinguish administrator-dialog
  cancellation, GUI-context loss, or termination before the disposable-process stage, so the operation remains
  an unknown no-retry stop. Its marker and empty state directory are retained unchanged.
- This is a procedure-only corrective generation; host/KILL code and its pass criteria are unchanged. Before the
  new generation starts operation 30, the operator must separately authorize and complete the fixed read-only
  network-time administrator check in a confirmed GUI-capable context. Operation 30 may then be started once,
  with no arguments, only from that same confirmed context. Missing dialog, missing sanitized result, timeout, or
  context uncertainty is terminal for that generation.
- All preparation operations restart at 00. No prior Keychain, Pushover, SMTP, email confirmation, host state,
  Public/Private GET, LaunchAgent, signal, quote, or operator confirmation is reusable. Frozen order intent,
  risk limits, permit rules, and broker transport are unchanged.

## 2026-07-20 active-M1 cache corrective generation

- The first preview generation stopped at `G013_PREVIEW_LOCAL_REMOTE_CONFLICT`; its slot marker is retained.
- Sanitized read-only evidence showed the local cache's last M1 row was written 31.78 seconds before that
  candle completed. No raw remote response was retained and no same-slot retry occurred.
- Preview and actual formal SHORT_V1 inference now use only the exact last 31 completed, unique, contiguous
  one-minute bars from their respective fresh one-use Public M1 response.
- Legacy local M1 no longer participates in either inference. Cache persistence excludes active M1/H1 bars.
- This correction does not alter direction thresholds, risk, quantity, order type, permit, or broker transport.
- External preparation, Private API, credential access, notifications, LaunchAgent, and broker POST were not
  performed during investigation or implementation. All old G012/G013/preview markers remain unchanged.

## 2026-07-20 operation 60 heartbeat-window corrective generation

- Generations `94a96eb2…` and `0e716008…` (the R2 official-ATR generation) both completed operations 00-50
  and then stopped at `MONITOR_LAUNCHAGENT_BLOCKED_NO_RETRY`. State evidence (loaded plist bound to the
  generation digest, running supervisor, fresh `WAITING_FOR_CANONICAL_RUNTIME` heartbeat) shows bootout and
  bootstrap succeeded; only the install-side wait for the first fresh heartbeat expired.
- Root cause: the resident supervisor's cold start (launchd exec + interpreter start + two full
  reviewed-files digest computations + application import) exceeded the fixed 20-second install heartbeat
  window on those runs, while earlier generations `d2032115…`/`e9b9efdf…` won the same race under 20 s.
- Corrective: raise the install-side `heartbeat_timeout_seconds` default from 20 to 50 seconds. The
  post-import second digest re-check still runs before `run_forever` emits the heartbeat, so the tamper
  gate is unchanged; the installer merely waits longer for that already-verified heartbeat, still bounded
  by the ≤60-second freshness check. No early-heartbeat / audit-flag mechanism is introduced.
- Scope: `v4_gmo_launchd.py` default, this report, and the AGENTS.md operation-60 note (20→50 s). The
  no-retry ledger flow, operation-60 clear condition, permit chain, and broker transport are not touched.
  Broker POST count remains zero; failed markers on prior generations remain immutable.
## 1.7 2026-07-22 operation 30 AC-power no-retry stop

- The generation bound to reviewed-files digest `sha256:1b3fecae855f5b92cd4f9565bd6b0d9256e5197b62fe1a1a191f51669d36e968` completed operations 00, 05, 10, 15, and 20, then stopped at operation 30 with `BLOCKED_CURRENT_HOST_AC_POWER_NOT_CLEAR`.
- The failed operation reported broker GET count 0, broker POST count 0, no actual runtime process killed, and no disposable process started. Its no-retry marker remains authoritative and must not be deleted, changed, reset, or retried.
- The operator connected the Mac to AC power only after that generation had stopped. The environmental correction does not authorize reuse of any earlier preparation evidence.
- The next corrective generation must be bound to a new reviewed-files digest and restart external preparation at operation 00. Frozen order intent, risk policy, one-attempt limits, and `actual_post_authorized=false` remain unchanged.
## 1.8 2026-07-22 operation 15 Keychain availability no-retry stop

- The generation bound to reviewed-files digest `sha256:7f276911cb8914cd9b1a298721bf778e04ac677ec9997323aae00fc69f889233` completed operations 00 and 05 and received the one-use Pushover acknowledgement at operation 10. At operation 15, the operator-session CLI output reported fixed safe status `NOTIFICATION_KEYCHAIN_ITEM_UNAVAILABLE`; durable state records only `ATTEMPT_STARTED_NO_RETRY` with no passed marker, so the terminal classification is session-observed rather than durable marker evidence.
- No broker operation was part of the SMTP path and broker POST count remained zero. SMTP acceptance was not established, so no delivery confirmation from this generation may be reused.
- The failed operation 15 no-retry marker remains authoritative and must not be deleted, changed, reset, or retried. Earlier presence, Keychain, and Pushover evidence is also non-reusable.
- After the stop, a value-free host check reported the login Keychain accessible and the Mac drawing from AC power. The next corrective generation must still restart external preparation at operation 00; no frozen order intent, risk rule, or authorization flag changes.

## 1.9 2026-07-22 operation 30 AC-power environmental corrective generation

- The generation bound to reviewed-files digest `sha256:0a5e981f6457c8728846662f0aa5d06019175c2a05dcb0525ae230bdb5ee36fe` and generation digest `sha256:893c4d8f89b8386e5f879e214f3256ccd42531d2134f4d4cc9db828465a46b5d` completed operations 00 through 20, then stopped at operation 30 with `BLOCKED_CURRENT_HOST_AC_POWER_NOT_CLEAR`.
- The stopped operation reported `external_power_connected=false`, broker GET count 0, broker POST count 0, and no disposable process start or KILL. Its started marker and all earlier operation evidence remain immutable and are not reusable.
- A subsequent read-only `/usr/bin/pmset -g batt` check, performed only after that generation had stopped, reported the Mac drawing from `AC Power`. This post-stop difference supports an execution-time environmental precondition failure as the corrective-generation basis, but it does not by itself fully exclude a parser-path defect. The production parser and its focused fake-first AC/Battery coverage are unchanged; no host/KILL code change is made.
- This docs-only corrective generation changes no frozen direction, symbol, size, execution type, risk limit, permit rule, transport, or authorization flag. External preparation must restart at operation 00 with all Keychain, notification, host, Public/Private GET, exclusivity, and LaunchAgent evidence obtained fresh. `actual_post_authorized=false` and broker POST count 0 remain unchanged.

## 1.10 2026-07-22 operation 60 launchctl phase-timeout corrective generation

- The generation bound to reviewed-files digest `sha256:bb9b5af3d927b501167961796a5e19dc84c7bef444b66bc7c7d3f778c7650cf5` and generation digest `sha256:3cbe3955251260070da6cc7493cc1f6f339b70cde001c65545c5038fc2c2d6ee` completed operations 00 through 50. Operation 60 retained its started marker without a passed marker, so the generation is terminal and none of its preparation evidence is reusable.
- Sanitized read-only evidence after the stop found the exact current-generation service loaded, a fresh generation-matching `WAITING_FOR_CANONICAL_RUNTIME` heartbeat, `broker_write=false`, and broker POST count 0. This proves that plist replacement/bootstrap took effect, but does not satisfy the durable operation-60 completion contract.
- The installer runner applied one 15-second subprocess timeout to every `launchctl` phase. The observed started-only result after an effective bootstrap is consistent with a timeout while the launchctl operation was still taking effect. The corrective runner keeps read-only `print` at 15 seconds and gives state-changing `bootout` and `bootstrap` separate 30-second bounds. Unknown launchctl actions are rejected without starting a subprocess.
- The 50-second fresh-heartbeat contract, exact post-bootstrap service check, no-retry ledger, immutable prior markers, monitor-only behavior, permit rules, frozen order intent, and broker transport are unchanged. The next generation restarts external preparation at operation 00 with `actual_post_authorized=false` and broker POST count 0.
