# Research Platform Productization（再利用可能な研究基盤の整理）— no-POST・2026-07-09

Step: `RESEARCH_PLATFORM_PRODUCTIZATION_NO_POST`

**目的: adaptive alpha engine や confidence 付き signal preview を作ることではない。これまで構築した
評価・安全・統治・記録の基盤を、将来の任意仮説/データに"正直に"適用できる再利用可能 research platform
として整理・索引化する。docs のみ（実装・取得・backtest 再実行・live 実行なし）。
raw price/spread/PnL/CSV row/ID/credential は扱わない。
performance_proof_status=false / live_ready=false / unattended_live_supported=false（維持）。**

## 0. スコープと DEFER 宣言（最重要）

- **本 Step で整理する（productization 対象）**: 評価 gate / false-positive rejection / backtest 基盤 /
  data 取込 / research governance / hypothesis registry / rejected ledger / safe execution template /
  reporting / 記述的 market-state observer の"仕様"（実装は最小）。
- **明示的に DEFER（validated edge が出るまで作らない）**:
  - **prescriptive signal preview（`AUTO_PREVIEW_SIGNAL_BUY/SELL`）**
  - **confidence / uncertainty スコア**
  - **live research budget（実弾）**
  - **auto-trade / unattended full-auto**
  - **market-regime を"live 判断入力"にすること**（regime は研究ラベル用途のみ）
  理由: validated edge が無い所での confidence は「ノイズへの確信」＝誤誘導・裁量化・HARKing の温床。
  校正には測れる outcome を持つ検証済み signal が要る。→ 作らないことが最善の対策。
- 有効化するには **(i) validated edge の獲得（本 gate 合格）＋(ii) operator の明示承認** の両方が必要。

## 1. プラットフォーム構成（durable assets・索引）

各 component は「何か / どこ（module・doc） / 再利用の仕方」。すべて **no broker/network/credential・
safe-aggregate のみ**。

### 1.1 評価 gate（HARDENED・中核資産）
- **何**: 偽 edge を再現的に却下する厳格評価。walk-forward/rolling OOS・**2.0×cost stress**・slippage・
  **leg 別 spread**・**sign-permutation p90**・multi-seed random・**multi-resolution unanimous**・
  **minimum sample**・cumulative trial budget・**post-OOS retuning 禁止**。
- **どこ**: `backend/app/services/gmo_strategy_evaluation_hardening.py`
  （`StandardEvaluationGate` / `evaluate_under_standard_gate` / `sign_permutation_median_pf_percentile` /
  `run_walk_forward_for_*`）。gotobi 型は `gmo_strategy_gotobi.py`（`evaluate_gotobi_effect`：非対照/曜日層化置換/Nブロック）。
  docs: `STRATEGY_EVALUATION_HARDENING_NO_POST_20260708.md` / `STRATEGY_GATE_CORRECTION_AND_SESSION_HYPOTHESIS_NO_POST_20260708.md`。
- **再利用**: 新候補は runbook §1 手順で `evaluate_under_standard_gate(...)` に渡すだけ（timeframe 別に
  `window_bars_resolutions`/`lead` を override 可）。

### 1.2 false-positive rejection framework
- **何**: 小標本の"見かけの好成績"を却下する仕組み（例: gotobi 16件 PF高→166件で PF≈1.00 へ収束を検出）。
- **どこ**: 上記 gate の minimum-sample＋sign-permutation＋multi-resolution。
- **再利用**: 「良さそう」を出したら必ず本 framework を通す（単一指標超えでは合格にしない）。

### 1.3 backtest 基盤
- **何**: 決定論的 backtest（engine / metrics / report / dataset）。
- **どこ**: `gmo_strategy_backtest_{engine,metrics,report,dataset}.py` / `gmo_strategy_redesign.py`
  （families・ATR exit・**vol_regime_mode（研究ラベル）**・sign-permutation override）。

### 1.4 historical data 取込（local-file-only）
- **何**: repo 外 CSV を検証・取込（BID+ASK→spread・forbidden 列拒否・no fetch）。
- **どこ**: `gmo_historical_data_import_adapter.py`（`import_historical_csv`）。
- **注意**: dataset は `__bool__=False`。存在判定は `if ds is not None:`。

