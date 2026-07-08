# Operator Pre-Trade Caution Briefing — 設計（凍結）・no-POST・2026-07-09

Step: `OPERATOR_PRE_TRADE_CAUTION_BRIEFING_DESIGN_NO_POST`
CASE: `OPERATOR_DECISION_SUPPORT_RESCOPED_TO_WARNING_FIRST_CAUTION_BRIEFING_NO_POST`

**本書は設計の凍結（docs のみ）。実装・UI・API・dashboard・broker 接続・data fetch・backtest 再実行・
paper・live・POST は一切行わない。raw price/spread/PnL/size・account/order/transaction/position/trade ID・
API key/secret/signature/header/.env・broker raw request/response は表示しない。
performance_proof_status=false / live_ready=false / unattended_live_supported=false（維持・不変）。**

**これは売買判断を AI に代行させる設計ではない。** operator が最終判断（ENTRY_BUY / ENTRY_SELL / HOLD）を
行う"前"に、AI/システムが read-only・safe-aggregate の範囲で**警告・文脈・NO_ACTION 理由・過去棄却との照合・
リスク確認**を提示する、**warning-first / PULL 式**の caution briefing の設計である。

## 0. 一言定義

`OPERATOR_PRE_TRADE_CAUTION_BRIEFING` は、operator が売買判断を行う前に、AI/システムが read-only /
safe-aggregate で**警告・文脈・NO_ACTION 理由**を提示する **PULL 式 briefing** である。

- これは**売買推奨ではない**。
- これは**自動売買エンジンではない**。
- これは**edge 証明ではない**。
- これは**permission ではない**。

briefing の目的は**利益ではなく、operator の過信・後付け最適化・過剰売買を防ぐ規律・摩擦・文脈提示**。

## 1. 基本原則

- **warning-first**（警告・禁止・NO_ACTION を最上位に）。
- **PULL 式**（operator が売買を検討し始めた時に自分で要求）。**system は好機を PUSH しない**。
- **NO_ACTION default**（既定は「様子見」。行動は例外）。
- **no-flag ≠ permission**（警告ゼロは GO ではない・毎回明示）。
- **no validated edge / not advice を毎回表示**（`current_strategy_status=NO_ROBUST_EDGE_FOUND_IN_TESTED_SCOPE`）。
- **最終判断は operator**。ENTRY_BUY / ENTRY_SELL / HOLD は **operator safe label のまま**。**AI は ENTRY を代行しない**。
- **confidence / alpha / expected profit / win-rate を出さない**。
- **direction / recommendation を出さない**（"今は買い/売り"を含む）。
- **briefing は執行しない**（SERE を起動しない・人間が必ず挟まる）。
- **実 POST は別 Step**（current-turn exact confirmation）。
- **max one POST / no retry / no repost は不変**。

## 2. 目的・非目的・利用境界

- **目的**: 判断"前"の read-only な警告・文脈・NO_ACTION・棄却照合・リスク確認の提示。
- **非目的**: 売買判断の代行／方向提示／収益予測／自動執行／edge 主張／permission 付与。
- **利用境界**: read-only・safe-aggregate のみ。broker への runtime private GET を行わない
  （§8 の通り、briefing は**内部 safe 状態**を読む。真の broker 照合は別の operator-gated read-only Step）。

## 3. 出してよい情報（read-only・safe-aggregate のみ）

- 恒久 disclaimer（no validated edge / not advice / no-flag ≠ permission / 最終判断は operator）。
- NO_ACTION status（既定＝様子見・該当理由カテゴリ）。
- hard-stop status（該当有無：spread 異常カテゴリ・event 近接・uncertainty 高・budget 超過 等）。
- tested-scope 判定（inside / outside・safe label）。
- rejected-ledger 照合（"この状況は棄却済 H-XX に類似"の safe label）。
- current exposure safe summary（内部 safe label：例 FLAT / ONE_POSITION_OPEN）。
- active / pending order safe status（safe count / safe label）。
- daily risk budget safe status（safe 割合カテゴリ・上限 safe label）。
- market-state descriptive labels（trend/range・volatility/spread/liquidity/time-of-day **カテゴリ**・**方向なし・価値判断なし**）。
- event proximity warning（safe label）。
- risk warnings（safe category）。
- mandatory stop conditions（列挙・safe label）。
- safe execution readiness（**記述のみ**：例 READY_LABEL / NOT_READY_REASON_CATEGORY）。
- uncertainty notes（不確実性・未検証領域の記述）。
- forbidden claims reminder（禁止表現の再掲）。
- operator final confirmation prompt（decision＝operator safe label を明示的に入力させる）。
- operator decision reason log prompt（判断理由を記録させる）。

## 4. 出してはいけない情報

