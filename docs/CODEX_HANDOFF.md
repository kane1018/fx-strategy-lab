# Codex 引き継ぎ（CODEX_HANDOFF）

Codex が新しいタスクを安全に開始するための要約済み文脈。詳細な現在地は
[PROJECT_STATUS.md](PROJECT_STATUS.md)、固定ルールは [`../AGENTS.md`](../AGENTS.md) を参照する。

## 1. 目的と現在地

FX Strategy Lab は、FX の検証、ペーパートレード、通知、将来の少額自動売買へ安全に段階移行するための
検証基盤である。現時点では実注文・実資金・注文API・broker・本番公開 API 追加を扱わない。

- repository: `https://github.com/kane1018/fx-strategy-lab.git`
- branch: `main`
- frontend production: `https://fx-strategy-lab.vercel.app`
- backend production: `https://fx-strategy-lab.onrender.com`
- production entrypoint: `app.main_readonly:app`
- 現在のフェーズ: **Step 5H Operator review procedure完了 / no order / no POST**。
  `backend/app/live_verification/live_order_operator_review.py` を追加し、Step 5Gの
  `ReviewGatedSessionBundle` からsanitizedな `LiveOrderOperatorReviewProcedure` と
  checklist itemsを作るoperator review procedure modelを実装した。
  ready bundleでは `READY_FOR_OPERATOR_CHECKLIST` になるが、これは人間が読むdry-run確認手順という
  意味だけで、`allowed_for_live=false`、`requires_human_approval=true`、
  `approval_gate_required=true`、`dry_run_only=true` を維持する。READY checklistにはdry-run確認、
  approval gateではないこと、live POSTを許可しないこと、candidate条件、risk gate、session policy、
  残りセッション枠、残り通貨枠、future approval gate / final dynamic preflightが別Stepであることを含める。
  blocked bundleやunsafe inputでは `BLOCKED_OPERATOR_REVIEW` となり、blocked reasonsを保持し、
  `Do not proceed to approval gate` / `Do not proceed to live POST` のchecklistを出す。
  Markdown renderingには `This operator review is dry-run only.`、
  `This review is not an approval gate.`、`This review does not authorize live POST.`、
  `allowed_for_live=false.` の警告を含める。Step 5Hは `live_order_once`、Private API、broker、
  HTTP client、read-only API、ledger、approval gateには接続していない。詳細は
  [STEP5H_OPERATOR_REVIEW_PROCEDURE.md](STEP5H_OPERATOR_REVIEW_PROCEDURE.md)。
  ready operator reviewはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も
  別Step・別承認で扱う。
- 直前フェーズ: **Step 5G Review-gated session bundle完了 / no order / no POST**。
  `backend/app/live_verification/live_order_review_session_bundle.py` を追加し、Step 5Eの
  `LiveOrderCandidateReviewReport` とStep 5Fの `ReviewGatedSessionPolicyDecision` から
  sanitizedな `ReviewGatedSessionBundle` を作るoperation bundle modelを実装した。
  ready review + passed session policyでは `READY_FOR_OPERATOR_REVIEW` になるが、
  これは人間が読むdry-run運用判断レポート候補という意味だけで、`allowed_for_live=false`、
  `requires_human_approval=true`、`approval_gate_required=true`、`dry_run_only=true` を維持する。
  review / policy / bundle-levelの `blocked_reasons` を統合し、`remaining_sessions_today` と
  `remaining_daily_size` をsanitizedに計算する。capacityがmissing/unknown/negativeの場合はfail closedで
  `BLOCKED_BUNDLE` になる。Markdown renderingには `This operation bundle is dry-run only.`、
  `This bundle is not an approval gate.`、`This bundle does not authorize live POST.`、
  `allowed_for_live=false.` の警告を含める。Step 5Gは `live_order_once`、Private API、broker、
  HTTP client、read-only API、ledger、approval gateには接続していない。詳細は
  [STEP5G_REVIEW_GATED_SESSION_BUNDLE.md](STEP5G_REVIEW_GATED_SESSION_BUNDLE.md)。
  ready bundleはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も
  別Step・別承認で扱う。
- 直前フェーズ: **Step 5F Review-gated session policy完了 / no order / no POST**。
  `backend/app/live_verification/live_order_session_policy.py` を追加し、Step 5Eの
  `LiveOrderCandidateReviewReport` とsanitizedな `ReviewGatedSessionPolicySnapshot` から
  fail-closedな `ReviewGatedSessionPolicyDecision` を作るsession policy modelを実装した。
  初回micro-live完了、前回結果確定、結果不明なし、`open_positions_count=0`、
  `active_orders_count=0`、1日最大2セッション、セッション間120分以上、1セッション100通貨、
  1日合計200通貨以下、Git/tests/ruff/secret scan正常、raw response未保存・未表示、
  market window allowed、maintenance false、important event window confirmedを評価する。
  safe snapshotでは `policy_passed=true`、`eligible_for_review_session=true` になるが、
  `allowed_for_live=false`、`requires_human_approval=true`、`approval_gate_required=true`、
  `dry_run_only=true` を維持する。unknown / missing / unsafe inputは `BLOCKED` となり、
  複数の `blocked_reasons` を返す。Step 5Fは `live_order_once`、Private API、broker、
  HTTP client、read-only API、ledger、approval gateには接続していない。詳細は
  [STEP5F_REVIEW_GATED_SESSION_POLICY.md](STEP5F_REVIEW_GATED_SESSION_POLICY.md)。
  policy passはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も
  別Step・別承認で扱う。
- 直前フェーズ: **Step 5E Candidate review report完了 / no order / no POST**。
  `backend/app/live_verification/live_order_candidate_review.py` を追加し、Step 5Bの
  `LiveOrderCandidate`、Step 5Cの `LiveOrderCandidateRiskDecision`、Step 5Dの
  `LiveOrderCandidateTraceRecord` からsanitizedな `LiveOrderCandidateReviewReport` を作る
  review/reporting modelを実装した。`READY_FOR_HUMAN_REVIEW` は人間が読むdry-run report候補という
  意味だけで、`allowed_for_live=false`、`requires_human_approval=true`、`approval_gate_required=true`、
  `dry_run_only=true` を維持する。risk decisionやtraceがblockedの場合は `BLOCKED_REVIEW` として
  blocked reasonsを統合し、`fix_blocked_reasons_no_post` を返す。Markdown renderingには
  `This review report is dry-run only.`、`This report is not an approval gate.`、
  `This report does not authorize live POST.`、`allowed_for_live=false.` の警告を含める。
  Step 5Eは `live_order_once`、Private API、broker、HTTP client、read-only API、ledger、approval gateには
  接続していない。詳細は [STEP5E_CANDIDATE_REVIEW_REPORT.md](STEP5E_CANDIDATE_REVIEW_REPORT.md)。
  次フェーズを行う場合も、approval gateやlive POSTへ直接進まず、別Step・別承認で扱う。
