# Phase 2E-3.5: Public ticker bid/ask provenance連携監査

Phase 2E-3で実装されたPublic ticker bid/ask provenance連携について、Phase 2E-4のgmo-public
risk/audit手動確認へ進む前の実装レビュー / safety auditを行った。

今回はレビュー・監査・docs化のみで、backendコード、tests、frontend、公開API、`main_readonly.py`は変更していない。
GMO Public実run、Private API、APIキー、broker、実注文、実資金、自動売買、本番公開API追加にも進んでいない。

## 1. 監査対象

- 対象commit: `ac7fd4e feat: add public ticker bid ask provenance for shadow risk`
- 対象範囲:
  - `backend/app/shadow/risk.py`
  - `backend/app/shadow/session.py`
  - `backend/app/shadow/audit_schema.py`
  - `backend/app/shadow/aggregate.py`
  - `backend/app/shadow/gmo_public.py`
  - `backend/scripts/run_shadow_session.py`
  - `backend/scripts/summarize_shadow_runs.py`
  - 関連offline tests
- 監査目的:
  - GMO Public ticker由来のbid/askだけが`REAL_PUBLIC_BID_ASK`になること
  - kline-only経路がsynthetic spread rejectを維持すること
  - invalid / missing / stale / future / skew tickerがfail closedになること
  - raw response、headers、secret、Private情報を保存しないこと
  - summary / metadata / aggregateの後方互換を壊していないこと

## 2. 総合判定

判定: **B: 軽微な改善候補はあるが、Phase 2E-4設計へ進める**

修正必須事項は見つからなかった。Public ticker bid/askをrisk/audit経路へ接続する条件はlocal-onlyかつfail closedで、
Private API、APIキー、broker、OrderRequest、`.env`、実注文経路への接続は確認されなかった。

Phase 2E-4はまず設計または実行指示作成へ進める。ただし、この監査ではPhase 2E-4実行、gmo-public実run、
Private API、実注文、実資金、自動売買には進んでいない。

## 3. Public ticker bid/ask取得・validation監査

結果: **合格**

- CLIは`--source gmo-public`かつ`--enable-shadow-risk`時だけPublic tickerを取得する。
- session本体はnetworkを行わず、sanitized snapshot providerを受け取るだけである。
- ticker取得失敗時にPrivate API、APIキー、brokerへfallbackしない。
- GMO Public adapterはPublic endpointをGETするread-only経路で、認証headerやAPIキーを扱わない。
- sourceが`gmo-public`ではない経路は`REAL_PUBLIC_BID_ASK`にならない。
- symbol mismatch、bid/ask欠損、timestamp欠損、不正値はfail closedになる。

## 4. MarketSnapshot / provenance監査

結果: **合格**

- `MarketSnapshot`はfrozen dataclassで、`source == "gmo-public"`、`spread_provenance == REAL_PUBLIC_BID_ASK`、
  `private_api_used=false`、`api_key_used=false`、`raw_response_saved=false`を検証する。
- `create_public_market_snapshot()`は、Public ticker由来として使える値だけを`MarketSnapshot`へ正規化する。
- `UNKNOWN`、`SYNTHETIC_ZERO`、`CANDLE_DERIVED`のspread provenanceはrisk評価でALLOWされない。
- bid <= 0、ask <= 0、ask < bid、NaN、Infinityはfail closedになる。
- raw responseやheadersをDTOに保持しない。

## 5. timestamp / freshness監査

結果: **合格**

- `max_ticker_age_seconds = 30`
- `max_ticker_kline_skew_seconds = 90`
- `max_future_skew_seconds = 5`
- stale tickerは`STALE_DATA`でfail closedし、summaryでは`ticker_stale_count`へ計上される。
- future tickerは`INVALID_DATA`でfail closedし、summaryでは`ticker_invalid_count`へ計上される。
- ticker/kline skew超過は`STALE_DATA`でfail closedし、summaryでは`ticker_kline_skew_reject_count`へ計上される。
- stale/skewは通常のreject/no-tradeとして扱われ、不要にsafety violation化しない。

## 6. spread_pips監査

結果: **合格**

- USD/JPYのpipは`Decimal("0.01")`として扱われる。
- spreadは`(ask - bid) / Decimal("0.01")`で計算される。
- negative spread、NaN、Infinityはrejectされる。
- `RiskPolicy.max_spread_pips = 0.5`との比較でwide spreadはrejectされる。
- real Public ticker由来のzero spreadはMarketSnapshotとしては許容される。
- synthetic zero spreadは`SYNTHETIC_SPREAD_NOT_ALLOWED`でrejectされる。

## 7. candidate生成 / risk reject監査

結果: **合格**

- kline-onlyのmock/risk有効runはsynthetic spreadとしてcandidate生成後にrisk rejectされる。
- valid Public ticker snapshotだけが`REAL_PUBLIC_BID_ASK`のcandidateへ進む。
- invalid / stale / future / skew snapshotはcandidateなしのNO_TRADE、またはrisk reject側に倒れる。
- REJECT時は`virtual_result_log`を生成しない。
- ALLOW時のみcandidate / risk decision / virtual resultが相関する。
- `risk_ticker_fn`のような未検証ticker hookは`UNKNOWN` provenanceとなり、real Public扱いにならない。

