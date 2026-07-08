# GOTOBI 長期M5 再検定: 事前登録gateで NOT_ROBUST（no-POST・2026-07-08）

Step: `GOTOBI_MULTI_YEAR_M5_PUBLIC_GET_AND_RETEST_NO_POST`
基準: [STRATEGY_GOTOBI_FIX_DRIFT_PREREGISTRATION_NO_POST_20260708.md](STRATEGY_GOTOBI_FIX_DRIFT_PREREGISTRATION_NO_POST_20260708.md)（凍結契約）

**重要: performance proof でも live 許可でもない（performance_proof_status=false /
live_ready=false）。raw price/spread/PnL/CSV row/ID は扱わない。凍結ルールに対し
**1回だけ採点**し、結果を見ての条件変更（post-OOS retuning）は行っていない。合格しても
解錠は paper-forward 検討のみ・「勝てる/収益性/edge証明」は断定しない。**

## 1. 取得（operator承認 public GET・認証なし）

- まず bounded プローブで GMO public FX klines の **M5 履歴は ~2023-11 開始**（それ以前は HTTP 404）と確定。
  既存窓（H1=15ヶ月/M5=3ヶ月）は API制約でなく export 側のハードコード選択だった。
- 承認のもと **USD_JPY M5 BID+ASK を 2023-11-01〜2026-07-07 JST 日次取得**（監査済み公開GET経路のみ・
  credential/env不使用・rate-limit安全・repo外CSV・**未commit**）。safe summary:
  - BID/ASK 各 **198,129 bars**・shared timestamp 198,129（完全整合）・**ask<bid 異常 0 件**。
  - coverage: 2023-11-01 00:00 〜 2026-07-07 23:55 JST（≈2.7年）。

## 2. 採点（凍結ルール・M5・03:00→09:55 JST・safe aggregate）

primary（exit 09:55）— **これが verdict**:

| leg | n | PF | 勝率 | 期待値符号 |
|---|---|---|---|---|
| GOTOBI | 166 | **0.9994** | 0.542 | NEGATIVE |
| NON_GOTOBI 対照 | 384 | 0.794 | 0.503 | NEGATIVE |
| GOTOBI 2.0×コスト | 166 | **0.977** | 0.542 | NEGATIVE |

- skipped gotobi days: 26（03:00足なし=主に月曜プレオープン）
- benchmark p90: **曜日層化置換 0.981** / 素の日ラベル置換 1.115 / 符号置換 **1.175**
- 期間3ブロック PF: **(0.825, 0.905, 1.506)**・件数 (55,55,56)
- 5対照の成否:
  - コスト込みPF>1 & 期待値非負: **False**（PF<1・NEGATIVE）
  - 非ゴトー対照超え: **False**（PF<1のため)
  - 符号置換 p90 超え（方向優位）: **False**（0.9994 < 1.175 = 方向を無作為化した方が良い）
  - 曜日層化ラベル置換 p90 超え: **True**（0.9994 > 0.981・微差）
  - 3ブロック全て PF>1: **False**（前2ブロックは<1）
- **VERDICT: `GOTOBI_EFFECT_NOT_ROBUST_REJECT`**

secondary（exit 09:50・参照のみ・verdict外）: ほぼ同一で NOT_ROBUST（GOTOBI PF 0.988 / stressed 0.964）。

## 3. 解釈（正直に）

- **凍結gateを通過しない → GOTOBI_FIX_DRIFT は本データ（≈2.7年・166件）では棄却。**
  base コスト（1.0×spread+0.5pip/side slippage）で **PF≈1.00（実質breakeven）**、
  2.0×コストで **0.977（マイナス）**。
- **方向優位なし**: 符号置換 p90（1.175）に負ける＝同じゴトー日の方向を無作為化した方が良い。
  見かけの数字はドリフトの「方向」ではなく exit形状/timing の副産物。
- **非持続**: ブロック別 (0.82,0.90,1.51) で優位は最終期に偏在。
- **微弱な"ゴトー日らしさ"は残る**: 非ゴトー(0.794)・曜日層化置換(0.981)を僅かに上回る。だが
  breakeven未満・非方向・コストで消滅・非持続で、**tradeable edge ではない**。
- **前回16件 PF 5.38 の正体判明**: 166件で PF≈1.00 へ収束。**16件は小標本の偶然**であり、
  事前登録の最小標本gate（≥90・3ブロック）が**その偽陽性を正しく却下**した。本Stepの本質的価値は
  「機構ベース仮説を事前登録し、十分な標本で正直に棄却し、小標本の魅力に飛びつかなかった」こと。

## 4. status と規律

- status: **GOTOBI_REJECTED_ON_MULTI_YEAR_M5**（NOT_ROBUST・棄却）。
- post-OOS retuning は行わない。同一データで entry/exit/定義を変えて再走しない。
  次に進むなら **新規事前登録 × 新規/独立データ or 別仮説**のみ。
- performance_proof_status=false / live_ready=false（不変）。live移行は不可。
- 取得CSVは repo外・未commit。本Stepでコード追加変更なし（採点は既 commit 済み凍結コードで実行）。

## 5. recommended next（実装は別Step・提示のみ）
- テクニカル4family・session構造・仲値ドリフトはいずれも robust edge に至らず。次の実質前進候補:
  1. **別の機構仮説**（月末リバランス/イベント構造/クロスアセット lead-lag 等）を、
     必要データを明示し**少数だけ事前登録**して同枠組みで検証。
  2. or **別通貨/別市場**での同一 gate 一般化確認（operator承認取得前提）。
- いずれも paper-forward 以降のみ。robust edge 不在の間は live 不可。
