# H-11 v4 Actual Activation Preparation Report（pre-canary / no broker POST）

Date: 2026-07-16

Status: `HOST_NETWORK_TIME_ADMIN_PROBE_CORRECTIVE_VALIDATED_PRECANARY_VETO_REMAINS`

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
- reportはUSD/JPY限定の3 count、flat、active-order-zeroだけ。口座全体の排他性やcanary clearを
  この3 GETだけから主張しない。
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

## 4. Fake-first validation

```text
focused_preparation_tests=84 passed
h11_auto_related_tests=361 passed
repository_app_tests=7953 passed, 2 keychain-write tests deselected
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

## 5. Remaining safety VETO

外部準備試験の前に次が必要。

- current worktreeの完全差分レビュー、commit、push（授権済み、実行前）
- working tree clean
- `HEAD == origin/main`
- focused／related tests、focused ruff、diff check、danger scanのclear
- architecture／safety／operationsの3 review clear
- actual-preparation exact artifactとreviewed-files digest一致

canary broker POSTの前には、外部準備とは別に次の未解決VETOもclearにする必要がある。

- v4 relaxed generation manifestとvalidator schemaの一致、PENDING 0
- implementation digest／manifest digest／operator selection digestの永続binding
- frozen ATR persistenceとactual OCO planへのbinding
- entry前のworst-case loss <= 5,000円判定
- actual runtime coordinatorはPOST不能のまま組み立て、persistent attempt ledgerへ結線
- actual v4 runtimeのprocess lock／dead-man／KILL経路のhost proof
- major-incident resume declarationの別承認と発効
- post-implementation independent review clear

上記がclearになるまで、actual Keychain、通知送信、Private GETを実行してもactivation evidenceとして採用しない。

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
credential_value_exposed=false
activation_permit_issued=false
resume_declaration_effective=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
api_ip_restriction=DISABLED_OPERATOR_ACCEPTED_RESIDUAL_RISK
```
