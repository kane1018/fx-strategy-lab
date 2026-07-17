# H-11 v4 G012 Canary Preparation Report

Date: 2026-07-17

Status: `IMPLEMENTED_REVIEWED_PRE_EXTERNAL_PREPARATION_NO_BROKER_POST`

## 1. Authorized boundary

G012の初回10,000通貨canaryについて、actual broker POST直前までの実装、有限外部準備、
monitor-only LaunchAgent導入を対象とする。broker write、permitの実発行、major-incident resume発効、
current-turn最終確認、broker POSTは本Stepに含めない。

```text
actual_post=false
broker_write=false
activation_permit_issued=false
major_incident_resume_effective=false
current_turn_confirmation_consumed=false
```

## 2. Generation-bound activation design

- canary intentはG012 generation digest、cycle、正式side、`USD_JPY`、`MARKET`、10,000通貨へ固定する。
- major-incident resume proofと、ランダムnonceを含むfresh current-turn challengeは別のone-use型とする。
- 両proofのexact一致後だけ、canonical generation state rootへpermit-issued markerを`O_EXCL`で保存できる。
- permitは30秒、最大60秒以内に一度だけactual runtimeへbindできる。再利用、期限切れ、別generation、
  別cycle、既存markerは拒否する。
- 本Stepでは実generationのresume/current-turn proofを作らず、permitを発行しない。

## 3. Actual runtime and transport boundary

- runtime bindingはcanonical coordinator/risk/dead-man/process-lock pathだけを受理し、permitのgeneration/cycleと
  SQLite上の単一cycleが一致した場合だけactual-shaped transportを組み立てる。
- credentialは専用Keychain pairからrequest直前にsealed readする。env、`.env`、汎用Step 6G transportは使用しない。
- writeはcoordinatorがDBへattempt/pending markerをcommitして発行するone-use authorizationをadapterが再検証し、
  transport専用proofへ変換した場合だけ通過する。permit単独またはtransport直接呼出しではPOSTできない。
- transportは同一generation/cycle/actionの二回目をrequest前に拒否し、retry、queue、sleep、repostを持たない。
- hard guardの`allow=True`は上記permitとDB-backed proofの双方を消費したPOST分岐だけに存在する。
  preparation/runtimeの実行ではこの分岐を呼ばない。
- fake credentialとfake httpx clientだけを使う専用testで形状を確認する。

## 4. Monitor-only resident supervisor

- supervisorはcredential loader、HTTP client、Private API、adapter、broker writeをimportしない。
- generation専用`supervisor.lock`で単一processを強制し、15秒ごとにsafe heartbeatをatomic更新する。
- MARKET attempt後15秒を超えてexact protection未確認ならpersistent HALTをlatchする。
- 通常23時間期限または金曜の土曜03:45 JST期限で、one-use `exit-sequence-dispatch-required` markerを作る。
- 金曜entryが土曜04:00 JSTに未flatなら`flat-target-missed` markerとpersistent HALTを保存し、再試行しない。
- supervisor自身はexit writeを行わず、broker read/write countは常に0である。

## 5. Generation-bound finite exit dispatcher

- dispatcherはresident supervisorから分離し、actual runtimeが保持するcanonical coordinator pathと
  process lockだけを受理する。supervisorはdispatcherをimportせず、broker capabilityを持たない。
- supervisorの`exit-sequence-dispatch-required`をgeneration digest一致で`O_EXCL` claimした場合だけ一度進む。
- 固定順序は、fresh reconciliation、保護OCO取消用Public OPEN確認、取消1 attempt、fresh reconciliation、
  position-specific close用の別Public OPEN確認、close 1 attempt、fresh reconciliation、flat記録である。
- cancel／closeの各attemptはcoordinatorのDB-backed one-use authorizationとactual transportの同一cycle/action
  検証を通る。結果不明、拒否、market非OPEN、flat不成立はpersistent HALTとなり、同markerを再claimしない。
