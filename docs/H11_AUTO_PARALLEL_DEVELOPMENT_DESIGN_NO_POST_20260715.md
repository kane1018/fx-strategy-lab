# H-11 完全自動売買・並行開発設計（manual主運用維持 / no-POST）

Date: 2026-07-15

Status: `RELAXED_V4_SELECTED_IMPLEMENTED_FAKE_ONLY`

Revision: `V2_PARALLEL_DEVELOPMENT_AND_ACCOUNT_ISOLATION_20260715`

## 1. 結論

手動シグナルUIを止めず、完全自動売買を**別トラック**として並行開発する。
ただし、凍結中のH-11 v3をそのまま再開しない。予測モデルとbroker執行を分離し、
broker非依存の安全基盤を先に完成させ、公式仕様を満たすexecution profileが選定された後だけ
actual adapterへ進む。

```text
manual_track=PRIMARY_OPERATOR_TRADING
auto_track=PARALLEL_FAKE_ONLY_PHASE_B
h11_v3=FROZEN_AND_BLOCKED_BY_BROKER_CONSTRAINTS
h11_v4=H11_V4_GMO_MARKET_THEN_EXACT_OCO_NO_POST_V1
actual_post=false
broker_write=false
credential_read=false
live_ready=false
unattended_live_supported=false
```

ここでいう「並行」は次の2段階を区別する。

| 対象 | 現在の可否 | 条件 |
| --- | --- | --- |
| manual UI と auto の設計・offline test・paper・fake soak | 可能 | process / state / port / credentialを分離 |
| manual UI と auto のactual liveを別口座で同時稼働 | 将来可能 | 専用口座、別credential、別ownership、別risk budget |
| manual売買とauto actual liveを同一口座で同時稼働 | 現状不採用 | broker公式のownership識別が確認できないため |

manual trackの停止や置換をauto完成条件にしない。autoがHALTしてもmanualへ自動fallbackせず、manualの
取引開始記録をauto intentへ転用しない。両trackは同じformal signalを参照できるが、注文・建玉・予算・
停止状態は相互に継承しない。

## 2. 共有するもの・共有しないもの

### 共有してよいもの

- 凍結済みformal signalの**sanitized値**
- model version、signal config hash、horizon、観測時刻、validity、`p_up`
- 研究用のsafe aggregate

### 共有しないもの

- process
- port
- SQLite / journal / lock file
- manual trade plan / manual settlement ledger
- Keychain service / credential
- broker session / rate limiter
- position ownership
- retry state / attempt counter

manual UIとauto engineの直接importは禁止する。auto側は、固定schemaへ変換済みのformal signalだけを
read-onlyで受け取る。

## 3. 全体構成

```text
Formal Signal Producer (10分 / 30分)
        |
        | sanitized immutable snapshot
        v
Auto Signal Adapter
        |
        v
Frozen Policy + Persistent Risk Gate
        |
        v
Intent Journal -> one-attempt CAS -> Execution Port
                                      |
                 +--------------------+--------------------+
                 |                                         |
          Fake/Paper Adapter                         Actual Adapter
          current Phase A/B                 profile選定・別授権後のみ
                 |                                         |
                 v                                         v
        Synthetic Broker State                   Broker-native protected entry
                 |                                         |
                 +--------------------+--------------------+
                                      v
                         Reconciliation / HALT latch
                                      |
                                      v
                      Safe status projection / notifier
```

予測層は注文権限を持たない。execution adapterもrisk policyを変更できない。`actual POST allowed`を
返す汎用allow bridgeは作らない。
signal / risk / execution / exit / data / hostを1つへ固定する完全generation manifestのtemplateは
`H11_AUTO_FROZEN_GENERATION_MANIFEST_TEMPLATE_NO_POST_20260715.md`を正とし、PENDINGを含むmanifestを
actual profileとして扱わない。

## 4. 自動運転の固定契約

### Signal

- actual候補は正式な10分または30分の**どちらか1つ**
- 毎秒ローリングと24時間表示はactual inputにしない
- `BUY / SELL`だけがentry候補、`STAY / UNKNOWN`はno action
- model version、config hash、horizonは起動時policyと完全一致
- signal expiry後はentryを作らない
- horizon選択はactual実装前にoperatorが固定し、成績に応じた自動切替をしない

