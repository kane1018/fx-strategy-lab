# Execution-Realism Hardening: H1 candidate REJECTED under slippage（no-POST・2026-07-08）

Step: `STRATEGY_EXECUTION_REALISM_HARDENING_NO_POST`
実装: `gmo_strategy_evaluation_hardening.py`（slippage・2.0×実使用・多seed random）
+ backtest runner 群への後方互換 `slippage_price_per_side`

**重要: performance proof ではない（performance_proof_status=false / live_ready=false）。
raw price/spread/PnL は扱わない。本Stepは「有望に見えた H1 候補が現実的摩擦で消える」ことの
厳密確認であり、edge の否定を証明するものでもない。**

## 1. 背景（Fable5 確認で判明した弱点の是正）

前 H1 hardening は TREND_CONTINUATION×ride を ROBUST 候補とした。だが妥当性確認で:
- verdict の cost stress が **実際は 1.5× までしか使われていなかった**（2.0×は宣言のみ）
- random benchmark が **単一path**（分布でない）
- **スリッページ未モデル化**（fills at exact close/TP/SL・stop gap 無視）
が判明。**median PF が 1.06 と薄い**ため、これらは結論を覆し得る。本Stepで是正・再判定した。

## 2. 実装した是正（no-POST・engine無変更）

- 3 runner（baseline / redesign / random）に後方互換 `slippage_price_per_side`（既定0.0）を追加。
  entry+exit の2側に adverse fill を課す（latency/market impact/stop gap 近似）
- verdict の cost stress を **`max(cost_multipliers)`（=2.0×）** に修正（従来は1.5×止まり）
- random benchmark を **多seed分布（既定30seed）の p90** に修正。
  `beats_random = 候補 median PF > random p90`（単一pathでなく分布の高percentile超え）

## 3. スリッページ感度（H1・winner・base cost 1.0・USD/JPY 1pip=0.01）

| per-side slippage | pass率 | median PF | passed/qualified |
|---|---|---|---|
| 0.0 pip | 0.625 | 1.060 | 5/8 |
| 0.3 pip | 0.625 | 1.024 | 5/8 |
| **0.5 pip** | **0.50** | **1.001** | **4/8** |
| 0.8 pip | 0.375 | 0.968 | 3/8 |

→ **break-even はおよそ 0.5 pip/side**。現実的なリテール slippage（〜0.5 pip）で
median PF は breakeven（≈1.00）へ落ち、robust バー（pass率0.60）を割る。

## 4. 是正後フルバッテリー（slippage 0.5 pip/side・cost stress 2.0×・random p90 30seed）

- baseline base-cost pass率: 0.375
- **全8候補 = NOT_ROBUST_REJECT**（winner: base_pass 0.50 / median PF 1.001 / stress2x pass 0.375）
- any_robust_candidate: **false** / overall: **NO_ROBUST_EDGE_ACROSS_WALK_FORWARD_AND_COST_STRESS**

前回 ROBUST とされた候補は、**現実的 slippage を入れると robust バーを満たさない**。
見かけの優位は execution friction のマージン内だった。

## 5. 結論（正直に）

- **H1 の当該候補は、現実的な約定コスト前提では robust ではない → REJECTED_AS_NOT_ROBUST**
- 「時間足を上げると trend continuation が成立し得る」方向性は残るが、**0.5 pip の摩擦で消える薄さ**
- 本Stepの本質的価値: **偽の edge を paper-forward / 実運用に持ち込む前に、厳密化した評価で却下できた**
  こと（評価信頼度の向上）。前 hardening の 3つの過小評価（1.5×止まり・単一path random・
  slippage未考慮）を是正済み

## 6. recommended next Step

- 単純テクニカル（M5/H1）× 現実的コストでは持続 edge を確認できていない。次の実質前進は:
  1. **さらに長期/複数年・複数期間の独立OOS**（同一期間の窓分割ではなく別データ）で
     微弱な優位が残るかを、本 slippage 前提で再確認
  2. **テクニカル以外のシグナル源**（セッション/ボラ構造/フロー等）への仮説刷新
- live 移行は不可（robust edge 不在・operator判断・paper forward要）