BUY 推奨 / SELL 推奨 / ENTRY_BUY・ENTRY_SELL・HOLD の代行 / `AUTO_PREVIEW_SIGNAL_BUY/SELL` /
confidence score / alpha score / expected profit / win-rate prediction / "今は買い" / "今は売り" /
"edge あり" / "勝てる" / "live_ready" / performance_proof_status=true に見える表現 /
**no flag を GO と解釈させる表現** / favorable・good setup・opportunity 等の**価値判断語** /
**過去の勝ちトレード参照** / 他者・SNS 意見 / raw price / raw spread / raw PnL / raw size /
account・order・transaction・position・trade ID / credential・header・signature・.env 内容。

## 5. 推奨レポート順序（warning-first・固定）

1. **恒久 disclaimer**（no validated edge / not advice / no-flag ≠ permission / 最終判断 operator）。
2. **NO_ACTION status**（既定＝様子見・該当理由）。
3. **hard-stop 該当有無**。
4. **tested-scope / rejected-ledger 照合**。
5. **risk / exposure / budget safe status**。
6. **market-state 記述**（方向なし・価値判断なし）。
7. **pre-ENTRY checklist**。
8. **uncertainty notes**。
9. **operator final decision and reason prompt**。

（色/強調は**警告に割り当て**、"好機"を演出しない。方向・スコアは一切出さない。）

### 5.1 pre-ENTRY checklist（例・operator が確認）
- [ ] disclaimer を読んだ（no edge / not advice / no-flag ≠ permission）。
- [ ] NO_ACTION 該当理由を確認した。
- [ ] hard-stop 条件に該当していない。
- [ ] tested-scope / rejected 照合を確認した（棄却領域か・未検証領域か）。
- [ ] risk budget / exposure が上限内。
- [ ] **この判断は自分（operator）の裁量であり、system の validated edge に基づくものでない**。
- [ ] 決定理由を記録する。

## 6. Daily operation flow（PULL 式・warning-first）

1. **operator が売買検討を始めた時だけ PULL で briefing を要求**（system は PUSH しない）。
2. read-only safe status（**内部 safe 状態**・§8）。
3. caution briefing 生成（§5 の順序）。
4. NO_ACTION / hard-stop 確認。
5. tested-scope / rejected-ledger 照合。
6. risk / exposure / budget 確認。
7. market-state 記述確認（方向なし）。
8. **operator が自分で ENTRY_BUY / ENTRY_SELL / HOLD を判断**。
9. **operator が判断理由を記録**。
10. 実 POST が必要なら**別 Step で current-turn exact confirmation**。
11. **max one POST / no retry / no repost**。
12. post-trade read-only confirmation。

**明示**: 3〜7 で警告がゼロでも「GO」ではない（no-flag ≠ permission）。briefing は方向を持たない。

## 7. tested-scope / rejected-ledger 照合設計（signal 化を防ぐ）

- operator の想定文脈（記述ラベル：trend/range・vol/spread カテゴリ・time-of-day・event 近接 等）を、
  [HYPOTHESIS_REGISTRY_NO_POST.md](HYPOTHESIS_REGISTRY_NO_POST.md) の **rejected ledger（H-01..H-10）**と
  **記述レベルで照合**し、類似があれば **"この状況は棄却済 H-XX に類似（NO_ROBUST_EDGE）"** の caution を出す。
- **signal 化の禁止**：照合は**caution のみ**を生む。「棄却に類似 → だからトレードするな/しろ」も、
  「棄却に非類似 → だから GO」も**出さない**。
- **"outside tested scope" の扱い**：一致が無い場合は **"未検証領域（unknown・no validated edge・
  no-flag ≠ permission）"** と明示する。**"非棄却＝許可"と読ませない**（live FX の大半は tested scope の外で、
  検証済み edge は存在しない）。
- 照合は**決定論的・記述的**（confidence/score を持たない）。

## 8. hard-stop / risk / exposure / budget の扱い（no runtime private GET）

- briefing は **内部 safe-aggregate 状態**（system が保持する safe label / safe count / safe category）を読む。
  **runtime での broker private GET は行わない**（不変則）。表示は「internal state（live broker 照合ではない）」と明示。
- **真の broker 照合が必要な場合は、briefing の外の別 operator-gated read-only Step**に分離する
  （それ自体も no-private-GET 規律の下でのみ）。
- **hard-stop 条件**（該当時は NO_ACTION を強制表示）：spread 異常カテゴリ / event 近接 / uncertainty 高 /
  daily risk budget 超過 / exposure 上限 / safe execution NOT_READY / 内部状態が想定外。
- risk budget / exposure は **safe カテゴリ・safe 割合**でのみ表示（raw 値・ID を出さない）。

