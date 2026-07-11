# H-11 v3 — 実口座確認チェックリスト（no-POST・operator専任）

Date: 2026-07-11

Status: **CHECKLIST_FOR_OPERATOR**（credential・ログイン操作はAIが代行しない。確認結果のみ§2へ転記）

GMOコイン会員ページへログイン後、以下を確認し、結果を
`docs/H11_V3_ACTUAL_ACTIVATION_OPERATOR_DECISION_SHEET_NO_POST_20260711.md` §2 へ
sanitizedな値（YES/NO・カテゴリ）のみ転記する。**残高・建玉数量・注文ID等のraw値は
このリポジトリのどこにも記載しないこと。**

## 確認項目

| # | 確認先（目安） | 確認すること | 記録する値 | 状態 |
|---|---|---|---|---|
| 1 | 外国為替FX メニュー内「証拠金・ポジション管理方式」 | netting（自動相殺）か hedging（両建て可）か | `NETTING` or `HEDGING` | **未確認** |
| 2 | 外国為替FX API設定ページ | APIキーの発注権限が有効か（照会のみ権限になっていないか） | `TRADE_PERMISSION_ENABLED` or `READ_ONLY` | ✅ **確認済み(2026-07-11)**: IFDOCO注文含む必要権限をON、それ以外はOFF（最小権限） |
| 3 | 同上 | IPアドレス制限の有無・設定状況 | `IP_RESTRICTED` or `NO_IP_RESTRICTION` | **未確認** |
| 4 | ~~USD/JPY取引画面または仕様ページ~~ → live public API直接照会で解決 | 最小取引単位 | `CONFIRMED_100`（10,000ではない） | ✅ **確認済み(2026-07-11)**: `GET /public/v1/symbols`直接照会でUSD_JPY minOpenOrderSize=100・sizeStep=1・maxOrderSize=500000。以前の記録は`10000`という誤りだった（[API能力表訂正](API_CAPABILITY_SHEET_SANITIZED_NO_POST.md)参照）。operatorのスクリーンショット（「1通貨単位から取引可能」）とも整合。v3凍結position_size=10,000通貨は最小値を上回るため変更不要 |
| 5 | [外国為替FX取引約款PDF](https://coin.z.com/corp_imgs/policy/kawasefx-yakkan.pdf?ver=20250208)（第20〜22条） | 自動売買・API利用に関する禁止事項・責任条項の有無 | ✅ **確認済み(2026-07-11)**: `REVIEWED_NO_BLOCKING_CLAUSE`。個人の自動売買を禁止する条項なし（第8条2項でAPI注文を公式経路と明記）。詳細は[条項サマリー](H11_V3_YAKKAN_API_CLAUSES_SUMMARY_NO_POST_20260711.md)参照 |
| 6 | 手数料ページ | API自動売買の手数料（公開情報では約定金額の0.002%） | `CONFIRMED_0.002PCT` or 実際の値 | ✅ **確認済み(2026-07-11)**: 0.002%、当該キーは既存発行のため無料期間は2026-07-25まで |

## 完了後

残る4項目（1・3・4・5）がすべて記録できたら、decision sheet §2 の該当行ステータスを
確認済みの値へ更新する（AIが代行して書き換え可）。
