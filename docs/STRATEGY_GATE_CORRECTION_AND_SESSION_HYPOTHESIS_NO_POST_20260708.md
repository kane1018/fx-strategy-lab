# 評価gate是正 + 新仮説(session) + 多解像度化: 全候補 NO_ROBUST_EDGE（no-POST・2026-07-08）

Step: `STRATEGY_GATE_CORRECTION_AND_SESSION_HYPOTHESIS_NO_POST`
実装: `gmo_strategy_redesign.py`（SHORT側ASK約定・sign-permutation側override・
新family SESSION_MOMENTUM）/ `gmo_strategy_evaluation_hardening.py`
（sign-permutation benchmark・標準gate明文化・**多解像度(multi-resolution)化**）

**重要: performance proof ではない（performance_proof_status=false / live_ready=false）。
raw price/spread/PnL/CSV row/ID は扱わない。本Stepは前回確認で残した弱点の是正と、
テクニカル以外の新仮説を厳格gateに通した「正直な棄却」の記録であり、edge の証明でも
edge 不在の証明でもない（この15ヶ月・この銘柄/時間足での観測結果）。**

## 1. 背景（前回確認で残した「潰すべき所」）

前回のexecution-realism確認で、以下2点を "未解消の残課題" として正直に開示していた:
- (a) **SHORT側の約定近似**: BID足のhigh/lowで両サイドのTP/SL touchを判定しており、
  買い戻し(ASK)で約定するSHORTのstop/targetがspread1本分だけ楽観方向にずれる。
- (b) **random benchmarkのゲート非対称**: fixed-cadence(bar%4)のrandom entryは、戦略と
  entry頻度・gating・trade countが一致せず、benchmarkとして弱い。

本Stepでこの2点を是正し、標準gateを明文化し、さらにテクニカル以外の新仮説を1つ構築した。

## 2. 実装した是正（no-POST・frozen signal engine無変更）

- **(a) SHORT側ASK約定モデル**: exit touch判定を純関数 `_exit_touch(...)` に抽出。
  LONGはBID(売り)で判定、**SHORTはASK=BID+bar_spreadで判定**（rising stopもfalling target
  も）。これで「SHORT stopがspread1本分遅れて引かれる」楽観を除去。unit testで
  BID/ASKの分岐を直接検証。
- **(b) sign-permutation directional benchmark（主benchmark化）**: 戦略の**entry bar・
  gating・cadence・exit configをそのまま再利用し、方向(long/short)だけを決定的LCGで
  ランダム化**。entry機会集合が窓ごとに一致するため、「entry頻度やexit形状の副作用」では
  なく **方向判断そのものの優位** を分離できる。verdictの `beats_random` は
  fixed-cadence random p90 ではなく **sign-permutation p90** で判定するよう変更
  （fixed-cadence random p90 は secondary reference として併記）。
- **標準gateの明文化 + 多解像度化**: `StandardEvaluationGate` に必須条件を固定
  （slippage 0.5pip/side・cost 2.0×・sign-permutation p90・min trades/window・
  no post-OOS retuning）。**さらに再確認で判明した window-count 依存性**
  （同じ候補が粗い窓では robust・細かい窓では NOT_ROBUST）に対処するため、
  **複数の window 解像度で全て robust（unanimous）でなければ ROBUST としない**
  多解像度要件を追加（`evaluate_under_standard_gate` が既定解像度 (1000,1400) bars で
  各々 min_qualified_windows 以上を要求）。
- **新仮説 SESSION_MOMENTUM**（テクニカル指標ではない構造仮説）: bar の実epoch(JST時刻)を
  用い、**セッションオープン(既定16 JST≈London open)の足のみ**で、直近の日中ドリフト
  (momentum)方向にentryする "session-open continuation"。既定8候補とは別バッテリーとして
  同じ厳格gateで評価。

## 3. 是正後の判定（USD/JPY H1・約7,828 bars・safe aggregate）

多解像度標準gate（slippage 0.5pip/side・cost 2.0×・sign-permutation p90・window解像度
1000/1400 bars・両解像度で unanimous robust 要求）:

### テクニカル8候補
- **全候補 robust_all_resolutions=False → NO_ROBUST_EDGE**
- 例: `TREND_CONTINUATION__EXIT_RIDE_ATR` は 1400-bar窓(5窓)で ROBUST だが
  1000-bar窓(7窓)で NOT_ROBUST → **解像度間で不一致 → 棄却**（窓分割の当たり外れに依存）。

### 新仮説 SESSION_MOMENTUM
- **robust_all_resolutions=False → NO_ROBUST_EDGE**
- `SESSION_MOMENTUM__EXIT_RIDE_ATR` は raw の median PF が両解像度で 1.2 台と高めだが:
  1. **1000-bar窓(7窓・より信頼できる解像度)で `beats_dir=False`**
     （median PF < 自身のentryの sign-permutation p90）。すなわち **方向ルールに優位はなく**、
     見かけの正PFは「session-openという時刻のentry timing＋exit形状」の構造的副産物。
  2. 1400-bar窓では robust に見えるが **解像度間で不一致 → 棄却**。
- → **fixed-cadence random では見逃していた「方向優位の不在」を sign-permutation が検出**
  （まさに (b) の是正が効いた例）。

## 4. 結論（正直に）

- **この15ヶ月・USD/JPY H1では、テクニカル4family も 新仮説 session-open continuation も、
  是正後の厳格gate（現実的slippage・2.0×コスト・sign-permutation・多解像度unanimous）を
  通過しない → NO_ROBUST_EDGE。**
- 本Stepの本質的価値:
  1. (a)(b) の残課題を実装で是正（SHORT約定はより保守的に、benchmarkはgate一致の
     sign-permutationへ）。
  2. 再確認で **window-count依存の偽robust** を発見し、多解像度unanimous要件で是正
     （偽陽性を1つ潰した）。
  3. 新仮説を1つ構築し、同じ厳格gateで正直に棄却。sign-permutationが
     「session仮説の方向優位の不在」を検出した。
- **performance proof でも live 許可でもない。** unattended_full_auto_completed=false /
  unattended_live_supported=false は不変。actual POST には常に fresh gate 一式＋operator
  current-turn confirmation が必要。

## 5. recommended next Step（判断材料の提示のみ・実装は別Step）

- 単純テクニカル/単一構造仮説はこの期間で尽きた感触。次の実質前進候補:
  1. **別の独立期間 / 別銘柄での同一gate再確認**（同一期間の窓分割ではなく真に独立なOOS）。
     ただし追加データ取得は operator承認の public GET が前提。
  2. **多要因/条件付き仮説**（session×volatility regime×spread状態の交差条件など）を、
     多重検定予算を管理しつつ少数だけ事前登録して検証。
  3. いずれも **paper-forward 以降のみ**。live移行は robust edge 不在のため不可。
