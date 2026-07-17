# H-11 v4 Actual Activation Preparation Report（pre-canary / no broker POST）

Date: 2026-07-16

Status: `PRECANARY_CORRECTIVE_VALIDATED_EXTERNAL_PREPARATION_PENDING`

## 1. Authorization boundary

Operatorは次を明示授権した。

- Keychain 6件の値非表示presence確認と、有限試験内のsealed internal read
- Pushover 1回のapplication send、emergency receipt poll、operator acknowledgement確認
- email 1回のSMTP/TLS送信（宛先はSMTP usernameと同一）
- GMO FX `latestExecutions` / `openPositions` / `activeOrders` の各1回Private GET
- current Macのread-only host確認とdisposable subprocessのSIGKILL、persistent KILL再読込試験
- 独立read-only review
- current working tree全差分の必要単位commitと`main`へのpush

次は授権されていない。

```text
broker_post=false
order=false
cancel=false
change=false
close=false
oco_creation=false
activation_permit_issuance=false
canary_execution=false
commit_push_authorized_for_current_worktree=true
```

## 2. Start review

`code architecture`、`safety`、`operations`の3担当がread-only pre-reviewを行った。3担当とも、actual外部
試験の開始判定は`NOT_CLEAR`だった。

主因:

1. working treeがdirtyで、`main`は`origin/main`より1 commit ahead。
2. 従来AGENTS.mdはfake-only adapter実装だけを許可していた。
3. existing actual transportはGETにもunconstructibleなPOST activation permitを要求した。
4. existing reconciliationは3 GETを即時連続実行し、0.25秒cadenceに適合しない。
5. actual Pushover／SMTP senderが存在しなかった。
6. host rehearsalがsynthetic clock、disabled launchd、fake notificationだけだった。
7. generation manifestとvalidator schemaがv4 relaxed profileで不一致。
8. actual runtime-to-adapter binding、frozen ATR persistence、entry前5,000円loss boundが未完成。

## 3. Corrective implementation completed in this worktree

### Policy boundary

AGENTS.mdへ`H-11 GMO relaxed v4 actual activation準備限定例外`を追加した。notification POSTとbroker POSTを
区別し、broker write、permit、hard guard変更、allow bridge、env、raw/ID/secret exposureを禁止した。

### Keychain presence

`v4_actual_preparation_guard.py`は、固定6 itemを`security find-generic-password`の値出力optionなしで確認し、
出力を破棄してpresent countだけを返す。外部試験CLIはclean main／HEAD一致と、完全なreview artifactの
固定ファイルdigest一致を先に強制する。

外部準備は次の順序に固定し、各段階の外部I/O前にgitignore済みlocal stateへ`ATTEMPT_STARTED_NO_RETRY`を
atomic保存する。失敗・中断・process再起動後も同じ段階を再試行しない。

各外部関数は、固定ledgerが発行したexact型・private token・対象operation一致のsingle-use permitだけを受理する。
同名methodを持つ任意objectによるduck-typed bypassは拒否し、正規permit以外ではKeychain、通知、host、Private GETの
I/Oへ到達しない。

```text
presence
-> sealed Keychain access rehearsal
-> Pushover send + acknowledgement
-> SMTP email send
-> operator email receipt confirmation
-> current-host generic KILL preparation
-> operator account-exclusivity confirmation
-> three Private GETs
```

各実行集合のstate rootはreviewed-files digestごとの新規generation directoryに固定する。
失敗済みの旧generation markerは保持し、同じdigestでは再試行できない。

### First external attempt and corrective generation

初回generationでpresenceは6/6成功したが、notification開始時のKeychain internal readが
5秒timeoutで失敗した。credential値は表示されず、Pushoverとemailは送信開始前だった。
`10_notification.started.json`はno-retry証跡として保持している。

修正generationでは、通知より前に固定6 itemのinternal readだけを行う独立段階を追加し、
Keychain対話承認の待機をoperation全体で最大120秒に延長した。timeoutの部分出力は
例外context/causeにも保持しない。broker read-only preflightのKeychain読取りも
同じ120秒に固定した。読み取った値はレポート・exception・markerに含めない。

