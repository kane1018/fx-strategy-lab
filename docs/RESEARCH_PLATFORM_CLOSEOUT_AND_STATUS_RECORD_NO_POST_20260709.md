# 研究プラットフォーム クローズアウト & 正式ステータス記録（no-POST・2026-07-09）

Step: `RESEARCH_PLATFORM_CLOSEOUT_AND_STATUS_RECORD_NO_POST`

**本書は戦略探索フェーズの正式な締め記録。docs のみ（新仮説実装・追加データ取得・backtest 再実行なし）。
raw price/spread/PnL/CSV row/ID/credential は一切扱わない。以下の status flag を正式確定する:
performance_proof_status=false / live_ready=false / unattended_live_supported=false /
current_strategy_status=NO_ROBUST_EDGE_FOUND_IN_TESTED_SCOPE。**

## 0. クローズアウト宣言

- 事前登録ラダーの **null #1/3** の時点で、operator 判断により **RESEARCH_PLATFORM_CLOSEOUT を前倒し**。
  「tested scope で robust edge 不在」を正式記録し、評価基盤・runbook・status を整理して探索を一旦終える。
- 本書は「edge 不在の全域証明」ではない。**検証した範囲（tested scope）での結論**であり、
  将来 operator 承認の新規/独立データ＋新規事前登録があれば再開可能（→ runbook）。

## 1. 正式ステータス（確定）

| flag | 値 |
|---|---|
| current_strategy_status | **NO_ROBUST_EDGE_FOUND_IN_TESTED_SCOPE** |
| performance_proof_status | **false** |
| live_ready | **false** |
| unattended_live_supported | **false** |
| unattended_full_auto_completed | **false** |
| evaluation_framework_status | **HARDENED（強化済み・本プロジェクトの持続的資産）** |
| research_phase | **CLOSED_OUT（operator 判断で再開可）** |

## 2. Rejected ledger（棄却台帳・safe aggregate）

| # | 仮説 | scope / data | 判定 | 主因（safe） | 記録 |
|---|---|---|---|---|---|
| 1 | M5 technical 4family×2exit | M5 | REJECTED_NO_ROBUST_EDGE | 全候補 NOT_ROBUST | [redesign](STRATEGY_RULE_REDESIGN_NO_POST_20260708.md) / [hardening](STRATEGY_EVALUATION_HARDENING_NO_POST_20260708.md) |
| 2 | H1 trend continuation / ride | H1 15ヶ月 | REJECTED_NOT_ROBUST_UNDER_EXECUTION_FRICTION | 0.5pip/side で breakeven化・多解像度不一致 | [execution-realism](STRATEGY_EXECUTION_REALISM_HARDENING_NO_POST_20260708.md) / [gate-correction](STRATEGY_GATE_CORRECTION_AND_SESSION_HYPOTHESIS_NO_POST_20260708.md) |
| 3 | SESSION_MOMENTUM | H1 | REJECTED_DIRECTION_RULE_NOT_BEATING_SIGN_PERMUTATION | 方向ルールが符号置換p90に負け・非unanimous | [gate-correction](STRATEGY_GATE_CORRECTION_AND_SESSION_HYPOTHESIS_NO_POST_20260708.md) |
| 4 | GOTOBI_FIX_DRIFT（仲値ドリフト） | M5 2.7年・166件 | REJECTED_ON_MULTI_YEAR_M5 | PF≈1.00・2.0×コスト負・符号置換負け・非持続。16件PF5.38は小標本の偶然 | [preregistration](STRATEGY_GOTOBI_FIX_DRIFT_PREREGISTRATION_NO_POST_20260708.md) / [retest](STRATEGY_GOTOBI_MULTI_YEAR_M5_RETEST_NO_POST_20260708.md) |
| 5 | VOL_REGIME_CONDITIONAL_BREAKOUT | M5 2.7年 primary / H1 参照 | REJECTED（NOT_ROBUST） | 高vol化で改善方向は確認(H1 0.80→0.94)だが PF<1・符号置換未達・コスト非生存 | [retest](STRATEGY_VOL_REGIME_CONDITIONAL_BREAKOUT_RETEST_NO_POST_20260708.md) |

- 共通結論: **USD/JPY メジャーの単純・単一・方向性ルールは、現実的コスト後に robust edge を示さない**
  （効率的・裁定済み市場での予想通りの結果）。
- 未検証で near-term 困難（データ壁/標本過少）: 三角relative-value（文献: 小口は"mirage"）・月末リバランス
  （標本過少）・cross-asset lead-lag / event drift（外部非FXデータ要）。
  → [inventory](STRATEGY_HYPOTHESIS_INVENTORY_AND_PREREGISTRATION_NO_POST_20260708.md)。

