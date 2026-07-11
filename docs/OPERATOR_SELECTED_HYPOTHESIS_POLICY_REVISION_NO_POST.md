# Operator-Selected Hypothesis Policy Revision（方針改定・草案）— no-POST

Date: 2026-07-10

Status: **ACTIVE**

本書は方針改定の**草案**であり、operator が承認して Status を `ACTIVE` に更新するまで、
いかなる効力も持たない。本書の存在・起草・コミットは次のいずれも意味しない。

- actual POST permission / entry POST / settlement POST の許可
- E1 / E2 gate 通過、E3 / live readiness
- per-trade operator confirmation の除去
- research phase の再開
- 「勝てる」「edge あり」「performance_proof=true」のいかなる主張

```text
actual_POST=false / entry_POST=false / settlement_POST=false / POST_count=0
performance_proof_status=false / live_ready=false / unattended_live_supported=false
```

---

## 1. 背景と根拠（なぜ改定するか）

### 1-1. 確定している事実

- 標準 gate（walk-forward × コスト2.0×ストレス × slippage 0.5pip/side × random p90 対照）の下で、
  採点済み全仮説（H-01〜H-05、candidate-config 概数 ~20）は **REJECTED**。
  `current_strategy_status=NO_ROBUST_EDGE_FOUND_IN_TESTED_SCOPE`、research_phase=CLOSED_OUT。
- 2026-07-08 に operator-gated one-shot の完全 live サイクル
  （entry POST 受理 → ポジション確認 → 公式 settlement POST 受理 → フラット確認）が完了済み。
  実行境界は一巡の実弾実績を持つ。
- E1 shadow full-auto engine は実装済みだが `E1_IMPLEMENTED_NOT_GATE_PASSED`。
  キャンペーン・証拠審査は未実施。

### 1-2. 診断（operator と Fable5 の合意点）

1. **「絶対勝てるロジック」は存在し得ない。** 持続的・単純・発見可能な edge は裁定で消える。
   あらゆる edge は確率的・レジーム依存・減衰性である。
2. **「edge の統計的証明が先、live 露出が後」という暗黙規範は実質的に永久停止と同義。**
   +0.05R/trade の検出には約 2,500 トレード（個人頻度で 5〜10 年）を要する。
3. 既存フレームワークは「何を棄却するか」の規則は完備していたが、
   **「何も通らなかったとき、次にどう行動するか」の決定規則を持っていなかった。**
   その空白がプロセスの自己増殖（証拠受入機構の過剰精緻化）を生んだ。
4. 自動売買ツールの本質は alpha の発見装置ではなく、**operator が選んだ理論を
   感情抜きで機械的に執行する規律装置**である。

### 1-3. 譲らない前提（本改定でも不変）

- **感情を除去しても期待値の符号は変わらない。** 計測済みマイナスのロジックの機械実行は
  「感情抜きで淡々と負けること」である。よって operator-selected 運用は
  「勝ちの期待」ではなく「**既知の摩擦コスト＝実験の価格**を支払って自分が選んだ実験を走らせる」
  行為として定義し、必ず予算化する。
- **感情は消えず一段上（仮説レベル）へ移動する。** 本改定で自動化が守るべき規律は
  トレードレベルではなく仮説レベル（事前登録・凍結・予算・停止基準）である。

---

## 2. 改定の中核: フレームワークの役割変更

```text
旧: evaluation framework = GATEKEEPER
    （robust edge の証明が live 露出の前提条件）

新: evaluation framework = SCOREKEEPER + RISK ENFORCER
    （edge の賭けは operator が選ぶ。機械は執行規律・リスク上限・計測の誠実さのみを守る）
```

- edge 選定の権限と責任は **operator に帰属**する。エージェント・エンジン・フレームワークは
  edge の有無を承認しないし、承認できない。
