# H-11 v3 — GMOコインサポート問い合わせ下書き（no-POST）

Date: 2026-07-11

Status: **DRAFT_FOR_OPERATOR_TO_SEND**（本書はAIが送信しない。operatorが公式問い合わせ窓口からコピー&ペーストで送信することを想定）

公開API仕様（[api.coin.z.com/fxdocs](https://api.coin.z.com/fxdocs/)）に記載がなく、
v3 actual activationの必須確認事項として残っている3点について、問い合わせ文面を用意した。

## 問い合わせ文面（コピー用）

```text
件名: 外国為替FX API（ifoOrder / IFDOCO・証拠金計算方式）の仕様確認

外国為替FX APIについて、公開ドキュメントで確認できなかった点を3点お伺いします。

1. pending order（有効期限=expiryフィールドを持つ未約定の第一注文）について、
   ifoOrder requestに有効期限を指定する項目が見当たりませんでした。
   デフォルトの有効期限は何時間・何日ですか。またこれは固定値ですか、
   それとも注文種別（STOP/LIMIT）や商品によって異なりますか。

2. ifoOrderの第一注文が部分約定した場合の挙動について教えてください。
   - 部分約定は発生し得ますか（USD/JPYのMARKET/STOP執行において）
   - 部分約定時、第二注文（OCO保護）のサイズは自動的に調整されますか、
     それとも約定済みサイズと保護サイズの不一致が生じ得ますか
   - executionEvents / orderExecutedSize フィールドで部分約定を検知できますか

3. 証拠金計算方式について、同一通貨ペア（例: USD/JPY）で買いポジションと
   売りポジションを同時に保有すること（両建て）は可能ですか。それとも、
   反対方向の新規注文は既存ポジションと自動的に相殺（ネッティング）される
   仕様ですか。

APIを用いた個人の自動売買システムの安全設計のための確認です。よろしくお願いいたします。
```

## 送信先の候補

- 会員ページのお問い合わせフォーム（ログイン後）
- 外国為替FX APIドキュメントページに記載の問い合わせ窓口

## 回答が得られたら

回答内容（safe aggregateのみ・raw文面の個人情報部分は除く）を
`docs/H11_V3_ACTUAL_ACTIVATION_OPERATOR_DECISION_SHEET_NO_POST_20260711.md` §2 の
`broker-native pending expiry` / `actual partial-fill semantics` 行、および
`docs/H11_V3_ACCOUNT_CHECK_CHECKLIST_NO_POST_20260711.md` 項目1（account mode）へ反映する。
