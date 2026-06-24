# Phase 3B-4: Private API read-only local connection review

Phase 3B-4では、GMOコイン外国為替FX Private APIのread-onlyローカル接続確認結果を総合レビューする。

今回は **レビュー・docs化のみ** である。Private APIへの追加接続、APIキー確認、APIキー入力、
`.env`確認、backend実装、broker、注文API、実注文、実資金検証、Live Verification Mode実装、
自動売買、本番公開API追加には進まない。

## 1. 目的

- Private API read-onlyローカル接続確認の総合レビューを行う。
- APIキー / secretを表示しない運用が維持されたか確認する。
- read-only endpointだけを確認したか整理する。
- raw response、headers、signatureを保存していないか確認する。
- 注文系endpoint、broker、OrderRequestに進んでいないか確認する。
- Phase 3B-4を完了扱いにできるか判断する。
- Phase 3C Live Verification Mode設計へ進めるか判断する。

Phase 3B-4は実資金検証ではない。注文、注文変更、注文取消、決済、自動売買には進まない。

## 2. レビュー対象

対象フェーズ:

- Phase 3B-4R: `account/assets` 成功、`openPositions` failure確認。
- Phase 3B-4S: `openPositions` failureをsanitized diagnosticsで `schema_error` と分類。
- Phase 3B-4T: `openPositions` object wrapper内 `list` 形式にsanitizer対応し、成功確認。
- Phase 3B-4U: `activeOrders` 専用diagnosticsを追加し、成功確認。

対象commit:

- `a737c43 feat: add private readonly connection check`
- `a1305a9 feat: add sanitized diagnostics for private readonly connection`
- `d4fe425 fix: handle open positions schema safely`
- `4012cd9 feat: add active orders readonly diagnostics`

## 3. 確認済みendpoint

Phase 3B-4で確認したPrivate API read-only endpointは次の3件である。

```text
GET /private/v1/account/assets
GET /private/v1/openPositions
GET /private/v1/activeOrders
```

追加で `/private/v1/orders`、`/private/v1/executions`、`/private/v1/latestExecutions`、
`/private/v1/positionSummary` へは実接続していない。

## 4. endpoint別レビュー

| endpoint | 確認フェーズ | 最終結果 | 件数 | raw response保存 | headers保存 | credentials表示 | 追加課題 |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| `GET /private/v1/account/assets` | Phase 3B-4R / 3B-4T | success | `account_assets_count=1` | なし | なし | なし | Phase 3B-4範囲ではなし |
| `GET /private/v1/openPositions` | Phase 3B-4R / 3B-4S / 3B-4T | success | `open_positions_count=0` | なし | なし | なし | object wrapper内 `list` 形式に対応済み |
| `GET /private/v1/activeOrders` | Phase 3B-4U | success | `active_orders_count=0` | なし | なし | なし | Phase 3B-4範囲ではなし |

## 5. `account/assets` 確認結果

確認結果:

```text
account_assets: success
account_assets_count: 1
raw_response_saved: false
headers_saved: false
credentials_printed: false
```

評価:

- Private API read-only接続確認として成功した。
- 金額詳細は最終報告に記載していない。
- raw response、headers、signature、credentialは保存・表示していない。

## 6. `openPositions` 確認結果

初回のPhase 3B-4Rでは `schema_error` によりfailureだった。
Phase 3B-4Sでsanitized diagnosticsを追加し、Phase 3B-4Tでobject wrapper内 `list` 形式にsanitizerを対応させた。

最終確認結果:

```text
open_positions: success
open_positions_count: 0
has_open_positions: false
response_data_shape: object
response_data_keys: list
raw_response_saved: false
headers_saved: false
credentials_printed: false
retry_attempted: false
```

評価:

- `openPositions` の実レスポンス形状は、raw値ではなくshape-only diagnosticsで確認した。
- `data` object内の `list` を安全に処理できるようになった。
- 建玉詳細、金額、ID値は表示・保存していない。
- Phase 3B-4範囲では追加確認不要である。

## 7. `activeOrders` 確認結果

Phase 3B-4Uでは、不要な追加接続を避けるため `activeOrders` 専用診断経路で確認した。
`account/assets` と `openPositions` には再接続していない。

確認結果:

```text
active_orders: success
active_orders_count: 0
has_active_orders: false
response_data_shape: object
response_data_keys: list
raw_response_saved: false
headers_saved: false
credentials_printed: false
retry_attempted: false
```

評価:

- `GET /private/v1/activeOrders` のread-only接続確認は成功した。
- 実行対象は `activeOrders` のみだった。
- 注文ID詳細、約定ID詳細、注文内容の値は表示・保存していない。
- 未約定注文は0件だったため、Phase 3C設計前のread-only確認として十分である。

## 8. APIキー / secret管理評価

評価結果:

- APIキー値は表示していない。
- secret値は表示していない。
- 確認したのは `set` / `missing` の状態だけである。
- APIキー値をdocsへ書いていない。
- secret値をdocsへ書いていない。
- `.env` は表示していない。
- `.env` は変更していない。
- `.env.example` は変更していない。
- terminal outputにsecret値は出していない。
- commitに実credentialや秘密鍵素材は含めていない。

補足:

- Phase 3B-4総合レビューでは、APIキー存在確認も追加実施しない。
- APIキー / secretは引き続きユーザーのローカル環境管理とし、docs・commit・ログに出さない。