- 直前フェーズ: **Step 5D Candidate trace record完了 / no order / no POST**。
  `backend/app/live_verification/live_order_candidate_trace.py` を追加し、Step 5Bの
  `LiveOrderCandidate` とStep 5Cの `LiveOrderCandidateRiskDecision` を、sanitizedな
  `source_signal_id` / `paper_trade_ref` / `shadow_run_ref` / optional decision refsへ紐付ける
  `LiveOrderCandidateTraceRecord` を実装した。`candidate_id` と `risk_decision.candidate_id` の不一致、
  `allowed_for_live=true`、dry-run / human approval / approval gate条件の欠落、source signal欠落、
  paper/shadow参照欠落、unsupported symbol/side/size/execution_typeはfail closedで `BLOCKED` になる。
  risk decisionがblockedの場合も監査用に `BLOCKED_TRACE_RECORDED` を作れるが、
  `eligible_for_human_review=false`、`allowed_for_live=false` を維持する。`READY_FOR_REVIEW` は
  review/reporting候補という意味だけで、approval gateやlive POST許可ではない。Step 5Dは
  `live_order_once`、Private API、broker、HTTP client、ledger、approval gateには接続していない。
  詳細は [STEP5D_CANDIDATE_TRACE_RECORD.md](STEP5D_CANDIDATE_TRACE_RECORD.md)。
  推奨次フェーズはStep 5E candidate review/reportingであり、引き続きno POSTとする。
- 直前フェーズ: **Step 5C Live order candidate risk gate完了 / no order / no POST**。
  `backend/app/live_verification/live_order_candidate_risk_gate.py` を追加し、Step 5Bの
  `LiveOrderCandidate` とsanitizedな `LiveOrderCandidateRiskSnapshot` からfail-closedな
  `LiveOrderCandidateRiskDecision` を作るrisk gateを実装した。safe snapshotでは
  `risk_gate_passed=true`、`eligible_for_human_review=true` になるが、`allowed_for_live=false`、
  `requires_human_approval=true`、`approval_gate_required=true`、`dry_run_only=true` を維持する。
  unsafe / unknown / missing inputは `BLOCKED` となり、複数の `blocked_reasons` を返す。Step 5Cは
  risk gate passをlive POST許可とは扱わず、candidate review候補へ進めるだけで停止する。
  `live_order_once`、Private API、broker、HTTP client、ledger、approval gateには接続していない。
  詳細は [STEP5C_LIVE_ORDER_CANDIDATE_RISK_GATE.md](STEP5C_LIVE_ORDER_CANDIDATE_RISK_GATE.md)。
  推奨次フェーズはStep 5D/5E candidate review/reportingであり、引き続きno POSTとする。
- 直前フェーズ: **Step 5B Live order candidate dry-run model完了 / no order / no POST**。
  `backend/app/live_verification/live_order_candidate.py` を追加し、sanitizedな `StrategySignalInput` から
  非実行の `LiveOrderCandidate` またはblocked resultを作るdry-runモデルを実装した。BUY / SELL signalは
  `USD_JPY`、`size=100`、`execution_type=MARKET`、`status=REVIEW_REQUIRED` のcandidateになるが、
  `allowed_for_live=false`、`requires_human_approval=true`、`risk_gate_required=true`、
  `approval_gate_required=true`、`dry_run_only=true` を固定する。`NO_TRADE` / `hold`、unsupported symbol、
  invalid confidence、missing rationaleはcandidateなしの `BLOCKED` resultへfail closedする。
  candidate idは `LOCAND-` prefixのdeterministic dry-run IDで、order id、execution id、position id、
  client order idではない。`live_order_once`、Private API、broker、HTTP client、ledger、approval gateには
  接続していない。詳細は [STEP5B_LIVE_ORDER_CANDIDATE_DRY_RUN.md](STEP5B_LIVE_ORDER_CANDIDATE_DRY_RUN.md)。
  推奨次フェーズはStep 5C candidate risk gate implementationであり、Step 5Cもno POSTとする。
- 直前フェーズ: **Step 5A Paper / Shadow / Live接続設計レビュー完了 / no order / no POST**。
  Step 4 micro-live完了後の次フェーズとして、paper trading、shadow run、live verificationの役割分担と
  安全な接続設計を [STEP5A_PAPER_SHADOW_LIVE_CONNECTION_REVIEW.md](STEP5A_PAPER_SHADOW_LIVE_CONNECTION_REVIEW.md)
  にdocs-onlyで整理した。提案フローは `Market data -> Strategy signal -> Paper / Shadow decision record ->
  Live order candidate -> Risk gate -> Human approval gate -> Final dynamic preflight -> One-shot live POST ->
  Read-only reconciliation -> Stop`。Paperは仮想取引・仮想P/L・研究用、Shadowはpublic market data由来の
  candidate/risk/audit記録、Liveは人間承認・final preflight・one-shot ledger後にのみ扱う分離を明文化した。
  Live order candidate schema draftとrisk gate必須項目を定義したが、実装、HTTP POST、実注文、決済、取消、
  注文変更、approval id発行、approval gate、BUY/SELL live判断、Private API接続、API key / secret確認、
  ledger変更は行っていない。推奨次フェーズはStep 5B strategy signal -> live order candidate dry-run model
  であり、Step 5Bもno POSTとする。
- 直前フェーズ: **Step 4H micro-live検証完了レビュー完了 / no order / no close / no POST**。
  Step 4B〜Step 4G-Cのmicro-live検証を
  [STEP4_MICRO_LIVE_COMPLETION_REVIEW.md](STEP4_MICRO_LIVE_COMPLETION_REVIEW.md)
  に総括した。到達点は「新規注文API成功 -> ユーザー手動決済 -> read-onlyで建玉0・有効注文0確認」。
  確認できたこと、未検証範囲、安全境界、次フェーズ候補、次にlive POSTへ進む条件をdocs化した。
  BUYはユーザー指定であり、戦略システムが自動判断したものではない。決済はユーザーがGMO Web画面で
  手動実施し、Codexは決済APIを実行していない。今回のStep 4HではHTTP POST、新規注文、追加注文、
  決済注文、取消、注文変更、approval id発行、approval gate、approval command表示、ledger reset、
  credential / headers / signature / raw request / raw response / order id / execution id / position idの
  表示・保存は未実行。推奨次フェーズは、候補A paper/shadow-to-live接続設計レビュー、候補B
  戦略シグナルdry-run、候補C close API仕様調査とfake transportの順であり、候補D/Eへ直接進まない。
- 直前フェーズ: **Step 4G-C 手動決済後read-only確認完了 / MANUAL_SETTLEMENT_CONFIRMED / no order / no close**。
  ユーザー報告として、GMO Web画面から前回の `USD_JPY BUY 100通貨` 建玉を手動決済済みで、
  建玉サマリー・建玉一覧に対象取引なしと表示されている。Codex側では2026-06-26にread-only確認のみを実施し、
  `GMO_FX_API_KEY: set` / `GMO_FX_API_SECRET: set` を値非表示で確認した。ledgerは
  `POST_COMPLETED`、`attempt_count=1`、`result_category=success` のままsanitized確認し、
  ledger reset / delete / edit / overwriteは行っていない。既存read-only runnerで
  `account/assets=success`、`open_positions_count=0`、`active_orders_count=0`、raw response保存なし、
  headers保存なし、credential表示なしを確認した。manual settlement API confirmationは `true`、
  position statusは `closed`、active order statusは `none`。Step 4G-CではHTTP POST、新規注文、
  追加注文、決済注文、取消、注文変更、approval id発行、approval gate、approval command表示は未実行。
  raw request / raw response、order id、execution id、position id、open price、execution price、
  timestamp、詳細損益、残高詳細、建玉詳細は表示・保存していない。今回のmicro-live検証は
  「新規注文API成功 -> ユーザー手動決済 -> read-onlyで建玉0・有効注文0確認」まで到達した。
