# Operator提案: v4に実装すべき「エッジ」の最終整理(proposal-only / no-POST)

Step: `OPERATOR_V4_EDGE_IMPLEMENTATION_PROPOSAL_NO_POST`
Status: **OPERATOR_APPROVED_IMPLEMENTED_PRECANARY_NO_POST**
Applies to: H-11 v4 execution profile(canary前)
Date: 2026-07-16
前提: v4 canary準備(`PRECANARY_CORRECTIVE_VALIDATED_EXTERNAL_PREPARATION_PENDING`)の進行を尊重する。
凍結済みpredictor(v2 config_hash=sha256:483fa9e4…)には一切触れない。broker POST/credential/
activation permitの状態を変更しない。

---

## 0. 結論(3行)

- 実装すべきは**3件のみ**: **(A)** ロールオーバー帯の実行フィルタ(確定的コスト回避) **(B)** canary起動前契約(成功基準の事前固定) **(C)** 約定紐付けの完全ID化。
- いずれも「エッジの追加」ではない。**確定的なコスト削減と、証拠の質の担保**である。半年の独立検証(エッジ研究repo)で方向性エッジは全カテゴリ棄却済みであり、**v4に載せるべき新シグナルは存在しない**。
- したがってcanaryの期待値は「利益」ではなく「**執行スタックの実証＋H-11の未収集フォワード証拠の収集**」。この定義をcanary開始前に固定する(§3)。

## 1. 背景(独立研究の確定結論・要約)

- USD/JPY方向性シグナルは、テクニカル/セッション/カレンダー/金利差(leak-free)/暗号トレンド(walk-forward)/fundingポジショニングの全カテゴリで棄却(詳細はエッジ研究リポジトリの不変台帳)。
- 生き残ったのは2種のみ: ①**実行コストの時間帯構造**(決定論的・本提案A) ②リスクプレミアム収穫(暗号funding carry=別venue・待機中/G10 carry=フォワード検証中・評決~2028)。②は本repoのスコープ外(§5)。
- H-11 v2はself-declared `NOT_EDGE_EVIDENCE` / `performance_proof_status=false`。実測(dev 14,965バー): 出力確率は0.438–0.641、**SELL側(p≤0.42)の発火0%**=構造的ロングオンリー。
- → **canaryは「エッジの運用」ではなく「試験」である。** この認識のズレが後の全判断を歪めるため、最初に固定する。

## 2. 提案A: ロールオーバー帯の残存コスト露出(確定的コスト回避)

**【2026-07-16 独立レビュー訂正】** 従来の時間帯gateはStage 1 paper専用で、
v4 actual経路には引き継がれていなかった。現在はv4専用policy/generation digestへ
`blocked_hours_jst=(5,6,7,8)`、金曜終日・週末禁止を固定し、
coordinatorがMARKET transport直前に強制する。

### 根拠(GMO実データ実測: H1 BID/ASK 16,560バー、2023-11〜2026-07)

| UTC時間帯 | JST | close-spread中央値 | p90 | 現行`BLOCKED_HOURS_JST`での扱い |
|---|---|---|---|---|
| 01–19時 | 10:00–04:59 | 0.2–0.4 pips | ≤0.6 | (対象外・平常) |
| **21–23時** | **06:00–08:59** | **12.0–12.8 pips** | 20.8–21.1 | **✅ 既にblock済み**(`{5,6,7,8}` JST = UTC 20–23) |
| 00時 | **09:00** | **1.4 pips** | **9.3** | **❌ 未block(唯一の残存ギャップ)** |

Stage 1 contractと同じ値をv4にも明示的に固定したが、両者は別config hashである。
Stage 1の実装が存在することをv4の実行証拠としては扱わない。

### 残る本当のギャップは2つだけ

1. **JST 9:00(UTC 00:00)がblock対象外。** 中央値1.4pips・p90 9.3pipsで平常時の3.5〜25倍。
   ただし**`BLOCKED_HOURS_JST`はfrozen contract(spec §4)であり**、本提案の非ゴール(§5)が定める
   「凍結値の変更=再登録が必要」の原則がそのまま適用される。**execution-layerの静かなパッチとして
   滑り込ませてはならない。** 追加するなら、v1/v2と同じ手続き(operator決定→新config_hash)を踏む
   独立の意思決定として扱うこと。効果も小さい(平常より数pips/回・低頻度)ため、優先度は低い。
2. **保有中のSL/TP露出は、entry gateでは救えない(ここが本当に新規・非redundant)。**
   `BLOCKED_HOURS_JST`は`pre_trade_gate_reasons`(entry前のみ)にしか効かず、決済・timeout側には
   一切適用されない。JST 9–20時台にentryした23h保有ポジションは、保有期間中にロールオーバー帯を
   1回通過し、**その間のSL/TP発動は無制限にbid側の悪化(6–17pips)を受け得る**。これはfrozen値に一切
   触れない**純粋な計測強化**で実装できる: 全fill(特にSL/TP発動)時のスプレッド/mid乖離をledgerへ記録し、
   「窓内発動」を事後分析可能にする。

### スコープ境界(明記):現在実弾稼働中の`h11_manual`は対象外

`backend/app/h11_manual/*.py` には時間帯ゲートが**一切存在しない**(grep 0件)。現在の実弾約定
(2026-07-15〜16、12件)はロールオーバー帯を偶然回避していただけで、方針として保護されていない。
本提案は operator の現行方針(v4完成優先)に従い**this repoのv4スコープに限定**するが、
h11_manualが実弾を扱い続ける限りこのギャップは残ることを記録しておく。