実行時はMacをロックせず、Terminalを前面にして待つ。SecurityAgentは最大6回表示され得る。
想定した`security`による固定item accessだけを承認し、後続の通知／Private GETで再表示させないため
「常に許可」を推奨する。想定外のprocess・item・表示なら拒否し、そのgenerationを停止する。

### Second external attempt and split-notification correction

digest `1668d9ec...dd110`のgenerationではpresence 6/6、Keychain access 6/6がpassした。
PushoverとSMTPを同一notification operationで各1回attemptした。Pushoverは09:33:05に端末へ配送されたが、
3分のrehearsal待機内にはackされず、operatorは後に端末上でackを完了した。emailはInbox、All Mail、Spam、
Sentのいずれにも到達しなかった。`10_notification.started.json`は保持し、このgenerationは再利用しない。
Private GET、host/KILL、broker POSTは実行していない。

次generationではPushoverとSMTPを別operation／別markerへ分離する。Pushoverは1 application sendのまま、
preparation限定でack待機を最大15分、poll間隔を10秒とする。SMTPはPushover pass後に1回だけ実行し、
失敗時は接続／EHLO／TLS／認証／送信／宛先／session終了の固定safe labelだけを返す。raw provider response、
account、credential、receiptはreport、marker、exceptionへ保存しない。
receipt GETが締切前に開始しても応答が締切後ならackを採用しない。SMTPはEHLOの戻りcode 250を明示確認し、
全宛先拒否exceptionをgeneric送信失敗と分けて宛先失敗へ分類する。

### Third external attempt and Keychain access-control correction

split通知版digest `d5031cc7...aa2a4`のgenerationではpresence 6/6がpassしたが、
`05_keychain_access`はstarted後に`PREPARATION_KEYCHAIN_ACCESS_FAILED`で停止した。passed markerはなく、
Pushover、SMTP、Private GET、broker POSTはいずれも0回である。started markerは保持し、このgenerationは
再利用しない。operatorはメール用Keychain 2件のaccess controlを確認したと明示した。次generationは
新しいreviewed-files digestへ分離し、同じ固定順序とno-retry規則を維持する。

### Fourth external attempt and SMTP CA-bundle correction

access-control修正版digest `dda6af51...3693b`のgenerationではpresence 6/6、Keychain access 6/6、
Pushover 1 application sendとoperator acknowledgementがpassした。SMTPはstarted後、メール送信前の
STARTTLSで`SMTP_TLS_FAILED_NO_RETRY`となり停止した。SMTP passed markerはなく、Private GETとbroker POSTは
0回である。ローカルread-only診断ではPython 3.11のdefault CA file/pathが未設定で、インストール済み
certifi CA bundleは存在した。次generationではSMTP TLS contextへ固定certifi bundleを明示し、
`backend/requirements.txt`もreviewed-files digestへ含める。失敗generationのmarkerは保持し再利用しない。

### Fifth external attempt and host/network-time correction

SMTP CA修正版digest `ed6d01a9...d2b3e`のgenerationではpresence 6/6、Keychain access 6/6、
Pushover送信とack、SMTP provider acceptance、operatorのemail受信完全一致確認までpassした。
`30_host_kill`はstarted後に`HOST_REHEARSAL_NOT_CLEAR`で停止し、passed markerはない。sanitized診断では
macOS、disk、clock probe、5秒以内のclock skewはclearだったが、AC電源は未接続、一般ユーザー権限の
network-time設定確認はUNKNOWNだった。Private GETとbroker POSTは0回である。operatorはその後、AC接続、
自動時刻ON、管理者read-only確認を明示承認した。次generationでは一般権限の固定probeが失敗した場合だけ、
macOS標準認証画面を介して固定`systemsetup -getusingnetworktime`を1回実行する。管理者passwordはOS画面だけで
扱い、Python stdin/stdout、report、marker、ログへ渡さない。通常host probeは5秒timeoutを維持し、固定admin
probeだけを専用runnerで最大120秒待つ。固定command以外は専用runnerが拒否する。host failure時はsafe aggregate reportを表示し、
失敗operationの再試行やmarker変更は行わない。