- 直前フェーズ: **Step 4G-A 建玉read-only確認完了 / POSITION_CONFIRMED / no close / no order**。
  Step 4F-B後のOPEN建玉確認として、2026-06-26にread-only確認のみを実施した。
  `GMO_FX_API_KEY: set` / `GMO_FX_API_SECRET: set` を値非表示で確認し、ledgerは
  `POST_COMPLETED`、`attempt_count=1`、`result_category=success` のままsanitized確認した。
  既存read-only runnerで `account/assets=success`、`open_positions_count=1`、
  `active_orders_count=0`、raw response保存なし、headers保存なし、credential表示なしを確認した。
  openPositionsのsanitized summaryは `position_count=1`、`symbol=USD_JPY`、`side=BUY`、
  `size_total=100`。建玉ID、注文ID、約定ID、position ID、open price、execution price、
  timestamp、詳細損益、残高詳細、建玉詳細、raw responseは表示・保存していない。public tickerは
  `bid=161.804`、`ask=161.809`、`spread_jpy=0.005`、`ticker_age_seconds=0.236`。
  判定は **POSITION_CONFIRMED**。USD/JPY 100通貨では、1円変動で概算約100円、0.1円変動で
  概算約10円の損益変動があり得る。Step 4G-AではHTTP POST、新規注文、追加注文、決済、
  取消、注文変更、approval id発行、approval gate、ledger resetは未実行。決済する場合は
  Step 4G-Bとして別タスク・別承認で扱う。
- 直前フェーズ: **Step 4F-B one-shot retry with approval gate 完了 / live order success、OPEN建玉あり**。
  `dd705dd` 対応後、2026-06-26 11:09 JSTに `STEP4F-` approval gateを発行し、
  ユーザーが同じCodexセッションで短い1行approval commandを完全一致入力した。承認後再preflightでは
  `GMO_FX_API_KEY: set` / `GMO_FX_API_SECRET: set`、`account/assets=success`、
  `open_positions_count_before=0`、`active_orders_count_before=0`、当日one-shot ledger
  `PREPARED` / `attempt_count=0`、Git clean、market window allowed、maintenance false、
  `bid=161.8`、`ask=161.805`、`spread_jpy=0.005` を確認した。HTTP POSTは承認後に1回だけ実行し、
  sanitized結果は `transport_result=success`、`api_status_success=true`、`result_unknown=false`。
  実行後read-only照合では `account/assets=success`、`open_positions_count_after=1`、
  `active_orders_count_after=0`。raw request / raw response / headers / signature / credential値 /
  order ID / execution IDは表示・保存していない。ledgerは `POST_COMPLETED`、`attempt_count=1`、
  `result_category=success`。retry、loop、追加注文、注文変更、取消、決済、自動クローズは行っていない。
  OPEN建玉が残っている可能性があるため、以後の操作は別タスク・別承認で扱う。
- 直前フェーズ: **Step 4F-APPROVAL修正完了 / runner approval仕様をStep 4F-Bへ整合**。
  Step 4F-B実行前コード確認で、Step 4F-Bプロンプトが要求する `STEP4F-` approval id prefix、
  `ACK_ORDER_PERMISSION=YES`、`ACK_IP_ACCOUNT_CHECK=YES` と既存runnerの旧Step 4 compact
  approval仕様が一致していないため、安全停止した。runner側はStep 4F-B用approval idを
  `STEP4F-` prefixに統一し、Step 4F-B用approval commandでは `ACK_ORDER_PERMISSION=YES` と
  `ACK_IP_ACCOUNT_CHECK=YES` を必須ACKとして扱う。旧compact command（追加ACKなし）と `STEP4-`
  prefixはStep 4F-B用としてfail closedする。approval TTL 300秒、承認後再preflight必須、
  最終動的preflightからPOSTまで30秒以内、HTTP POST最大1回、retry / loop禁止は維持する。
  この修正ではHTTP POST、実注文、approval id発行、approval gate発行、fresh preflight、read-only接続、
  ledger reset / delete / edit / overwrite、credential / headers / signature / raw response表示・保存は未実行。
  次回Step 4F-Bは別タスクとしてfresh preflightから再実行し、approval gateで必ず停止する。
- 直前フェーズ: **Step 4F-A sanitized retry preflight / no POST完了、READY_FOR_LATER_4F_B、
  本日再POST不可**。ユーザー報告として、GMO外国為替FX APIキー設定で「トレード > 注文」権限に
  チェックを入れた後、Codex環境では `GMO_FX_API_KEY: set` / `GMO_FX_API_SECRET: set` を値非表示で確認した。
  read-only Private APIはsanitized出力で `account/assets=success`、`open_positions_count=0`、
  `active_orders_count=0`。public rulesはUSD_JPY `minOpenOrderSize=100` / `sizeStep=1`、
  `maxOrderSize=500000`、TRY_JPY / ZAR_JPY / MXN_JPY例外にUSD_JPYは含まれないことを確認した。
  public tickerは `bid=161.789`、`ask=161.794`、`spread_jpy=0.005`、`ticker_age_seconds=0.650`、
  service status `OPEN`、maintenance false。ただし確認時刻は `2026-06-25T14:54:16+0900 JST` で、
  初回retry候補の10:00-14:30 JST枠外。ledgerはsanitized確認のみで `POST_COMPLETED`、
  `attempt_count=1`、`result_category=api_rejected` のままなので、本日再POST不可を維持する。
  read-only successは注文権限成功を意味しない。Step 4F-Bへ進めるのは別日または明示された新ledger方針があり、
  ユーザー側permission/IP/account確認が完了し、fresh preflightが全て通る場合のみ。Step 4F-Bでも
  approval gateで停止し、即POSTしない。Step 4F-AではHTTP POST、実注文、approval id発行、approval gate、
  retry、loop、追加注文、注文変更、取消、決済、ledger reset / delete / edit / overwrite、raw response表示・保存は未実行。
- 直前フェーズ: **Step 4E GMO FX API注文権限追加後no POST確認完了 / same-day retry禁止維持**。
  ユーザー報告として、GMO外国為替FX APIキー設定で「トレード > 注文」権限にチェックを入れたことを
  `docs/STEP4_API_REJECT_REVIEW.md` に追記した。これはユーザー報告の記録であり、CodexがGMO管理画面を
  直接確認したものではなく、API上で注文権限が有効化されたことを確定確認したものでもない。
  Step 4E自体ではAPI key / secretがmissingだったためread-only確認は未実行だったが、Step 4F-Aでset環境の
  read-only no-POST preflightを実施した。
