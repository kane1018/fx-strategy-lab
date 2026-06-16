# M5 単純テクニカル戦略 研究フェーズ総括

GMO Public API の実価格を使った **read-only ペーパー検証**で、M5 / current_cost 環境の
単純テクニカル戦略に頑健な正エッジがあるかを調べた研究フェーズの総括。

> 実注文・実決済・Private API 接続・APIキー使用は一切なし。すべて仮想売買（in-memory DB
> でのリプレイ）。`analysis_exports/` の生成物は gitignore。

評価プロトコルの詳細は [fx_strategy_evaluation_protocol.md](fx_strategy_evaluation_protocol.md) を参照。

## 1. 研究フェーズの目的

- GMO Public API klines (BID) を read-only で取得し、M5 戦略をペーパー（仮想）検証した。
- 実注文・Private API・APIキーは使用していない。
- M5 / current_cost 環境で、単純な単一構造のテクニカル戦略に **複数期間を通じた頑健な
  正エッジ** があるかを、同一15窓プロトコル（IS 10窓 + OOS 5窓）で確認した。
- 目的は「勝てる戦略を無理に探す」ことではなく、過剰最適化を避け、再現可能な検証基盤の
  うえで各戦略を採用/研究用/撤退に分類すること。

## 2. 固定条件

| 項目 | 値 |
| --- | --- |
| data source | GMO Public API klines (BID) |
| mode | read-only paper（仮想売買・in-memory DB） |
| timeframe | M5 |
| cost_scenario | current_cost |
| spread_pips | 1.2 |
| slippage_pips | 0.2 |
| stop_loss_pips / take_profit_pips | 30 / 60 |
| exit_policy | baseline（反対シグナル + SL/TP） |
| symbols | USD_JPY / EUR_JPY / GBP_JPY / AUD_JPY |
| continuous replay | 有効 |
| real_order | No |
| private_api_used | No |
| api_key_used | No |

## 3. 検証した戦略一覧

| 戦略 | 分類 | 理由 |
| --- | --- | --- |
| rsi_reversal M5 | 研究用ベースライン | 15窓で薄くプラスだが、OOS弱く実運用候補ではない。比較基準として保存 |
| ADX30 filter | 却下 | prior10で改善も OOS非再現（過剰最適化の疑い） |
| breakout M5 | 撤退 | 15窓で大幅マイナス、OOS全滅、rsiの負け窓を補完せず |
| Bollinger M5 | 撤退 | RSIより全指標で劣後、SLテール重い |
| market-structure M5 | 撤退 | 全戦略中最悪、取引数最多、low DEでも負け |
| rsi_reversal M15 baseline | 撤退寄りフラット | 取引数は減るが合計損益マイナス、OOS弱い |
| rsi_reversal M15 scaled-risk (SL50/TP100) | 撤退 | SL率は下がるが損益・PF・OOS・high_de損失が悪化 |
| regime予測可能性診断 | 価値なし/打ち切り | OOS balanced accuracy がランダム以下、high_de recall が低い |
| market-state 診断 | 補助分析基盤 | 戦略ではなく、勝ち負けと相場状態を突き合わせる分析基盤として有用 |
| 単純テクニカル＋regimeフィルタ | 研究終了 | 上記すべての結論として、本路線は正式にクローズ |

## 4. 主要結果の比較表（15窓）

| strategy | 期待値中央値 | PF中央値 | プラスwindow数 | 合計損益 | 最大DD最大値 | 分類 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| rsi_reversal | +0.0164 | 1.016 | 8/15 | +56.95 | 65.46 | 研究用ベースライン |
| breakout | -0.1123 | 0.837 | 3/15 | -628.52 | 124.66 | 撤退 |
| Bollinger | -0.0667 | 0.883 | 3/15 | -273.8 | 75.48 | 撤退 |
| market_structure | -0.0966 | 0.78 | 1/15 | -804.43 | 162.89 | 撤退 |

補足:

- **ADX30 filter**: rsi_reversal にトレンド回避（ADX≥30で新規見送り）を足した A/B。prior10 では
  中央値が改善したが、未使用 OOS 5窓では baseline より悪化（期待値中央値・PF・プラス窓・改善窓
  すべて劣化、見送り率は高い）。in-sample の改善が再現せず **却下**。閾値の追加探索もしない。
- **market-state 診断**: rsi/breakout の (date×symbol) 別勝敗を market state 指標
  （日次レンジ、ATR相当、direction efficiency=DE、M5反転回数、コスト比）と突き合わせた診断。
  rsi は低DE（チョップ）で勝ち高DE（トレンド）で負け、breakout はその逆。both_lose 日に明確な
  単一特徴はなく、単一 no-trade フィルタでの分離は弱い（最大の DE でも相対分離18%・分布重複）。
  戦略ではないが、今後の判断材料となる **補助分析基盤** として保存する。

## 5. 共通して見えた構造