## 3. 提案B: canary起動前契約(成功基準の事前固定)

### 原則

**評価基準は起動後に決めない。** 起動後の基準設定は必ず運用者に甘くなる(研究側で半年かけて実証した規律)。以下をcanary開始前に文書として固定し、変更はoperator授権+新文書によってのみ行う。

### 執行KPI(canaryの主目的。ハードゲート=違反1件でHALT)

- **OCOカバレッジ100%**: 全non-zero fillに対し、MARKET attemptから15秒以内に
  owned clientOrderIdの**別OCO**がexact filled sizeで確認される。例外ゼロ。
- **孤児ポジションゼロ / reconciliation不一致ゼロ。**
- **紐付け失敗ゼロ**(§4のID紐付けが全fillで成立)。
- **5,000円 loss bound**(既存仕様)到達後はpersistent risk stopとし、次entryを拒否する。
  保有中の異常はblind flatせず、fresh reconciliationと一致する単発risk-reducing actionだけを許可する。
- 全fillで**スリッページ(事前preflightのBID/ASK vs 約定平均価格)とスプレッドを記録**。
  v4 coordinatorのgeneration-bound SQLiteへ、予測`p_up`、preflight BID/ASK、約定平均価格、
  entry spread、direction-aware slippageを同一cycleで永続化する。raw responseやbroker IDは保存しない。
- OCOが未発動のままMARKET attemptから23時間に到達した場合、exact OCOを取消し、
  fresh reconciliation後にposition-specific MARKET time exitを1回だけ実行する。
  23時間はGMO `latestExecutions`の1日保持境界との衝突を避け、owned OPENの
  broker ID紐付けを保持範囲内で再確認するための安全側再凍結である。
- exact OCO取消transportの直前に、executor-owned monotonic clockで最大2秒以内の
  公式public status `OPEN` evidenceをone-use消費する。
  `CLOSE`、`MAINTENANCE`、unknown、stale時は
  OCOを取消さずpersistent HALTとする。

違反時はblindな即時flatを行わない。`HALT → fresh 3-GET reconciliation →
確定状態と一致する単発risk-reducing action`のみ許可する。

### モデルKPI(蓄積のみ。canary期間中の合否評決を禁止)

- v4 coordinatorはowned CLOSEの公式`lossGain + fee + settledSwap`からnet JPY、net pips、勝敗を
  cycle単位でexactly-once記録する。予測`p_up`もentry intent時に同一cycleへ固定する。
- 予測確率の較正(予測p vs 将来時点の実現方向)は、売買有無から独立した既存の
  `h11_manual` PROSPECTIVE forecast ledgerを正とし、v4のbroker coordinatorで再採点しない。
- **少数トレードでの合否判断を明示的に禁止する**(N<数百では統計的検出力がほぼゼロ。30トレードの結果に情報量はない)。モデルの評決はH-11既存のformal test契約(forward予約)に従う。

### canaryの成功定義

> **「執行KPI全通過 × 規律違反ゼロ × 予定期間の完走」= 成功。**
> P&Lは成功定義に含めない(loss boundは撤退条件であって成功条件ではない)。

## 4. 提案C: 約定紐付けの完全ID化

### 根拠(実測)

手動ツールの±120秒時間窓照合は構造的に破綻した: 74約定中**72件が未紐付け**(`applied_plan_id=None`)、同方向約定の密集時(07-15に20件超)は`AMBIGUOUS_OPEN`が原理的に不可避、plan 7は`WAITING_FOR_OPEN`のまま恒久停止。この結果、SL/TP付きプランが実弾に接続されず、UIは建玉を表示できなかった。

### 仕様

- v4自動経路では、**MARKET entry clientOrderId → OPEN execution → positionId**と、
  **別OCO/time-exit clientOrderId → CLOSE execution → positionId**の紐付けをbroker付与IDで行う。
- **時間窓ヒューリスティックのコードパスを自動経路から排除**する(手動ツール専用に隔離、または削除)。
- 「IDで紐付かない約定」を観測した場合は執行KPI違反として扱い、fail-closedで停止する。

## 5. 実装しないもの(non-goals / スコープ防衛)

| 項目 | 理由 |
|---|---|
| 新シグナル追加(センチメント/VIX/金利差/クロスアセット等) | 独立検証で棄却済み、または同時相関のみでリーク時だけ有効と確定 |
| レジームルーター/MoEの復活 | H-11 v1で実証済みの失敗(routerはequal-weightに勝てなかった) |
| v2の重み・閾値・SL/TP幅の再調整 | 凍結違反。変更=新versionとして再登録が必要 |
| ロングオンリー是正のためのbias/閾値調整 | 結果を見た後のモデル編集=最も危険な自己欺瞞。是正するなら新version |
| funding carry / G10 carryの本repo実装 | 前者は別venue(暗号取引所)、後者は評決~2028のフォワード検証中。v4は将来の「弾倉差し替え先」であればよく、多戦略への汎用化リファクタはcanary完了後に判断 |

## 6. 研究側から提供可能なもの

- 時間帯別スプレッドプロファイルの実測データと再現コード(エッジ研究repo: `fx-edge-v2/costmodel.py`、cost audit一式)
- canary起動前契約(§3)のドラフトおよび読み取り専用レビュー

---

(本文書のpre-canary契約はoperator授権により実装済み。actual POST/broker write/credential/
live permissionの状態は変更しない。performance_proof_status=false / live_ready=false)
