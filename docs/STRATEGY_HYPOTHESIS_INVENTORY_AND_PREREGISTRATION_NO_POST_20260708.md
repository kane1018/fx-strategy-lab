# 仮説インベントリ + 事前登録（凍結）— no-POST・2026-07-08

Step: `STRATEGY_HYPOTHESIS_INVENTORY_AND_PREREGISTRATION_NO_POST`

**本書は「棄却済み仮説の台帳」＋「次に検証する候補の事前登録契約」。docs のみ
（コード変更・取得・public GET・backtest 再実行なし）。raw price/spread/PnL/CSV row/ID は扱わない。
performance_proof_status=false / live_ready=false。合格しても解錠は paper-forward 検討のみ・
「勝てる/収益性/edge証明」は断定しない。**

## 0. 目的と freeze 宣言

- 4件連続の厳密棄却を受け、(a) 何をどの scope で棄却したかを台帳化し、(b) 次候補を**少数**に絞って
  **データ要件・評価gate・多重検定予算・最小標本を取得前に凍結**する。
- 以後の retest は本書を参照し、条件を後から変更しない（post-OOS retuning 禁止）。

## 1. 検証済み棄却インベントリ（safe aggregate）

| 仮説 | scope | status | 主因（safe） |
|---|---|---|---|
| M5 technical 4family×2exit | M5 | REJECTED_NO_ROBUST_EDGE | 全候補 NOT_ROBUST（コスト後 edge なし） |
| H1 trend continuation / ride | H1 15ヶ月 | REJECTED_NOT_ROBUST_UNDER_EXECUTION_FRICTION | 0.5pip/side でbreakeven化・多解像度不一致 |
| SESSION_MOMENTUM | H1 | REJECTED_DIRECTION_RULE_NOT_BEATING_SIGN_PERMUTATION | 方向ルールが符号置換p90に負け・非unanimous |
| GOTOBI_FIX_DRIFT | M5 2.7年・166件 | REJECTED_ON_MULTI_YEAR_M5 | PF≈1.00・2.0×コスト負・符号置換負け・非持続 |
| **current_strategy_status** | — | **NO_ROBUST_EDGE_FOUND_IN_TESTED_SCOPE** | tested scope の限定（全域否定ではない） |

- 共通教訓: **USD/JPY メジャーの単純・単一・方向性ルールは、現実的コスト後に robust edge を示さない**
  （効率的・裁定済み市場での予想通りの結果）。評価基盤(multi-resolution/sign-permutation/leg別spread/
  最小標本/多重検定台帳)は**強化済み＝本プロジェクトの持続的資産**。

## 2. 候補 longlist（tier 付き・literature 反映）

| # | 候補 | tier | prior | 近接可否 | 主障壁 |
|---|---|---|---|---|---|
| ① | VOL_REGIME_CONDITIONAL_BREAKOUT | **1** | 中 | **可（既存データ）** | overfit（regime定義の後出し） |
| ② | FX_RELATIVE_VALUE_TRIANGULAR | 2 | **低** | 否 | 3-legコスト（文献: 小口三角裁定は"mirage"）＋他ペア取得要 |
| ③ | MONTH_END_FIX_REBALANCING | 2 | 中 | 否 | 標本過少(≈12/年)＋方向に株式データ要 |
| ④ | CROSS_ASSET_RATES_LEADLAG | 2 | 中 | 否 | 先導資産(米金利/DXY)データが別源 |
| ⑤ | EVENT_DRIFT(BOJ/FOMC/NFP/CPI) | 3 | 低 | 否 | 方向driftは2015後減衰・確実なのは非方向vol・カレンダー要 |

- **research 反映**: 三角裁定は「小口・現実コストで不成立が通説（三spread同時・"mirage"）」→ ②は prior 低に降格。
  vol-regime条件付けは「高volで trend-following が改善する documented 支持あり／ただし regime手法は
  overfit・非頑健」→ ①は **単一の a priori 定義に固定**することを条件に採用。

## 3. 近接 actionable 事前登録: `VOL_REGIME_CONDITIONAL_BREAKOUT`（凍結）

**仮説（動機）**: breakout/trend continuation の順張りは、**高ボラregime限定**でのみコスト後の
方向 edge を持ち得る（低vol/レンジの whipsaw が無条件版の失敗要因という仮説）。機構は「edge の証明」
ではなく a priori な検証対象を絞るための動機。

**固定ルール（単一 variant・スキャン禁止）**:
- base signal = **既存 frozen redesign `BREAKOUT` family × `EXIT_RIDE`（ATR 2.5/1.0・max_hold48・debounce3）**
  （breakout は run に room が要るため ride を a priori 選択）。family も exit も**1つに固定**。
- regime filter = **atr_like(14) が「直前 lookback=200 barsの trailing median」を上回る bar のみ high-vol**。
  entry は high-vol ∧ base breakout signal ∧ 既存 spread-within ∧ session-allowed の時のみ。
  **閾値=trailing median(50%tile)を a priori 固定**（percentile もlookback もスキャンしない・lookaheadなし）。
- その他（decide-at-close・exits・cost）は frozen redesign runner に一致。