- 直前フェーズ: **Step 4D sanitized reject classification + API権限チェックリスト整備完了 / REJECT_CAUSE_PARTIAL**。
  `backend/app/live_verification/live_order_reject_classification.py` と
  `backend/app/tests/test_live_verification_live_order_reject_classification.py`、
  `docs/STEP4_API_REJECT_REVIEW.md` を追加し、前回Step 4B-Bの
  `transport_result=api_rejected` をraw responseなしで分類するlocal-only sanitized modelを整備した。
  ledgerは読み取りのみで `POST_COMPLETED`、`attempt_count=1`、
  `result_category=api_rejected` をsanitized確認し、ledger reset / delete / edit / overwriteは行っていない。
  raw error codeがないため判定は **REJECT_CAUSE_PARTIAL**。候補はAPI key scope、order permission、
  IP restriction、account procedure、account state、margin、signing、timestamp、body、size等に分け、
  user-side checklistとしてdocs化した。HTTP POST、実注文、retry、loop、追加注文、注文変更、取消、
  決済、approval id発行、BUY/SELL選択、API key / secret確認、read-only接続、raw response表示・保存は未実行。
  次候補はStep 4E user-side API permission/account/IP/settings checklist confirmationであり、
  Step 4D自体は再注文を許可しない。
- 直前実装フェーズ: **Step 4B-APPROVAL修正 短い1行approval command化完了 / Step 4B実行は未実行**。
  `backend/app/live_verification/live_order_once.py` と
  `backend/app/tests/test_live_verification_live_order_once.py` を追加し、live outbound bodyのfield allowlist、
  approval commandのexact match、300秒expiry（elapsed seconds <= 300は有効、> 300は失効）、
  persistent one-shot ledger、POST直前の`POST_STARTED`記録、
  fake transportでの1回限定実行、timeout時`RESULT_UNKNOWN`、no-retry / no-loop / no-leak guardを実装した。
  Step 4B-TTL修正では、以前の120秒固定を廃止し、実装・テスト・docsを300秒へ統一した。
  Step 4B-APPROVAL修正では、長い日本語承認文を廃止/非推奨化し、`STEP4_APPROVE <approval_id>
  SIDE=BUY|SELL SYMBOL=USD_JPY SIZE=100 ACK_...=YES` の短い1行ASCII command形式へ変更した。
  実資金損失、OPEN建玉、API scope、重要経済指標、retry / loop / 追加注文 / 注文変更 /
  取消 / 決済禁止、結果不明時停止はACK tokenで明示し、欠落、`YES`以外、余分なtoken、
  改行、余分な空白、旧日本語長文承認文はfail closedする。
  ただし承認後再preflightは引き続き必須であり、最終動的preflightからPOSTまで30秒以内の条件も緩めない。
  送信bodyは `symbol=USD_JPY`、`side=BUY|SELL`、`size="100"`、`clientOrderId`、
  `executionType=MARKET` のみで、`timeInForce` / `settleType` / price系 / internal metadataは
  live outbound bodyへ含めない。実HTTP transport関数は明示実行関数からしか使えず、API key / secretは
  関数引数のみで扱い、`.env`や環境変数は読まない。APPROVAL修正ではHTTP POST、実注文、
  approval_id発行、API key / secret確認、read-only接続、BUY/SELL選択、注文取消、決済、
  追加注文、実資金検証は未実行。Step 4B実注文は別タスク・別承認で扱う。
