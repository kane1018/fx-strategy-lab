# H-11 v2 Stage 1 Paper Wiring 完了記録（no-POST）

Date: 2026-07-11
Step: `STAGE1_PAPER_WIRING_STEP`（2026-07-11 operator授権済み）
Status: **STAGE1_EXECUTION_STARTED**（operator開始確認 2026-07-11・初回run実行済み）

```text
config_hash=sha256:483fa9e4cc094251c3b3bfc5daaa007242a3385ba41c57caa95e5106fa4c4af3（v2）
stage1_wiring=COMPLETE / stage1_execution_started=false
actual_post=false / entry_post=false / settlement_post=false / post_count=0
real_transport=none（fake-transport-only を型と実行時チェックで強制）
performance_proof_status=false / live_ready=false / unattended_live_supported=false
```

## 1. 実装（`backend/app/services/h11_stage1_paper_wiring.py`）

- **配線経路**: v2予測（`H11Prediction`）→ preview adapter（v2 config_hashにpin・
  他versionはblock）→ 事前ゲート → 既存 paper auto-cycle runner（fake transport専用・
  1 entry / 1 settlement・no retry）。
- **予算・停止基準はコード定数**（実行時変更不可・ACTIVE policy §4）:
  月間5万円 / 日次1万円 / 1トレード5千円（構造上界）/ 5連敗停止 / 1トレード/日。
- **事前ゲート**（fail-closed・全通過が必要）: kill=off / 停止状態でない /
  平日 / 9:00〜翌5:00 JST / 金曜21:00以降の新規なし / event除外ウィンドウ外 /
  当日トレード枠残。
- **停止の性質**: 日次停止は翌日自動解除。月次・連敗停止は自動解除されず、
  `operator_reload` のみ（**同月内reload・冷却14日未満はコードが拒否**。post-mortem＋
  review window承認は運用側手続きとして別途必須）。
- **kill switch**: 新規サイクルのみblock。自動close・自動settlementは発火しない。

## 2. 発火テスト（ACTIVE policy §5 Stage 1昇格条件 (b) 対応）

`backend/app/tests/test_h11_stage1_paper_wiring_no_post.py` — **11件全パス**:

| 系統 | テスト |
|---|---|
| 日次予算停止 | 発火＋翌日解除を確認 |
| 月次予算停止 | 発火＋同月reload拒否＋冷却14日未満拒否＋冷却後受理 |
| 連敗停止 | 5連敗で発火・勝ちでストリークreset |
| 1日1トレード | 2件目block・翌日reset |
| 1トレード上界違反 | discipline violationとして記録 |
| 時間帯・カレンダー | 6:00 JST block / 金曜21:30 block / 土曜block / event除外block |
| kill | block＋自動決済なし＋reload不可 |
| HOLD帯・BLOCKED予測 | 注文なし |
| version pinning | v1 hashの予測はUNKNOWN_BLOCKED |
| 凍結定数 | §8承認予算と一致することを機械検証 |

## 3. Stage 1 実稼働（2026-07-11 開始）

- operator は 2026-07-11 に実稼働開始を確認した。開始時刻（UTC）:
  `2026-07-10T21:19:18+00:00`（昇格条件「連続2週間以上」の起点）。
- **運用形態**: 常駐プロセス・cron は Stage 3 方針 Step まで禁止のため、
  `python -m scripts.h11_stage1_daily_run` の**手動日次バッチ**で運用する。
  1回の起動 = キャッシュ更新（operator授権 public GET・read-only）→
  建玉あれば凍結exit契約（SL/TP/24h timeout のみ）で決済判定 →
  フラットかつ全ゲート通過なら最大1 paper entry → journal追記。
- 状態・journal は `backend/market_data/`（gitignore・ローカルのみ）。
  レビュー時に safe aggregate を docs に転記する。
- 初回run（2026-07-11 06:19 JST・土曜）: `WEEKEND_BLOCKED` +
  `OUTSIDE_TRADING_HOURS` で正しく block — カレンダーゲートの実データ発火を確認。
- 昇格判定（→Stage 2）は 2週間以上 かつ 20 paper trades 以上 かつ 違反0 を
  満たした後の operator review でのみ行う。実稼働は paper のみであり、
  Stage 2 以降・live・POST の許可ではない。