### Sixth external attempt and Keychain prompt-window correction

G006（reviewed digest `e4d324b1...b5fa9`、generation digest `c6a23b33...2d8a0`）では、
presence 6/6がpassしたが、Keychain access operationはOS対話承認を完了できず
`PREPARATION_KEYCHAIN_ACCESS_FAILED`で停止した。`05_keychain_access.started.json`は保持し、
同generationを再利用しない。Pushover、SMTP、Private GET、broker POSTはいずれも0回である。
次generationでは、固定6 itemのinternal readだけを対象とする有限なoperation全体の待機上限を
300秒へ延長する。値非表示、部分出力非保持、one-attempt、no-retry、旧marker保持は変更しない。

### Seventh external attempt and network-time fallback correction

G007ではpresence、Keychain access 6/6、Pushover送信・ack、SMTP provider acceptance、
operatorのemail受信完全一致確認までpassした。`30_host_kill`はread-only host checkで停止し、
Private GETとbroker POSTはいずれも0回である。sanitized診断ではAC接続とclock skewはclearだったが、
macOS `systemsetup -getusingnetworktime`が権限不足文を出力しながら終了code 0を返すため、既存実装が
固定administrator read-only fallbackへ進まないことを確認した。次generationでは、direct probeの
終了codeだけでなく`Network Time: On/Off`のparse成功を要求し、parse不能時だけ既存の固定admin fallbackを
使用する。設定変更、時刻変更、追加command、retry、broker accessは行わない。
direct probeの成功判定は、trim・case-normalize後の固定文字列`Network Time: On`または
`Network Time: Off`との完全一致に限定し、`permission`や`cutoff`等のsuffix一致を受理しない。

### Notification

`h11_v4_notification_actual_preparation.py`をfake-only notifierから分離した。

- Pushover application sendは専用operationで1回のみ。
- priority 2、retry 60秒、expire 3600秒。
- receipt GETは10秒間隔、preparation限定で最大15分とする。
- provider receipt、request ID、user key、account、credential、raw responseをreportへ出さない。
- SMTPは別operationで`starttls`、固定host/port、宛先＝username、送信1回。
- PushoverがpassしなければSMTPを開始しない。
- SMTP失敗は固定safe stage labelだけを返す。
- SMTP成功は`SMTP accepted`までとし、実受信は別のoperator exact confirmationを必要とする。
- broker endpoint／broker POST機能なし。

### Private GET

`h11_v4_gmo_readonly_preflight.py`をPOST-capable transportから分離した。

- methodは内部固定GETのみ。
- routeは3経路を内部固定し、caller指定不能。
- 各requestの実start間隔を0.25秒以上にする。先行GETが遅延しても次のstart間隔を短縮しない。
- instanceあたり1 sequenceのみ。
- `latestExecutions`は公式仕様どおりUSD/JPYを必須指定し、`openPositions`と`activeOrders`は
  `symbol`を省略して口座全体を確認する。GET回数は各route 1回、合計3回のまま増やさない。
- reportは口座全体のposition count、active-order count、flat、active-order-zeroだけを返す。
  この準備snapshotを2秒以内のcanary preflight clearとは扱わない。
- POST route、activation permit、hard guardへの参照なし。
- POST-capable actual transportへのtransitive importなし。

### Host / KILL

`v4_actual_host_kill_rehearsal.py`は、disk、AC power、network-time settingに加え、NTPとの絶対clock skewが
5秒以内かをsanitized確認する。実runtimeではなくdisposable childだけをSIGKILLし、risk KILLをlocal stateへ
atomic保存後、再読込してnew entry拒否を確認する。この結果はgeneric KILL preparationであり、actual v4
runtime supervisorの完全proofとは扱わない。
sleep、reboot、network変更、Keychain lock、launchd install、cron、resident processは行わない。

### 15-second confirmation correction

exact-size protectionをsnapshotで確認した時点でも、MARKET attemptからのelapsedを再検査する。
15秒ちょうどまでを許容し、15秒超は成功扱いせずpersistent operator-review HALTへ移行する。既に存在する
exact OCOを取消したりblind closeしたりしない。

### Actual transport hard disable correction

