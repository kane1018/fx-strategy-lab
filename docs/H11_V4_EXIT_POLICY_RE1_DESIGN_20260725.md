# H-11 v4 出口戦略 R-E1 実装設計 v3(研究先行・本番は別ゲート)

作成: 2026-07-25(v1)、改訂: 2026-07-25(v2: 外部レビュー20項目反映、v3: 追加提案7項目反映)。
入力: operator提供の「H-11 Exit-only研究報告」+ v1への外部レビュー(20項目)+ v2への追加改善提案(7項目)。

## 0. 結論(この設計書が約束すること・しないこと)

報告書自身の判定は「**本番採用は見送り、paper trading前までの研究実装は着手可**」である。
本設計はそれに従い、研究実装(Phase A1/A2)・実運用シミュレーション(B1)・
前向き検証(B2)・本番再凍結判断(C)・canary(D)を明確に分離する。

**最重要の正直な前提**: 2026-07時点の既存バックテスト(19ヶ月・4547シグナル)では
全exit規則がコスト後マイナスで、30分固定決済が最も浅い損失だった。出口はエッジを
作らない(報告書H6)。採択ゲートを全候補が落ちた場合の帰結は
「**SHORT_V1シグナルでの自動売買は出口改善では救えない**」であり、それも正当な成果
として事前登録する。§6のC0(コストなし)比較により「エッジ不足」と「コスト負け」を
分離診断する。

**v3の設計目的の明確化**: 候補選定の目的は「1取引あたりの損失回避」ではなく、
**固定資本下・コスト控除後の累積利益の最大化**である。安全性は利益探索を支配する
フィルタではなく、独立した審査(Safety Qualification)として並置する(§8)。

## 0.1 v1→v2 改訂採否表(外部レビュー20項目)

| # | 提案 | 採否 | 理由 |
|---|---|---|---|
| 1 | common_Rの候補間共通化 | **採用** | v1はSL倍率変更でTP絶対距離も動く設計バグ。真の3×3独立比較に修正 |
| 2 | クランプをcommon_R側へ | **採用** | 候補ごとクランプはR比率を歪める。クランプ率の出力も追加 |
| 3 | OOSの一度きり使用・正直な名称 | **採用** | 2026-07以降は既閲覧のため「reused holdout」と明記。最終判定はprospective OOS(B2) |
| 4 | 階層的選択(Stage制) | **採用** | A2/A3を見た後のA1選び直しを構造的に禁止 |
| 5 | Phase C前にLayer2 | **採用** | B1として独立Phase化 |
| 6 | TRスパイクの同一時間尺度化 | **採用** | v1の`hourly_ATR/24`はスケール誤り。M1同士の比較+逆行時限定+次バー約定に修正 |
| 7 | BID/ASK分離 | **採用(条件付)** | GMO公開klineは`priceType=BID/ASK`両方取得可。コストモード2系統(二重控除防止) |
| 8 | A2-h11の隠れパラメータ明示 | **採用** | 確認回数・評価間隔・確定足限定・中立リセット・約定タイミングを事前固定 |
| 9 | A2-ind(逆行持続型)の削除 | **採用(削除)** | 実態は確認付きソフトストップで自由パラメータ2個追加。将来課題へ |
| 10 | A3専用ゲート(非劣性+tail) | **採用** | v3で§8のSafety Qualificationへ統合 |
| 11 | spread急拡大のヒステリシス | **採用** | live専用仕様。v3で#5(v3側)によりさらに保守化(§9.2) |
| 12 | quote stale時は保護状態遷移 | **採用** | blind close禁止。v3でsoft/hard stale二段化(§9.3) |
| 13 | tickSize量子化 | **採用** | GMO刻み(USD/JPY=0.001円)へ量子化、sim/liveで同一関数共有 |
| 14 | ExitDecisionとOCO価格計算の分離 | **採用(案A)** | OCO価格はentry時builder責務。ExitPolicyは判断のみ。reasonはenum化 |
| 15 | evidence/監査ログ二層化 | **採用** | PolicyDecision=sanitized、ExecutionAudit=監査限定ストレージ |
| 16 | A0-23hを回帰確認へ分離 | **採用** | `PROD-G014-REPLAY`。FDR母集団外。「23時間出口の簡易比較」とラベル |
| 17 | C0(コストなし)追加 | **採用** | エッジ不足とコスト負けの分離診断。損益分岐コスト出力 |
| 18 | bootstrap完全事前登録 | **採用** | 5000回・単位・統計量・CI法・seed固定(§7) |
| 19 | 研究実行manifest | **採用** | 全実行でハッシュ・seed保存(§11) |
| 20 | 追加単体テスト | **採用** | §12へ統合 |

