# H-11 v3 — 実口座確認チェックリスト（no-POST・operator専任）

Date: 2026-07-11

Status: **CHECKLIST_FOR_OPERATOR**（credential・ログイン操作はAIが代行しない。確認結果のみ§2へ転記）

GMOコイン会員ページへログイン後、以下を確認し、結果を
`docs/H11_V3_ACTUAL_ACTIVATION_OPERATOR_DECISION_SHEET_NO_POST_20260711.md` §2 へ
sanitizedな値（YES/NO・カテゴリ）のみ転記する。**残高・建玉数量・注文ID等のraw値は
このリポジトリのどこにも記載しないこと。**

## 確認項目

| # | 確認先（目安） | 確認すること | 記録する値 |
|---|---|---|---|
| 1 | 外国為替FX メニュー内「証拠金・ポジション管理方式」 | netting（自動相殺）か hedging（両建て可）か | `NETTING` or `HEDGING` |
| 2 | 外国為替FX API設定ページ | APIキーの発注権限が有効か（照会のみ権限になっていないか） | `TRADE_PERMISSION_ENABLED` or `READ_ONLY` |
| 3 | 同上 | IPアドレス制限の有無・設定状況 | `IP_RESTRICTED` or `NO_IP_RESTRICTION` |
| 4 | USD/JPY取引画面または仕様ページ | 最小取引単位が公開仕様どおり10,000通貨か | `CONFIRMED_10000` or 実際の値カテゴリ |
| 5 | 外国為替FX API利用規約（ページ下部「各種規約」） | 自動売買・API利用に関する禁止事項・責任条項の有無 | `REVIEWED_NO_BLOCKING_CLAUSE` or 懸念点の要約 |
| 6 | 手数料ページ | API自動売買の手数料（公開情報では約定金額の0.002%） | `CONFIRMED_0.002PCT` or 実際の値 |

## 完了後

上記6項目がすべて記録できたら、decision sheet §2 の該当行ステータスを
`PENDING_OPERATOR` から確認済みの値へ更新する（AIが代行して書き換え可）。