Pythonの低レベル生成でactivation permitやtransportの通常constructorを迂回するケースもレビューした。
現在ビルドでは`V4GmoHttpxPrivateTransport`のconstructorと`request()`の両方を常時拒否し、
credential読取りとnetworkへ到達しない。POST分岐のcommon hard guardも`allow=False`で維持する。
準備用Private GETはPOST routeを持たない別のread-only preflightだけを使う。canaryに進むには、
別授権と別レビューのactivation変更が必要である。

### Independent review VETO corrective cycle

architecture／safety／operationsの初回差分レビューで、pre-canary coordinatorに対するVETOが出たため、
broker transportを有効化せず次を修正した。

- persisted intentのside、size、cycleとMARKET planをexact-matchし、不一致ではattemptを記録しない。
- current generation／cycle／signalへ結び付いたfresh flat preflightを永続化し、2秒超ではMARKETを拒否する。
- preflightはzero position、zero active order、zero unowned position/order、clock、notification、account
  exclusivityの固定safe factを要求する。
- one-use authorizationはcoordinatorだけが発行し、adapter transport直前にcommitted attempt row、plan digest、
  generation、HALTをSQLiteから再照合する。testやadapterから直接mintする経路は除去した。
- MARKETからexact OCO確認までの15秒はexecutor所有のmonotonic clockで測り、callerは時刻を指定できない。
- MARKET attempt／risk budget永続化後、transport直前にdead-manを再評価する。
- cancel remainder、mismatched OCO cancel、position-specific emergency exitは、それぞれfresh authoritative
  reconciliationの固定状態前提を満たす場合だけattemptを永続化する。
- 部分約定後はpending entry remainderが0になり、entry statusが`FILLED`に確定するまで
  exact-size OCOを許可しない。先に残entryを単発cancelし、fresh 3-GETで全量の実建玉を再確認する。
- transport直前はpersisted pending markerのactionとcycleをSQLiteから再照合し、欠落または改変は
  transport 0回で拒否する。
- process crash後はpending markerからunknown HALTをlatchし、freshな3-GETのみで
  `FLAT_OR_REJECTED`、`MARKET_PARTIAL_PENDING`、`FILLED_UNPROTECTED`、
  `FILLED_PROTECTED`、`FILLED_PROTECTION_MISMATCHED`へ分類する。分類後もHALTは解除せず、
  MARKETのretry/repostは常に禁止し、分類と一致する単発risk-reducing actionのみ許可する。
- host KILL reportはactual runtimeをkillしたと主張せず、disposable coordinator childのkillを別fieldで記録する。
- no-retry preparation state rootはreviewed-files digestとgeneration manifest digestの両方へ結合する。
- preparationのpassed markerは単な完了名ではなく、operation別のsanitized clear report、
  reviewed-files digest、generation digestの正規hashに結合する。markerだけの作成では完了証拠をmintできない。

### Second independent-review VETO corrective cycle

strategy／architectureの再レビューで残ったVETOに対し、broker transportを有効化せず次を追加した。

- completed preparation evidenceはgeneration state rootへ結合し、最初のpreflight消費時に
  `O_EXCL`＋file/directory `fsync`でgeneration-level consumed markerを永続化する。同じgenerationから
  evidenceを再読込することも、事前に複数loadして別coordinatorへ渡すことも拒否する。
- v4 Friday-limited v2 generationへ、月〜木`blocked_hours_jst=(5,6,7,8)`、金曜09:00以上21:00未満、
  土日禁止を固定し、MARKET attemptを永続化する直前のcoordinatorで強制する。Stage 1のgateを
  v4の証拠として流用しない。
- 通常の最大保有時間は82,800秒（23時間）を維持する。金曜entryだけは通常期限と土曜03:45 JSTの
  早い方をexit-sequence startとし、土曜04:00 JSTをflat目標とする。開始期限前のtime exitは拒否し、期限後はexact OCOを単発cancel、fresh reconciliation、
  position-specific time exitの順に限定する。各actionは別の永続one-attempt契約である。
