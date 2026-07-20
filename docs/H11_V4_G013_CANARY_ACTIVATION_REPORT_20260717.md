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
新generation専用runtime pathのheartbeatが20秒以内にfreshとなり、generation digest一致、
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
正式30分signalは準備時だけでなくPOST直前にも観測から120秒以内であることを再検査する。
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