### Position / budget

```text
maximum_open_positions=1
maximum_entry_attempts_per_jst_day=1
maximum_entry_attempts_per_intent=1
maximum_exit_attempts_per_intent=1
scale_in=false
hedging=false
opposite_entry_as_exit=false
retry=false
repost=false
```

金額、数量、1回・1日・月次損失上限はactual profile選定時に別configとしてoperatorが記名固定する。
予測確率を数量へ直接比例させない。

### Entry

- intentをSQLiteへcommitしてから送信attemptを開始
- entryはbroker-native server-side損失限定を同時に成立させる方式だけ
- signal validity内にbroker側または公式routeで失効できること
- 部分約定でも保護sizeが実建玉を超えないこと
- timeout / unknown / client error / server error後に再送しない

### Exit

- positionを一意に指定するdedicated settlement routeだけ
- generic opposite orderを決済として使わない
- broker-side SL / TPを最優先
- time exit、formal edge loss、risk stopはposition-specific exit intentへ変換
- exitも最大1attempt。unknownなら再送せずHALT

## 5. 状態機械

```text
OFF
  -> BOOT_RECONCILING
  -> ARMED
  -> WAITING_SIGNAL
  -> INTENT_PERSISTED
  -> PROTECTED_ENTRY_PENDING
  -> POSITION_PROTECTED
  -> EXIT_PENDING
  -> FLAT_RECONCILED
```

不明、stale、外部建玉、手動取引、active order競合、部分約定保護不一致、通知経路異常は
`HALTED_OPERATOR_REVIEW_REQUIRED`へ遷移する。HALTは再起動してもSQLiteに残り、operatorが原因確認後に
専用reload手順を実行するまで新規intentを拒否する。broker非依存Phase Aにはreload APIを作らない。
選定済みGMO relaxed v4には、exact phraseとfresh fake flatを要求し、履歴を削除せず
`OPERATOR_RELOAD_CLEARED`へ遷移するno-POST限定reloadを別実装した。actual reloadではない。

## 6. 口座分離

manual売買とauto actual liveを本当に同時稼働する場合、**自動売買専用口座を必須**とする。
manual UIが読む手動口座とauto口座を分け、API key、rate limiter、position ownership、損失予算を共有しない。

専用口座を用意できない場合、同一口座での「並行live」は行わない。代替は、manualとautoを同時に動かさない
排他的なtime-sharing運用であり、次をすべて固定しない限りactualへ進まない。

- auto運転時間中の手動売買禁止
- bootと各event後に全建玉・有効注文をreconcile
- engine由来と確認できない建玉・注文を検出したらHALT
- position ownershipを公式識別子で一意に追跡できる
- 「最大1建玉」とmanual建玉が衝突しない

現状のGMO仕様でownershipを十分に分離できない場合、同一口座の同時稼働案は不採用とする。

## 7. credential・process・network境界

- manual read-only credentialとauto credentialを共有しない
- Phase A/Bはcredential loader自体をbindingしない
- actual credentialはKeychain等のsealed local loadingのみ。env / `.env`は禁止
- API key / secret / signature / raw response / broker IDをUI・log・SQLite・Gitへ出さない
- auto processはmanual UIと別entrypoint、別port、別state directory、別lock
- public market dataとPrivate APIのrate limiterも別管理し、全体上限内でbudgetを固定
- actual常駐化はコード完成ではなく、execution host・supervisor・通知先・時刻同期を別gateで確認

## 8. 開発Phase

### Phase A — broker-independent foundation（現在）

実装済み:

- frozen signal / policy contract
- persistent state machine、one-attempt CAS、重複拒否
- JST日次1回制限、HALT永続ラッチ
- refusing/fake transportだけのentry / exit lifecycle
- crash/restart decision
- pure BID/ASK cost model
- position-specific exit policy
- 100-cycle synthetic fault soak

完了条件:

- focused tests / related isolation tests / Ruff / danger scanがclear
- actual transport、credential、network、broker importが0