- time exitのexact OCO取消transport直前とposition-specific time exit transport直前に、
  executor-owned monotonic clockで最大2秒以内の公式public status `OPEN` evidenceを、
  それぞれ別のone-use evidenceとして消費する。attempt永続化中または直前callbackで2秒を超えた
  場合も該当broker transportへ進まない。
  OCO取消前にOPENを確認できない場合はbroker writeを行わず、OCOを維持したままpersistent HALTへ移る。
  OCO取消後の決済前に確認できない場合はclose transportを行わずpersistent HALTへ移る。
- owned close executionだけからsanitized realized PnLとclosed sizeを集計し、fresh flatかつexpected size一致時だけ
  persistent risk ledgerへcycle単位でexactly once反映する。負の小数円は安全側へ切り下げる。
- canary KPIを、親IFDOCOではなく`MARKET -> separate exact-size OCO <= 15 seconds`へ訂正した。
  違反時はblind flatではなく、HALTを維持したfresh 3-GET分類と一致する単発risk-reducing actionだけを許可する。

これらはfake transportでのみ検証する。actual transport constructor、hard guard、activation permitは引き続き
無効であり、この修正だけでbroker POST可能にはならない。

## 4. Fake-first validation

```text
precanary_corrective_focused_tests=108 passed
precanary_related_h11_auto_tests=419 passed
precanary_full_app_tests=8007 passed
h11_auto_related_tests=414 passed
repository_app_tests=7997 passed, disposable v3 Keychain test file 6 tests excluded
full_ruff_app_scripts=passed
git_diff_check=passed
danger_scan=no_broker_POST_route_or_activation_permit_in_preparation_paths
actual_keychain_read_attempted=true
actual_keychain_read_completed=true
external_notification_send_attempt_count=2
pushover_delivered=true
pushover_acknowledged_within_rehearsal=false
pushover_acknowledged_later_by_operator=true
historical_first_email_delivery_confirmed=false
ed6_generation_email_delivery_operator_confirmed=true
broker_private_get=false
broker_private_post=false
```

## 5. Remaining pre-external gates

外部準備試験の前に次が必要。

- current worktreeの完全差分レビュー、commit、push（授権済み、実行前）
- working tree clean
- `HEAD == origin/main`
- focused／related／full tests、full ruff、diff check、danger scanのcurrent-diff clear
- strategy／architecture／safetyの3 independent review clear
- actual-preparation exact artifactとreviewed-files digest一致

### 2026-07-16 pre-canary corrective implementation

strict `H11_AUTO_GENERATION_V1`は変更せず、GMO relaxed v4専用の
`H11_AUTO_GENERATION_V4_GMO_RELAXED_V1`を追加した。専用coordinatorは、次をtransportより前に
別SQLiteへ永続化する。

- complete generation manifest digest
- implementation digest
- operator selection digest
- policy config hash
- risk policy label/digest
- dead-man policy label/digest
- formal signal fingerprint
- frozen ATR(24)とsignal-bound ATR digest
- ATR stop幅、0.1 pip tick丸め allowance、5.0 pips adverse-slippage allowanceによるplanned loss
- MARKET attempt timestamp
- actual fillから算出したexact-size OCO plan digest

planned loss gateは`10,000通貨 × (1.5 ATR stop幅 + 0.1 pip tick丸め allowance + 5.0 pips)`を
円換算し、5,000円超をentry前に拒否する。
これは成行の無制限gap/slippageに対する保証ではない。actual損失が5,000円を超え得るresidual riskは残り、
初回canaryは極小・監視付きでもこの性質を変えない。

Private GET reconciliationのactual-coordinator経路は、各request start間を最低0.25秒、各route 1回、
retry 0に固定した。adapter新規生成またはrestart直後も最初のGETを0.25秒遅延するため、
通常の開始offsetは0.25/0.50/0.75秒以降となる。一方、activation preparation専用の有限preflightは
AGENTS.mdの別契約に従い0.00/0.25/0.50秒以上であり、runtime coordinatorの再起動cadenceと混同しない。
host/KILL rehearsalはgeneric子プロセスに加え、transportに到達しないrehearsal pending markerを
永続化したpre-canary coordinator子プロセスをSIGKILLする。再起動後はpending markerから
unknown HALTが永続的にlatchされ、transport markerが生成されないことのみを確認する。
MARKET attemptや実transport後のsecond attempt拒否をこのhost rehearsalが証明したとは扱わない。

