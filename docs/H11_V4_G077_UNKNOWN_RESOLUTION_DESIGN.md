# H-11 v4 G077 Unknown-Resolution Read-Back 設計書（no-POST・fake-only実装先行）

- 日付: 2026-08-05
- 対象: G076の「UNKNOWN = generation terminal」が産む新generation再挑戦パイプラインの最適化
- ステータス: **設計書提出（operatorレビュー待ち）**。D1/D2はoperator未回答のため推奨案を採用
  （D1=a: 次cycle新規観測 / D2=b: 全write action共通）。変更可能。

## 1. 問題定義：不要な工程とは

G076契約（`H11_V4_G076_FINAL_COMPLETION_CONTRACT.md`）では、write actionの結果が
`UNKNOWN`（応答不明・timeout・部分不明）になると同generationはterminalとなり、次の試行に
新corrective generationが必要になる。その際に毎回発生する工程：

1. 新reviewed-files digest / generation digestの再計算・再凍結
2. 実装＋fake test（数百件）＋全スイート検証
3. 独立Architecture/Safety/Operationsレビュー（VETO対応含む）
4. AGENTS.md例外セクション追加
5. commit/push → canonical昇格
6. 完全なfresh external preparation（Keychain presence・通知rehearsal・Private GET）
7. operation 60再実行 → initial activation再実行

G074→G075→G076の実績では、G075はop60=PASSEDの後にinitial activationがUNKNOWNとなり、
上記1〜7を全て無駄にした。**UNKNOWNの大半は「writeの応答喪失」であり、writeの成否自体は
readで確定できる**。read-back解決を同generation内に持てば、新generationパイプラインは
「read-backも不明（UNRESOLVED）」というレアケースにだけ縮小できる。

## 2. 目標と非目標

### 目標
- write actionがUNKNOWNになったとき、**同generation内で**read-back（読み取りのみ）により
  「約定済み（CONFIRMED_EXECUTED）」「未約定（CONFIRMED_NOT_EXECUTED）」を確定する。
- 確定結果はopaque digest付きevidenceとして個別に記録し、次のscheduled cycleが
  「新規観測」として続行できるようにする（既存原則「後続cycleはretryではなく新観測」を踏襲）。
- UNRESOLVED（read-back自体が不明・曖昧）だけをterminalとし、新generationを要するレアパスにする。

### 非目標（外さない制約）
- writeそのものは**各actionにつき1回のみ**。same-action retry / repost / second attemptは一切行わない。
- read-back解決は**generation-bound・one-use**。started marker作成後に失敗・結果不明なら
  同generationで再試行しない。
- read-backは各endpoint（`latestExecutions` / `openPositions` / `activeOrders`）**各最大1回**。
- 解決結果をauthorization booleanとして組み立てない。`__bool__`型のallow値、aggregate allow、
  hard-guard解除値は生成しない。次のactionは常に新規opaque action scopeを要する。
- credential値・raw request/response・header・signature・実ID・実数量・価格は読み書きしない。
- `main_readonly.py`不変。hard guard（`assert_real_broker_post_allowed`）不変・default-deny維持。
- G073/G074/G075/G076のmarker・state root・evidence・authorizationを変更・再利用しない。
- 実装・testはfake/syntheticのみ。実Keychain・実Private GET・実POST・通知・ARM変更は別境界。

## 3. 状態モデル（G076状態への追加・独立投影）

| 状態値 | 意味 |
|---|---|
| `resolution_state = NOT_REQUIRED` | UNKNOWNなし。解決不要 |
| `resolution_state = REQUIRED` | write actionがUNKNOWN。解決stepを要する |
| `resolution_state = CONFIRMED_EXECUTED` | read-backで「所有権・数量が確定した約定」を確認 |
| `resolution_state = CONFIRMED_NOT_EXECUTED` | read-backで「flat・active order 0・該当約定なし」を確認（action kind別に次cycle or terminal） |
| `resolution_state = CONFIRMED_PARTIAL_FILL` | 約定あり・所有権/数量がexactでない部分約定。fail-closedでterminal（HALT: G077_PARTIAL_FILL_TERMINAL） |
| `resolution_state = UNRESOLVED` | read-back不明・曖昧・timeout。terminal（persistent HALT） |

`resolution_state`は `arm_state` / `release_state` / `effective_state` / `entry_gate` /
`reconciliation_state` とは独立してUIへ投影する。**解決結果は「次のactionの許可値」ではない。**

## 4. 解決プロトコル（`run_g077_unknown_resolution_once`）

