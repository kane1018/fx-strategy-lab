# Strategy Evaluation Hardening Report（no-POST・2026-07-08）

Step: `STRATEGY_EVALUATION_HARDENING_NO_POST`（report部）

**aggregate rates / safe counts / sign labels のみ。raw price/spread/PnL・
per-trade値・sample rows・ID・credentialは含まない。performance proofではない。**

## 1. 検証設計

- rolling OOS windows: 9 / window bars: 2,000 / indicator lead-in: 40（warmup）
- cost multipliers: 1.0 / 1.5 / 2.0（spread cost stress）
- 頑健判定閾値: walk-forward pass率 >= 0.60（qualifying窓 >= 3）かつ
  cost stress(1.5x) pass率 >= 0.60 かつ beats_random（median PF差 > 0.05）
- 判定: ROBUST_CANDIDATE_FOR_PAPER_FORWARD / NOT_ROBUST_REJECT / INSUFFICIENT_WINDOWS

## 2. 集計結果（safe aggregate）

- baseline base-cost pass率: 0.22
- random benchmark median PF（base）: 0.63
- 全8候補: ROBUST到達なし（7候補 NOT_ROBUST_REJECT / 1候補 INSUFFICIENT_WINDOWS）
- any_robust_candidate: false
- overall_conclusion: NO_ROBUST_EDGE_ACROSS_WALK_FORWARD_AND_COST_STRESS

（候補別のpass率・median PF・beats_random は
[STRATEGY_EVALUATION_HARDENING_NO_POST_20260708.md](STRATEGY_EVALUATION_HARDENING_NO_POST_20260708.md) の表を参照）

## 3. 過学習・安全チェック

- 未来データ不使用・chronological・lead-inはindicator warmupのみ（leakageなし）
- ランダムベンチマークは決定論的LCG（`random`モジュール不使用）で再現可能
- cost乗数は entry/exit 判定を変えず、記録PnLのみスケール（決定論を保持）
- performance_proof_status=false / live_ready=false / real_data_used=true /
  CSV commit=false / public kline export再実行=false / 過大表現なし

## 4. 結論

前回の単発OOSで freeze された候補を含め、**時間×コストにわたる持続edgeは確認できず**。
本Stepの価値は「偽陽性を構造的に弾く評価信頼度」の獲得。次の実質前進は
データ拡張（長期・複数期間・別時間足）での再評価、またはシグナル源の刷新。