**対象データ（無取得・既存 local CSV）**:
- primary = **既存 USD_JPY M5 2023-11-01〜2026-07-07（2.7年・198,129 bars）**
  （本 M5 では breakout signal は未採点＝相対的に fresh）。
- secondary(参照) = 既存 H1（無条件 breakout は棄却済みのため参照のみ）。

**評価 gate = 明文化済み標準gate（multi-resolution）**:
- walk-forward rolling OOS・**cost 2.0× stress**・**slippage 0.5pip/side**・**leg別spread**・
  **sign-permutation p90**（方向優位）・**multi-resolution 窓（M5用に window_bars を再設定: 例 12,000 と
  16,800 bars ≈ 42/58 取引日、両解像度 unanimous）**・min qualifying windows ≥4。
- 追加対照: **high-vol regime vs low-vol regime の breakout 比較**（regime が効いていることの確認）。

**最小標本**: 条件付けで trade は減る。**各窓で min trades を満たす regime のみ qualify**。
未達なら `INSUFFICIENT`。

**verdict ラベル**: `RETEST_PASSED_CANDIDATE_FOR_PAPER_FORWARD` / `NOT_ROBUST` / `INSUFFICIENT`。
合格でも perf_proof/live は false（paper-forward 検討のみ解錠）。

**多重検定**: 本仮説は **trial 1件（BREAKOUT×RIDE×regime=ATR>trailing-median-200）**。§5 台帳に加算。
family/exit/閾値/lookback のスキャンは行わない。

**operator 承認**: **不要（新規取得なし・既存データ）**。次の retest step で実装→1回採点。

## 4. deferred 事前登録: `FX_RELATIVE_VALUE_TRIANGULAR`（契約skeleton・BLOCKED）

- 仮説: EUR/USD×USD/JPY と EUR/JPY の三角残差の平均回帰（非方向）。
- **BLOCKED 理由**: (a) 文献上、小口・現実コストの三角裁定は**成立困難（"mirage"・3 spread 同時）**→ prior 低、
  (b) 他ペア(EUR/USD・EUR/JPY)の GMO public 供給可否が**未確認**（監査済みclientは symbol を素通しのみ）。
- 進める場合の必須固定: 3-leg コスト合算・placebo=残差の時間シフト/シャッフル・非方向用対照・最小標本。
- **operator 承認要**: 他ペア M5 の public GET 取得可否確認（bounded プローブ）＋取得承認。**near-term 非推奨**。

## 5. program 全体 多重検定台帳 + 予算方針

- これまでの trial 概数（family×config ベース）: M5 technical ~8、H1 technical ~8、SESSION ~2、
  GOTOBI ~2（primary+secondary）＝ **累計 ~20 trial**。全て REJECT。
- **予算方針**: 単一 benchmark(p90) は ~20 trial で偶然 pass を生むため、**合格は常に "unanimous 多対照 ×
  multi-resolution"** を要求（単一指標超えでは合格としない）。新仮説ごとに台帳へ +1。
- **エスカレーション則**: pre-registered 新仮説が **さらに K=3 件連続で NOT_ROBUST** なら、探索を停止し
  `RESEARCH_PLATFORM_CLOSEOUT`（D）へ移行して「tested scope で edge 不在」を正式記録する。
- **post-OOS retuning 禁止**（全 step 不変則）。失敗データの条件変え再走は不可。

## 6. 標準 gate 参照

明文化済み（`gmo_strategy_evaluation_hardening.StandardEvaluationGate` / `evaluate_under_standard_gate`）:
slippage 0.5pip/side・cost 2.0×・sign-permutation p90・multi-resolution unanimous・min qualifying windows・
no post-OOS retuning。gotobi 系は `gmo_strategy_gotobi`（leg別spread・末日暦・曜日層化置換・N-block・最小標本）。

## 7. 次 step と承認

- **推奨次 step**: `VOL_REGIME_CONDITIONAL_BREAKOUT_RETEST_NO_POST`
  — §3 の凍結ルールを実装（regime filter 追加）→ 既存 M5(2.7年)＋H1 で標準 multi-resolution gate により
  **1回だけ採点**。**新規取得なし・operator 承認不要**。
- ①(RV) を進めるなら別途、他ペア供給確認＋取得承認（BLOCKED 解除）が前提。
- いずれも paper-forward 以降のみ。live 移行は robust edge 確認まで不可（不変）。

---
**Sources（safe・literature）**: 
[LJMU Volatility Filters for Active Asset Trading (PDF)](https://researchonline.ljmu.ac.uk/id/eprint/5793/1/431316.pdf) /
[SSGA Decoding Market Regimes with ML (PDF)](https://www.ssga.com/library-content/assets/pdf/global/pc/2025/decoding-market-regimes-with-machine-learning.pdf) /
[NBER w26706 Execution Risk and Arbitrage in FX (PDF)](https://www.nber.org/system/files/working_papers/w26706/w26706.pdf) /
[arXiv 0812.0913 The Mirage of Triangular Arbitrage in Spot FX (PDF)](https://arxiv.org/pdf/0812.0913) /
[ScienceDirect Price discovery and triangular arbitrage in currency markets](https://www.sciencedirect.com/science/article/abs/pii/S0261560623001134)