- フレームワークの標準 gate は廃止しない。役割が「事前承認」から
  「**事後の誠実な採点**（scorekeeper）」と「**リスク上限・執行規律のコードによる強制**
  （risk enforcer）」に変わる。
- 本改定は research phase の再開ではない。研究トラック（多重検定台帳・escalation 則・
  unanimous 合格基準）は CLOSED_OUT のまま独立に維持する。

---

## 3. 新ステータス: `OPERATOR_SELECTED_UNPROVEN`

[HYPOTHESIS_REGISTRY_NO_POST.md](HYPOTHESIS_REGISTRY_NO_POST.md) の状態凡例に以下を追加する
（operator 承認後に registry を更新）。

- **OPERATOR_SELECTED_UNPROVEN**: operator が自らの判断とリスク所有の下で実践投入を選定した仮説。
  **標準 gate の合格を意味しない。** `VALIDATED` とは永久に区別され、いかなる時点でも
  相互に変換されない。多重検定 null にはカウントしない（研究トラック外のため）。

### 3-1. 選定の規則

- registry 上のどの状態（REJECTED / FROZEN_UNEXECUTED / DEFERRED / 新規）からでも選定できる。
  ただし **REJECTED からの選定**は、登録簿に `selected_despite_rejected=true` と
  棄却証拠へのリンクを必須で記載する（計測済み非 robust の事実を隠さない）。
- 選定は operator の明示的な記名判断のみで成立する。エージェントは選定を提案できるが
  代行できない。
- 同時に `OPERATOR_SELECTED_UNPROVEN` 状態を持てる仮説は **最大1件**（初期値。review window で変更可）。

### 3-2. ラベルと権限の分離（意味漂流の防止）

- `OPERATOR_SELECTED_UNPROVEN` はラベルであり、**いかなる実行権限も与えない**。
- 実行権限は常に `stage 資格 ∧ 予算残 ∧ risk gate 通過 ∧ kill=off ∧
  （Stage 2 では per-trade operator confirmation）` の合成でのみ発生する。
- レポート・summary・briefing は本仮説を常に `UNPROVEN` として表示し、
  `performance_proof_status=false` の明記を省略しない。ツールの出力が operator の確信を
  証拠らしく見せた時点で本方針は失敗である。

---

## 4. 仮説レベル規律（非交渉・コードで強制）

選定仮説は稼働開始前に以下を**凍結登録**しなければならない。未登録項目が1つでもあれば
どの Stage も開始できない。

| 項目 | 内容 |
|---|---|
| 凍結スペック | entry/exit 条件・サイズ・対象ペア・時間枠・取引可能時間帯（スプレッド提示時間 9:00〜翌5:00 JST 内）・想定頻度。`config_hash` で同一性を固定 |
| 予算（実験の価格） | 月間最大損失・1日最大損失・1トレード最大損失（サイズ×SL で構造的に上界）・最大連敗停止・最大トレード数/日。**数値は operator が記入**（§8）。コード内定数とし実行時変更不可 |
| 停止基準（反証可能性） | 「何が起きたらこの仮説を止めるか」を事前登録（例: 予算到達 / 連敗 N / 稼働 M 週での採点結果）。停止基準のない仮説は登録不可 |
| 変更禁止 | 稼働中のスペック・予算・停止基準の変更は禁止。変更は review window でのみ可能で、変更後は新 `config_hash` として再登録（=別実験として採点） |
| 増額禁止 | 勝ってもサイズ・予算を上げない。負けても条件を変えない |
| 予算再装填 | 予算到達→自動停止→post-mortem 必須→冷却期間（**最低2週間**）→review window 承認→スペック不変更の確認→新予算。**同月内の再装填は禁止**（コードで強制） |
| 誠実な採点 | 稼働結果は既存の hardened framework（スリッページ込み・コストストレス・random 対照）で定期採点し、safe aggregate のみ記録。採点結果が良くても `VALIDATED` へは昇格しない（研究トラックの標準 gate を別途通過した場合のみ） |