- 直前フェーズ: **Step 4-SPEC USD_JPY最小注文数量 仕様差異解消完了 / READY_FOR_STEP4_RETRY**。
  `docs/STEP4_SYMBOL_RULES_RECONCILIATION.md` を作成し、live public API
  `GET /public/v1/symbols`、公式商品ページ、2025-04-04お知らせ、2025-09-25お知らせ、
  API docs response exampleを照合した。live public APIではUSD_JPY
  `minOpenOrderSize=100` / `sizeStep=1`、TRY_JPY / ZAR_JPY / MXN_JPYは
  `minOpenOrderSize=10000`。公式商品ページと2025-09-25お知らせもUSD_JPYを100通貨対象に含め、
  TRY/JPY・ZAR/JPY・MXN/JPYだけを10,000通貨例外としている。API docsのUSD_JPY
  `minOpenOrderSize=10000` は `responsetime=2022-12-15` の古いresponse exampleであり、
  2025年以降の公式通知と現在のlive public APIより現行値ではないと分類した。判定は
  **READY_FOR_STEP4_RETRY**。ただしStep 4 retry、approval id、HTTP POST、実注文、
  Private API注文系接続、BUY/SELL選択、10000通貨への変更は未実行。次に進む場合も
  Step 4A retryとしてpreflightを再実行し、exact approval gateで停止すること。
  Step 3では `LiveOrderPreflightSnapshot` / `LiveOrderPreflightDecision` /
  `evaluate_live_order_preflight` をlocal-onlyで追加し、API key / secretはpresence flagのみ、
  read-only checks、open positions count、active orders count、known previous result、
  Step 2 skeleton / mock submission、tests / ruff / git、market / maintenance / event window、
  attempt count、retry / loop、kill switch、HTTP POST / real order attemptを監査対象にした。
  Step 3実装時のCodex実行環境では `GMO_FX_API_KEY: missing` /
  `GMO_FX_API_SECRET: missing` だったため、既存read-only接続手順は実行せず、Step 3判定は
  **NO_GO**。HTTP POST、実注文、実資金検証、Private API書き込み、broker、`OrderRequest`、
  real order API client、本番公開API追加には進んでいない。
  Phase 2E-4Rでは直近kline条件の
  `gmo-public / USD_JPY / M1 / steps 5 / --enable-shadow-risk` run
  `20260622_100540_shadow_USD_JPY_gmo-public` をレビューし、実runで `REAL_PUBLIC_BID_ASK` candidate、
  `ALLOW_SHADOW` decision、対応するvirtual result、candidate/decision/virtual resultのID相関を確認した。
  古い3 stepはticker/kline skewによりcandidate生成前の`NO_TRADE`へ安全に倒れた。safety violation 0、
  broken 0、raw response保存なし、Private API/APIキー/broker/実注文なし。詳細は
  [PHASE2E4R_GMO_PUBLIC_REAL_BID_ASK_REVIEW.md](PHASE2E4R_GMO_PUBLIC_REAL_BID_ASK_REVIEW.md)。
  Phase 2E-5では、今後のgmo-public risk/audit継続確認をmanual only、`USD_JPY / M1 / steps 5`、
  1日1回まで、短期3回・中期5〜10回を目安に進める計画を定義した。成功/保留/停止条件、ticker/kline skew評価、
  Phase 2Fへ進む条件は
  [PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md](PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md)。
  Phase 2E-5 1回目run `20260622_103430_shadow_USD_JPY_gmo-public` では `REAL_PUBLIC_BID_ASK` 2件、
  candidate 2件、`ALLOW_SHADOW` 1件、`REJECT_SHADOW` 1件、ALLOW時のみvirtual result、REJECT時virtual resultなし、
  `cooldown_active` reject、ticker/kline skew 2件の安全`NO_TRADE`を確認した。同日2回目は1日1回ルールにより
  未実行で停止した。詳細は
  [PHASE2E5_RUN1_REVIEW_AND_NEXT_RUN_PREP.md](PHASE2E5_RUN1_REVIEW_AND_NEXT_RUN_PREP.md)。
  Phase 2E-5短期3回確認レビューでは、
  `20260622_103430_shadow_USD_JPY_gmo-public`、`20260623_000652_shadow_USD_JPY_gmo-public`、
  `20260624_001906_shadow_USD_JPY_gmo-public` の3runを整理し、3回すべてで`REAL_PUBLIC_BID_ASK`、
  candidate、`ALLOW_SHADOW`、ALLOW時のみvirtual resultを確認した。1回目と3回目では`cooldown_active`による
  `REJECT_SHADOW`とREJECT時virtual resultなしを確認した。ticker/kline skewは`stale_data` / `NO_TRADE`へ
  安全fail closedし、safety violation、broken、invalid risk row、kill switch active、raw response保存、
  Private API/APIキー/broker/実注文はなし。判定は **A: Phase 2Fへ進んでよい**。ただしPhase 2F実行は
  別タスクであり、Private API、APIキー、broker、実注文、実資金、自動売買、本番公開API追加には進まない。
  詳細は [PHASE2E5_SHORT_RUNS_REVIEW.md](PHASE2E5_SHORT_RUNS_REVIEW.md)。
  Phase 3A準備では、将来のPrivate API read-only、APIキー / secret管理、Live Verification Mode、
  100通貨・1回だけの極小実資金検証までのロードマップをdocs-onlyで整理した。これは実装ではなく、
  Private API接続、APIキー入力・表示・保存、`.env`変更、broker、注文API、実注文、実資金検証には進んでいない。
  詳細は [PHASE3A_PRIVATE_API_READONLY_AND_LIVE_VERIFICATION_ROADMAP.md](PHASE3A_PRIVATE_API_READONLY_AND_LIVE_VERIFICATION_ROADMAP.md)。
  Phase 2FではPublic shadow risk/audit安定性レビューを完了し、3runすべての`REAL_PUBLIC_BID_ASK`、
  ALLOW、ALLOW時virtual result、1回目/3回目の`cooldown_active` REJECT、REJECT時virtual resultなし、
  skew / stale_dataの安全`NO_TRADE`を確認した。判定は **A: Public shadow risk/auditはPhase 3B準備へ進める水準**。
  ただしPhase 3B実装へ即進まず、先にPhase 2G Public shadow risk/auditオフライン最終デバッグ監査を
  半日程度で挟むことを推奨する。詳細は
  [PHASE2F_PUBLIC_SHADOW_RISK_AUDIT_STABILITY_REVIEW.md](PHASE2F_PUBLIC_SHADOW_RISK_AUDIT_STABILITY_REVIEW.md)。
  Phase 2Gではgmo-public再実行やコード修正を行わず、既存テスト、focused test、offline mock run、summarize、
  禁止参照確認でPublic shadow risk/auditの最終デバッグ監査を完了した。`python3 -m pytest -q` は354 passed、
  `ruff check .` はclean、focused testは177 passed。mock run
  `20260624_005528_shadow_USD_JPY_mock` ではsynthetic spreadがfail closedでREJECTされ、virtual resultは0、
  safety violation / invalid risk row / raw response保存は0だった。判定は
  **A: Phase 3B read-only公式仕様確認・実装設計へ進んでよい**。詳細は
  [PHASE2G_PUBLIC_SHADOW_RISK_AUDIT_OFFLINE_DEBUG_AUDIT.md](PHASE2G_PUBLIC_SHADOW_RISK_AUDIT_OFFLINE_DEBUG_AUDIT.md)。
  Phase 3B-0ではGMOコイン外国為替FXの公式API docsを確認し、Private REST APIのread-only候補GET endpoint、
  禁止する注文・変更・取消・決済系POST endpoint、認証・署名仕様、APIキー / secret管理、Phase 3B分割案を
  docs-onlyで整理した。Private API接続、APIキー入力、`.env`変更、backend実装、broker、注文API、実注文、
  実資金には進んでいない。詳細は
  [PHASE3B0_PRIVATE_API_READONLY_OFFICIAL_SPEC_DESIGN.md](PHASE3B0_PRIVATE_API_READONLY_OFFICIAL_SPEC_DESIGN.md)。
  Phase 3B-1では `backend/app/private_api/` に実接続なし・APIキー環境読込なし・`.env`読込なしの
  read-only skeleton、auth/signing helper、sanitized schemas、errors、forbidden endpoint guardを追加し、
  mocked testsとno-order-import guardを整備した。GET read-only候補だけをwhitelistし、POST/PUT/DELETEの
  注文・変更・取消・決済系endpointは例外で拒否する。Private API実接続、APIキー入力、`.env`変更、broker、
  注文API、実注文、実資金には進んでいない。
  Phase 3B-2ではread-only endpointごとのmocked tests、sanitizer、error handlingを拡張した。GET候補7件の
  mocked provider変換、sanitized `PrivateApiError`、error時no-retry、forbidden endpoint guardを確認した。
  実HTTP接続、APIキー入力、`.env`読込・変更、broker、注文API、実注文、実資金には進んでいない。次に進む場合は
  Phase 3B-3としてローカル接続前レビュー、APIキー管理手順レビュー、実接続しない運用設計確認を別タスクで扱う。
  Phase 3B-3ではPrivate API read-onlyローカル接続前レビューとして、APIキー / secret管理手順、
  read-only権限分離、`.env`安全手順、Phase 3B-4初回接続endpoint、禁止endpoint、接続前後チェックリスト、
  停止条件をdocs化した。判定は **A: Phase 3B-4 read-onlyローカル接続確認へ進んでよい**。ただしPhase 3B-4は
  別タスクであり、Phase 3B-3ではPrivate API実接続、APIキー入力、`.env`変更、broker、注文API、実注文、
  実資金には進んでいない。詳細は
  [PHASE3B3_PRIVATE_READONLY_PRECONNECT_REVIEW.md](PHASE3B3_PRIVATE_READONLY_PRECONNECT_REVIEW.md)。
  Phase 3B-4では `account/assets`、`openPositions`、`activeOrders` の3 endpointについて、
  Private API read-onlyローカル接続確認結果を総合レビューした。最終結果は3 endpoint successで、
  raw response、headers、signature、credentialsの保存・表示なし、broker、OrderRequest、注文API、
  実注文、実資金検証なしを確認した。判定は **A: Phase 3B-4 read-onlyローカル接続確認は完了**、
  **A: Phase 3C Live Verification Mode設計へ進んでよい**。ただし次タスクでも、まず設計レビューとして扱い、
  Live Verification Mode実装、broker、注文API、実注文、実資金検証へは進まない。詳細は
  [PHASE3B4_PRIVATE_READONLY_CONNECTION_REVIEW.md](PHASE3B4_PRIVATE_READONLY_CONNECTION_REVIEW.md)。
  Phase 3CではLive Verification Modeの定義、許可範囲、禁止範囲、注文前read-onlyチェック、risk decision /
  candidate / order intent相関、order intent設計、kill switch / STOP / fail closed条件、実注文前後の
  チェックリスト、Phase 3Dへ進む条件をdocs-onlyで整理した。Live Verification Mode実装、order intent実装、
  broker、OrderRequest、注文API、実注文、実資金検証には進んでいない。詳細は
  [PHASE3C_LIVE_VERIFICATION_MODE_DESIGN.md](PHASE3C_LIVE_VERIFICATION_MODE_DESIGN.md)。
  Phase 3C実装設計レビューでは、実装をPhase 3C-1 mocked core、Phase 3C-2 ID相関テスト、
  Phase 3C-3 dry-run統合、Phase 3D前 broker / order API実装前レビューへ分割した。order intent、
  read-only precheck、live verification state、ID相関、テスト方針をdocs-onlyで整理した。Live Verification Mode実装、
  order intent実装、broker、OrderRequest、注文API、実注文、実資金検証には進んでいない。詳細は
  [PHASE3C_IMPLEMENTATION_DESIGN_REVIEW.md](PHASE3C_IMPLEMENTATION_DESIGN_REVIEW.md)。
  Phase 3C-1では `backend/app/live_verification/` に、order intent、read-only precheck result、
  live verification state、errorsのpure mocked coreとmocked unit tests / no-order-import guardを追加した。
  `USD_JPY`、100通貨、ALLOW相当、read-only precheck passed、manual confirmation必須の条件を満たす場合だけ
  order intentを作れる。READY_FOR_ORDER_REVIEWまでで停止し、broker、OrderRequest、注文API、実注文、
  実資金検証、Private API追加接続、APIキー確認、`.env`確認には進んでいない。次に進む場合は
  Phase 3C-2 ID相関テストを別タスクで扱う。
  Phase 3C-2では `backend/app/live_verification/correlation.py` と
  `backend/app/tests/test_live_verification_id_correlation.py` を追加し、signal、candidate、risk decision、
  readonly precheck、order intent、verification runのID相関をpure mocked helperとtestsで固定した。
  必須ID欠損、verification_run_id不整合、ALLOW系以外、precheck failed、同一run内の2件目intentを
  fail closedし、READY_FOR_ORDER_REVIEWまでで停止することを確認した。broker、OrderRequest、注文API、
  実注文、実資金検証、Private API追加接続、APIキー確認、`.env`確認には進んでいない。次に進む場合は
  Phase 3C-3 dry-run統合テストを別タスクで扱う。
  Phase 3C-3では `backend/app/live_verification/dry_run.py` と
  `backend/app/tests/test_live_verification_dry_run.py` を追加し、read-only precheck、risk decision、
  ID correlation、order intent、state transition、no-order guardを1本のpure mocked dry-run flowとして接続した。
  成功系はREADY_FOR_ORDER_REVIEWまで到達し、precheck failed、ALLOW系以外、ID不整合、同一run内2件目intent、
  unsupported symbol / units、manual confirmationなし、open position / active orderあり、raw response /
  headers / credentials保存・表示フラグありはfail closedする。broker、OrderRequest、注文API、実注文、
  実資金検証、Private API追加接続、APIキー確認、`.env`確認には進んでいない。次に進む場合も、
  Phase 3D前 broker / order API実装前レビューを別タスクで行う。
  Phase 3D前レビューでは、broker / order API実装へ進む前の安全条件、禁止境界、分割計画、
  実注文前の明示承認条件をdocs-onlyで整理した。判定は
  **A: Phase 3D-0 公式仕様・危険endpoint再レビューへ進んでよい**。ただしPhase 3D前レビューでは
  broker、OrderRequest、注文API client、注文payload builder、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。次に進む場合も、まず
  [PHASE3D_PRE_ORDER_API_REVIEW.md](PHASE3D_PRE_ORDER_API_REVIEW.md) に従って
  Phase 3D-0 docsレビューだけを別タスクで扱う。
  Phase 3D-0では、GMOコイン外国為替FXの公式API docsと既存Phase 3B / 3C / 3D前docsに基づき、
  read-only endpointと注文系endpointを分離し、`order`、`speedOrder`、IFD / IFDOCO、change、cancel、
  `closeOrder`、`ws-auth` 系endpointをHigh risk / forbidden now / review onlyとして整理した。判定は
  **A: Phase 3D-1 order review model / final checklist mocked設計・実装へ進んでよい**。ただしPhase 3D-0でも、
  broker、OrderRequest、注文API client、注文payload builder、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。詳細は
  [PHASE3D0_ORDER_API_OFFICIAL_SPEC_REVIEW.md](PHASE3D0_ORDER_API_OFFICIAL_SPEC_REVIEW.md)。
  Phase 3D-1では `backend/app/live_verification/order_review.py` と
  `backend/app/tests/test_live_verification_order_review.py` を追加し、`OrderIntent` からreview-only
  `OrderReview` を生成するpure functionと、実注文前の `FinalOrderChecklist` 評価を実装した。
  checklistは全必須項目がtrueの場合だけpassedとなり、false項目を `fail_reasons` に保持する。
  これは注文payloadではなく、broker、OrderRequest、注文API client、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。次に進む場合はPhase 3D-2
  broker boundary / no-network adapter mocked設計を別タスクで扱う。
  Phase 3D-2では `docs/PHASE3D2_BROKER_BOUNDARY_NO_NETWORK_ADAPTER_DESIGN.md` を作成し、
  `OrderReview` / `FinalOrderChecklist` の先に置くbroker boundary、no-network adapterの責務、
  `NoNetworkBrokerBoundaryResult` 候補、fail closed条件、no-order guard policy、Phase 3D-2A以降の分割案を
  docs-onlyで整理した。no-network adapter実装、broker、OrderRequest、注文API client、注文payload builder、
  Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。次に進む場合は
  Phase 3D-2A no-network broker boundary adapter mocked実装を別タスクで扱う。
  Phase 3D-2Aでは `backend/app/live_verification/broker_boundary.py` と
  `backend/app/tests/test_live_verification_broker_boundary.py` を追加し、
  `NoNetworkBrokerBoundaryResult` と `evaluate_no_network_broker_boundary()` をpure mocked / no-networkで実装した。
  checklist未pass、READY_FOR_ORDER_REVIEW以外、network/API key/payload/broker/real order flags、
  `USD_JPY` / 100通貨 / `live_verification` 逸脱、ID不整合は `boundary_passed=false` でfail closedする。
  broker、OrderRequest、注文API client、注文payload builder、HTTP POST、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。次に進む場合はPhase 3D-2B
  fail closed / no-order guard hardeningを別タスクで扱う。
  Phase 3D-2Bでは `backend/app/tests/test_live_verification_broker_boundary.py` と
  `backend/app/tests/test_live_verification_no_order_imports.py` を強化し、複数fail closed理由の同時検出、
  no-network flag横断、ID不整合 / checklist failure / state failureの蓄積、payload / transport / credential
  フィールド非保持、HTTP client import、GMO FX env名、注文endpoint文字列、注文送信状態名、payload field名の
  実装コード混入検出を追加した。broker、OrderRequest、注文API client、注文payload builder、HTTP POST、
  Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。次に進む場合は
  Phase 3D-3 order payload builder実装前レビューを別タスクで扱う。
  Phase 3D-3では `docs/PHASE3D3_ORDER_PAYLOAD_BUILDER_PRE_IMPLEMENTATION_REVIEW.md` を作成し、
  将来のmocked order payload builderの責務、Phase 3D-4で扱ってよい候補field、
  Phase 3D-4でも扱わない注文種別、`OrderReview` / `FinalOrderChecklist` /
  `NoNetworkBrokerBoundaryResult` との関係、mocked payload candidate候補データ、fail closed条件、
  broker / API client / HTTP POSTとの分離、Phase 3D-4以降の分割案、no-order guard方針をdocs-onlyで整理した。
  order payload builder実装、order payload model実装、broker、OrderRequest、注文API client、HTTP POST、
  Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。次に進む場合は
  Phase 3D-4 mocked order payload builder実装を別タスクで扱う。
  Phase 3D-4では `backend/app/live_verification/payload_candidate.py` と
  `backend/app/tests/test_live_verification_payload_candidate.py` を追加し、`MockedOrderPayloadCandidate` と
  `build_mocked_order_payload_candidate()` をpure mocked / local-onlyで実装した。`OrderReview` /
  `FinalOrderChecklist` / `NoNetworkBrokerBoundaryResult` がpassしている場合だけcandidateを生成し、
  endpoint、method、URL、request body、raw response、headers、signature、credentialは保持しない。
  broker、OrderRequest、注文API client、HTTP POST、Private API追加接続、APIキー確認、`.env`確認、
  実注文、実資金検証には進んでいない。次に進む場合はPhase 3D-4B mocked payload builder
  fail closed / no-network guard hardeningを別タスクで扱う。
  Phase 3D-4Bでは `test_live_verification_payload_candidate.py` と
  `test_live_verification_no_order_imports.py` を強化し、candidateのfail closed、許可値固定、
  非送信・非payload本体、HTTP / credential / endpoint / env / broker混入禁止を追加で固定した。
  `payload_candidate.py` 本体は送信不能なlocal-only candidateのまま維持し、broker、OrderRequest、
  注文API client、HTTP POST、Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には
  進んでいない。次候補はPhase 3D-5 real order API client実装前レビューである。
  Phase 3D-5では `docs/PHASE3D5_REAL_ORDER_API_CLIENT_PRE_IMPLEMENTATION_REVIEW.md` を作成し、
  real order API client実装前の安全条件、まだ作らない範囲、将来扱う可能性がある最小endpoint候補、
  APIキー / secret / `.env` の扱い、実HTTP POST禁止方針、Phase 3D-6以降の推奨分割、
  実装前・実注文前の明示承認条件をdocs-onlyで整理した。判定は
  **A: Phase 3D-6 real order API client no-network skeleton / disabled-by-default設計・mock実装へ進んでよい**。
  ただしreal order API client、broker、OrderRequest、注文API client、HTTP POST、Private API追加接続、
  APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。
  Phase 2E-1Hでは`app/shadow/`内の
  OrderCandidate、pure risk評価、sticky Kill switch、deterministic ID、local JSONL writer、legacy互換summarizeに
  対し、Phase 2E-1.5監査のD-1〜D-4を修正した。spread provenanceのfail closed化、malformed inputの
  reason付きreject、typed audit schema/root containment、unsafe risk rowのsummary検出を実装済みである。
  再監査では統合前必須修正なし、Phase 2E-2の設計着手可と判定した。Phase 2E-2設計では、run単位の
  KillSwitchState ownership、pre-gate、AuditLogWriteError時のexit code 2、STOPファイル、candidate/decision/
  virtual result相関、summary互換、統合test方針を整理した。実装では`--enable-shadow-risk`の明示フラグ時のみ
  STOP pre-gate、candidate生成、pure `evaluate()`、typed audit JSONL、REJECT時virtual result抑止、audit失敗時
  fail closed/exit code 2、summary/metadataのrisk情報を接続した。デフォルトrunはlegacy互換を維持する。
  Phase 2E-2.5監査では修正必須事項なし、Phase 2E-3設計へ進行可と判定した。詳細は
  [PHASE2E2_INTEGRATION_AUDIT.md](PHASE2E2_INTEGRATION_AUDIT.md)。Public ticker bid/ask連携実装、
  Private API、broker、実注文へは明示承認なしに進まない。設計は
  [PHASE2E2_SESSION_INTEGRATION_DESIGN.md](PHASE2E2_SESSION_INTEGRATION_DESIGN.md)、再監査結果は
  [PHASE2E1H_REAUDIT.md](PHASE2E1H_REAUDIT.md)、初回監査と修正追記は
  [PHASE2E1_SAFETY_AUDIT.md](PHASE2E1_SAFETY_AUDIT.md)、設計は
  [PHASE2E0_SAFETY_DESIGN.md](PHASE2E0_SAFETY_DESIGN.md) と
  [PHASE2E0_5_SAFETY_REVIEW.md](PHASE2E0_5_SAFETY_REVIEW.md) を参照する。
  Private API、APIキー、実注文、本番公開には進まない。

