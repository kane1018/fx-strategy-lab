# Unattended Gap Assessment — operator-gated cycle と無人自動化の差分（no-POST）

Step: `STEP_6G_PC_OX_Z_OPERATOR_GATED_CYCLE_CLOSEOUT_TO_SUPERVISED_AUTO_LIVE_PREVIEW_NO_POST_C` Phase 2
記録日: 2026-07-08。前提となる cycle 事実は
[LIVE_OPERATOR_GATED_CYCLE_CLOSEOUT_20260708_NO_POST.md](LIVE_OPERATOR_GATED_CYCLE_CLOSEOUT_20260708_NO_POST.md)。

本書は評価のみであり、operator confirmation の削除・自動代替・RiskPolicy緩和を
実装するものではない。`unattended full auto completed = false` は不変。

## 1. Gap matrix

owner分類: `operator`（人間が担った）/ `code`（実装済み自動）/
`future runner`（将来自動化候補）/ `unsupported`（自動化対象外・当面禁止）。

| # | 判断・作業 | 今回のowner | 自動化リスク | 自動化前に必要なguard | 到達段階の推奨 |
|---|---|---|---|---|---|
| 1 | signal決定（ENTRY_BUY） | operator | 高（誤シグナル=誤発注） | paper実績・preview実績・kill switch・シグナル品質基準 | paper → supervised preview（実装済み: AUTO_PREVIEW_SIGNAL_*）→ 当面 operator 最終決定を維持 |
| 2 | entry current-turn exact confirmation | operator | 最高（実資金write許可そのもの） | 削除・自動生成は当面 unsupported。縮約するなら別途の明示的再開方針Stepが必須 | unsupported（維持） |
| 3 | settlement current-turn exact confirmation | operator | 最高（同上） | 同上 | unsupported（維持） |
| 4 | sealed local value（symbol/size）供給 | operator | 高（サイズ誤り=想定外リスク量） | sealed channel は実装済み。値の自動決定は riskポリシー接続と上限guardが前提 | operator供給を維持（fileは再利用可） |
| 5 | spread block後の再実行タイミング判断 | operator | 中（待つだけなら損失は市場リスクのみ） | spread/市場時間帯の safe label 判定は実装済み。再実行スケジューリングは future runner 候補 | paper runner でcycle再試行ポリシーを検証してから |
| 6 | 建玉保有中のリスク監視・wait vs manual close 判断 | operator | 高（無監視=無制限の市場リスク） | 監視ループ・kill switch・最大保有時間/損失guardの実装と検証 | future runner（paperで先行検証） |
| 7 | broker write リスクの受容 | operator | 最高 | 自動化不可（責任主体は常に operator） | unsupported |
| 8 | safe status report の解釈 | operator | 中 | safe label は機械可読。判定の機械化は preview package で部分実装済み | supervised preview で提示、最終解釈は operator |
| 9 | post-cycle closeout 判断 | operator | 低 | closeout record の様式は本Sprintで確立 | code（記録生成）+ operator（承認） |
| 10 | side機械写像・plan構築・one-shot送信・sanitized変換・hard guard | code | —（実装済み・fail-closed） | 既存テストで固定済み | code（維持） |
| 11 | fresh runtime read（read-only GET）と safe label化 | code（operator ack必須） | 低 | 実装済み。無人実行時の頻度制御が必要 | future runner |

## 2. unattended full auto までの残り段階

1. **paper auto cycle runner**（本Sprint Phase 3・実装済み）: fake transport で
   signal→entry→confirmation→settlement→confirmation の全cycleを no-POST 検証
2. **supervised auto live preview**（本Sprint Phase 4・実装済み）: 自動判断を
   AUTO_PREVIEW_SIGNAL_* として live gate 直前まで preview。POST・credential・
   private GET なし。operator confirmation は必須のまま
3. **supervised live**（未実施・将来Step）: preview を operator が採用した場合のみ、
   従来どおり operator current-turn confirmation 付き live gate で実行
4. **unattended live**（未実施・当面 unsupported）: 上記 #2/#3/#7 の解除が必要で、
   これは boolean 判定器やコードではなく operator の明示的な方針Stepでのみ扱う
   （allow bridge 禁止の incident 方針を継承）

## 3. 結論

コード側の残blockerは実質なし（paper runner / preview は本Sprintで実装）。
残るgapはすべて **operator専権事項**（confirmation・リスク受容・サイズ供給）と
**監視guard未実装**（kill switch・最大保有時間/損失上限の無人版）であり、
これらが解決されるまで unattended live へ進んではならない。