## 8. audit log / raw response非保存監査

結果: **合格**

- raw API response、response headers、request headersを保存しない。
- candidate/risk/virtual/kill switchのaudit schemaはunknown/raw fieldを拒否する。
- schema forbidden fieldsにsecret、token、password、private key、authorization、raw request/response/header/body等が含まれる。
- audit logは必要最小限のtyped JSONLで、Private API情報や注文IDを保存しない。

## 9. summary / metadata監査

結果: **合格**

追加されたoptional keyはlegacy summary互換を維持している。

- `ticker_bid_ask_used_count`
- `real_public_bid_ask_count`
- `synthetic_spread_reject_count`
- `ticker_missing_count`
- `ticker_stale_count`
- `ticker_invalid_count`
- `ticker_kline_skew_reject_count`
- `public_ticker_fetch_error_count`
- `spread_too_wide_count`
- `raw_response_saved=false`

aggregate markdownにも`Public Ticker Bid/Ask`セクションがあり、legacy runの欠損keyは0として扱われる。

## 10. import / dependency監査

結果: **対象経路は合格**

広域スキャンでは既存の研究・ペーパー用`backend/scripts/*`に`app.brokers` importが検出された。
これはPhase 2E-3のPublic ticker bid/ask接続対象経路ではなく、今回変更していない既存スクリプトである。

対象経路に絞った追加スキャンでは、`backend/app/shadow`、`backend/scripts/run_shadow_session.py`、
関連`test_shadow_*`に以下は検出されなかった。

- `OrderRequest`
- `risk_service`
- `app.brokers`
- `dotenv`
- `os.environ`
- `getenv`
- `submit/send/place/cancel/amend`系関数定義

## 11. tests監査

結果: **十分**

以下がoffline testsで確認されている。

- valid Public ticker bid/askで`REAL_PUBLIC_BID_ASK`
- missing bid / ask
- bid <= 0 / ask <= 0
- ask < bid
- NaN / Infinity
- stale / future / ticker-kline skew
- symbol mismatch
- `raw_response_saved` / `private_api_used` / `api_key_used`安全flag違反
- zero spread real public
- zero spread synthetic reject
- unvalidated ticker hook reject
- summary optional key後方互換
- legacy mock run互換
- risk/audit enabled mock run互換

追加必須テストはない。将来の改善候補として、Phase 2E-4前後にCLIのgmo-public経路をoffline mockでより直接確認する
テストを追加してもよい。

## 12. 実行した検証

```text
python3 -m pytest -q app/tests/test_shadow_session.py app/tests/test_shadow_session_risk_integration.py app/tests/test_shadow_summary.py app/tests/test_shadow_risk.py app/tests/test_shadow_audit.py app/tests/test_gmo_public_adapter.py
=> 124 passed in 0.58s

python3 -m pytest -q
=> 354 passed in 4.22s

python3 -m ruff check .
=> All checks passed!

python3 -m scripts.summarize_shadow_runs --input-root shadow_exports --format markdown
=> runs_count: 18, broken/skipped: 0, safety_violation_runs_count: 0, invalid_risk_row_count: 0

python3 -m scripts.run_shadow_session --source mock --symbol USD_JPY --interval M1 --steps 5
=> run_id: 20260622_093735_shadow_USD_JPY_mock, orders=4, halted=False

python3 -m scripts.run_shadow_session --source mock --symbol USD_JPY --interval M1 --steps 5 --enable-shadow-risk
=> run_id: 20260622_093739_shadow_USD_JPY_mock, candidates=4, allow=0, reject=4, orders=0, exit_code=0

python3 -m scripts.summarize_shadow_runs --input-root shadow_exports --format markdown
=> runs_count: 20, broken/skipped: 0, safety_violation_runs_count: 0, invalid_risk_row_count: 0
```

## 13. 生成物とcommit対象

mock runにより`backend/shadow_exports/`配下にlocal生成物が追加されたが、gitignoredでありcommit対象外とした。
`git ls-files | grep shadow_exports`は出力なしで、tracked生成物はない。

## 14. 軽微な改善候補

- 現在のCLI実装は、gmo-public risk run時にtickerを1回取得してsessionへ渡す設計である。複数stepの過去klineに対しては
  ticker/kline skewによりfail closedしやすい。これは安全側の挙動であり、Phase 2E-4の手動確認ではstepsを小さくし、
  NO_TRADE / rejectがあり得る前提で評価する。
- `public_ticker_fetch_error_count`はsummary-levelの失敗カウントとして扱われる。実際のcandidate/reject件数とあわせて読む必要がある。
- MarketSnapshotそのものを独立audit logには保存していない。現状はcandidate/risk/summaryで必要最小限の記録に留めており、
  raw response非保存の観点では妥当である。

## 15. 次に行うべき作業

次はPhase 2E-4の設計または実行指示作成に進める。

ただし、Phase 2E-4実行、gmo-public risk/audit手動確認、Private API、APIキー、broker、実注文、実資金、
自動売買、本番公開API追加は、別タスクで明示承認を得てから行う。