## 2. 完了済みフェーズ

- **v0.1 read-only reports 公開版**: `/`、`/reports`、`/reports/[run_id]`。backend は `/health` と
  `/api/reports*` の GET のみ。orders / paper / automation は公開していない。
- **Production Smoke**: `npm run e2e:prod`、7 tests passed の実績あり。
- **Phase 2A**: `backend/app/shadow/` に local-only / no-network / no-order の shadow 検証土台を実装。
- **Phase 2B**: GMO Public API read-only adapter と local CLI を実装。Public API のみで APIキー・注文なし。
- **Phase 2C**: local shadow run、demo 用 `momentum_signal`、`events.jsonl` / `summary.json` /
  `metadata.json`、仮想 PnL 集計を実装。出力は `shadow_exports/`。
- **Phase 2D**: 複数 run の集計 CLI、Markdown / CSV 出力、safety 違反検出を実装。
- **Phase 2E-3.5**: Public ticker bid/ask provenance連携監査を完了。B判定で、修正必須事項なし。
  Phase 2E-4設計または実行指示作成へ進めるが、実runやPrivate/APIキー/broker/実注文には別承認が必要。
- **Phase 2E-4.5**: gmo-public risk/audit結果レビューを完了。`ticker_kline_skew_reject_count=2` は
  安全fail closed。実runでの`REAL_PUBLIC_BID_ASK` candidate/ALLOWは未確認。