### Phase B — bounded paper forward（broker非依存部分を実装済み）

broker回答を待たずに実装可能:

1. 有限時間だけ動くpaper clock runner（cron / resident化なし）
2. formal signal snapshotを読み、同一policyでpaper lifecycleを進める
3. restart、kill、journal tamper、clock skew、stale data、notification lossのprocess-level test
4. safe aggregate日次・週次report
5. auto専用read-only status projection
6. 24h wall-clock fake soak（Macが稼働し続ける独立実行環境で行う）

実装済みのrunnerはlocal sanitized JSONLだけを入力にし、最大件数・最大実行秒数を必須化する。
専用process lockを取得できなければ開始せず、fake protected entry後は明示的なsynthetic auto-flatを
指定しない限りその場で停止する。run generation label、strategy version、config hash、selected horizon、
risk policy、dead-man policyはSQLite metadataへ初回binding時にdigest固定し、同じstateを別設定で
再利用しようとするとfail-closedにする。SIGKILL後のSQLite attemptとOS lock解放もprocess-level testで確認する。

safe aggregateとstatus projectionはSQLiteをread-only URIで開き、cycle数、attempt数、state、HALT reason
code、journal検証結果だけを出す。intent / signal fingerprint / broker ID /価格 / 数量は出力しない。
generation / strategy / horizon / risk / dead-manは値そのものではなく登録済みsafe labelだけを出す。
status projectionはone-shot CLIであり、server、port、resident processを追加しない。

24h wall-clock fake soakは既存checkpointを上書き・自動resumeせず、観測gapが上限を超えた場合は
成功時間へ算入せずfailする。開始時のauto source digestをcheckpointへ固定し、完走後のコードと
一致しないrunをclearに使わない。Phase Bは収益性の証明ではなく、運用機構が壊れないことの確認である。

manual current responseとの受渡しは、auto packageがmanual packageをimportまたはlocalhost GETするのではなく、
broker / position / execution / trade-plan fieldsを除去した`signals`だけのmapping契約で行う。Phase Bでは
pure extractorとfake testsまで実装し、実localhost bindingは追加していない。

current endpointはGETでもmanual ledger更新を伴い、top-levelとrecord fieldもauto契約より広いため直接利用を
却下した。専用の副作用なしsanitized routeに必要なexact schemaとtest gateは
`H11_AUTO_FORMAL_SIGNAL_LOCALHOST_BINDING_REVIEW_NO_POST_20260715.md`でreview済み。binding実装は別授権とする。
M1確定、freshness、clock、poll cadenceは
`H11_AUTO_FORMAL_DATA_CLOCK_CONTRACT_DRAFT_NO_POST_20260715.md`へ分離し、consumerによる暗黙data fetchや
model trainingを禁止した。

HALT後の再開は
`H11_AUTO_OPERATOR_HALT_REVIEW_RELOAD_DRAFT_NO_POST_20260715.md`で草案化した。HALT rowの変更・削除、
attempt reset、old checkpoint resumeは行わず、別承認後に新run generationを作る方針である。

broker非依存のpersistent risk / dead-man契約も`app.h11_auto.runtime_safety`として独立実装した。
risk policyは数値をコードへ仮固定せず、policy label、1回・日次・月次損失上限、連敗停止数をすべて
明示入力し、canonical digestとpersistent stateを一致させる。1日entry上限だけは1から変更できない。
per-trade超過はKILL、日次・月次・連敗はpersistent stopとし、月次・連敗・KILLはcalendar rolloverで
自動復帰しない。generic risk stopのreload関数は実装していない。GMO relaxed v4のcycle/global HALTだけは、
exact phrase＋fresh fake flatを要求し、解除とresumeを別操作にするno-POST限定関数を実装済みである。

dead-man heartbeatはpolicy digestとUTC時刻だけをatomic保存し、missing / corrupt / policy mismatch /
future / stale / time reversalをfail-closedにする。process control、external send、actual permissionは持たない。
bounded paper runnerはrisk / dead-man storeとexact `FakeNotifier`を必須注入し、各signal cycle前のfake
notification heartbeat失敗をentry attempt前のHALTにする。実risk数値はoperator freeze前のため
active defaultを持たず、CLIの明示値をpolicy digestへ固定する。external notification送信は実装しない。