actual-shaped統合経路は、process lock、generation-bound risk/dead-man digest、fresh dead-man heartbeat、
persistent 1日1entry gateをMARKET attempt前に確認する。MARKET attemptとrisk entry消化はtransport前に
永続化し、adapter例外または結果不明はpersistent HALTへ移す。結果不明後も、broker状態を確定するための
固定3-GET reconciliationと、既知の実建玉を保護・解消する単発risk-reducing actionは遮断しない。
cancel、exact-size OCO、position-specific emergency exitもaction別attemptをtransport前に永続化し、
同一actionの第2attemptを拒否する。クラッシュ後はpending attemptとfresh 3-GETを照合し、
分類した実状態と一致する行動以外を拒否する。この回復処理はHALT解除やMARKET再許可を行わない。

canary broker POSTの前には、外部準備とは別に次の未解決VETOもclearにする必要がある。

- frozen generation artifactとcurrent reviewed-files digestのexact一致
- planned loss gateの5.0 pips仮定に対するoperator最終受入
- actual v4 coordinator KILL経路のcurrent host実地proof
- actual runtime supervisor/restartの発効（本preparation Stepではresident/launchdを追加しない）
- actual account exclusivity confirmationと3-route Private GETのfresh clear
- major-incident resume declarationの別承認と発効
- post-implementation independent review clear

なお、v4専用entry-time gate、通常82,800秒（23時間）／金曜土曜03:45開始境界、
closed PnLのcycle単位exactly-once risk反映、
completed preparation evidenceのgeneration単位永続one-useは実装済みである。これらの実装済み事実は、
actual runtime supervisorの発効、04:00 target monitor、activation permit、broker POSTを許可するものではない。

追加のcorrective cycleでは、GMO `latestExecutions`の`amount`を損益として扱わず、owned CLOSEの
`lossGain + fee + settledSwap`だけからnet realized JPYを算出するよう修正した。CLOSEはowned OPENの
positionId、反対side、position別累計size上限の全てに一致しなければUNKNOWN/HALTとなる。v4 coordinatorは
entry前BID/ASK、約定平均価格、entry spread、direction-aware slippage、予測`p_up`、closed net JPY、
net pips、勝敗を同一cycleへ永続化する。予測較正は売買操作と独立した既存PROSPECTIVE forecast ledgerを正とする。

さらに、`latestExecutions`が直近1日分・最新100件というbroker保持境界であるのに対し、従来の
86,400秒exitでは最初のtime-exit判定時にentry OPEN行が保持範囲外となり得た。このためoperatorの
安全側変更承認に基づき、通常最大保有を82,800秒（23時間）へ短縮した。さらに2026-07-17のoperator判断で、
金曜は09:00以上21:00未満だけentryを許可し、金曜entryのexit sequenceを土曜03:45 JSTから開始、04:00を
flat目標とするFriday-limited v2へ再凍結した。03:45開始境界はcoordinatorへ実装済みだが、自動dispatcherと
04:00 target monitorは次のactivation実装で必須とする。04:00時点で未flatなら再試行せずpersistent HALTする
契約も、そのmonitor実装・review完了まで発効しない。

上記がclearになるまで、actual Keychain、通知送信、Private GETを実行してもactivation evidenceとして採用しない。

### 2026-07-17 G009 external run and G010 account-wide correction

G009はKeychain 6/6、Pushover 1回送信＋acknowledge、SMTP 1回送信＋operator受信確認、current-host
read-only/KILL rehearsal、operator account-exclusivity confirmation、Private GET 3回まで固定順序で完了した。
broker POSTは0回である。G009のPrivate GETではUSD/JPY建玉0・有効注文0だったが、当時の実装は
`openPositions`と`activeOrders`にも`symbol=USD_JPY`を指定していたため、口座全体のcanary前提には採用しない。
G009のpassed markerとno-retry stateは保持し、再利用しない。

