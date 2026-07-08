# GOTOBI_FIX_DRIFT 事前登録(凍結contract)— no-POST・2026-07-08

Step: `GOTOBI_FIX_DRIFT_PREREGISTRATION_NO_POST`

**本書は「契約(pre-registration)」であり、複数年/長期 M5 データを見る前に評価ルールを凍結する
ためのもの。以後の retest(`GOTOBI_MULTI_YEAR_M5_PUBLIC_GET_AND_RETEST_NO_POST`)は本書を
参照し、ここで固定した条件を後から変更しない。データは凍結ルールに対し1回だけ採点する。**

**重要: performance proof でも live 許可でもない(performance_proof_status=false /
live_ready=false)。raw price/spread/PnL/CSV row/ID は一切扱わない。本Stepは docs のみ
(コード変更・取得・public GET・backtest再実行なし)。合格しても解錠するのは paper-forward
検討のみで、live化ではない。「勝てる/収益性あり/edge証明済み」とは断定しない。**

## 0. freeze 宣言

- 本書コミット以降、entry/exit・ゴトー日定義・コスト計上・対照・最小標本・合格基準は**凍結**。
- retest は本書を唯一の基準として実行。**結果を見てから条件を変えない(post-OOS retuning 禁止)**。
- 失敗しても同一データで条件を変えて再走しない。次は**新規事前登録 × 新規/独立データ**のみ。

## 1. 仮説(動機であり証明対象ではない)

- **機構(動機)**: 実効ゴトー日に、日本の輸入企業のドル決済需要が 9:55 JST 仲値(TTM)へ向かい、
  USD/JPY が概ね 03:00→09:55 JST に上方ドリフトしやすい(arXiv 2301.13204 / NBER w22820)。
- **検証する**: (a) 03:00→09:55 long のコスト込み符号/収益方向、(b) ゴトー日特異性、
  (c) 方向(long)の優位、(d) 期間持続性。
- **検証しない/断定しない**: 機構そのもの(実需フローは観測不能=動機であり証明対象でない)、
  事前登録外の時刻最適化、他通貨、"勝てる/収益性/edge証明/live化"。
- 陽性=「本テスト条件下でドリフトと整合し robust」まで。陰性=「本データではコスト込みで検出不能」。

## 2. 対象(固定)

- symbol = **USD_JPY 固定**(機構が JPY 輸入特異。他通貨は別仮説)。
- timeframe = **M5 primary 固定**(09:55 ちょうどに決済できる粒度)。
- **M1 は今回含めない(後回し)**。仲値直前 exit / 仲値後リバーサル / 微 timing 用の任意精緻化。
- **H1 は判定から除外(reference-only-unsuitable)**。exit 足が 10:00 JST に閉じ仲値後を含むため。

## 3. entry / exit(固定)

- **primary(単一)**: entry = **03:00 JST の足終値**でロング、exit = **09:55 JST の足終値**で決済。
- **bar 選択規則**: entry=「close 時刻 ≥ 03:00 の最初の足」、exit=「close 時刻 ≥ 09:55 の最初の足」。
  M5 では entry=開始02:55/終値03:00 足、exit=開始09:50/終値09:55 足(=仲値ちょうど)。
- **03:00 足が無い日(月曜プレオープン等)はスキップ(捏造しない)**。skip 件数を報告。
- **verdict は primary 単一で計算**。
- **secondary(任意・最大2点)**: exit ∈ {09:50, 09:55} のみ。採用する場合も (i) primary は 09:55、
  (ii) grid は**全点合格**を要求 or percentile を p90→p95 に厳格化、(iii) 試行数を多重検定台帳(§8)に記録。
  **最良点を後から primary に採用することは禁止**。

## 4. ゴトー日定義(固定)

- **基準日 = {5, 10, 15, 20, 25, 末日(=当月最終日)}**。※現行コードの「30 日」枠は
  **末日採用へ変更**して retest で実装(31 日月の真の末日を拾うため)。
- **日本銀行営業日への前倒し**: 基準日が銀行営業日でない(土日・国民の祝日〈振替含む〉・
  年末年始 12/31–1/3 銀行休業)場合、**直前の銀行営業日**へ前倒し。
- **祝日表**: 出典=内閣府 国民の祝日 + 銀行休業慣行(12/31・1/2・1/3)。retest では
  **取得 range 全体をカバーする静的表**をこの出典規則で生成し凍結。
- **skip 規則**: 03:00 足なし日はスキップ、skip 件数を safe count で報告。

## 5. 約定・コスト(固定)

- **leg 別 crossing-side spread 計上**: long は entry で ask(entry 足 spread)・exit は bid(追加なし);
  short(符号置換側)は exit で ask(**exit 足 spread**)。→ 現行の short 過小計上を retest で是正。
- **slippage = 0.5 pip/side(0.005)を両 fill に**。
- **cost stress = 2.0×**(primary 判定は 2.0× 生存を要求)。1.0/1.5/2.0 を併記。
- **bar-level spread 近似の限界**: spread は per-bar(BID/ASK 足 close 差)で tick-level ではない。
  仲値時(9:55)の一時的スプレッド拡大は5分足で捕捉不足の可能性 → コストは近似・保守寄りと明記。
  任意で **fix-time spread stress(exit 足 spread に追加倍率)を secondary** に用意可。