完全generation manifestはoffline validatorでdraft/frozenを分離し、PENDINGを含むfrozen候補、unsafe invariant、
non-canonical threshold、設定の一部差し替えを拒否する。frozen時だけcanonical JSON SHA-256を生成するが、
runtime bindingやactivation permissionは生成しない。

### Phase C — execution profile selection

operatorの公式broker回答をsafe aggregate化し、次を満たすprofileを1つ選ぶ。

- short pending expiry
- full-fill-or-none、または部分約定量と保護量が原子的に一致
- server-side SL / TP
- position-specific settlement
- read-after-unknown reconciliation
- API permission、rate limit、fee、ToSが確認済み

GMOはstrict条件を満たさなかった。operator判断によりbroker変更ではなく、strategy側を即時成行前提へ
再設計し、残余リスクを明文化したrelaxed v4を選択した。actual接続はまだ行わない。

選定候補は次の3 profileに限定する。名前ではなく、公式仕様で非交渉条件を満たすかで判定する。

| profile | 採用条件 | 現在の扱い |
| --- | --- | --- |
| A. 短期expiry付きatomic bracket | entryとserver-side SL/TPが原子的、短期TIF、部分約定量と保護量が一致 | 第一候補 |
| B. 即時entry付きatomic protection | resting entryを使わず、実約定と同時にposition-specific保護が成立 | 公式確認後のみ候補 |
| C. 別brokerのnative bracket | AまたはBを公式に満たし、read-after-unknownと専用決済routeを持つ | GMO不成立時の候補 |

> 2026-07-15 operator override: この段落のstrict atomic条件は、現在のGMO向けv4には適用しない。
> operatorは同等安全性を必須にせず、最大15秒の一時的無保護を受容するMARKET→fill reconcile→
> exact-size OCOを別versionとして選択した。現在の正は
> `H11_V4_GMO_RELAXED_EXECUTION_PROFILE_NO_POST_20260715.md`。client timerによるpending entry取消、
> 同一actionのretry/repost、unknownからの継続は引き続き採用しない。

### Phase D — disabled actual adapter

profile選定と別実装授権後のみ:

- typed sender / reconciler / sanitized result contract
- fake HTTP clientとfake credentialだけで署名・request mappingを検証
- defaultは常にrefusing
- actual transportはproduction runtimeへbindingしない
- source isolation / no-POST regression / fault injectionをclear

profile非依存のreconciliation、unknown result、future package allowlist、fake-only test gateは
`H11_AUTO_PHASE_C_D_PREIMPLEMENTATION_DESIGN_NO_POST_20260715.md`で事前設計済み。これはPhase D実装授権、
actual adapter、broker access、credential、POSTを意味しない。

profile非依存のtyped entry / reconciliation / exit result契約は
`H11_AUTO_DISABLED_ADAPTER_INTERFACE_DRAFT_NO_POST_20260715.md`でdocs-only草案化済み。endpoint、payload、
credential、HTTPはGMO回答と別授権まで未実装とする。

### Phase E — supervised activation rehearsal

別授権後のみ:

- 専用口座、権限、sealed credentialのpresence確認
- read-only boot reconciliation
- notification / dead-man / clock / host / budget確認
- actual POSTなしのpreviewを固定期間実行
- operatorが全状態と停止・復旧手順を理解できることを確認

### Phase F — minimum-size observed unattended live

重大インシデントresume宣言、AGENTS.md例外、fresh activation、operator記名承認を別々に要求する。
最小数量・1日1回・最大1建玉で開始し、operator目視は補助とするが、自動執行の成立条件にしない。

## 9. reconciliation契約

actualでは次の時点でfresh readを要求する。

- boot
- entry attempt直前
- entry result直後
- position監視中の固定間隔
- exit attempt直前
- exit result直後
- WebSocket再接続後
- process restart後

次のどれかが一致しなければ新規writeを行わずHALTする。

```text
local state
broker position count
broker active order count
protected size
entry / exit attempt journal
position ownership
```

