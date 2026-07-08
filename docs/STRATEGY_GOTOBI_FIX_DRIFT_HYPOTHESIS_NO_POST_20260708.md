# 新仮説 GOTOBI_FIX_DRIFT(仲値ドリフト): 現データでは未確認（no-POST・2026-07-08）

Step: `STRATEGY_GOTOBI_FIX_DRIFT_HYPOTHESIS_NO_POST`
実装: `backend/app/services/gmo_strategy_gotobi.py`（ゴトー日暦 + 時刻窓runner + 4対照評価）
+ `backend/app/tests/test_gmo_strategy_gotobi_no_post.py`

**重要: performance proof ではない（performance_proof_status=false / live_ready=false）。
raw price/spread/PnL/CSV row/ID は扱わない。本Stepは Web ディープリサーチで選定した
機構ベース仮説を1つ事前登録し、既存 local データ read-only で厳格に検証した記録。
結論は「現データでは確認できない（棄却/判定保留）」であり、edge の証明でも否定でもない。**

## 1. 仮説と機構（ディープリサーチで選定）

- **機構(実需)**: 日本の輸入企業がゴトー日(日付末尾が5か0)にドル建て決済を行うため、
  銀行が **9:55 JST の仲値(TTM)に向けてドル買い** → USD/JPY が仲値に向けて上昇しやすい。
- 学術的裏付け: USD/JPY は **朝3:00 JST 頃から9:55へ上昇**する傾向（arXiv 2301.13204 は
  GMO外貨ex共著、2018–2020分足で spread控除後 PF≈2.62・勝率0.68 と報告。NBER w22820 /
  ScienceDirect は fix前のドル買い注文インバランスとして機構を裏付け）。
- 単純テクニカルと違い**時刻+実需カレンダー**に根拠がある点が新しい。

## 2. 事前登録した固定ルール(1つ・後付けチューニングなし)

- **実効ゴトー日** = 基準日{5,10,15,20,25,30}。基準日が**日本の銀行営業日でない**
  (土日・祝日・年末年始 12/31–1/3 の銀行休業)場合、決済需要は**直前営業日に前倒し**。
  祝日表は 2025-04〜2026-07 の静的・監査可能テーブル(内閣府祝日 + 銀行休業)。取得なし。
- 各実効ゴトー日: **03:00 JST の足終値で USD/JPY ロング → 09:55 JST の足終値で決済**
  (固定時刻窓・TP/SLなし)。03:00に板がない日(月曜プレオープン等)は**捏造せず当日スキップ**。

## 3. 評価法(4対照 + コストストレス・全てコスト込み)

naive な陽性に騙されないよう、**0.5pip/side slippage + spread、2.0×コスト**の下で:
1. **非ゴトー日対照**: 同じ時刻窓を非ゴトー日で実行 → ゴトー日がこれを上回る必要
2. **日ラベル置換 p90**: 全営業日から同数の日をランダム抽出(多seed)した PF分布の p90 超え
3. **符号置換 p90**: 同じゴトー日で**方向のみランダム化**した PF分布の p90 超え(方向優位の検定)
4. **期間前後半の安定性**: 両半期で PF>1

## 4. 結果(USD/JPY・既存 local CSV read-only・safe aggregate)

### H1(2025-04〜2026-07・~15ヶ月・主検定=標本十分)
| leg | n | PF | 勝率 | 期待値符号 |
|---|---|---|---|---|
| GOTOBI(exit 09:55) | 80 | 0.757 | 0.525 | NEGATIVE |
| NON_GOTOBI 対照 | 181 | 0.814 | 0.514 | NEGATIVE |
| GOTOBI 2.0×コスト | 80 | 0.730 | 0.513 | NEGATIVE |

- label_perm p90=1.01 / sign_perm p90=1.27 / 前後半PF 0.45 / 1.31
- **全対照に負け・PF<1・不安定 → GOTOBI_EFFECT_NOT_ROBUST_REJECT**
- 診断(公平化): exit を **09:00 JST(仲値前・リバーサル回避)** にしても PF=0.77(NEGATIVE・
  前後半0.34/1.62)、exit 08:00 で PF=0.46。**どの出口でも H1 では優位なし**。
- **ただし H1 は本質的に不適**: H1 の exit足は 10:00 JST に閉じ、**仲値後のリバーサルを含む**
  (9:55 ちょうどに出られない)。この効果は**時間内(sub-hour)現象**であり H1 は粒度不足。

### M5(2026-04〜2026-07・~3ヶ月・確認=粒度は正しいが標本過少)
| leg | n | PF | 勝率 | 期待値符号 |
|---|---|---|---|---|
| GOTOBI(exit 09:55) | 16 | 5.38 | 0.813 | NON_NEGATIVE |
| NON_GOTOBI 対照 | 40 | 0.688 | 0.500 | NEGATIVE |
| GOTOBI 2.0×コスト | 16 | 5.09 | 0.813 | NON_NEGATIVE |

- label_perm p90=3.72 / sign_perm p90=2.03 / 前後半PF 99.0 / 1.52
- 4対照を全て上回りコストも生存だが、**トレード数16 (< 30) → INSUFFICIENT_GOTOBI_SAMPLE**。
  評価器は**16件の見かけの好成績を robust と認めない**(前半"99.0"=無敗8件は小標本の産物)。

## 5. 結論(正直に)

- **現データでは GOTOBI_FIX_DRIFT を確認できない。**
  - H1: 標本は十分だが**粒度が不適**(仲値ちょうどに出られず、どの出口でも優位なし)。
  - M5: **粒度は正しく、4対照全通過の強い数字**だが **3ヶ月/16件で統計的に不十分**。
- **framework の健全性**: 16件の魅力的な数字に飛びつかず INSUFFICIENT で正しく保留した。
- **前進に必要なもの**: 本仮説の適正検定には **複数年の M5(または M1) USD/JPY** が必要
  (sub-hour現象ゆえ H1不可、3ヶ月M5は件数不足)。取得は **operator承認の public GET が前提**。
  M5の示唆は「仮説を捨てる」のでなく「多年M5で検定する価値がある」ことを示す(過信は禁物)。
- **performance proof でも live 許可でもない。** unattended_full_auto_completed=false /
  unattended_live_supported=false は不変。live移行は robust edge 確認まで不可。

## 6. recommended next Step(実装は別Step)
1. **operator承認のもと、USD/JPY M5(または M1)を複数年 public GET → local CSV 化**し、
   本 `evaluate_gotobi_effect` で同一の事前登録ルール・4対照・コストストレスを再検定。
2. 併せて exit を 9:55 ちょうどに合わせられる粒度(M5/M1)で、entry/exit時刻の
   小さな事前登録グリッド(多重検定予算管理下)を1度だけ評価。

**Sources**: arXiv 2301.13204 / NBER w22820 / ScienceDirect S0022199617301204 /
Ranaldo 2009 (J. Banking & Finance) / 内閣府 祝日リスト(2025・2026)。