```
前提: あるwrite actionのoutcomeがUNKNOWNとして記録済み（action_scope_digest付き）
 0. digest検証・action kind検証・非fake port拒否（post-start前の拒否はstateを書かない）
 1. flock工程ロック（g077-resolution.lock・非blocking・release on close）
    → 保持中は G077_PROCESS_LOCK_HELD
 2. start window検証: UNKNOWN観測から15秒以内に開始（超過は G077_RESOLUTION_START_WINDOW_EXCEEDED）
 3. 予算検証: 同generationで最大3解決（g077-resolution.budget.json・各scope最大1回）
    → 超過は G077_RESOLUTION_BUDGET_EXCEEDED
 4. O_EXCLで per-scope started marker g077-resolution.{scope}.started.json を生成
    （credential/networkより先）→ 既存なら G077_RESOLUTION_ALREADY_STARTED_NO_RETRY
 5. 固定順でread-backを各1回のみ・各read間に0.25秒以上（max 4 GET/sec）:
      a. latestExecutions   → sanitized count / matched_execution_seen
      b. openPositions      → sanitized count / account_flat / ownership_exact / quantity_matches / protection_confirmed
      c. activeOrders       → sanitized count / active_orders_zero
    開始から60秒以内に完了しない場合はtimed_outとして打ち切り → UNRESOLVED（HALT）
 6. action kind別に分類（fail-closed・§11の表）
 7. 結果を per-scope evidence g077-resolution.{scope}.evidence.json へopaque digest付きで
    原子的に記録（sanitized count / boolean / status / policy / 各digestのみ）
 8. 予算をincrement（resolutions_used+1）
 9. UNRESOLVED / PARTIAL / TERMINAL policy の場合のみ g077-persistent-halt.json を記録
 10. 解決step中は一切のwrite・通知・ARM変更を行わない
     post-start失敗はmarker保持のままG077_RESOLUTION_INTERNAL_FAILUREでHALTし再raise
```

### 分類の根拠（fail-closed）

| 観測 | 判定 | 根拠 |
|---|---|---|
| 所有権exact・数量exact・該当約定あり | CONFIRMED_EXECUTED | 自分が建てたことが確定。exit管理・OCOは「次アクション」 |
| flat・active order 0・該当約定なし | CONFIRMED_NOT_EXECUTED | 何も所有していないことが確定。次cycleは「新規観測」 |
| read不明・flatなのに約定あり・所有権不一致等 | UNRESOLVED | 曖昧は決してauthorizationにしない（default-deny） |

## 5. D1/D2 採用決定（operatorレビュー項目）

- **D1（CONFIRMED_NOT_EXECUTED後の扱い）: 採用 (a) 次scheduled cycleの新規観測として再評価**
  - 同一generation内での即時新action（(b)）は「retryに等しい再入」の構造を作るため不採用。
  - (a)はG076既存原則「A later scheduled cycle is a new observation, not a retry」に完全一致。
- **D2（read-back解決の適用範囲）: 採用 (b) 全write action共通**
  - initial activation・entry・OCO・cancel・closeの全UNKNOWNに同一プロトコルを適用。
  - 実装は解決stepを汎用化し、action kindをscope digestにbindする形にする。
- **D3（新設・明文化）: UNRESOLVEDは同generationでHALT、解除はoperator確認＋新generationのみ**
  - G076のno-retry・no-marker-reset契約をG077でも維持。

## 6. 契約上の不変境界（実装が満たすべき項目）

1. write: 1 attempt / action。retry・repost・second attempt 0。
2. read-back: 3 endpoint各最大1回 / 解決step。解決stepは同generationで1回のみ。
3. `actual_post_authorized=false` / `broker_post_authorized=false` / `entry_authorized=false` をevidenceに固定。
4. 解決結果はboolを返さない。`__bool__`は常にfalse。
5. started markerはcredential/networkより先にO_EXCL作成。全post-start失敗は同generationでretryしない。
6. UNRESOLVEDはpersistent HALT。markerの削除・変更・reset禁止。
7. fake-only: read-back portは`G077FakeOnlyCallable`以外を拒否。
8. 実装moduleから実transport・credential・broker write経路へのimport/到達をsource scanで禁止。

## 7. fake-only acceptance matrix（実装完了条件）