unknown結果を「失敗」と推定して再送しない。readで確定できない場合は停止を正解とする。

actual adapterが保持してよいbroker参照は、local専用keyで不可逆化したopaque ownership referenceだけとする。
raw order / execution / position IDはUI、通常log、safe report、Gitへ出さない。brokerがownership識別子を
提供しない場合、専用口座の「口座内の全建玉・全注文がauto所有」という前提でのみreconcileし、1件でも
外部状態を検知したらHALTする。

## 10. UI / 通知

manual UIはそのまま主運用として維持する。autoの状態は別のread-only画面へ以下だけ表示する。

- `OFF / ARMED / ACTIVE / HALTED`
- policy version / config hash（safe prefixではなく登録済みlabel）
- 本日entry attempt数
- position有無（件数のみ）
- protection確認状態
- last reconciliation age
- last heartbeat age
- budget stop状態
- HALT理由code

価格、数量、ID、raw broker response、credential情報は表示しない。通知はheartbeat loss、entry確定、
protection異常、exit確定、HALT、budget stopを扱い、通知失敗時も新規entryを止める。

## 11. 検証マトリクス

必須synthetic scenario:

- duplicate signal / duplicate process
- crash before intent / after intent / after attempt / after broker accepted
- timeout / unknown / delayed response
- partial fill / excess protection / missing protection
- stale ticker / stale formal signal / clock skew
- manual or external position conflict
- active order conflict
- notification loss / heartbeat loss
- daily / monthly loss stop
- restart with open protected position
- restart with unknown entry or exit
- journal tamper

各scenarioで次を固定する。

```text
maximum_entry_attempts_observed <= 1
maximum_exit_attempts_observed <= 1
unknown_causes_halt=true
unprotected_position_allowed=false
automatic_restart_from_halt=false
actual_post_count=0  # Phase A-D
```

## 12. 完成の定義

コード量やUI完成ではなく、次のすべてが揃った状態を完全自動売買の完成とする。

1. frozen signal / execution / risk / exit contracts
2. broker-native protected entryと短期expiryの公式確認
3. dedicated accountまたは同等のownership分離
4. persistent duplicate preventionとunknown HALT
5. boot / periodic / post-event reconciliation
6. sealed credentialと最小API permission
7. always-on host、supervisor、clock、dead-man、外部通知
8. fault soakとrestart recoveryの合格
9. operator reload / incident / rollback手順
10. 独立safety review、actual activationの別承認

さらに、次の4条件を「並行運用の完成条件」とする。

11. manualとautoのstate / credential / account / budgetが分離されている
12. auto停止・再起動・HALTがmanual UIへ影響しない
13. manual操作がautoのentry / exit / reloadを暗黙に発火させない
14. autoのactual結果をmanual台帳へ自動混入させない

収益性の検証は極小額liveと並行できるが、2〜9はlive開始前条件であり省略しない。

## 13. 現在の次Step

broker回答と独立して、Phase Bのコードは次まで実装した。

```text
1. bounded paper clock runner: `IMPLEMENTED_FAKE_ONLY`
2. process crash / restart fault test: `IMPLEMENTED_SIGKILL_TEST`
3. safe aggregate report: `IMPLEMENTED_READ_ONLY`
4. separate read-only status projection: `IMPLEMENTED_ONE_SHOT_CLI`
5. 24h wall-clock fake soak mode: `RUNNING_CODE_BOUND_NOT_YET_COMPLETED`
```

並行してoperatorはexecution profileの公式回答を取得する。回答が揃うまでPhase C以降へ進まず、
Phase A/Bのno-POST品質を上げる。

Phase B commands:

```bash
cd backend

# Local sanitized formal signal JSONLを有限処理
python3 -m scripts.h11_auto_phase_b_paper_run \
  --signals /absolute/path/to/sanitized_signals.jsonl \
  --state-dir market_data/h11_auto_phase_b \
  --strategy-version SHORT_V1 \
  --signal-config-hash '<operator-frozen hash>' \
  --horizon 10m \
  --generation-label '<new immutable generation label>' \
  --risk-policy-label '<operator-approved auto policy label>' \
  --per-trade-loss-bound-jpy '<operator-approved integer>' \
  --daily-loss-limit-jpy '<operator-approved integer>' \
  --monthly-loss-limit-jpy '<operator-approved integer>' \
  --maximum-consecutive-losses '<operator-approved integer>' \
  --dead-man-policy-label '<operator-approved dead-man label>' \
  --dead-man-maximum-age-seconds '<operator-approved integer>'

# safe aggregate
python3 -m scripts.h11_auto_safe_report \
  --state market_data/h11_auto_phase_b/auto_state.sqlite3

# 日次転記用（operator起動のみ）
python3 -m scripts.h11_auto_safe_report \
  --state market_data/h11_auto_phase_b/auto_state.sqlite3 \
  --since-jst YYYY-MM-DD \
  --until-jst YYYY-MM-DD \
  --format markdown

# 週次はMondayとSundayを同様に指定する。cron / launchdへ登録しない。
# 詳細な停止・集計・引き継ぎ手順はH11_AUTO_PHASE_B_OPERATOR_RUNBOOK_NO_POST_20260715.mdを参照。

# one-shot safe status
python3 -m scripts.h11_auto_status \
  --state market_data/h11_auto_phase_b/auto_state.sqlite3

# 24h bounded fake soak（新しいcheckpoint pathを毎回使う）
python3 -m scripts.h11_auto_wall_clock_soak \
  --checkpoint market_data/h11_auto_phase_b/soak_YYYYMMDDTHHMMSS.json \
  --duration-seconds 86400 \
  --batch-interval-seconds 60 \
  --maximum-gap-seconds 180

# heartbeat / completion確認
python3 -m scripts.h11_auto_wall_clock_soak_status \
  --checkpoint market_data/h11_auto_phase_b/soak_YYYYMMDDTHHMMSS.json \
  --maximum-heartbeat-age-seconds 180
```

## 14. 完全自動liveのend-to-end契約

将来のactual runtimeは、次の順序を崩さない。

```text
BOOT
  -> local journal integrity確認
  -> fresh broker read-only reconcile
  -> clock / heartbeat / notification / budget確認
  -> ARMED
  -> selected formal signal待機
  -> signal expiry / data quality / spread / risk gate
  -> intent先行永続化
  -> protected entryを最大1attempt
  -> read-only reconcileでpositionとprotectionを確認
  -> position-specific監視
  -> broker-native SL/TP または固定time/edge-loss exit intent
  -> dedicated settlementを最大1attempt
  -> read-only reconcileでFLAT確認
  -> 次のJST日まで新規entry停止
```

どの段階でもtimeout、unknown、local/broker不一致、protection不明、heartbeat不達、通知不達、budget stop、
外部建玉を検知したら、新規writeを行わずpersistent HALTへ移る。既存建玉はbroker-side protectionを維持し、
自動retry/repostや反対売買によるgeneric closeを行わない。HALT解除は自動化せず、別run generationで
operator review後に行う。

## 15. 今後の実装順序と授権境界

| Step | 内容 | 現在 | 次へ進む条件 |
| --- | --- | --- | --- |
| 1 | broker-independent core | 実装済み・fake only | focused/related検証clear |
| 2 | bounded paper / crash recovery / 24h soak | 実装済み・soak進行中 | code-bound 24h完走 |
| 3 | 副作用なしformal signal localhost binding | review済み・未binding | 専用schemaと別授権 |
| 4 | execution profile選定 | broker回答待ち | Phase Cの全条件clear |
| 5 | disabled actual adapter | 未着手 | profile freezeと実装授権 |
| 6 | read-only activation rehearsal | 未着手 | 専用口座・credential・host・通知承認 |
| 7 | minimum-size auto live | 禁止中 | AGENTS例外、incident resume、fresh activation、記名承認 |

Step 1〜3はmanual主運用と並行できる。Step 4〜7はGMO回答だけで自動的に解除されず、各Stepごとに
独立したreviewとoperator授権を必要とする。現行AGENTS.mdの通常境界では完全自動POSTは許可されないため、
live activationは別のpolicy改定なしには行わない。