GMO外国為替FX公式仕様では、`latestExecutions.symbol`は必須、`openPositions.symbol`と
`activeOrders.symbol`はoptionalである。この仕様に合わせたG010 corrective cycleでは次を固定する。

- 準備3-GETは`latestExecutions`のみUSD/JPY、残る2 GETは`symbol`省略の口座全体snapshotとする。
- actual adapterの3-GETも同じquery契約とし、他通貨または別cycleの建玉・注文をfilterで捨てない。
- account-wide rowはowned executionの`positionId`とv4専用`clientOrderId`へ一致しない限りunownedとし、
  1件でもあればUNKNOWN／persistent HALTとする。
- coordinated preflightのunowned／active countは0をhardcodeせず、authoritative reconciliationから渡す。
- preparation snapshotはaccount-wide zeroでも`canary_preflight_clear=false`を維持する。MARKET直前には別の
  generation/cycle/signal-bound reconciliationを2秒以内で消費する。
- broker POST、activation permit、hard guard、retry/repost、risk/spec/quantityは変更しない。

G010 validation:

```text
account_wide_corrective_focused_tests=121 passed
h11_auto_related_tests=432 passed
repository_app_tests=8020 passed, existing v3 test-only Keychain file 2 tests excluded
repository_app_initial_run=8024 passed, 2 environment errors from sandbox-denied v3 test-only Keychain write
full_ruff_app_scripts=passed
git_diff_check=passed
changed_additions_danger_scan=no_new_POST_permit_guard_or_retry_enablement
broker_private_get_after_G010_change=0
broker_private_post=0
```

G010 external preparationはKeychain presence 6/6、Keychain access 6/6までclearとなり、Pushover emergency
messageをapplicationから1回だけ送信した。operator acknowledgementは有限待機内に確認できず、
`PUSHOVER_ACK_NOT_CONFIRMED_NO_RETRY`で停止した。G010のstarted markerは保持し、同generationでは再送しない。
G010のSMTP、Private GET、broker POSTはいずれも0回である。

operatorがPushoverを即時acknowledgeできる状態を明示したため、G011はこの履歴追記を含む新しい
reviewed-files digestとgeneration digestへ結合する。G010と実装コードは同一で、broker query、strategy、risk、
quantity、threshold、POST／permit／hard guard／retry契約を変更しない。G011の外部operationも固定順序・各1回・
no-retryを維持する。

G011 external preparationは、Keychain presence/access 6/6、Pushover 1回送信＋acknowledge、SMTP 1回送信＋
operator実配送確認、current-host/KILL、account exclusivity、口座全体のPrivate GET 3回を固定順序で完了した。
sanitized snapshotは建玉0・有効注文0、broker POST/write 0、raw/secret/ID exposure 0だった。

### 2026-07-17 Friday-limited v2 / G012 refreeze

operatorは金曜終日禁止による機会損失を避けるため、金曜09:00以上21:00未満のentry、土曜03:45 JSTの
exit-sequence start、土曜04:00 JSTのflat目標を選択した。通常の最大保有82,800秒は月〜木に維持し、
金曜entryは通常期限と土曜03:45の早い方をtime-exit開始期限とする。既存のexact OCO cancel、fresh reconciliation、position-specific close、
one-attempt、status `OPEN` evidence、unknown HALT契約は変更しない。

この変更はprofile、exit label、policy config hash、generation schema/digestを変更するため、G011の外部準備証拠を
新profileのactivation evidenceへ流用しない。G011 markerはhistorical/no-retry証拠として保持し、削除・reset・
上書きしない。G012は新しいreviewed-files digestへ結合し、検証・独立review・commit/push後にだけ有限準備を
最初から実行できる。broker POST、activation permit、hard guard、retry/repostは変更せずfalseを維持する。

```text
G012_focused_friday_and_coordinator_tests=87 passed
G012_h11_auto_related_tests=436 passed
G012_real_post_isolation_tests=19 passed
G012_ruff_app_scripts=passed
G012_git_diff_check=passed
G012_danger_scan=no_POST_permit_guard_retry_enablement
G012_broker_private_get=0
G012_broker_private_post=0
G012_external_notification_send=0
```

### Threat model boundary