## 9. raw response / headers / signature評価

評価結果:

- raw response保存なし。
- response headers保存なし。
- signature保存なし。
- 実API response fixtureなし。
- 実APIレスポンス全体をstdoutへ出していない。
- sanitized summaryのみをstdoutへ出した。
- 金額詳細、建玉詳細、注文ID詳細、約定ID詳細を報告に含めていない。
- response形状確認はshape-only diagnosticsに限定した。

この境界はPhase 3C以降も維持する必要がある。

## 10. read-only境界評価

確認できたこと:

- 実接続したHTTP methodはGETのみ。
- 実接続対象は `account/assets`、`openPositions`、`activeOrders` の3件まで。
- Phase 3B-4Uでは `activeOrders` だけを実行し、既に成功済みの2 endpointへ再接続していない。
- POST / PUT / DELETE endpointは呼んでいない。
- 注文系endpointは呼んでいない。
- broker実装・broker importには進んでいない。
- `OrderRequest` は追加していない。
- `submit` / `send` / `place` / `cancel` / `amend` の注文送信処理は追加していない。
- Live Verification Modeは実装していない。
- 自動売買、cron、schedule、常駐botは追加していない。
- backend公開API、`main_readonly.py`、frontendは変更していない。

## 11. tests / ruff結果

Phase 3B-4U時点の最新検証:

```text
python3 -m pytest -q app/tests/test_private_readonly_connection_script.py
15 passed

python3 -m pytest -q app/tests/test_private_readonly_errors.py
4 passed

python3 -m pytest -q app/tests/test_private_readonly_schemas.py
18 passed

python3 -m pytest -q app/tests -k "private_readonly"
73 passed, 354 deselected

python3 -m pytest -q
427 passed

ruff check .
All checks passed
```

今回の総合レビューでも、追加接続なしでmocked tests / ruffを再実行する。

## 12. Phase 3B-4完了判定

判定:

```text
A: Phase 3B-4 read-onlyローカル接続確認は完了
```

理由:

- `GET /private/v1/account/assets` はsuccess。
- `GET /private/v1/openPositions` は初回schema_errorを安全に診断し、sanitizer修正後にsuccess。
- `GET /private/v1/activeOrders` はactiveOrders専用diagnosticsでsuccess。
- APIキー / secret非表示を維持した。
- raw response、headers、signatureを保存していない。
- 実APIレスポンスfixtureを作っていない。
- 注文系endpoint、broker、OrderRequestに進んでいない。
- tests / ruffが通っている。
- 実データをcommitしていない。

## 13. Phase 3Cへ進めるか

判定:

```text
A: Phase 3C Live Verification Mode設計へ進んでよい
```

理由:

- Phase 3C設計に必要なread-only基礎確認として、口座資産、建玉、未約定注文の3系統を確認できた。
- 既存建玉なし、未約定注文なしをsanitized countとして確認できた。
- read-only確認中にcredential漏洩やraw response保存は発生していない。
- 注文可能なコードやbroker導線を追加していない。

ただし、今回のタスクではPhase 3Cへ進まない。Phase 3Cは次タスクで、設計レビューのみとして扱う。

## 14. Phase 3Cで扱うべき論点

Phase 3CはLive Verification Modeの設計フェーズであり、まだ実注文しない。

最低限扱うべき論点:

- Live Verification Modeの目的。
- まだ実注文しない設計段階であること。
- `USD_JPY`のみ。
- 100通貨固定。
- 1回限定。
- manual only。
- 既存建玉なし確認。
- 未約定注文なし確認。
- account/assets確認。
- openPositions確認。
- activeOrders確認。
- risk decision確認。
- kill switch確認。
- candidate / decision / order intentのID相関。
- APIキー / secret非表示の維持。
- raw response / headers / signature保存禁止。
- 注文前チェックリスト。
- 注文後停止条件。
- 実装前レビュー。
- 実注文前の明示承認条件。

Phase 3Cは、Live Verification Modeを実装するフェーズではない。実装可否を設計で固める段階である。

## 15. まだ進まない範囲

Phase 3B-4完了後も、次には進まない範囲:

```text
Live Verification Mode実装
broker
注文API
注文変更API
注文取消API
決済API
OrderRequest
実注文
実資金検証
自動売買
cron / schedule / 常駐bot
本番公開API追加
frontend変更
backend/app/main_readonly.py変更
DB本番化
認証実装
```

これらはPhase 3C設計レビュー、さらに注文API実装前レビュー、ユーザー明示承認がない限り扱わない。

## 16. 残っている課題

Phase 3B-4のread-onlyローカル接続確認としての追加課題はない。

Phase 3C以降の設計課題:

- Live Verification Modeの詳細設計。
- 実注文前チェックリストの厳密化。
- read-only確認結果とrisk decisionの接続設計。
- kill switchとSTOP条件の再確認。
- 注文APIを実装する前の別レビュー。

## 17. 結論

Phase 3B-4では、Private API read-onlyローカル接続確認として必要な初期3 endpointを確認できた。

結論:

- Phase 3B-4 read-onlyローカル接続確認は **A: 完了**。
- Phase 3C Live Verification Mode設計へは **A: 進んでよい**。
- ただし、Phase 3Cは次タスクであり、今回の総合レビューでは実装・追加接続・実注文・実資金検証へ進まない。