## 0.2 v2→v3 改訂採否表(追加提案7項目)

| # | 提案 | 採否 | 理由・ガード |
|---|---|---|---|
| 1 | Profit DiscoveryとSafety Qualificationの分離 | **採用** | 利益探索と安全審査の混在は「安全だが儲からない候補」を優遇するバイアス。最終採用=利益上位∩安全合格(§8) |
| 2 | Layer2主指標を実運用利益へ | **採用** | Layer1は`net_pips_per_trade`維持。Layer2主指標は`net_yen_per_month`(固定資本・コスト後)+見送りシグナルの機会損失計上(§5.2)。資本額はoperator入力(未設定間は月次上限¥50,000を基準単位とした相対表示) |
| 3 | C3・最大連敗を絶対失格から耐久性分類へ | **採用(ガード付)** | 恣意的な2倍定数より実測コスト分位が現実に厳密。ただし実測データが無い段階の暫定基準として「C1bで黒字」をB1/B2進出の必要条件に維持(C0のみ黒字はReject)。連敗5はlive側でrisk policyのラッチが強制するためLayer2でラッチ自体をシミュレートし、研究側は連敗分布・回復期間・破産確率proxyで評価(§8.2) |
| 4 | A2-edge-decay追加 | **採用** | 「反対方向が有利」と「保有継続の価値が消えた」は別物。中点0.50は自然な定数でチューニング対象でなく、凍結シグナル再利用の方針とも整合。Stage 2はopposite/edge-decayの2変種比較に(§3.3) |
| 5 | A3の売買出口とシステム安全機構の分離 | **採用** | TRスパイク=売買出口(sim対象)。spread/stale/OCO整合=システム安全機構(fault injection対象)。spread異常時の既定動作を「新規停止・保有はOCO保護下で維持」に変更し、強制決済は劣化併発時のみ(§9.2)。broker側OCOが保護の主体という現行アーキテクチャに、即時成行決済よりも整合 |
| 6 | 勝ち伸ばし候補はMFEデータを見て追加 | **採用(既存方針の明確化)** | v2 §13に既存。「30分超の条件付き延長」はラベル整合性の前提を壊すため、追加時は独立設計書+ラベル不整合の明示を必須とする(§13) |
| 7 | 最終ゲートのProfit Gate/Risk Gate二部構成 | **採用** | §8を全面再構成。Kill Switch独立性はB2 fault injectionのチェック項目に追加 |

**v3で緩めていないもの(明示)**: OOS規律(§4)・Stage制の選び直し禁止(§5)・
事前登録主義・「全滅なら出口では救えない」の帰結・A3を利益最適化しない方針。

## 1. 報告書・レビューとこのリポジトリのギャップ(翻訳表)

| 前提 | このリポジトリの現実 | 設計での扱い |
|---|---|---|
| OANDA v20 (trigger/fill分離, FOK/IOC) | GMOコインFX (MARKET entry→EXACT OCO, position-specific close) | GMO準拠に置換。`V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT`が既存 |
| bid/askティック必須 | M1 OHLC(bid)57万行。tickなし | 同一バーはSL先充足の悲観処理を標準。TP先の感度表併記 |
| ASK系列 | 未取得だがGMO公開klineは`priceType=ASK`対応 | Phase A1でASK M1取得、`BID_ASK_M1`モード実装。不能期間は`LEGACY_BID_ONLY` |
| spread履歴 | なし。entry gateはspread≤2.0pips/鮮度≤5秒 | コストは定数+ストレス系(§6)。実測分位はB2で取得し最終ゲートに使用(§8.1) |
| 30分ホライズン | 現行live exitは1.5ATR/1.5R/23h+金曜規則 | max hold 30分への変更はG015再凍結事項(Phase C) |
| 指標カレンダー | なし | JST時間帯プロキシ(§6 C5)。カレンダー統合は将来課題 |