---

## 5. Stage 定義と昇格条件

### Stage 1 — Paper 自動サイクル（方針変更不要・即時開始可）

- 選定仮説を既存の paper auto-cycle runner（fake-transport-only）＋ signal engine ＋
  scorekeeper で回す。実 POST・broker read・credential 一切なし。
- **昇格条件（Stage 1 → 2）**: 連続 **2週間以上** かつ **20 paper トレード以上** の稼働で、
  (a) 執行規律違反 0 件、(b) 予算・停止基準ロジックの発火テスト各1回以上成功、
  (c) 採点レポートが誠実ラベル（UNPROVEN 明記）で生成できること。
  ※ 損益の良否は昇格条件に**含めない**（含めた瞬間に小標本ノイズの選別になる）。

### Stage 2 — 監督付き半自動 live（per-trade confirmation 維持）

- エンジンが判断を生成し、**発注は既存 Step 6G 機構（AGENTS.md 限定例外）による
  operator current-turn confirmation 付き one-shot** で行う。1 POST ずつ、
  no retry / no repost / no second POST、公式 settlement route のみ。
- per-trade 承認のタイムラグは仮説頻度に依存する。**低頻度仮説（H1〜日次）を推奨** —
  M5 系に系統的 edge がないという自らの検証結果と整合し、承認除去の必要性自体を下げる。
- 予算・停止基準・kill は Stage 2 から実効（エンジン側で強制。operator 承認は
  予算を上書きできない）。
- **昇格条件（Stage 2 → 3）**: (a) **4週間以上** かつ **10 live トレード以上** を
  規律違反 0・reconcile 不一致 0 で完走、(b) unknown-result / timeout の処理パスを
  実発生または注入で 1 回以上正しく処理、(c) [API能力表](API_CAPABILITY_SHEET_SANITIZED_NO_POST.md)
  の記入完了（特に **entry への server-side SL/TP 付帯可否**）、(d) 監視・通知経路と
  dead-man 相当の運用定義、(e) 常駐実行の運用方針（稼働時間帯・マシン稼働）確定、
  (f) Stage 3 用の別紙方針 Step の operator 承認。

### Stage 3 — per-trade confirmation の除去（将来・別方針 Step）

- **本書は Stage 3 を許可しない。** per-trade confirmation の除去は、docs の既定通り
  「コードではなく明示的な方針 Step でのみ」行う。AGENTS.md の限定例外の改定を伴う。
- 前提条件（本書時点の予告）: server-side SL による損失有界性（API 能力に条件付き。
  「無」の場合 Stage 3 のハードルは大幅に上がる）、予算・kill・dead-man のコード強制、
  Stage 2 実績、boot 時 reconcile-first、intent journal。
- E1 14日キャンペーンゲートは **Stage 3（無人自動化）資格専用**に再スコープする（§6）。

---

## 6. 既存ゲート・文書のスコープ変更

| 対象 | 変更 |
|---|---|
| E1 shadow gate（14暦日・10スロット等） | **無人自動化（Stage 3+）資格専用**に再スコープ。Stage 1 / Stage 2 は E1 gate 通過を要求しない。E1 の formal stage 表記（`E1_IMPLEMENTED_NOT_GATE_PASSED`）は変更しない |
| E1 Evidence Acceptance Charter（未コミット実装 約4,200行を含む） | **スコープ過剰と判定。** operator は次のいずれかを選択する: (a) 簡素化して完了・コミット（外部シール/ハッシュ連鎖レジストリ等を Stage 3 前提の最小要件まで縮小）、(b) 破棄（`git checkout/clean` で作業ツリーを HEAD に戻す）。**推奨は (b)**（サンクコストであり、Stage 3 到達時に必要最小限を再設計する方が安い） |
| HYPOTHESIS_REGISTRY | 状態凡例に `OPERATOR_SELECTED_UNPROVEN` を追加。研究トラックの escalation 則・多重検定台帳は不変（本状態はカウント外） |
| 標準 gate（hardened evaluation） | 廃止しない。役割を事後採点（scorekeeper）に変更 |
| INTEGRATED_ENGINE_STRATEGY_STATE / PROJECT_STATUS | 承認後、本改定の反映を1節追記 |