## 6. 対照群(全て primary 判定に含める・unanimous)

各対照が否定する対立仮説を明記:
1. **コスト込み収益方向**: gotobi long **PF>1 かつ 期待値符号 NON_NEGATIVE @2.0×**。
2. **非ゴトー日対照**: gotobi PF > 非ゴトー PF(「窓が"いつでも"儲かるだけ」を否定=日特異性)。
3. **符号置換 p90**: gotobi PF > sign-perm p90(「方向優位なし・ボラ構造で説明」を否定)。
4. **曜日層化ラベル置換 p90**: gotobi PF > 層化置換 p90(「ゴトー日の曜日偏りで説明」を否定)。
   ※非層化ラベル置換は secondary/reference。
5. **期間ブロック安定性**: 事前宣言した **3 ブロック以上の全てで PF>1**(「一部期間集中/非持続」を否定)。

## 7. 最小標本・合格基準(固定)

- **最小標本**: gotobi **≥ 90 件(理想 ≥150)** かつ **3 ブロック以上・各 ≥ 25 件**。
  実現データがこれ未満なら結果は **INSUFFICIENT_SAMPLE**(合格にしない)。
- **合格 = `RETEST_PASSED_CANDIDATE_FOR_PAPER_FORWARD`**: §6 の 5 対照 全成立 + 最小標本充足 +
  post-OOS retuning なし。**解錠するのは paper-forward 検討のみ**。
- **失敗ラベル**: `NOT_ROBUST` / `INSUFFICIENT_SAMPLE`。
- いずれの結果でも **performance_proof_status=false / live_ready=false を維持**。
  合格は「収益性/edge の証明」でも「live 許可」でもない。

## 8. 多重検定・後出し防止(固定)

- **多重検定台帳**: retest doc に、走らせる全 config(entry/exit 時刻・日付定義・対照 variant・
  ブロック分割)と試行数 k を**取得前に**列挙。**primary は単一**、verdict はそれのみ。
  secondary は厳格閾値(p95 or 全点合格)+ k を反映。
- **post-OOS retuning 禁止**: 長期データは凍結ルールに対し **1 回だけ採点**。失敗しても同一データで
  entry/exit/定義を変えて再走しない。次は新規事前登録 × 新規/独立データのみ。
- **凍結手段**: 本書(日付 + 実値)を fetch 前に commit。retest はこの commit を参照。interim peeking 禁止。

## 9. データ実現可能性(retest 前に要解決)

- **既存窓は API 制約でなく運用選択**: H1 export は `WINDOW_START_UTC=2025-04-01` を**ハードコード**で
  選び日次取得。M5 の 3 ヶ月も同様の選択窓(データ量抑制)。→ **GMO public FX klines の真の履歴深度は未確認**。
- したがって「複数年 M5」の可否は **GMO FX klines の最古提供日に依存**し、現時点で不明。
  retest 前に (a) operator の把握 or (b) operator 承認の小プローブ で**取得可能な最古日**を確定する。
- **volume 注意**: M5 は H1 の約12倍の bar 数。日次取得 × BID+ASK × 長期 = 相応の request 数・時間。
- **代替**: GMO public で十分な深さが得られない場合、別データ源(認証/有償など)は
  no-credential 方針と衝突しうる大きな operator 判断となるため、別途相談。

## 10. retest step が実装すべきコード変更(本書で凍結・retest で実装)

1. `_trade_pnl` を **leg 別 crossing-side spread** に(short は exit 足 spread)。
2. ゴトー日暦の「30 枠」を **末日** に。祝日表を取得 range に合わせ生成。
3. **曜日層化ラベル置換 p90** を追加し primary 判定へ。
4. 期間安定性を **halves → N ブロック(既定3)全て PF>1** に。
5. 最小標本 (≥90 / 3 ブロック ≥25) と verdict ラベル
   (`RETEST_PASSED_CANDIDATE_FOR_PAPER_FORWARD` / `NOT_ROBUST` / `INSUFFICIENT_SAMPLE`)。
- いずれも**機構中立**の改修で、既存 16 件(現 M5)に対する再採点は行わない(no peeking)。

## 11. 次 step の operator 承認項目(fetch 前に必須)

- **public GET(認証なし)実行の明示承認**: GMO public klines、**USD_JPY / M5 / BID+ASK 両方**。
- **取得 date range**(operator 指定の開始〜終了)。**取得可能な最古日の確認**(§9)。
- **repo 外・gitignore の local CSV 保存**(`~/Desktop/fx_strategy_lab_historical_data/`)、**commit しない**。
- 監査済み public GET 経路のみ・credential/env 不使用・rate-limit・日次分割の確認。
- 祝日表を取得 range に合わせ凍結出典から拡張する承認。
- 本テストは **confirmatory 限定・live/performance step ではない**ことの operator 了解。
- 報告は **safe aggregate のみ**(raw row/price/spread/PnL 非表示)。

---
**freeze footer**: 本書は GOTOBI_FIX_DRIFT の評価契約。retest は本 commit を基準に採点する。
コード変更・取得・public GET・backtest 再実行は本 Step では行っていない。