1. read-back全成功でCONFIRMED_EXECUTED（所有権・数量exact）になる
2. read-back全成功でCONFIRMED_NOT_EXECUTED（flat・zero active・約定なし）になる
3. 最初のread失敗でUNRESOLVED→persistent HALT、以後のreadを実行しない
4. 曖昧（flatなのに約定あり等）でUNRESOLVED→HALT（fail-closed）
5. started marker既存で再呼び出しを拒否（G077_RESOLUTION_ALREADY_STARTED_NO_RETRY）
6. 非fake portを拒否（G077_FAKE_ONLY_READ_BACK_REQUIRED）
7. evidenceのartifact_digestがcanonical hashに一致、digest束縛が一致
8. 各endpointが解決step中に最大1回しか呼ばれない
9. evidenceに`actual_post_authorized=false`・`broker_post_authorized=false`を固定
10. module source scanでhttpx/Keychain/credential/transport tokenが不在
11. 既存G076 focused testsが無変更で全件PASS（G077はadditive）

## 8. 実装ファイル（本設計書時点）

| ファイル | 種別 |
|---|---|
| `docs/H11_V4_G077_UNKNOWN_RESOLUTION_DESIGN.md` | 本設計書 |
| `backend/app/services/h11_v4_g077_runtime.py` | 解決step・状態・evidence（fake-only） |
| `backend/h11_v4_g077_reviewed_digest.py` | G077専用reviewed-files digest / generation digest |
| `docs/templates/h11_v4_g077_frozen_generation.json` | G077凍結generation（既存戦略契約を踏襲＋解決契約） |
| `backend/app/tests/h11_auto/test_v4_g077_unknown_resolution_fake_only.py` | fake-onlyテスト |

既存G076 module・shared reviewed digest（`backend/h11_v4_reviewed_digest.py`）・
AGENTS.md本体は**本スライスでは変更しない**（AGENTS.mdのG077例外セクション追加は、
設計承認後のgeneration凍結stepで実施）。

## 9. 実装後の工程

1. 設計承認（operator・D1/D2確認）→ 2. 実装済みmoduleの独立A/S/Oレビュー →
3. 新reviewed-files digest / generation digest再凍結 → 4. AGENTS.md例外セクション追記（diff提示）→
5. commit/push → 6. 別明示承認後のみoperation 60 / initial activation / read-back解決の実実行
   （実Keychain・Private GET・POSTは従来どおりoperator境界）

## 10. Definition of done

- fake acceptance matrix全件PASS、focused/related tests・Ruff・diff check・danger scan CLEAR
- 独立A/S/OレビューCLEAR（VETO修正含む）
- G077専用digestが実ファイルと束縛整合（binding field null化で自己無矛盾）
- 既存G076 tests無変更で全件PASS（additive性）
- 実Keychain・Private API・broker・通知・ARM・LaunchAgentへ未接続
- `actual_post_authorized=false` / `broker_post_authorized=false` / `live_ready=false` /
  `unattended_live_supported=false` を維持

## 11. v1.1 レビュー反映（2026-08-05・H1/H2/M1/M2/M3/L1/L2）

設計書レビュー（重大度順H1→L2）の指摘を反映した。v1.1は既存5ファイル＋本節の追記で実装済み。

### H1: 解決markerをaction scope単位へ・予算上限・GETレート制限

- started marker / evidence を **action_scope_digest単位**（`g077-resolution.{scope}.started.json` /
  `g077-resolution.{scope}.evidence.json`）に変更。entry→OCO連鎖の各UNKNOWNを別scopeとして
  個別に解決できる。
- 同一generationの解決予算は **最大3**（`G077_MAX_RESOLUTIONS_PER_GENERATION=3`・各scope最大1回）。
  予算台帳 `g077-resolution.budget.json`（generation_digest・resolutions_used・resolved_scopes）
  を原子的に更新。超過は `G077_RESOLUTION_BUDGET_EXCEEDED`。
- GETレート制限: read間隔 **0.25秒以上**（`G077_MIN_READ_INTERVAL_SECONDS=0.25`・max 4/sec）。
  monotonic clock + sleepを注入し、テストで決定論的に検証。

### H2: 解決タイムライン（15秒開始 / 60秒完了・injected clock）

- **開始窓**: UNKNOWN観測から **15秒以内**（`G077_RESOLUTION_START_WINDOW_SECONDS=15`。
  `maximum_unprotected_seconds=15`と同値）。超過はpost-start前拒否
  （`G077_RESOLUTION_START_WINDOW_EXCEEDED`・stateを書かない）。
- **完了予算**: started marker作成から **60秒以内**（`G077_RESOLUTION_COMPLETION_BUDGET_SECONDS=60`）。
  超過はtimed_outとして打ち切り → UNRESOLVED（HALT: `G077_RESOLUTION_TIMEOUT`）。