---

## 7. 本改定で変わらないもの（安全不変条件）

- one-shot 執行 / no retry / no repost / no second POST
- 公式 settlement route のみ（generic close / generic opposite close は実装非搭載のまま）
- sealed credential（値の表示・ログ・コミット禁止）/ raw request/response/ID/price/PnL 非露出
- `ENTRY_BUY` / `ENTRY_SELL` / `HOLD` / actual-POST 承認 / manual close は operator 専有ラベル・行為
- AGENTS.md「Step 6G Controlled one-shot POST 限定例外」の適用範囲と停止条件
- blocked pre-POST gate は同一 Step 内の再試行・再読取を許可しない
- `performance_proof_status=false` / `live_ready=false` / `unattended_live_supported=false`
  の表明（Stage 2 完走もこれらを true にしない）
- 常駐プロセス・cron 等の無人実行の禁止（Stage 3 方針 Step まで）

---

## 8. Operator 記入欄（承認時に確定させる項目）

2026-07-10 operator 確認済み。operator はH-11を選定した。ただしH-11は
`SELECTED_SPEC_PENDING`で、凍結仕様、`config_hash`、formal testが未確定である。
この選定は実装・paper・live・POST権限を付与しない。

```text
approval:
  status_change_to_ACTIVE: [x] yes / [ ] no
  approved_at (JST): 2026-07-10 21:28
selected_hypothesis:
  registry_id_or_new:            H-11_REGIME_ADAPTIVE_MOE_DIRECTIONAL_PROBABILITY
  selected_at:                   2026-07-10
  registry_status:               OPERATOR_SELECTED_UNPROVEN
  specification_substatus:       SELECTED_SPEC_PENDING
  selected_despite_rejected:     false
  related_rejected_evidence:     H-01 / H-02 / H-03 / H-05
  frozen_spec_doc:               NOT_YET_FROZEN
  selected_spec_draft:           STRATEGY_REGIME_ADAPTIVE_MOE_PREREGISTRATION_NO_POST_20260710.md
  staged_live_policy_draft:      REGIME_ADAPTIVE_MOE_STAGED_LIVE_POLICY_NO_POST_20260710.md
  frozen_spec:                   false
  config_hash:                   NOT_ASSIGNED
  formal_test:                   NOT_RESERVED
  current_stage:                 PRE_STAGE1_SPEC_INCOMPLETE
  execution_permission:          false
budget (円建て・sanitizedのまま記入可):
  monthly_max_loss:              50,000
  daily_max_loss:                10,000
  per_trade_max_loss_bound:      5,000   # サイズ×SLの構造上界
  max_consecutive_losses_stop:   5
  max_trades_per_day:            1
stop_criteria:                   # 反証条件（下記3条件のいずれか成立で自動停止＋post-mortem必須）
  - 予算到達（月間 or 連敗上限）。コード強制・即停止
  - Stage 2→3 レビュー時点で hardened framework 採点が REJECTED 相当
    （コストストレス負け or 符号置換 p90 未達）なら継続不可
  - 予算再装填 累計3回で改善傾向なしなら強制終了 → 状態 EXHAUSTED（registry に凡例追加）。
    同一 config_hash での再選定は永久不可（別実験として再登録のみ可）
evidence_charter_disposition:    # [ ] (a)簡素化して完了 / [x] (b)破棄（推奨）
api_capability_sheet:            未記入（Stage 2 着手前までに operator が記入。Stage 2 昇格の前提条件）
```

**注記（H-11選定後も残る条件）**:

- Stage 1 の配線・実稼働（`STAGE1_PAPER_WIRING_STEP`を含む）は §4 によりH-11の全未決定項目、
  凍結登録、`config_hash`確定が完了し、別Stepで明示授権されるまで**着手不可**。
- 上記予算・停止基準の数値はH-11仕様確定前に記入したものであり、spec freeze時に
  凍結スペック（時間枠・想定頻度）と整合するか**再確認する**。改定が必要な場合は
  review window で行い、新 `config_hash` として登録する（§4 変更禁止則に整合）。
- 将来live方針は`CONDITIONAL_STAGE2_SUPERVISED_LIVE`であり、現在のlive permissionではない。
  完成したfrozen spec→別授権のStage 1配線→2週間以上・20 paper trades以上と§5条件→operator review→
  別Stage 2 procedure→別major-incident resume policy→各Step 6G current-turn confirmationの順を全て要求する。
- H-11選定はresearch phaseを再開せず、`CLOSED_OUT`、多重検定台帳、escalation則を変更しない。

---

## 9. 承認後の実装 Step 候補（本書は着手を許可しない）

1. `POLICY_ACTIVATION_STEP`: 本書 Status を ACTIVE 化、registry 凡例追加、
   INTEGRATED/PROJECT_STATUS への反映、Evidence Charter 処置の実行（ツリーを clean に戻す）
2. `STAGE1_PAPER_WIRING_STEP`: 選定仮説の凍結登録＋既存 paper runner への配線＋予算/停止ロジックの発火テスト
3. `STAGE2_SUPERVISED_LIVE_PROCEDURE_STEP`: Step 6G 機構を用いた半自動 live 運用手順の確定
   （Stage 2 の各 POST は従来通り operator 依頼の Step 6G 実行としてのみ発生する）

いずれも no-POST の準備 Step であり、実 POST は従来通り Step 6G の gate 全通過時のみ・最大1回。

---

## 10. 2026-07-11 H-11 v3 accelerated observed-live amendment

Operatorは、[H-11 v3方針](H11_V3_OBSERVED_UNATTENDED_LIVE_POLICY_NO_POST_20260711.md)と
[v3凍結仕様](STRATEGY_H11_V3_IFDOCO_SPEC_FREEZE_NO_POST_20260711.md)を採用した。
本節はH-11 v3に限り、§5〜§7の旧stage順序より後発の限定改定として扱う。

- 収益性の事前検証期間（Stage 1の2週間/20 paper trades、Stage 2の4週間/10 live trades、
  E1 14日gate）はactual live開始のpermission条件から外し、live中のscorekeeperへ移す。
- operatorの目視は必須の安全補助だがper-trade execution gateではない。
- actual activation後のH-11 v3はautomatic entry / broker-side OCO / reconciliation /
  timeout settlementを目標とする。
- 二重attempt防止、unknown halt、server-side損失限定、boot reconcile-first、sealed credential、
  budget/kill/dead-manはlive前の非交渉条件として残す。
- H-11 v3は`OPERATOR_SELECTED_UNPROVEN`であり、`VALIDATED`へ昇格しない。
- `E1_IMPLEMENTED_NOT_GATE_PASSED`と`performance_proof_status=false`は変更しない。

今回のoperator授権は方針docs、v3 spec、pure IFDOCO builder、persistent safe state、fake lifecycle、
testsまでである。actual transport binding、AGENTS.mdのactual自動POST例外、credential/env、Private API、
broker read、actual POST、常駐/cron、commit/pushは別`H11_V3_ACTUAL_ACTIVATION_STEP`まで未許可。

```text
h11_v3_config_hash=sha256:737765dcbed89befceef8660d2b362c834344cc7e36e139d2ff75984914c3262
current_stage=V3_BUILD_NO_POST
actual_post=false
post_count=0
live_ready=false
unattended_live_supported=false
```
