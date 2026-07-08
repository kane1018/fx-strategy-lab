# 機構×時間軸×データ 実現可能性マップ（mechanism-first・no-POST・2026-07-09）

Step: `STRATEGY_MECHANISM_TIMESCALE_DATA_FEASIBILITY_NO_POST`
親: [runbook §6b](RESEARCH_RUNBOOK_NO_POST.md)（mechanism-first / data-dredging 禁止）

**docs のみ（実装・取得・backtest なし）。本書は「取得に進む前の整理」。
"日次データで何が試せるか"の列挙（=data-dredging）ではなく、**強い a-priori 機構を行に据え**、
各機構の「自然な時間軸／要求データ／no-credential 入手可否／検定力」を評価する（mechanism-first）。
performance_proof_status=false / live_ready=false。**

## 0. なぜ「整理が先」か

- 取得に飛びつくと、intraday 金利（no-credential で入手困難）に固執するか、逆に「取れる日次データで探す」罠に落ちる。
- 正しくは **機構ごとに自然な時間軸を当て、その時間軸で要求されるデータの入手性・検定力を評価**してから、
  取得の是非を決める。→ 下表。

## 1. 実現可能性マップ（行＝a-priori 強機構・列＝時間軸/データ/入手性/検定力/prior）

| 機構（a-priori） | 自然な時間軸 | 要求データ | no-credential 入手 | 検定力（既存/追加） | edge prior | 判定 |
|---|---|---|---|---|---|---|
| **金利差 / carry**（US-JP 利回り差 → USD/JPY） | **日次〜週次** | 日次 US/JP 利回り + 日次 USD/JPY（**数十年**入手可） | **高**（Treasury/FRED/Stooq 等・公開・無認証） | **高**（日次×数十年で十分） | **低**（教科書的・裁定済・低Sharpe） | **cleanにテスト可・ただし低prior** |
| **risk-sentiment**（equity/VIX → JPY 逃避） | 日次（intraday も） | 日次 equity index/VIX + 日次 USD/JPY | 高（公開・無認証） | 高（日次長期） | 低〜中（risk-off の円高は既知・裁定的） | cleanにテスト可・低〜中 |
| **月末リバランス** | 月次イベント | 月末暦 + 株式月次リターン（方向） | 高（公開） | 中（≈12/年 → 長期日次で件数確保） | 低〜中 | 長期日次で可・件数律速 |
| **cross-asset lead-lag**（金利/DXY が USD/JPY に分単位先行） | **intraday（分）** | **intraday** 金利/rate-futures M5 整合 | **低**（無認証で清潔な分足金利が困難） | 高（もし取得できれば） | 中（ただし within-spread リスク） | **データ壁でblocked**（既存M5契約） |
| carry の intraday 執行 | intraday | 同上 | 低 | — | 低 | 非推奨 |

## 2. この整理から分かること（重要な再枠組み）

- **日次（EOD）に落とすと、no-credential の壁がほぼ消える**: 日次 US/JP 利回り・USD/JPY・equity/VIX・暦は
  **公開・無認証・数十年**入手可能（例: US Treasury 公表値 / FRED の日次シリーズ / Stooq の日次CSV 等）。
  → **検定力（サンプル）も日次×数十年なら十分**。
- 代償: **日次で試せる強機構は"金利差/carry・risk-sentiment・月末"= いずれも教科書的・裁定済で edge prior が低い**。
  高 prior 候補（intraday microstructure の lead-lag）は逆に**分足データが no-credential で壁**。
- つまり **「清潔に取れるデータ」と「高い prior」はトレードオフ**。data-dredging を避ける限り、
  日次で回すのは「低 prior だが清潔・十分検定力」の機構になる。

## 3. 「整理 vs 取得」への回答

- **まず整理が正解**（本書）。その結果:
  - **intraday 金利（既存 M5 cross-asset 契約）への即取得は非推奨**（no-credential で清潔な分足金利が困難＝blocked のまま）。
  - 代わりに **日次に再枠組みすれば、公開・無認証・長期のデータで"金利差/carry"機構を清潔かつ十分検定力で1回採点できる**
    （ただし **prior は低い**＝おそらく null。しかし blocked ではなく実際に検定可能）。
- したがって「取得に進む」なら、対象は **intraday 金利ではなく、日次の公開・無認証データ**（US/JP 利回り・USD/JPY・
  必要なら equity/VIX）にすべき。これは operator 承認の public GET で清潔に取得可能（credential 不要）。

## 4. mechanism-first の維持（data-dredging 回避の担保）

- 日次に落としても、**機構を1つだけ事前登録**し、単一 variant・スキャン禁止・placebo（系列時間反転）・
  contemporaneous 対照・sign-permutation・walk-forward・最小標本・post-OOS retuning 禁止を課す。
- 「日次データを見て何が効くか探す」ことは**しない**。行（機構）を先に固定してからデータを取る。

## 5. 推奨（次の1点）

- **(推奨) 日次・公開・無認証データで "金利差/carry → USD/JPY" を mechanism-first で事前登録し、
  operator 承認の public GET で取得 → 標準gate（日次版 window）で1回採点。**
  期待は正直「低 prior＝null の公算」だが、**blocked を回避して清潔・十分検定力で決着**できる。
  既存の [M5 cross-asset 契約](STRATEGY_CROSS_ASSET_RATES_LEADLAG_PREREGISTRATION_NO_POST_20260709.md) は
  **intraday 版として保留のまま**、日次版を新規事前登録として起こす。
- **(代替) closeout 維持** — 低 prior に労力を割かない判断も正当。
- どちらでも **live 不可**（robust edge 未確認・不変）。

**Sources（safe）**: 日次公開データの存在（US Treasury 公表利回り / FRED 日次シリーズ / Stooq 日次CSV 等・無認証）。
過去の金利差/carry 効果は減衰・裁定前提で「検証候補」として扱う。