- 本Stepではdispatcherを実行しない。fake pathだけで成功順序、二度目拒否、generation不一致拒否、
  unknown時HALTを検証する。実dispatcherの起動は将来のactual canary current-turn Stepに属する。
- actual canary開始後は、permitを消費した同一foreground runtime driverがprocess lockを保持し、dead-manを
  5秒ごとに更新しながらmarkerを待ち、dispatcherを一度だけ呼ぶ。driverはLaunchAgent化せず、monitor-only
  supervisorとbroker capabilityを共有しない。driver例外はpersistent HALTとし、自動rebindしない。
- Mac電源断などでforeground driver自体が失われた場合は自動再bindしない。通常保有中はserver-side OCOが
  残るが、03:45のOCO取消受理後からposition close受理前に停止した場合は一時的に無保護となる。どちらも
  予定時刻の自動決済は保証されず、persistent HALTとoperator手動復旧が必要な初回canaryの残余リスクとする。

## 6. LaunchAgent

- labelは`com.fxstrategylab.h11v4.g012.monitor`へ固定する。
- `RunAtLoad=true`、`KeepAlive=true`、15秒monitor loop、30秒launchd throttleを使用する。
- plistはmonitor-only entrypoint、repository、safe local log pathだけを含み、credential、operator phrase、
  broker payload、IDを含めない。
- install/bootstrap/kickstartは有限各1回とし、cronを使用しない。
- 実導入は完全review、commit/push、clean main、generation digest整合後だけ行う。

## 7. Verification plan

```text
focused_activation_supervisor_tests=96_passed
h11_v4_related_tests=203_passed_249_deselected
real_post_isolation_tests=23_passed
full_backend_tests=8040_passed
full_backend_environment_exclusion=2_v3_keychain_write_setup_tests
ruff=passed
git_diff_check=passed
danger_scan=passed_expected_post_branch_only
architecture_review=clear
safety_review=clear
strategy_operations_review=clear
```

全体testでは、実Keychainへtest credentialを書き込む既存v3 testファイル
`test_h11_v3_keychain_credential_no_post.py`だけを除外した。この環境ではtest setupのKeychain writeが
`Operation not permitted`となるためであり、G012のsealed Keychain read rehearsalとは別境界である。
除外前の試行は`4740 passed / 2 setup errors`、除外後のclean runは`8040 passed`であった。

## 8. External preparation order

commit/push後のclean mainで、G011を流用せずG012専用generationとして固定順序を一度だけ実行する。

```text
1. Keychain presence 6/6
2. sealed Keychain access rehearsal
3. Pushover application send 1回 + acknowledgement
4. SMTP send 1回 + operator delivery confirmation
5. current-host / disposable KILL rehearsal
6. account exclusivity current confirmation
7. Public status/ticker GET
8. latestExecutions / openPositions / activeOrders 各1回
9. LaunchAgent install/bootstrap/kickstart + heartbeat/single-lock/HALT restart確認
10. major-incident resume発効直前で停止
```

各operationはstarted markerを先に保存し、失敗・不明時は同generationで再試行しない。safe aggregate以外の
credential、raw response、header、signature、receipt、実IDは表示・保存しない。

## 9. Remaining current-turn gates

- fresh正式30分signalが`BUY`または`SELL`で期限内。
- market `OPEN`、quote fresh、spread上限内。
- fresh 3-GETがaccount flat、active order 0、unowned 0。
- risk/dead-man/clock/notification/process lockがclear。
- 5.0 pips adverse-slippage仮定は上限保証でないというresidual riskのfresh operator承認。
- G012限定major-incident resume phraseのfresh入力。
- exact注文sheetを見た後のfresh current-turn confirmation。

これらは過去入力を再利用しない。本Stepはmajor-incident resume直前かつbroker POST直前で停止する。

## 10. Safety flags

```text
actual_post=false
broker_write=false
broker_post_count=0
retry=false
repost=false
second_attempt=false
credential_value_exposure=false
raw_response_exposure=false
real_id_exposure=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```
