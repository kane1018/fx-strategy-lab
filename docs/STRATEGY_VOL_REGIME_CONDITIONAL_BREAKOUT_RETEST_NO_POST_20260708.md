# VOL_REGIME_CONDITIONAL_BREAKOUT 再検定: NOT_ROBUST（no-POST・2026-07-08）

Step: `VOL_REGIME_CONDITIONAL_BREAKOUT_RETEST_NO_POST`
基準: [STRATEGY_HYPOTHESIS_INVENTORY_AND_PREREGISTRATION_NO_POST_20260708.md](STRATEGY_HYPOTHESIS_INVENTORY_AND_PREREGISTRATION_NO_POST_20260708.md)（凍結契約 §3）

**重要: performance proof でも live 許可でもない（performance_proof_status=false / live_ready=false）。
raw price/spread/PnL/CSV row/ID は扱わない。凍結ルールに対し **1回だけ採点**し、post-OOS retuning は
していない。合格しても解錠は paper-forward 検討のみ・「勝てる/収益性/edge証明」は断定しない。**

## 1. 採点対象（無取得・既存 local CSV）

- 実装（既 commit の凍結コード）: 既存 redesign runner に **vol-regime entry gate** を追加。
  `_high_vol_regime_flags` = ATR(14) が「直前200barの ATR 中央値」を上回る bar のみ high-vol
  （lookaheadなし・履歴不足はfail-closed）。candidate = **BREAKOUT × EXIT_RIDE × HIGH**（単一variant・スキャンなし）。
- primary = 既存 USD_JPY **M5 2.7年（198,129 bars）**、secondary(参照) = H1（7,828 bars）。
- gate = 明文化済み標準 multi-resolution（cost 2.0×・slippage 0.5pip/side・leg別spread・sign-permutation p90・
  min_qualified_windows 4）。M5 は window_bars=(12000,16800)・lead=250（regime 200 を包含）。

## 2. 結果（safe aggregate）

### M5（2.7年・primary）: **NO_ROBUST_EDGE**
| resolution | 窓 | median PF | base_pass | stress2x_pass | signperm_p90 | beats_dir | robust_here |
|---|---|---|---|---|---|---|---|
| wb=12000 | 12 | **0.772** | 0.0 | 0.0 | 0.779 | False | False |
| wb=16800 | 11 | **0.700** | 0.0 | 0.0 | 0.749 | False | False |
- robust_all=False → **NO_ROBUST_EDGE_ACROSS_RESOLUTIONS_COST_STRESS_AND_SIGN_PERMUTATION**
- **全窓で base_pass=0.0**（高volbreakoutは全窓で負け）。

### regime control（full-period・base cost + 0.5pip/side・PFは safe ratio）
| tf | OFF(無条件) | HIGH(高vol) | LOW(低vol) |
|---|---|---|---|
| M5 | PF 0.704 (9,087) | **PF 0.709 (5,740)** | PF 0.667 (4,163) |
| H1 | PF 0.799 (398) | **PF 0.936 (200)** | PF 0.673 (244) |
- **文献の"高volでbreakout改善"は方向として確認**: HIGH は OFF/LOW を上回る（H1で 0.80→0.94 と明瞭・M5では 0.70→0.71 と僅少）。
- だが**いずれも PF<1（赤字）**。改善は edge に届かない。

### H1（参照）: NOT_ROBUST
- wb=1000: median PF 0.926 / base_pass 0.43 / signperm_p90 0.979 / beats_dir False
- wb=1400: median PF 0.945 / signperm_p90 1.054 / beats_dir False
- robust_all=False。H1 では高vol化で改善するが、**符号置換に負け・2.0×コスト非生存・非unanimous**。

## 3. 解釈（正直に）

- **VOL_REGIME_CONDITIONAL_BREAKOUT は M5(primary)・H1(参照)とも NOT_ROBUST → 棄却。**
- **"grain of truth" は確認**: 高volレジーム条件付けは breakout の PF を改善する（documented効果と整合）。
  しかし **改善量が不足**（PF<1のまま・符号置換 p90 に届かず=方向優位なし・2.0×コストで消滅）。
- **M5(十分標本 5,740 高vol trade)では改善が僅少(0.70→0.71)で深く赤字** → 条件付けは breakout を救済しない。
- 本Stepの価値: 「documented効果を a priori 単一定義で事前登録し、十分標本で正直に棄却」。
  regime定義の後出しスキャン(overfit)を避けた。

## 4. status・多重検定台帳・エスカレーション

- status: **VOL_REGIME_CONDITIONAL_BREAKOUT_REJECTED**（NOT_ROBUST・棄却）。
- program 台帳: pre-registered 新仮説の **null #1 / 3**（契約 §5: さらに K=3 連続 NOT_ROBUST で
  `RESEARCH_PLATFORM_CLOSEOUT` へ移行）。**残り 2 件**。
- post-OOS retuning なし（regime lookback/閾値/family/exit の後出し変更禁止）。
- performance_proof_status=false / live_ready=false（不変）。取得なし・raw値/CSV commitなし・
  コードは既 commit の凍結版で採点。

## 5. recommended next（提示のみ）
- 残 candidate longlist はデータ壁/標本過少で near-term 困難（三角RV=mirage・月末=標本過少・
  cross-asset/event=外部データ）。**新規に低コストで試せる pre-registered 仮説は枯渇しつつある**。
- 候補: (a) longlist の Tier2 を進めるには **operator 承認の外部/別ペアデータ**が前提、
  (b) もしくは **`RESEARCH_PLATFORM_CLOSEOUT`（D）** に前倒しし「tested scope で robust edge 不在」を
  正式記録し基盤・runbook を固める（残り null 2件を待たずとも、operator 判断で選択可）。
- live 移行は robust edge 不在のため不可（不変）。