- 平均回帰系（rsi / Bollinger）は、低DE（チョップ）相場では一部エッジがある
  （low DE で期待値プラス、PF>1）。
- しかし、高DE・トレンド日で **SLテール**が重く、平均回帰完成時の利益をほぼ相殺する。
- 黒字源は一貫して「反対シグナル決済（平均回帰の完成）」、損失源は一貫して「トレンド日／
  ノイジー緩トレンド日の SL 到達」。
- breakout は rsi の負け窓を補完しなかった（rsiが負けた7窓でbreakoutがプラスは2窓のみ）。
- 入口指標を RSI → Bollinger → market-structure と替えても、SLテール問題は解決しなかった。
  むしろ market-structure は新スイング極値で過剰に発火し、取引数が最多・損益が最悪となった。
- ADX/DE 系のトレンド除外は OOS で非再現、または分離力が弱い。
- M5 では取引回数が多く、current_cost（spread 1.2 + slippage 0.2）の影響が相対的に大きい。

## 6. 最終判断

```text
M5 / current_cost における単純単一構造のテクニカル戦略研究は一区切りとする。
rsi_reversal M5 は研究用ベースラインとして保存する。
ADX30 / breakout / Bollinger / market-structure は主検証から外す。
今後は、入口条件の追加探索ではなく、検証基盤の整備、高時間足、低コスト条件、
または別市場の検証へ進む。
```

### 追補: 高時間足とregime予測（フェーズ・クローズ）

- M15 baseline（SL30/TP60）も M15 scaled-risk（SL50/TP100）も撤退〜フラットで、M5 を上回らず。
  律速はトレンド日（high DE）の損失で、時間足にも SL/TP スケールにも不変と確認。
- クローズ診断（`regime_predictability_diagnostics.py`, 売買なし）で、当日 DE 区分を前日までの
  情報で OOS 予測できるかを検証 → 全ルールの OOS balanced accuracy ≤ ランダム(0.333)、
  high_de はほぼ予測不可。**未来情報なしの no-trade/regime切替は機能しにくい**。
- 以上より、**M5/M15 の単純テクニカル＋regimeフィルタ路線は一区切り**。`rsi_reversal M5` を
  研究用ベースラインとして保存し、次は検証基盤整備・低コスト/別市場・別アプローチを検討する。

## 7. 今後やらないこと

- M5 の単純入口戦略を追加で増やさない。
- RSI / Bollinger / market-structure のパラメータ探索をしない。
- ADX / DE フィルタの閾値探索をしない。
- SL/TP の最適化にすぐ入らない。
- 「勝てるまで条件を重ねる」ことをしない。
- 実注文・Private API には進まない。

## 7b. 研究フェーズの正式クローズ（2026-06-16）

単純テクニカル＋regimeフィルタの研究フェーズを **正式にクローズ**する。確定事項:

- `rsi_reversal M5` のみを **研究用ベースライン**として保存（比較基準）。
- M15 RSI系（baseline / scaled-risk）は **撤退**。高時間足での RSI 救済探索は行わない。
- ADX30 / breakout / Bollinger / market-structure は **再探索しない**。
- regime予測可能性診断は **価値なし/打ち切り**（前日情報で当日regimeをOOS予測できない）。
- no-trade / regime切替は **現時点で売買ロジックへ入れない**（未来情報なしでは機能しにくい）。
- 予測市場・外部イベントデータも **まだ売買ロジックへ入れない**。

## 7c. 今回の研究フェーズでこれ以上やらないこと

- RSIパラメータの追加探索
- SL/TPの追加探索
- M30/H1で同じRSIロジックを救うための探索
- ADX/DE/no-tradeフィルタの売買ロジック組み込み
- breakout / Bollinger / market-structure の再探索
- 予測市場データの拙速な売買ロジック化
- 実注文 / Private API / APIキー利用

## 8. 次フェーズ（戦略追加ではなく検証基盤・レポート標準化へ）

次フェーズは新しい戦略探索ではなく、検証基盤とレポート標準化に移る。詳細な設計は
[fx_report_standardization_plan.md](fx_report_standardization_plan.md) を参照。

優先事項:

1. `analysis_exports/` の出力構造標準化
2. manifest / warnings / summary / metrics の共通化
3. 研究結果を比較しやすい report schema の固定
4. read-only / no real order / no private api の安全表示の標準化
5. 将来のレポート一覧UI / run詳細UIに備えたデータ構造整理
6. E2E導入候補フローのdocs化（導入自体はまだ行わない）

まだ行わないこと: E2Eツール導入 / Playwright・Cypress 追加 / UI実装 / 実注文 / Private API接続。

（補足: コストモデル精緻化や低コスト/別市場の検証は、基盤標準化のあとに別フェーズとして検討する。
着手済みなのは標準定義・固定条件・安全メタデータ・3分類判定の `scripts/fx_eval_common.py` 集約まで。）