## 2. R定義(共通リスク単位・事前固定)

```
entry_ATR      = 直近24時間の hourly ATR(entry後の足は不使用)
common_R_raw   = 1.0 × entry_ATR                     # fixed_atr_multiplier=1.0 全候補共通・固定
common_R       = clamp(common_R_raw,
                       floor = min_stop / min(sl_r) = 3.0 / 0.8 = 3.75 pips,
                       cap   = max_stop / max(sl_r) = 20.0 / 1.2 ≈ 16.67 pips)
SL_dist        = sl_r × common_R                      # sl_r ∈ {0.8, 1.0, 1.2}
TP_dist        = tp_r × common_R                      # tp_r ∈ {1.0, 1.5, 2.0}
```

- `min_stop = 3.0 pips`、`max_stop = 20.0 pips`(事前固定・最適化しない)
- TP/SL価格はGMO tickSize(USD/JPY: 0.001円)へ量子化。量子化関数はsim/live共有
- `floor_clamp_count / cap_clamp_count / clamp_rate` を出力
- Layer1主指標 `net_pips_per_trade`。`net_yen_per_trade`・`net_common_R_per_trade`併記。
  `local_R`(実SL距離基準)は補助指標

## 3. 候補レジストリ(事前登録・これ以上増やさない)

### 3.1 レジストリ

| ID | SL (×common_R) | TP (×common_R) | max hold | 反転 | 緊急 | FDR母集団 |
|---|---:|---:|---|---|---|---|
| A0 | なし | なし | 30分 | なし | なし | 基準線(検定の対照) |
| PROD-G014-REPLAY | 1.5ATR実距離 | 1.5R(local) | 23h | なし | なし | **対象外**(回帰確認。swap・金曜規則・gap未再現の簡易比較) |
| A1-{tp}-{sl} 9候補 | 0.8/1.0/1.2 | 1.0/1.5/2.0 | 30分 | なし | なし | 対象(9) |
| A2-opposite | Stage1上位を継承 | 同 | 30分 | 反対閾値型(§3.3) | なし | Stage2で比較 |
| A2-edge-decay | Stage1上位を継承 | 同 | 30分 | エッジ消失型(§3.3) | なし | Stage2で比較 |
| A3-sim | Stage2上位を継承 | 同 | 30分 | あり | TRスパイク(§3.4) | Stage3で専用審査 |