本実装のcompletion digest、generation digest、SQLite markerは、通常の誤操作、二重attempt、
process crash、結果不明に対するfail-closed証拠である。同一macOS userがローカルのコード、
Python process、SQLite、generation/evidence JSONを悪意をもって改ざんする状況まで暗号学的に
証明するものではない。activation evidenceの採用は、完全差分の独立レビュー、固定した
reviewed-files digest、commit/push後のclean main、`HEAD == origin/main`、実行時digest再検証を
すべて満たすことが前提である。

## 6. Current flags

```text
actual_post=false
broker_write=false
broker_private_get=false
historical_prior_generation_credential_read_completed=true
historical_prior_generation_external_notification_send_attempt_count=2
d503_generation_credential_read_completed=false
d503_generation_external_notification_send=false
latest_smtp_generation_credential_read_completed=true
dda6_generation_pushover_send_count=1
dda6_generation_pushover_acknowledged=true
dda6_generation_email_send_count=0
dda6_generation_smtp_tls_failed=true
ed6_generation_credential_read_completed=true
ed6_generation_pushover_send_count=1
ed6_generation_pushover_acknowledged=true
ed6_generation_email_send_count=1
ed6_generation_email_smtp_accepted=true
ed6_generation_email_operator_confirmed=true
ed6_generation_host_kill_passed=false
ed6_generation_private_get_count=0
next_generation_credential_read=false
next_generation_external_notification_send=false
v4_generation_schema=H11_AUTO_GENERATION_V4_GMO_RELAXED_V1
v4_generation_pending_count=0
v4_generation_digest_persistence=implemented_not_externally_rehearsed
v4_frozen_atr_and_oco_digest_binding=implemented_not_externally_rehearsed
v4_planned_loss_gate=implemented_atr_tick_rounding_plus_5_pips_assumption_not_gap_guarantee
v4_coordinator_market_attempt_persist_before_transport=implemented_exact_plan_bound
v4_coordinator_fresh_flat_preflight=implemented_generation_cycle_bound_max_age_2_seconds
v4_coordinator_persisted_authorization=implemented_db_reverified_one_use
v4_coordinator_deadline_clock=executor_owned_monotonic
v4_coordinator_transport_boundary_dead_man=implemented
v4_coordinator_risk_dead_man_digest_binding=implemented
v4_coordinator_fresh_dead_man_and_persistent_risk_gate=implemented
v4_coordinator_risk_reducing_attempt_persistence=implemented_state_precondition_bound
v4_coordinator_kill_rehearsal=pending_marker_persisted_restart_halt_observed_no_transport
v4_actual_get_cadence=implemented_min_0_25_inter_request_restart_first_get_delayed_no_retry
v4_partial_fill_protection_gate=implemented_pending_zero_and_filled_required
v4_crash_recovery_classification=implemented_fresh_three_get_halt_remains_no_market_retry
v4_preparation_completion_proof=implemented_operation_report_plus_review_and_generation_digest
v4_preparation_generation_consumption=implemented_persistent_o_excl_fsync_one_use
v4_entry_time_gate=implemented_v4_generation_bound_mon_thu_blocked_hours_friday_09_21_weekend
v4_maximum_hold_seconds=82800
v4_friday_exit_sequence_start=Saturday_03:45_JST
v4_friday_weekend_flat_target=Saturday_04:00_JST
v4_time_exit_sequence_start_boundary=implemented_min_23h_or_friday_03_45_then_exact_oco_cancel_reconcile_position_exit
v4_friday_04_flat_target_monitor=pending_actual_runtime_dispatcher
v4_closed_pnl_risk_binding=implemented_owned_flat_exact_size_cycle_exactly_once
v4_realized_pnl_source=official_lossGain_plus_fee_plus_settledSwap_amount_rejected
v4_execution_metrics=implemented_probability_quote_fill_spread_slippage_net_jpy_net_pips_win
v4_runtime_state_root=generation_bound_canonical_paths_enforced
credential_value_exposed=false
activation_permit_issued=false
resume_declaration_effective=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
api_ip_restriction=DISABLED_OPERATOR_ACCEPTED_RESIDUAL_RISK
```