## 3. 標準評価 gate（正式記録）

全 strategy 候補に適用する**必須 gate**（コードに明文化済み）:
- 実装: `backend/app/services/gmo_strategy_evaluation_hardening.py`
  （`StandardEvaluationGate` / `evaluate_under_standard_gate` / `MultiResolutionGateReport`）、
  gotobi 系は `backend/app/services/gmo_strategy_gotobi.py`（`evaluate_gotobi_effect`）。
- 構成:
  - walk-forward / rolling OOS（chronological・leakage なし）
  - **cost 2.0× stress**（最悪 multiplier で判定）
  - **slippage 0.5pip/side**（instrument別に保守化・両fill）
  - **leg 別 crossing-side spread**（long=entry ask / short=exit ask）
  - **sign-permutation p90**（方向優位の検定・主benchmark）
  - fixed-cadence random p90（副参照）
  - **multi-resolution unanimous**（複数 window 粒度の全てで robust 要求＝窓分割依存の偽陽性を却下）
  - **min qualifying windows / min sample**（薄い窓・小標本で pass させない）
  - **program 全体の多重検定台帳**（累計 ~20 trial・単一指標超えでは合格とせず常に unanimous 多対照）
  - **post-OOS retuning 禁止**（データは凍結ルールに1回だけ採点）
- 合格の意味: **paper-forward 検討の解錠のみ**。live は operator + paper-forward pass が別途必須。
  perf_proof/live は独立検証まで false。

## 4. 構築済み資産（持続的価値）

- 決定論的 backtest 基盤: engine / metrics / report / dataset（synthetic + operator-local CSV）。
- **評価 hardening**: 上記 gate 一式（multi-resolution・sign-permutation・leg別spread・多重検定台帳）。
- **historical data 取込アダプタ**（local-file-only・BID/ASK pair→spread・forbidden列拒否・no fetch）。
- **gotobi モジュール**（銀行営業日調整暦・時刻窓runner・4対照評価）。
- frozen 決定論的 signal engine（無変更・safe-labelのみ）。
- 全て **safe-aggregate 報告のみ / no broker / no network / no credential / no-POST**。

## 5. データ在庫（repo 外・未commit）

`~/Desktop/fx_strategy_lab_historical_data/`（gitignore 相当・repo 外・**一度も commit していない**）:
- USD_JPY H1 BID/ASK（2025-04〜2026-07・約15ヶ月）
- USD_JPY M5 BID/ASK（2026-04〜2026-07・約3ヶ月・初期／後継に置換済）
- USD_JPY M5 BID/ASK（2023-11〜2026-07・約2.7年・198,129 bars・gotobi/vol-regime retest 使用）
- 取得は全て operator 承認の **public GET（認証なし）**。raw row は非公開。

## 6. 安全不変則（クローズ後も継続）

以下は本プロジェクトの恒久制約（再開後も不変）:
- actual POST / entry・settlement・order POST / broker write / real broker HTTP / private API /
  runtime private GET / credential・env 値読取 = **一切行わない**（default-deny hard guard）。
- 新規データ取得は **operator 承認の public GET のみ**。CSV は repo 外・非commit・raw非公開。
- report は safe aggregate のみ（raw price/spread/PnL/CSV row/ID/credential を出さない）。
- frozen signal engine / RiskPolicy / hard guard を弱めない。allow=True 恒久化しない。
- **post-OOS retuning 禁止** / 事前登録なしの探索禁止。

## 7. 最終引き継ぎ要約（Codex/ChatGPT 向け）

- 戦略探索は **CLOSED_OUT**。5仮説を厳密 gate で棄却し、**tested scope で robust edge 不在**を確定。
  performance_proof=false / live_ready=false / unattended_live_supported=false は不変。
- **本当の成果物は「信頼できる評価基盤」**（偽陽性を再現的に却下できる。gotobi 16件PF5.38 の小標本
  mirage を最小標本gateが却下したのが象徴例）。
- 再開するなら **runbook**（[RESEARCH_RUNBOOK_NO_POST.md](RESEARCH_RUNBOOK_NO_POST.md)）に従い、
  新規事前登録 → operator承認データ → 凍結ルールを標準gateで1回採点、の順のみ。
- 現状 repo: main・作業ツリー clean。詳細は [PROJECT_STATUS.md](PROJECT_STATUS.md) /
  [CODEX_HANDOFF.md](CODEX_HANDOFF.md) 冒頭。