A2-ind(逆行持続型)は削除済み(v2 #9)。A4/S1は§13の条件を満たした場合のみ別設計書。

### 3.2 同一バー競合・約定タイミング(全候補共通)

- 同一M1バー内でTP/SL両到達の可能性がある場合は**SL先充足**(悲観)を標準。TP先の感度表を別出力
- 反転・緊急による決済は「足tの確定で判定 → **足t+1の始値で約定**」。
  足tの高安を見て足t内の価格で決済する処理は先読みであり禁止(テストで固定)

### 3.3 A2 仕様(2変種・隠れパラメータの事前固定)

共通:
```
closed_signal_only       = True   # 未確定足のp_upは使わない
reversal_confirmations   = 2      # 連続する確定M1足で2回
exit_fill                = 次バー始値(§3.2)
評価頻度(研究)          = M1確定足ごと
評価頻度(感度)          = 5分間隔評価の変種を併走(sim-liveギャップ測定)
```

変種別の発火条件(確定足でconfirmations回連続):
```
A2-opposite   : BUY保有中 p_up ≤ 0.42 / SELL保有中 p_up ≥ 0.58
                (反対方向のエントリー級シグナル。カウンタは中間域復帰でリセット)
A2-edge-decay : BUY保有中 p_up < 0.50 / SELL保有中 p_up > 0.50
                (保有継続価値の消失。カウンタは自陣側復帰でリセット)
```

中点0.50は凍結シグナルの自然な境界でありチューニング対象にしない。
edge-decayはoppositeより早く降りるため回転率が上がる — Layer2の機会損失計上(§5.2)で
初めて公平に比較できる点に注意。

**sim-liveギャップ注記**: 現行live機構には保有中の反転評価ループが存在しない
(保有監視はbroker側OCO任せ)。A2をliveへ配線する場合の評価周期・実行主体は
Phase Cの設計・レビュー事項。研究段階の結論は「M1評価と5分評価の成績差」まで。

### 3.4 A3-sim 仕様(売買出口としてのTRスパイクのみ・利益最適化しない)

```
ATR1m_entry   = entry直前60本の確定M1足のTR平均(entry後の足は不使用)
発火条件(足t確定時に判定):
    TR(足t) / ATR1m_entry ≥ 3.0
    AND 足t終値評価の含み損益 ≤ -0.25 × common_R
約定       = 足t+1の始値
```

- 利益方向の急伸はTPに任せ、**逆行時のみ**発火
- 閾値3.0/-0.25は事前固定。sim上の役割は「誤発火の被害測定」
- spread急拡大・quote stale・OCO整合・執行異常は**売買出口ではなくシステム安全機構**
  (§9)であり、fault injection(B2)で評価する。バックテストのEV比較には含めない

## 4. データ役割分割(OOSの一度きり使用)

| 区分 | 期間/取得 | 用途 | 禁止事項 |
|---|---|---|---|
| Development/IS | 〜2026-06-30 | バグ検出・A0再現・候補定義確認・コストモデル動作確認 | — |
| Validation | IS期間内のinner WFO(拡張窓) | Stage1-3の候補選択・FDR | — |
| **Reused holdout** | 2026-07-01〜現在 | Stage完了後に固定した候補の参考評価 | **候補定義の変更に使用しない**。既閲覧のため「完全未使用」を名乗らない |
| **Prospective OOS** | レジストリ・実装凍結後に新規到来するデータ(B2のshadow/paper) | Phase C移行判断の主根拠 | 凍結前の一切の参照 |

## 5. 階層的選択とLayer2

### 5.1 Stage制(選び直し禁止)

```
Stage 1: A0 vs A1×9 を Validation で比較 → BH-FDR(q=0.10) → 上位1〜2候補を固定
Stage 2: 固定したA1候補 + A2-opposite / A2-edge-decay → 採否判定(A1候補の選び直し禁止)
Stage 3: 固定したA2段候補 + A3-sim → §8.2の安全審査観点で判定
Final  : 全候補・全閾値を凍結 → reused holdout を1回だけ評価 → B1/B2へ
```

### 5.2 Layer2(B1)の主指標 — 実運用利益

Layer1のper-trade指標は回転率の差を無視する。早く降りる出口は後続シグナルを
拾える(機会獲得)一方、薄利連発でコストを積む可能性もある。B1では
production制約(ONE_POSITION_OPEN・entries/day cap {1,20}感度・連敗5ラッチ・
日次¥10,000/月次¥50,000ラッチ)下の実時系列シミュレーションを行い、主指標を:

```
net_yen_per_month(固定資本・コスト後)     # 主指標
net_yen_per_calendar_day                    # 併記
skipped_signal_count / 保有中に見送った後続シグナルの仮想損益   # 機会損失の計上
実時系列 maxDD・回復期間                    # Safety Qualification入力
```

固定資本に対するリターン率は、operatorが資本額を指定した時点で追加する
(未指定の間は月次損失上限¥50,000を基準単位とした相対表示に留める — 数値の発明をしない)。

## 6. コストモデル(事前登録)

| ID | 内容 | 値 |
|---|---|---|
| C0 | コストなし(診断用) | 0 |
| C1 | 従来backtest互換 | 往復0.5 pips |
| C1b | 基準(entry gate緩和後の現実的上限) | 往復1.0 pips |
| C2 | ストレス1.5× | 1.5 pips |
| C3 | ストレス2× | 2.0 pips |
| C5 | 高ボラ時間帯加算 | JST 21:00–24:00・05:00–09:00のexitに+0.5 pips |

価格面モード(二重控除防止・排他):

```
LEGACY_BID_ONLY : BID価格のみ使用+固定往復コスト控除(C0〜C5)
BID_ASK_M1      : BUY entry=ASK / BUY exit=BID / SELL entry=BID / SELL exit=ASK
                  追加控除はslippage・stress wideningのみ(固定spread再控除禁止)
```

診断出力: 候補ごとの `break_even_roundtrip_cost_pips`(Net EV=0となる往復コスト)。

### 6.1 コスト耐久性分類(v3 #3。絶対失格ではなく分類)

| 分類 | 定義 | 扱い |
|---|---|---|
| Robust | C3でも黒字 | 最良。優先採用候補 |
| Deployable | 実測往復コストのP90でも黒字(B2で実測後に判定) | **最終採用の下限**(§8.1) |
| Fragile | C1bでは黒字だがC2で赤字 | B2へ進めるが採用不可。実測次第で再分類 |
| Reject | C1bで赤字(C0のみ黒字を含む) | 失格。B1/B2へ進まない |

実測コスト分位が存在しない段階(B2前)の進出基準は「C1bで黒字」。
C3は失格条件ではなく分類ラベルとして全候補に併記する。

## 7. 統計事前登録

```
paired統計単位      : JST日次のpaired Δ(候補 − A0)net_pips 合計
bootstrap           : stationary bootstrap、期待ブロック長5営業日
リサンプル数        : 5,000
統計量              : mean Δnet_pips / median Δnet_pips / maxDD差
CI                  : percentile(補助でBCa)
seed                : 20260725(固定)
多重比較            : Stage1の9候補にBH-FDR q=0.10
破産確率proxy       : 日次P&Lのbootstrap再抽出で「1ヶ月以内に月次上限¥50,000ラッチへ
                      到達する確率」を推定(凍結済みrisk policy値のみ使用・新パラメータなし)
```

## 8. 最終採択ゲート(v3二部構成・事前固定)

最終採用 = **Profit Gate合格の上位候補 ∩ Risk Gate合格**。
どちらか一方だけの合格では採用しない。

### 8.1 Profit Gate(利益探索)

1. Validation→Final評価で `Net EV(候補) ≥ Net EV(A0)` かつ C1bで `Net EV > 0`
2. コスト耐久性分類(§6.1)が**Deployable以上**
   (= B2で実測した往復コストP90でも黒字。実測前はC1b黒字を暫定条件とする)
3. B1(Layer2)で、機会損失を含めた `net_yen_per_month` がA0構成を上回る
4. B2(prospective OOS / paper)で日次・月次Net P&Lがプラス
5. FDR生き残りであること

### 8.2 Risk Gate(安全審査)

1. 実時系列maxDD・CVaR(5%)が承認範囲内
   (承認範囲=凍結済みrisk policy: 日次¥10,000/月次¥50,000/1トレード¥5,000)
2. 破産確率proxy(§7)が事前上限内(上限=10%。事前固定)
3. 連敗評価: 連敗5ラッチをB1でシミュレートした上で、連敗分布・連敗時累積損失・
   回復期間を診断表として提出(即失格条件にはしない。ラッチはlive側で強制される)
4. fault injection合格: OCO不整合・quote stale・重複close・restart recovery(§9)
5. **Kill Switchが出口戦略から独立して強制されること**(出口ロジックの状態に
   関わらずHALT/killラッチが優先される構造の確認)
6. A3追加時の非劣性: `ΔEV(A3−直前候補) ≥ −0.01 common_R/trade` AND
   (maxDD ≤ 0.90×直前候補 or 最大連敗改善 or CVaR改善 or fault時安全終了率改善)

**全滅時の帰結(事前登録)**: 全候補がProfit Gateを落ちた場合、結論は
「出口では救えない」。entry側の再検討または撤退はoperator判断事項。

## 9. live側仕様(Phase C向け・今は実装しない)

### 9.1 責務分離

```
OcoBuilder(entry時) : common_R計算・TP/SL価格決定・tickSize量子化 → EXACT OCO発注
ExitPolicy(保有中)  : 反転確定・TRスパイクのみ判断(売買出口)
SafetyMonitor        : spread異常・quote stale・OCO整合・HALT/reconcile(システム安全機構)
```

```python
class V4ExitReason(str, Enum):
    REGIME_REVERSAL = "REGIME_REVERSAL"
    EMERGENCY_TR_SPIKE = "EMERGENCY_TR_SPIKE"
    MAX_HOLD = "MAX_HOLD"
    NONE = "NONE"

class V4SafetyState(str, Enum):
    NORMAL = "NORMAL"
    SPREAD_ANOMALY = "SPREAD_ANOMALY"        # 新規停止・保有はOCO保護下で維持
    SOFT_STALE = "SOFT_STALE"                # 新規停止・出口更新停止
    HARD_STALE_RECONCILE = "HARD_STALE_RECONCILE"
    FORCED_EXIT_PENDING = "FORCED_EXIT_PENDING"

@dataclass(frozen=True)
class V4ExitDecision:
    action: V4GmoAction                 # 既存enumのみ
    reason: V4ExitReason                # enum(自由文字列禁止)
    halt_new_entries: bool
    evidence: Mapping[str, float | int | bool]   # sanitized数値のみ
    def __bool__(self) -> bool: return False
```

ExitPolicyの評価順序固定: **TRスパイク → 反転確定 → max hold → HOLD**。
TP/SLはbroker側OCOが担い、クライアント側TP/SL監視ループは作らない(現行踏襲)。
SafetyMonitorはExitPolicyの上位で動き、安全状態が`NORMAL`以外のとき
ExitPolicyの新規判断を停止する。

### 9.2 spread異常(v3 #5: 既定は保有維持・強制決済は劣化併発時のみ)

```
検知: spread ≥ 2.0 pips が2秒以上持続 AND その間のquote更新 ≥ 3回
既定動作: 新規entry停止。保有positionはbroker側OCO保護下で維持
          (最も不利な価格での成行決済を避ける)
強制決済への昇格条件(いずれか):
    含み損 ≤ -0.5 × common_R まで劣化
    OCO整合性喪失(broker照合でTP/SL注文が消失・不一致)
実測spread蓄積後: 検知閾値を max(2.0 pips, 3.0 × rolling_median_spread) へ拡張可(将来課題)
```

### 9.3 quote stale(v3 #5: soft/hard二段・blind close禁止)

```
SOFT_STALE (quote_age ≥ 5秒)  : 新規entry停止・出口更新停止。OCO正常なら保有継続
HARD_STALE (quote_age ≥ 30秒) : broker上のposition/OCOをreconcile
復旧後: OCO整合が確認できれば保有継続を許容。
        整合喪失または§9.2の昇格条件成立時のみ position-specific close
```

秒数(5/30)は事前固定。既存entry gateの鮮度5秒と整合。
既存のHALT/reconcile機構・kill switchとの統合はPhase Cの独立レビュー対象。
**kill switchはこの全状態機械より優先される**(§8.2-5)。

### 9.4 evidence/監査の二層化

```
PolicyDecision : safe enum + sanitized数値のみ(価格生値・broker ID禁止)
ExecutionAudit : position/order ID・OCO価格・entry/exit約定・fee/slippage・MFE/MAE
                 → 監査用ストレージ限定。モデル入力・一般表示へ出さない
```

live側ExecutionAuditの永続化設計は、sanitized永続化規約との整合を
Phase Cの独立レビューで確認してから実装する。

## 10. Phase構成

| Phase | 内容 | digest影響 | 誰が |
|---|---|---|---|
| A1 | データ・基準線: ASK M1取得・common_R実装・A0/PROD-G014-REPLAY再現・コストモデル・manifest | なし | Claude実装可 |
| A2 | Layer1比較: A1グリッド→Stage制→A2 2変種→A3-sim→MFE/MAE→bootstrap/FDR | なし | Claude実装・実行可 |
| B1 | Layer2実運用sim: production制約下の実時系列・機会損失計上・`net_yen_per_month`主指標・連敗/DD/破産確率proxy診断 | なし | Claude実装・実行可 |
| B2 | 最終検証: WFO・reused holdout1回評価・prospective shadow/paper・**実測spread/slippage分位の取得**・fault injection | なし(shadowは既存no-POST機構) | Claude+operator |
| C | G015再凍結判断: operator明示承認・独立レビュー2本・AGENTS.md 2箇所更新・再凍結 | あり | operator判断+実行 |
| D | 監視付きcanary→OCO/position整合・kill switch確認→無人移行判断 | — | operator |

**Phase C移行条件** = §8のProfit Gate合格 AND Risk Gate合格(いずれも事前固定値)。

## 11. 研究実行manifest(全実行で保存)

```
git_commit / script_sha256 / entry_artifact_sha256 / bid_data_sha256 / ask_data_sha256
candidate_registry_sha256 / config_sha256 / python_version / dependency_lock_hash
bootstrap_seed / run_started_at / run_finished_at / output_sha256
```

Phase Bでoperatorへ提示する結果表はmanifestと一対一で紐づける。

## 12. 単体テスト(Phase A分)

| テスト | 確認内容 |
|---|---|
| common_R固定 | 同一entryで全候補のcommon_Rが一致 |
| TP/SL独立性 | sl_rを変えてもTP距離が不変 |
| クランプ境界・発生率 | floor/cap動作とclamp_rate出力 |
| ATR未来参照禁止 | entry後の足をATR計算に不使用(hourly・1m両方) |
| 同一バーTP/SL競合 | SL先の悲観処理 |
| A2確認回数 | 1本では発火しない・リセット規則(opposite=中間域/edge-decay=自陣側) |
| A2変種独立性 | oppositeとedge-decayが同一entryで異なる決済点を取り得る |
| A2/A3次バー約定 | 足t高安を見て足t内決済しない |
| A2評価頻度 | M1版と5分版が独立に動く |
| A3逆行時限定 | 利益方向のTRスパイクで発火しない |
| BID/ASK価格面 | BUY exit=BID / SELL exit=ASK |
| コスト二重控除禁止 | BID_ASK_M1で固定spreadを再控除しない |
| コスト耐久性分類 | C0/C1b/C2/C3の結果からRobust〜Rejectが正しく付く |
| tick量子化 | 全注文価格が0.001の倍数 |
| entry列hash | 全候補でentry列が同一 |
| 機会損失計上 | Layer2で保有中の見送りシグナルが記録される |
| 破産確率proxy | 凍結policy値のみ使用・seed固定で決定的 |
| OOS非再利用 | reused holdout評価が候補選択ループから呼べない構造 |
| bootstrap決定性 | seed固定で同一CI |
| A0再現 | 既存スクリプトの基準値と一致 |
| manifest生成 | 全ハッシュ項目が埋まる |

## 13. 将来課題(スコープ外・事前明記)

- A2-adverse-persistence(旧A2-ind): 根拠データが揃った場合のみ再検討
- A4(単段トレール)/S1(分割利確)/30分超の条件付き延長: Phase A2のMFE分析で
  「1R到達後も1.5R/2Rへ伸びる取引が多い」「30分時点でも方向エッジが残る」
  「延長がコスト後利益を増やす」が確認された場合のみ、**独立設計書**として起こす。
  30分超延長は凍結シグナルのラベル整合性を壊すため、その旨の明示を必須とする
- bid/ask spread実測の前向き収集(B2で開始。§8.1のP90判定の入力)
- 経済指標・東京仲値カレンダー統合
- DSR/PBO(CSCV)の本格実装(初期はFDR+Stage制+prospective OOSで代替)
- spread閾値の相対値化(§9.2)
- 固定資本額のoperator指定とリターン率表示(§5.2)
