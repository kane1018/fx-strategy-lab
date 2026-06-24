# Phase 3D-12: APIキー確認専用レビュー

Phase 3D-12では、実注文、HTTP request、署名実装、Private API接続へ進む前に、
GMO FX Private API用の環境変数が現在のプロセス環境に存在するかだけを確認する。

今回は **APIキー確認専用レビュー** である。確認してよいのは `set` / `missing` のみであり、
APIキー値、secret値、`.env` の中身、環境変数一覧は表示しない。

## 1. Phase 3D-12の目的

目的:

- APIキー確認専用レビューを行う。
- `GMO_FX_API_KEY` / `GMO_FX_API_SECRET` の `set` / `missing` だけを確認する。
- 値を表示しない。
- `.env`を表示しない。
- HTTP requestを作らない。
- Private APIへ接続しない。
- 署名を実装しない。
- 実注文しない。
- 実資金検証しない。

今回の扱い:

- 今回は実注文ではない。
- 今回はHTTP request実装ではない。
- 今回は署名実装ではない。
- 今回はPrivate API接続確認ではない。
- 今回は実資金検証ではない。
- 今回はcredential値を扱わない。

## 2. 確認対象

確認対象は次の2つだけである。

```text
GMO_FX_API_KEY
GMO_FX_API_SECRET
```

確認結果:

```text
GMO_FX_API_KEY: set
GMO_FX_API_SECRET: set
```

上記は存在有無のみであり、値は表示していない。

## 3. 確認方法

使用した確認方法は、環境変数の値を出さずに `set` / `missing` だけを出す方法に限定した。

```text
GMO_FX_API_KEY: set または missing
GMO_FX_API_SECRET: set または missing
```

確認時の安全条件:

- APIキー値を出力しない。
- secret値を出力しない。
- `.env`を読まない。
- `.env`を表示しない。
- 環境変数一覧を表示しない。
- Private APIへ接続しない。
- HTTP requestを作らない。
- 署名値を作らない。

## 4. 禁止事項

Phase 3D-12では次を禁止する。

- APIキー値の表示。
- secret値の表示。
- `echo` によるcredential表示。
- `printenv` によるcredential表示。
- `env` による環境変数一覧表示。
- `set` による環境変数一覧表示。
- `.env` のcat。
- `.env` のgrep。
- docs / logs / stdout へのcredential値出力。
- Git diffへのcredential混入。
- Private API接続。
- HTTP request実装。
- HTTP client import。
- HTTP POST。
- headers生成。
- request body生成。
- raw request生成。
- raw response保存。
- `API-KEY` / `API-SIGN` / `API-TIMESTAMP` の実値生成。
- actual signature生成。
- HMAC処理実装。
- broker実装。
- `OrderRequest`作成。
- real order API client実装。
- 注文API client実装。
- `POST /private/v1/order` 実行または実装。
- 注文変更API実装。
- 注文取消API実装。
- 決済API実装。
- 実注文。
- 実資金検証。
- retry注文。
- loop注文。
- cron / schedule / 常駐bot追加。
- frontend変更。
- 本番公開API追加。

## 5. set / missing の評価

### 両方set

`GMO_FX_API_KEY` と `GMO_FX_API_SECRET` が両方 `set` の場合、次フェーズ候補へ進める可能性はある。
ただし、これは実注文許可ではない。HTTP request実装、署名実装、Private API接続、実注文、実資金検証へは
まだ進まない。

今回の確認結果は両方 `set` である。

### 片方missing

片方だけ `missing` の場合、不足している環境変数名だけを報告して停止する。
値の入力は求めない。`.env`を読まない。Private APIへ接続しない。

### 両方missing

両方 `missing` の場合、APIキー確認未完了として停止する。
値の入力は求めない。`.env`を読まない。Private APIへ接続しない。

## 6. 次へ進む条件

両方 `set` の場合でも、次に進む候補は実注文ではない。

次候補:

```text
Phase 3D-13:
署名 / headers / request body 実装前レビュー
```

Phase 3D-13でも、すぐに実注文しない。まず署名、headers、request bodyを実装する前の責務境界、
値の保存禁止、出力禁止、HTTP POST禁止、実注文禁止を再レビューする。

Phase 3D-13でまだ行わないこと:

- HTTP request実装。
- 署名実装。
- headers生成。
- request body生成。
- HTTP POST。
- Private API接続。
- 実注文。
- 実資金検証。

## 7. まだ進まない範囲

Phase 3D-12では次へ進まない。

- HTTP request実装。
- 署名実装。
- headers生成。
- request body生成。
- HTTP POST。
- Private API接続。
- broker。
- `OrderRequest`。
- real order API client。
- 注文API client。
- `POST /private/v1/order`。
- 実注文。
- 実資金検証。
- 自動売買。
- retry。
- loop。
- cron / schedule / 常駐bot。
- frontend変更。
- 本番公開API追加。

## 8. 値非表示確認

今回確認できたこと:

- `GMO_FX_API_KEY` は `set` とだけ確認した。
- `GMO_FX_API_SECRET` は `set` とだけ確認した。
- APIキー値は表示していない。
- secret値は表示していない。
- `.env`は表示していない。
- 環境変数一覧は表示していない。
- raw request、raw response、headers、signatureは生成・保存していない。

## 9. Git / 生成物境界

Phase 3D-12の差分はdocs-onlyに限定する。

commitしてよいもの:

- `docs/PHASE3D12_API_KEY_PRESENCE_REVIEW.md`

commitしないもの:

- `.env`
- `.env.example`
- secret
- `backend/shadow_exports/`
- `analysis_exports/`
- 実APIレスポンス
- raw request
- raw response
- headers
- signature
- frontend
- backend実装コード
- backend tests

## 10. 結論

Phase 3D-12では、APIキー環境変数の存在確認を `set` / `missing` だけで行った。

結果:

```text
GMO_FX_API_KEY: set
GMO_FX_API_SECRET: set
```

値は表示していない。`.env`は読んでいない。Private API接続、HTTP request実装、署名実装、
HTTP POST、broker、`OrderRequest`、real order API client、実注文、実資金検証には進んでいない。

Phase 3D-13では、署名 / headers / request body 実装前レビューをdocs-onlyで完了した。
次候補は Phase 3D-14 signature / headers / request body plan実装である。ただし、Phase 3D-14でも
actual signature、actual headers、actual request body、HTTP POST、実注文、実資金検証、自動売買、
本番公開API追加には進まない。