### 1.5 公開 GET client（承認取得時のみ・no-credential）
- **何**: GMO 公開 klines（認証なし）。取得は **operator 承認の別 Step**。
- **どこ**: `app/shadow/gmo_public.py`。※当 sandbox は GMO host のみ到達可（外部 host は operator 提供 CSV）。

### 1.6 safe execution template（one-POST safety gate）
- **何**: operator-gated 実行の型。**default-deny hard guard**・**max one POST / no retry / no repost**・
  operator current-turn confirmation・**official settlement route 分離**・raw/ID/value 非露出。
- **どこ**: hard guard `app.security.real_broker_post_hard_guard.assert_real_broker_post_allowed(*, allow)`
  （既定 deny）。実行系は `app/live_verification/` 配下（**POST 可能・default-deny 封印**。詳細と
  【重大インシデント記録】は `CODEX_HANDOFF.md` 冒頭を必ず参照）。
- **再利用**: 将来 live が許される場合の**唯一の実行テンプレート**。無人化・retry・repost は不可（不変則）。

### 1.7 research governance
- **何**: pre-registration・多重検定台帳・freeze/review window・**post-OOS retuning 禁止**・
  escalation（pre-registered null が K=3 連続で closeout）・mechanism-first（data-dredging 禁止）。
- **どこ**: `RESEARCH_RUNBOOK_NO_POST.md`（§6b mechanism-first 含む）/ 各 pre-registration doc。

### 1.8 hypothesis registry / rejected ledger
- **どこ**: `HYPOTHESIS_REGISTRY_NO_POST.md`（本 Step で新設）/ `RESEARCH_PLATFORM_CLOSEOUT_AND_STATUS_RECORD_NO_POST_20260709.md`。

### 1.9 reporting（safe-aggregate only）
- **何**: PF/win_rate/pass 率/sign ラベル/safe count/verdict のみ。raw 値・ID・credential を出さない。
- **どこ**: `gmo_strategy_backtest_report.py` + 各 doc の記法。

### 1.10 記述的 market-state observer（仕様のみ・prescriptive 非提供）
- **何**: 市場状態の**記述**（trend/range・vol カテゴリ・spread カテゴリ・session・event 近接）と
  **NO_ACTION 層**（uncertainty 高・regime 不明・spread 異常・event 近接→強制 NO_ACTION）。
- **境界**: **BUY/SELL は出さない・permission でない・regime を live 入力にしない**（研究ラベル用途）。
  prescriptive preview/confidence は §0 の通り DEFER。

## 2. 自律境界（productization 後も不変）

- **AI 自律可**: 市場状態の記述分類・NO_ACTION 判定・registry/ledger 更新・**backtest 専用 gate 実行**・
  記録・safe-aggregate reporting。
- **operator confirmation 必須**: **あらゆる live POST（max one・no retry・no repost）** / パラメータ・ルール更新 /
  データ取得（public GET）/ サイズ・予算変更 / **DEFER 層（preview/confidence/live）の有効化そのもの**。
- **ENTRY_BUY/ENTRY_SELL/HOLD は operator safe label のまま**。AI は当面 **AUTO_PREVIEW_SIGNAL を出さず**、
  記述と NO_ACTION まで。AI に ENTRY 代行判断はさせない。

## 3. 現状ステータス（維持）

- research_phase: **CLOSED_OUT**（productization は探索再開ではない）
- current_strategy_status: **NO_ROBUST_EDGE_FOUND_IN_TESTED_SCOPE**
- performance_proof_status=false / live_ready=false / unattended_live_supported=false /
  unattended_full_auto_completed=false（すべて不変）
- evaluation_framework_status: **HARDENED**

## 4. 再開・再利用の入口

- 研究再開: `RESEARCH_RUNBOOK_NO_POST.md`（mechanism-first → 承認データ → 標準 gate で1回採点）。
- 仮説状況: `HYPOTHESIS_REGISTRY_NO_POST.md`。
- 現在地: `PROJECT_STATUS.md` / `CODEX_HANDOFF.md` 冒頭。
- **DEFER 層を有効化する場合**: validated edge（gate 合格）＋operator 承認の両方を先に満たすこと。
