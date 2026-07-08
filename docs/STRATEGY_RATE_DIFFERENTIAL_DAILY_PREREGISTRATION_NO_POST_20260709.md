# RATE_DIFFERENTIAL_DAILY 事前登録（凍結・単一仮説）— no-POST・2026-07-09

Step: `RATE_DIFFERENTIAL_DAILY_PREREGISTRATION_NO_POST`
親: [runbook §6b](RESEARCH_RUNBOOK_NO_POST.md)（mechanism-first）/
[feasibility map](STRATEGY_MECHANISM_TIMESCALE_DATA_FEASIBILITY_NO_POST_20260709.md)

**本書は「契約」。ここで条件・期間・評価gate・合格基準を全て固定し、取得・採点は本 commit を基準に行う。
結果を見た後の条件変更（post-OOS retuning）は禁止。単一仮説・単一variant のみ。他の日次仮説や
"取れるデータからの探索"には広げない。docs のみ（本 Step では取得・実装・採点なし＝別 commit）。
raw price/spread/PnL/CSV row/ID/credential は扱わない。performance_proof_status=false /
live_ready=false。合格しても解錠は paper-forward 検討のみ。「勝てる/収益性/edge証明」は断定しない。**

## 1. 機構仮説（a-priori・動機であり証明対象でない）

- USD/JPY は**日米金利差の従属変数**（金利差拡大＝USD/JPY 上昇圧力）。
- **検証する**: 「直前 k 営業日の **US–JP 10年利回り差の変化**の符号」が、その後 h 営業日の
  USD/JPY リターンの符号／コスト後収益を**予測するか**。
- **検証しない/断定しない**: 因果の証明、carry の静的保有(level)戦略、他 horizon/他ペア、live 化。

## 2. データ（no-credential 公開日次のみ・機構が要求するもの）

- **US 10年利回り（日次）**: FRED `DGS10`（`fredgraph.csv?id=DGS10`・APIキー不要）。
- **JP 10年利回り（日次）**: 財務省 JGB 日次利回り CSV（`jgbcm_all.csv`・無認証公開）。
- **USD/JPY（日次）**: FRED `DEXJPUS`（`fredgraph.csv?id=DEXJPUS`・APIキー不要・参照レート）。
- 取得は **public GET・認証なし・no-POST**。CSV は **repo 外・非commit・raw非公開**。
- **入手できないソースがあれば、代替に作り替えず BLOCKED として報告**（§6b）。
- 整合: 3系列を**共通営業日で inner join**（US/JP 祝日差は除外）。**lookahead 厳禁**
  （signal は判定日までに確定した過去値のみ）。DEXJPUS 欠損日はスキップ。

## 3. 対象期間（固定）

- **2005-01-01 〜 2026-07-07**（約21.5年・日次）。walk-forward で全期間を等分ブロック採点。
- 期間の後出し変更禁止（データ都合で切り縮めない）。

## 4. 固定ルール（単一 a-priori variant・スキャン禁止）

- D_t = US10y(t) − JP10y(t)（共通営業日）。
- signal(t) = sign( D_t − D_{t−k} ), **k = 5 営業日**（up→USD/JPY long / down→short / 0→no-entry）。
- entry = signal 確定日の USD/JPY 終値、exit = **h = 5 営業日後**の終値。**TP/SL なし**。
- **one-position-at-a-time**（flat の時のみ entry・保有 h 日・その後 re-entry 可）。
- **k・h・方向規則・利回り年限(10y)は固定**。グリッド/最適化しない。

## 5. 約定・コスト（固定）

- 日次参照レートに bid/ask は無いため、**round-trip 固定コスト**を課す:
  **baseline = 1.0 pip（price 0.01）**、**stress = 2.0 pip（0.02）**（1pip=0.01・USD/JPY）。
- 判定は **stress（2.0 pip）で行う**（保守）。

## 6. 対照群（primary・全 unanimous 要求）

1. **コスト込み収益方向**: PF>1 かつ 期待値符号 NON_NEGATIVE @2.0pip。
2. **lead-lag placebo**: D 系列を**時間反転／シャッフル**すると予測性が消えること（spurious 同時相関の排除）。
3. **contemporaneous 対照**: lag=0（同日 D 変化）では取引不能→ **lag>0 の予測性**が本質であることの確認。
4. **sign-permutation p90**: 同じ entry 日で方向を無作為化した分布の p90 を、本戦略 PF が上回ること。
5. **期間ブロック安定性**: **3 ブロック以上の全てで PF>1**。

## 7. 最小標本・合格基準（固定）

- **最小標本**: 総 trade **≥ 200** かつ **3 ブロック以上・各 ≥ 50**。未達は `INSUFFICIENT`。
- **合格 = `RETEST_PASSED_CANDIDATE_FOR_PAPER_FORWARD`**: §6 全成立 + 最小標本 + post-OOS retuning なし。
  **解錠は paper-forward 検討のみ。perf_proof/live は false 維持。**
- 失敗 = `NOT_ROBUST` / `INSUFFICIENT`。
- **null なら closeout 維持**（条件を変えて再探索しない）。

## 8. 多重検定・不変則

- 本仮説 = **trial 1件**（単一 variant）。program 台帳へ +1。
- **post-OOS retuning 禁止 / 単一仮説のみ / 他日次仮説・データ探索へ広げない**。
- 採点は本 commit（凍結）を基準に**1回**。

## 9. 実行手順（別 commit で実施）

1. 本契約を commit/push（=凍結・本 Step）。
2. §2 の3系列を public GET（no-credential）で取得 → repo外CSV。
3. §4 の固定ルール + §6 対照 + §5 コストで **1回採点**。
4. safe aggregate で記録（PF/win/PF_p90/block PF/verdict）。null→closeout。
