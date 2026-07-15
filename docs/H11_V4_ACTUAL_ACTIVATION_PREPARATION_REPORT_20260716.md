# H-11 v4 Actual Activation Preparation Report（pre-canary / no broker POST）

Date: 2026-07-16

Status: `CORRECTIVE_IMPLEMENTATION_VALIDATED_EXTERNAL_REHEARSAL_PENDING_CLEAN_MAIN`

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
-> Pushover + SMTP
-> operator email receipt confirmation
-> current-host generic KILL preparation
-> operator account-exclusivity confirmation
-> three Private GETs
```

### Notification

`h11_v4_notification_actual_preparation.py`をfake-only notifierから分離した。

- Pushover application sendは1回のみ。
- priority 2、retry 60秒、expire 3600秒。
- receipt GETは公式条件どおり5秒未満の間隔でpollしない。
- provider receipt、request ID、user key、account、credential、raw responseをreportへ出さない。
- SMTPは`starttls`、固定host/port、宛先＝username、送信1回。
- Pushoverが失敗してもsecondary emailを独立に1回だけ試行する。
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
corrective_core_tests=45 passed
preparation_plus_notification_binding_tests=49 passed
expanded_preparation_and_isolation_tests=101 passed
h11_auto_related_tests=341 passed
repository_app_tests=7933 passed, 2 keychain-write tests deselected
full_ruff_app_scripts=passed
git_diff_check=passed
danger_scan=no_broker_POST_route_or_activation_permit_in_preparation_paths
actual_keychain_read=false
external_notification_send=false
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
credential_read=false
external_notification_send=false
activation_permit_issued=false
resume_declaration_effective=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
api_ip_restriction=DISABLED_OPERATOR_ACCEPTED_RESIDUAL_RISK
```
