# CROSS_ASSET_RATES_LEADLAG 事前登録（mechanism-first・凍結）— no-POST・2026-07-09

Step: `CROSS_ASSET_RATES_LEADLAG_PREREGISTRATION_NO_POST`
親: [RESEARCH_RUNBOOK_NO_POST.md](RESEARCH_RUNBOOK_NO_POST.md) §6b（mechanism-first / data-dredging 禁止）

**本書は「契約」。docs のみ（実装・取得・backtest 再実行なし）。データを見る前に機構と発動条件を
凍結し、その機構が"要求する"データを明示する（データ都合で仮説を選ばない）。
raw price/spread/PnL/CSV row/ID/credential は扱わない。performance_proof_status=false /
live_ready=false。合格しても解錠は paper-forward 検討のみ。「勝てる/収益性/edge証明」は断定しない。**

## 0. なぜこの仮説か（機構主導・data-dredging 回避）

- 選定基準は **a-priori 機構の強さ**であって、データの入手容易さではない。
- USD/JPY は**日米金利差とリスク選好の従属変数**（最も確立した経済的ドライバ）。→ 「取れる FX ペアで何か探す」
  より、**金利という真のドライバの lead-lag** を検証する方が筋が良い。
- 入手容易だが弱機構の代替（追加FXペアの relative-value 等）には**流れない**。要求データが揃わなければ
  closeout を維持する（§8）。

## 1. 機構仮説（動機であり証明対象ではない）

- **機構**: 米金利（US 2y/10y 利回り、または rate-futures proxy）の日中変化が **USD/JPY に先行**し、
  USD/JPY は数分の遅れで**同方向**に追随しやすい（金利差の織り込みラグ・裁定の有限速度）。
- **検証する**: 「直前 k bar の米金利変化の符号」が、その後 h bar の USD/JPY リターンの符号/コスト後収益を
  **予測するか**（lag=予測性。contemporaneous な同時共変動ではない）。
- **検証しない/断定しない**: 因果の証明、任意 latency での成立、live 化。陽性=「本条件下で lead-lag と整合し robust」まで。

## 2. 要求データ（この機構が"要求する"もの・データ都合で選ばない）

- **US 金利系列**: US 2y および/または 10y Treasury 利回り（または liquid rate-futures proxy）。
  **日中・M5 以下・UTC 時刻整合**、既存 USD/JPY M5（2023-11-01〜2026-07-07）と**重なる期間**で。
- **入手方針（no-credential 厳守）**: **operator が local CSV で提供**する（FX CSV と同様 repo 外・非commit・
  raw非公開）か、**認証不要の公開ソースを明示承認**する場合のみ。**私は credentialed ソースを取得しない。**
- **品質要件**: USD/JPY M5 と同一タイムスタンプ格子への整合、欠損/祝日の扱い明記、**lookahead 厳禁**
  （signal は必ず「決済判断時刻までに確定した過去 bar」のみ）。
- ※ DXY を proxy にする場合の注意: DXY は JPY を含むため USD/JPY 予測に**部分循環**。使うなら JPY を除いた
  USD 指数か、金利そのものを優先（本契約は金利を primary とする）。

## 3. 固定ルール（単一 a-priori variant・スキャン禁止）

- signal = **直前 k=3 bar（15分）の米金利変化の符号**（up→USD/JPY long / down→short）。
- entry = signal 確定 bar の USD/JPY 終値、exit = **h=3 bar（15分）後の終値**（固定 horizon・TP/SL なし）。
- entry/exit の時刻整合は §2 の格子で決定的に。**k・h・方向規則は事前登録で固定**（グリッド/最適化しない）。
- gating: 既存 spread-within / session-allowed を踏襲。

## 4. 約定・コスト

- **USD/JPY 単一取引（1 spread）**。金利系列は**シグナル専用**（取引しない）→ triangular のような
  多leg コストは発生しない。
- **leg 別 crossing-side spread + slippage 0.5pip/side + 2.0×cost stress**（標準gate）。

## 5. 対照群（primary・unanimous）

1. コスト込み収益方向: PF>1 かつ期待値符号 NON_NEGATIVE @2.0×。
2. **lead-lag placebo**: 米金利系列を**時間反転／シャッフル**すると予測性が**消える**こと
   （spurious な同時相関でないことの検定）。
3. **contemporaneous 対照**: lag=0（同時）では取引不能 → **lag>0 の予測性**が本質であることを示す。
4. **sign-permutation p90**（方向優位）。
5. **multi-resolution walk-forward**（M5 用 window_bars・lead 分を包含）で全解像度 unanimous・3ブロック安定。

## 6. 最小標本・合格基準

- 高頻度シグナルのため trade 数は多いが、**各 window の min trades / min qualifying windows** を満たすこと。
- 合格 = `RETEST_PASSED_CANDIDATE_FOR_PAPER_FORWARD`（§5 全成立 + 最小標本 + post-OOS retuning なし）。
  合格でも perf_proof/live は false。失敗 = `NOT_ROBUST` / `INSUFFICIENT`。

## 7. 多重検定

- 本仮説 = **trial 1件**（k=3/h=3/金利符号・単一 variant）。program 台帳へ +1（**pre-registered null #2/3** 相当）。
- k/h/proxy のスキャン禁止・post-OOS retuning 禁止。

## 8. status と operator ゲート

- 現 status: **BLOCKED_PENDING_OPERATOR_PROVIDED_RATE_DATA**。
- operator 決定（次の1点）:
  - **(可) US 2y/10y 利回り（or rate-futures proxy）の日中 M5 整合 CSV を提供／認証不要ソースを承認**
    → 実装（signal 生成＋既存 runner 再利用）→ 標準gateで **1回採点**。
  - **(不可) 入手できない** → **§6b により、弱機構×易データの代替に流れず closeout を維持**
    （安易な FX-only 仮説に作り替えない）。
- live 移行は robust edge 確認まで不可（不変）。

## 9. Sources（safe・literature）
[NBER w26706 Execution Risk and Arbitrage in FX (PDF)](https://www.nber.org/system/files/working_papers/w26706/w26706.pdf) ほか
（USD/JPY の金利差ドライバ・裁定の有限速度に関する一般的知見。過去効果は減衰前提で「検証候補」として扱う）。
