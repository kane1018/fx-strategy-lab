# H-11 v3 — LINE Messaging API 将来切替手順書（no-POST・operator専任）

Date: 2026-07-11

Status: **FUTURE_OPTION_NOT_IMPLEMENTED**（現在の通知既定はメール。本書は将来LINEへ
切り替えたくなった場合の手順書であり、今回の実装対象ではない）

## 背景

LINE Notify は2025-03-31にサービス終了。後継として公式が案内しているのは
LINE Messaging API（LINE公式アカウント経由でのメッセージ配信）。旧LINE Notifyの
「1クリックでトークン発行」より設定手数が増えるため、今回は既定をメールとした。

## 切替時にoperatorが行う設定（AIが代行できない部分）

1. **LINE Developersアカウント作成**（LINEアカウントでログイン、開発者登録）
   - https://developers.line.biz/
2. **Provider作成**（任意の名前でよい。例: 個人利用）
3. **Messaging APIチャネルの作成**
   - チャネル名・説明・カテゴリ等を入力（個人用途で問題なし）
4. **チャネルアクセストークン（長期）の発行**
   - チャネル基本設定 → Messaging API設定タブ → 「チャネルアクセストークン（長期）」を発行
   - この値がcredential相当。以降はKeychain経由で読み取る運用にする
5. **公式アカウントを自分のLINEで友だち追加**
   - 発行された公式アカウントのQRコード/IDを自分のLINEアプリで友だち追加
   - 通知はこの公式アカウントから自分宛に送られる形になる
6. **自分のuserIdの確認**
   - Webhook経由で取得するか、LINE Developersコンソールのテスト送信機能で確認
   - push message送信にはuserIdまたはtargetTypeの指定が必要

## 実装側（切替が決まったらAI/Codexが行う）

- `backend/app/services/h11_v3_notification_binding_no_post.py` の fake notifier を、
  LINE Messaging API `push message` エンドポイント（`POST /v2/bot/message/push`）を叩く
  実senderに差し替える。
- チャネルアクセストークンはmacOS Keychain経由で読み取り、値をログ・Git・チャット出力に
  出さないsealed設計を維持する。
- 通知本文はsafe labelのみ（例: `H11_V3_KILL_ENGAGED` / `H11_V3_UNKNOWN_HALT` 等）とし、
  raw price/PnL/IDを含めない。
- 送信失敗時（トークン失効・APIエラー等）はfail-closedとし、通知失敗を理由に
  新規entryを止める設計は維持する（既存のnotification_failure halt方針を継続）。

## 現在の状態

```text
line_messaging_api_configured=false
line_channel_access_token_provisioned=false
notification_default=EMAIL
notification_switch_authorized=false
```

切替を希望する場合、上記1〜6をoperatorが完了させ、その結果（トークンの存在確認のみ・
値は共有しない）をAI/Codexへ伝えれば実装Stepに進める。