- **Phase 2E-4R**: 直近kline条件のgmo-public再確認レビューを完了。実runで`REAL_PUBLIC_BID_ASK`
  candidate、`ALLOW_SHADOW`、virtual result相関を確認。Phase 2E-5設計へ進める。
- **Phase 2E-5**: gmo-public risk/audit継続確認計画を設計。manual only、1日1回まで、
  `USD_JPY / M1 / steps 5 / --enable-shadow-risk`、短期3回・中期5〜10回、成功/保留/停止条件、
  Phase 2Fへ進む条件を定義。実行、コード変更、Private API、broker、実注文には進んでいない。
- **Phase 2E-5 1回目レビュー**: run `20260622_103430_shadow_USD_JPY_gmo-public` をレビューし、
  `REAL_PUBLIC_BID_ASK` 2件、ALLOW 1件、REJECT 1件、ALLOW時のみvirtual result、REJECT時virtual resultなし、
  1日1回ルールによる同日2回目未実行停止を確認。次は別日に2回目を1回だけ実行する。
- **Phase 2E-5短期3回確認レビュー**: 3runすべてで`REAL_PUBLIC_BID_ASK` / candidate / ALLOW /
  virtual resultを確認し、1回目と3回目で`cooldown_active` REJECTとREJECT時virtual resultなしを確認。
  safety violation、broken、invalid risk row、raw response保存、Private API/APIキー/broker/実注文はなし。
  判定はAで、Phase 2Fレビュー着手可とした。その後Phase 2Fレビューは完了済み。