- monotonic clock（`time.monotonic`）とsleep（`time.sleep`）は引数注入。
  個々のreadのtransport timeoutはread-back client側の責務（本stepはfake-only）。

### M1: CONFIRMED_PARTIAL_FILL（部分約定）はfail-closedでterminal

- GMO MARKET注文は部分約定が現実。約定あり・建玉あり・所有権/数量がexactでない観測は
  `CONFIRMED_PARTIAL_FILL` として区別する（`partial_fill=true` をevidenceに記録）。
- **本stepはfake-onlyのため未約定残のcancelを自動実行しない**。`CONFIRMED_PARTIAL_FILL`は
  **terminal**（HALT: `G077_PARTIAL_FILL_TERMINAL`）。未約定残cancelはfresh観測を持つ
  operator実行action（別境界・別承認）とする。

### M2: action kind別の解決解釈表（`G077WriteActionKind`）

| action kind | CONFIRMED_EXECUTED | CONFIRMED_NOT_EXECUTED（policy） | それ以外 |
|---|---|---|---|
| MARKET_ENTRY | 約定あり・所有権exact・数量exact・非flat | flat・zero active・約定なし → NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION | 部分約定=PARTIAL(terminal) / 曖昧=UNRESOLVED(terminal) |
| POSITION_SPECIFIC_EXIT | flat・zero active | 建玉所有（サイズ不一致含む） → NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION | 読取不明=UNRESOLVED(terminal) |
| EXACT_SIZE_OCO_PROTECTION | 保護確認・所有権exact・数量exact・非flat | flat・zero active（保護不要） → NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION | 建玉あり保護なし=UNRESOLVED(terminal・保護ギャップ) |
| CANCEL_UNFILLED_REMAINDER | active order 0 | active order残存 → TERMINAL（G013: pending残存時の追加write禁止） | — |
| INITIAL_ACTIVATION | —（market read-backではactivation成否を確定できない） | — | 常にUNRESOLVED(terminal・G075/G076前例) |

- evidenceに `action_kind`・`resolution_policy`（ACTION_CONFIRMED /
  NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION / TERMINAL_FOR_GENERATION）を記録。
- 「次scheduled cycleの新規観測」は**同一M1 slot内の再評価を禁止**（L2）。30分cycleの
  次回M1 slotからでないと新actionを試行できない。

### M3: プロセス間ロック（flock）

- `g077-resolution.lock` を非blocking `flock(LOCK_EX|LOCK_NB)` で保持。保持中は
  `G077_PROCESS_LOCK_HELD`。fd close / process exitで自動解放（crash安全）。
- O_EXCL started marker（no-retry保証）と二重化。解決stepはsingle-process契約。

### L1: UIへの独立投影（wiringは別Step）

- `g077_resolution_status` は `resolution_state` / `resolutions_used` / `resolutions_limit` /
  各scopeのevidence概要を、`arm_state` / `release_state` / `effective_state` /
  `entry_gate` / `reconciliation_state` と独立して返す（inert read-only）。
- 解決結果はauthorization値に接続しない。実際のUI wiringはruntime結線Stepで行う。

### L2: 「次のscheduled cycle」の定義

- 30分cycleの**新しいM1 slot**で、fresh observation（fresh Private GET）から始まる
  next cycleのみを「新規観測」とみなす。同一M1 slot内での再評価・再試行は禁止。

### v1.1 acceptance matrix（§7への追加）

12. 同一scopeの再解決を拒否（scope marker既存）→ `G077_RESOLUTION_ALREADY_STARTED_NO_RETRY`
13. 別scopeは予算内で解決可能（各scope最大1回）
14. 予算3超過で4件目を拒否 → `G077_RESOLUTION_BUDGET_EXCEEDED`
15. UNKNOWN観測から15秒超の開始をpost-start前拒否（state不変）
16. 60秒超過の解決はtimed_out → UNRESOLVED（HALT: G077_RESOLUTION_TIMEOUT）
17. read間隔0.25秒のpacingを検証（injected clock）
18. プロセスロック保持中を拒否 → `G077_PROCESS_LOCK_HELD`
19. 部分約定 → `CONFIRMED_PARTIAL_FILL` + HALT（G077_PARTIAL_FILL_TERMINAL）
20. action kind別解釈（exit/OCO/cancel/initial activation）が表の通り
21. post-start契約違反（非G077SanitizedRead返却等）はHALT+再raise
22. status投影がevidence不正をUNRESOLVEDとして報告