## 9. market-state descriptor の扱い

- **記述ラベルのみ**：trend/range・volatility カテゴリ・spread カテゴリ・liquidity カテゴリ・time-of-day・
  event 近接。**方向（up/down・buy/sell）も価値判断（good/favorable）も出さない**。
- **決定論的・safe-label**。confidence/score を持たない。**regime を live 判断入力にしない**（研究ラベル用途）。
- descriptor は "状態の記述" であって "行動の示唆" ではない。

## 10. uncertainty notes / forbidden claims

- uncertainty notes：不確実性の所在・**未検証領域**・データ/前提の限界を記述（confidence の代替）。
- forbidden claims reminder：§4 の禁止表現を毎回再掲し、混入を防ぐ。

## 11. operator final decision & reason log

- briefing 末尾で **operator が decision（BUY/SELL/HOLD＝operator safe label）と理由を明示入力・記録**。
- 目的：**監査証跡**＋**後付け合理化の抑止**（後日レビューで「結果を見て理由を変えていないか」を検証可能に）。
- decision と reason は **operator のもの**であり、AI は生成・提案しない。

## 12. SERE との関係

- **briefing = read-only / non-execution / context and caution**。
- **SERE（Safe Execution & Risk Engine）= execution / risk / governance container**。
- 今回は **briefing の design only**。**briefing は SERE を起動しない**（人間が必ず挟まる）。
- SERE 実行は**別 Step**。SERE でも **operator-gated / max one POST / no retry / no repost** を維持。
- auto-trade / unattended live は**対象外**。

## 13. 実 POST 別 Step 分離

- briefing は**執行しない**。実 POST が必要な場合は、必ず**別 Step**で
  **current-turn exact confirmation → max one POST → no retry / no repost → post-trade read-only confirmation**。
- briefing から実 POST への"直行動線"は作らない（人間の明示 Step を挟む）。

## 14. operator 確認境界（autonomy boundary）

- **AI 自律可**：内部 safe 状態の記述・NO_ACTION 判定・rejected-ledger 照合・briefing 生成・記録。
- **operator confirmation 必須**：**あらゆる live POST（max one・no retry・no repost）** /
  あらゆるパラメータ・ルール更新 / データ取得 / **DEFER 層（AUTO_PREVIEW_SIGNAL/confidence/live budget/auto-trade）の有効化** /
  真の broker 照合 read-only Step。
- **ENTRY_BUY / ENTRY_SELL / HOLD は operator safe label のまま。AI は AUTO_PREVIEW_SIGNAL を出さない（DEFER）。**

## 15. 採用条件

read-only / safe-aggregate のみ / PULL 式 / warning-first / NO_ACTION default / no-flag ≠ permission /
no validated edge 表示 / not advice 表示 / direction なし / confidence なし / recommendation なし /
rejected-ledger 照合あり / operator 判断理由記録あり / 実 POST 別 Step 分離 /
performance_proof_status=false 維持 / live_ready=false 維持 / unattended_live_supported=false 維持 /
runtime private GET なし（内部 safe 状態を使用）。

## 16. 停止条件（この briefing 機能自体・該当で停止・見直し）

- 出力が BUY/SELL 推奨に読める。
- no flag が permission と解釈される。
- operator が briefing を GO サインとして扱う。
- confidence 的表現が混入する。
- favorable / good setup / opportunity 等が混入する。
- raw / ID / value / credential exposure の兆候。
- continuous dashboard 化で過剰監視・過剰売買が起きる。
- system PUSH 通知化される。
- 実 POST 確認 Step が省略される。
- recent performance で即時ルール変更される。
- regime 変化で即時パラメータ変更される。

## 17. Future implementation notes（本 Step では実装しない）

- 実装時も **read-only・safe-aggregate・no runtime private GET・no-POST** を厳守。
- 実装は **briefing generator（内部 safe 状態 + 決定論的 descriptor + NO_ACTION rule + rejected matcher +
  checklist + disclaimers → safe-aggregate 出力）**。**PULL 式・非執行・SERE 非起動**。
- **DEFER（validated edge ＋ operator 承認まで作らない）**：AUTO_PREVIEW_SIGNAL_BUY/SELL / confidence・uncertainty
  スコア / live research budget / auto-trade / regime を live 判断入力にすること。
- 実装着手には **operator の明示承認＋docs-only 設計（本書）を基準**とすること。

---
**freeze footer**: 本書は operator pre-trade caution briefing の設計基準。実装・live・POST・fetch は本 Step では
行っていない。max one POST / no retry / no repost / official settlement route 分離 / generic close 禁止 /
default-deny hard guard は不変。performance_proof_status=false / live_ready=false /
unattended_live_supported=false。