- **Phase 2F Public shadow risk/audit安定性レビュー**: Phase 2E-5短期3runを安定性レビューし、
  Public shadow risk/auditはPhase 3B準備へ進める水準と判定。Phase 3B実装へ即進まず、先にPhase 2G
  オフライン最終デバッグ監査を挟むことを推奨。Private API、APIキー、broker、実注文、実資金には進んでいない。
- **Phase 2G Public shadow risk/auditオフライン最終デバッグ監査**: gmo-publicを再実行せず、既存テスト、
  focused test、offline mock run、summarize、禁止参照確認でSTOP / kill switch / audit failure /
  safety violation / duplicate / cooldown / 相関検出を監査。判定はAで、Phase 3B read-only公式仕様確認・
  実装設計へ進んでよい。ただしPrivate API接続、APIキー入力、broker、注文API、実注文、実資金には進んでいない。
- **Phase 3B-0 Private API read-only公式仕様確認・実装設計**: 公式API docsに基づき、REST GETのread-only候補、
  POSTの注文・変更・取消・決済系禁止endpoint、認証・署名、APIキー / secret管理、Phase 3B分割案を整理。
  実装・接続・APIキー入力・`.env`変更・broker・実注文はなし。
- **Phase 3B-1 mocked private readonly skeleton**: `backend/app/private_api/` のauth helper、
  readonly client skeleton、schemas、errors、mocked tests、no-order-import guardを追加。実HTTP接続、
  APIキー入力、`.env`読込、broker、注文API、実注文はなし。
- **Phase 3B-2 mocked private readonly endpoints**: GET read-only候補7件のmocked tests、
  sanitizer、sanitized error handling、forbidden endpoint guard拡張を追加。実HTTP接続、APIキー入力、
  `.env`読込・変更、broker、注文API、実注文はなし。
- **Phase 3B-3 private readonly preconnect review**: APIキー / secret管理、read-only権限分離、
  `.env`安全手順、Phase 3B-4初回endpoint、禁止endpoint、接続前後チェックリスト、停止条件をdocs化。
  判定はAだが、実接続、APIキー入力、`.env`変更、broker、注文API、実注文はなし。
- **Phase 3A準備ロードマップ設計**: Private API read-only、APIキー / secret管理、read-only境界、
  Live Verification Mode、Phase 3D極小実資金検証条件をdocs-onlyで整理。実装、接続、`.env`変更、broker、
  注文API、実注文はなし。Phase 3BへはPhase 2E-5短期確認、Phase 2Fレビュー、Phase 2G監査の完了後に、
  read-only公式仕様確認・実装設計を別タスクで扱う。
- 直近確認実績: backend 354 passed、`ruff check .` OK、production smoke 7 passed。

実績値はスナップショットであり、作業時は利用可能なコマンドで再確認する。

## 3. 安全制約と公開境界

### 公開してよい範囲

- 無害な `e2e_*` サンプルによる read-only reports と、その加工済みメタ情報。
- 実取引、実資金、APIキー、個人情報を含まない Markdown 概要。
- CSV 本文を含まないファイルメタ情報。

### 公開・実装してはいけない範囲

- Private API、APIキー、secret、`.env`、実資金、実注文。
- 残高、建玉、注文履歴、約定の取得、および注文・変更・取消。
- 実 API レスポンス、実取引由来レポート、実データ CSV、本番 DB の内容。
- paper / shadow の実行情報、シグナル、ポジション、設定・管理・実行画面の本番公開。
- 本番公開 API の追加、`backend/app/main_readonly.py` の変更、`ENABLE_LIVE_TRADING=true`。
- Render / Vercel 設定変更、DB 本番化、認証実装。
- `shadow_exports/`、集計出力、実データ入り `analysis_exports/` の commit。

公開判断の詳細は [PUBLICATION_POLICY.md](PUBLICATION_POLICY.md) を単一参照点とする。

## 4. Codex 中心運用と役割分担

- 基本運用は Codex で、指定タスクの実装・検証・commit・push を行う。ただし commit / push は依頼された場合のみ行う。
- ChatGPT は次タスクの整理、Codex 用プロンプト作成、最終報告レビューに使う。
- Claude Code は大きめの既存設計確認、安全レビュー、複数ファイルにまたがる慎重な改修時に補助的に使う。
- 重要フェーズは ChatGPT または Claude Code で設計確認してから進める。
- Private API、APIキー、実資金、実注文、本番公開 API 追加、DB、認証に近づく場合は必ず事前レビューを挟む。

## 5. 変更境界

タスクごとに、変更してよいファイルを明示して最小限に編集する。shadow 運用タスクの通常範囲は
local-only の `backend/app/shadow/`、関連する `backend/scripts/`、offline tests、関連 docs である。

明示承認なしに変更しない範囲:

- `backend/app/main_readonly.py`、`backend/app/main.py`、backend 公開 API。
- frontend 本番 UI、production smoke、Render / Vercel 設定。
- `.env`、`.env.example`、APIキー、secret、DB、broker、注文・RiskManager 経路。

## 6. 検証コマンド候補

必ず `backend/pyproject.toml` と `frontend/package.json` を先に確認し、変更範囲に必要なコマンドだけを実行する。

```bash
# backend（ローカル・offline）
cd backend
.venv/bin/pytest
.venv/bin/ruff check .

# frontend
cd frontend
npm run lint
npm run test
npm run build
npm run e2e

# production read-only smoke（非破壊。依頼・必要性がある場合のみ）
cd frontend
npm run e2e:prod
```

文書だけの変更では、リンク・記述・diff・禁止対象が未変更であることの確認を優先し、無関係な全テストを
機械的に実行しない。ネットワークを使う GMO Public CLI は自動検証に含めない。

## 7. 生成物を git add しない確認

```bash
git status --short
git status --ignored --short -- shadow_exports backend/shadow_exports analysis_exports
git diff --cached --name-only
git diff --cached --name-only | grep -E '(^|/)(shadow_exports|analysis_exports)/' && exit 1 || true
```

実 API レスポンスや集計出力が別名・別パスにないかも確認する。生成物が見つかった場合は add せず、
ユーザーの既存ファイルを勝手に削除しない。

## 8. 次タスクの始め方

1. `AGENTS.md` と本書を読む。
2. `PROJECT_STATUS.md` とタスクに関係する runbook / policy / plan を読む。
3. `git status --short --branch`、`git log -1 --oneline`、既存コードとテストを確認する。
4. 変更対象、触らない箇所、検証方法を整理する。
5. 最小変更を実装し、最大5回まで修正・再検証する。
6. 成功したら停止し、次フェーズへ自動的に進まない。

Phase 2D-2 を始める場合も、まず [SHADOW_RUNBOOK.md](SHADOW_RUNBOOK.md) に沿って注文なし・local-only・
上限付き run であることを確認し、運用手順と蓄積確認だけを一つの明確なタスクとして切り出す。

## 9. 最終報告テンプレート

```markdown
# 作業報告

## 結果
- 完了 / 未完了と、その理由

## 変更内容
- 変更ファイル: `path`
- 要点

## 検証
- `実行コマンド`: 成功 / 失敗（件数や要点）
- 未実行項目と理由

## 安全確認
- Private API / APIキー / 実注文 / 実資金: なし
- 本番公開 API・設定変更: なし
- 生成物の commit: なし

## Git
- branch / commit / push の状態

## 次の候補
- 明示依頼があるまで着手しない次タスク
```
