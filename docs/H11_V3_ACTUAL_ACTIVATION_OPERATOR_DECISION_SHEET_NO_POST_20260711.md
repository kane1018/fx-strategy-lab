# H-11 v3 Actual Activation — Operator Decision Sheet（no-POST）

Date: 2026-07-11

Status: **BLOCKED_V3_BROKER_CONSTRAINTS**

Purpose: `H11_V3_ACTUAL_ACTIVATION_STEP`前の未決定事項を一箇所に固定する。

本書はactual activation、API、credential、broker read、POST、resident process、cronを許可しない。

## 1. 現在clearなもの

```text
v3_spec_frozen=true
config_hash=sha256:737765dcbed89befceef8660d2b362c834344cc7e36e139d2ff75984914c3262
capability_contract_hash=sha256:f35fe67b0129c310154bbc4b877d30165db98e6e5617547504145baa4af5f5d5
pure_ifdoco_builder=true
automatic_preview_signal_adapter=true
persistent_process_lock=true
one_entry_attempt_cap=true
one_settlement_attempt_cap=true
unknown_result_halt=true
same_day_second_entry_block=true
fake_server_side_protection_reconcile=true
append_only_safe_journal=true
persistent_risk_stop=true
state_specific_boot_reconcile=true
persistent_dead_man=true
partial_fill_fail_closed_policy=true
protection_children_reconcile_policy=true
disabled_actual_boundary=true
sender_contract_and_injection_point=true
default_refusing_sender=true
fake_credential_and_fake_http_client_binding=true
actual_post_allowed_structurally_false=true
real_ifdoco_sender_scaffold_implemented=true（h11_v3_real_ifdoco_sender_no_post.py・
  実HMAC署名/実Keychain credential結合済み・one-attempt-only・inert timestamp既定・
  現ビルドに呼び出し口なしのため実行不能）
private_ws_token_and_reconnect_design=true
fake_external_notifier_binding=true
heartbeat_dead_man_entry_settlement_notification_tests=true
agents_md_v3_exception_draft=true
major_incident_resume_declaration_draft=true
synthetic_fault_soak=100_of_100_matched
wall_clock_24h_fake_soak=RUNNING_UNTIL_2026-07-12T13:45:56+09:00
keychain_credential_wrapper=implemented_tested_on_real_keychain_test_entries_only
email_notification_injection_point=implemented_default_refusing_fake_transport_tested
backend_full_tests=7557_passed
backend_ruff=passed
actual_post=false
```

上記のsender/notification項目は設計・fake実装がclearであることだけを意味する。production
sender、actual WebSocket、外部送信、activation tokenは存在しない。

## 2. Operator / actual account専任の未決定

| 項目 | 現在値 | 推奨値・停止規則 |
|---|---|---|
| broker-native pending expiry | `CONFIRMED_FIXED_30_TRADING_DAYS_EXCEEDS_SIGNAL_WINDOW` | operator経由のGMOサポート回答（2026-07-13）で、IFDOCO一次注文は固定30取引日・requestごとの短縮指定なしと確認。v3は自動cancelを持たず、短期signal windowを超えるためactual activationをblock。safe要約: [broker response summary](H11_V3_GMO_SUPPORT_RESPONSE_SAFE_SUMMARY_NO_POST_20260713.md) |
| actual account capability profile | `API_PERMISSION_MIN_LOT_IP_CONFIRMED_ACCOUNT_MODE_EXPERIENTIALLY_CONFIRMED` | operator確認 2026-07-11: API権限で**IFDOCO注文を有効化済み**（注文/決済注文/IFDOCO注文/注文情報取得/有効注文一覧/約定情報取得/建玉一覧を取得のみON。注文変更系・キャンセル系・スピード注文・WebSocket通知4種はOFFのまま=最小権限でv3設計と整合）。**最小取引単位も訂正確認済み**: 公式ページ「API利用時 USD/JPY新規100通貨/回」（10,000通貨必須はTRY/ZAR/MXN/HUF/SEK/NOK系のみ）。v3凍結position_size=10,000通貨は最小値を上回るため問題なし。**IP制限=`NO_IP_RESTRICTION`（未設定）を確認済み**。**account mode=`HEDGING`をoperator実体験で確認**（過去に決済目的の反対注文が相殺されず両建てになった実績）— v3設計の「決済はofficial closeOrderルートのみ・generic opposite closeは禁止」の正しさを裏付ける。GMOサポート回答（[問い合わせ下書き](H11_V3_GMO_SUPPORT_INQUIRY_DRAFT_NO_POST_20260711.md)質問3）で公式に裏付け中だが、activation blockerではなくなった |
| actual partial-fill semantics | `CONFIRMED_FIXED_OCO_SIZE_PARTIAL_MISMATCH_RISK` | operator経由のGMOサポート回答（2026-07-13）で、部分約定は発生し得て、第二OCO注文のsizeは約定量へ自動調整されず、`orderExecutedSize`で検知可能と確認。検知は既約定後であり、v3には安全な不一致是正経路がないためactual activationをblock。safe要約: [broker response summary](H11_V3_GMO_SUPPORT_RESPONSE_SAFE_SUMMARY_NO_POST_20260713.md) |
| ToS / fee / responsibility acceptance | `FEE_AND_TOS_CONFIRMED` | operator確認 2026-07-11: 手数料=約定金額×0.002%。当該APIキーは既存発行のため無料期間は**2026-07-25まで**（新規発行なら発行から30日間無料）。**約款原文確認済み**（第20〜22条）: 個人自動売買を禁止する条項なし、API注文は約款第8条2項で公式経路と明記、IFD-OCOも第9条(4)で正式注文種別と明記。システム誤動作の損害はoperator全責任（GMOの故意・重過失時を除く）— [条項サマリー](H11_V3_YAKKAN_API_CLAUSES_SUMMARY_NO_POST_20260711.md)参照。**無料期間終了に活性化スケジュールを合わせる判断はしない**（安全確認未完了のまま急ぐ理由にしない） |
| notification destination and owner | `DECIDED_EMAIL_DEFAULT_BINDING_IMPLEMENTED_DISABLED` | operator承認: 既定はメール（kansuinaoi@gmail.com）。[将来LINE切替手順書](H11_V3_LINE_MESSAGING_API_FUTURE_SETUP_NO_POST_20260711.md)を用意済み。**注入点を実装済み**（`backend/app/services/h11_v3_email_notification_binding_no_post.py`）: SMTP transport contract・default refusing transport・fake transport testのみ。実smtplib送信は未実装のまま次のactivation Stepで追加する |
| execution host / observation window | `DECIDED_THIS_MAC` | operator承認: このMacで運用。sleep抑止はcaffeinateのみでは不十分な可能性があるため、電源接続＋システム設定でのスリープ無効化を併用する方針。実装時に手順を提示する |
| bounded background authority | `false` | 24h fake soakを除くactual運用プロセス権限は別途明示。cron導入は別判断 |
| sealed credential provision | `REGISTERED_AND_VERIFIED` | operator承認: macOS Keychain経由。**実GMO API key/secretの登録・検証完了(2026-07-11)**。`security add-generic-password`（ターミナルCLI）で登録、`read_h11_v3_keychain_secret`で読み取り確認（値は非表示・文字数のみ: api_key length=32 / api_secret length=64）。※新macOS「パスワード」アプリの新規パスワード機能では読み取り不可だったため、確実なCLI方式に切り替えて解決 |
| v3 major-incident resume declaration | `DRAFT_NOT_EFFECTIVE` | v3限定でoperatorが記名発効。generic allow bridgeは禁止 |
| actual activation authorization | `false` | 上記完了後も別current-turnの専用activation承認が必須 |

## 2A. 2026-07-13 broker回答によるv3 veto

回答原文は保存しない。operatorから共有された公式サポート回答の安全な事実要約だけを
[H11_V3_GMO_SUPPORT_RESPONSE_SAFE_SUMMARY_NO_POST_20260713.md](H11_V3_GMO_SUPPORT_RESPONSE_SAFE_SUMMARY_NO_POST_20260713.md)
に記録する。

```text
v3_pending_expiry=CONFIRMED_FIXED_30_TRADING_DAYS_EXCEEDS_SIGNAL_WINDOW
v3_partial_fill=CONFIRMED_FIXED_OCO_SIZE_PARTIAL_MISMATCH_RISK
v3_actual_activation=false
v3_safety_veto=true
v4_docs_only_redesign=RECOMMENDED
```

このvetoは、検知可能性を「安全な是正可能性」と取り違えないためのもの。v3の凍結config、
禁止されているauto-cancel、generic opposite close、retry/repostを変更して解消してはならない。

## 3. Activation前の必須実証

1. fresh boot reconciliationがposition/order unknownをHALTする。
2. IFDOCO acceptance後、entry legとOCO protectionの存在をsafe status/countで確認できる。
3. timeout後に追加entry、retry、repostが0件である。
4. process二重起動がlockで拒否される。
5. dead-man、kill、notification failureが新規entryを止める。
6. budget stop後に自動再開しない。
7. actual senderはIFDOCO route一つだけに固定し、generic order/close/cancel/changeへ到達しない。
8. credential、raw request/response、headers、signature、ID、price、PnLを出力しない。

## 4. 次Stepの推奨scope

```text
step=H11_V4_BROKER_CONSTRAINT_REDESIGN_STEP
phase_A=docs_only_constraint_review_and_operator_decision
phase_B=official_broker_capability_answers_for_a_new_execution_profile
phase_C=new_frozen_config_and_independent_safety_review_if_a_safe_profile_exists
phase_D=separate_future_activation_only_after_all_new_gates_clear
```

fake transport/notification実装と24h soakの完了は、上記phaseのpermissionを自動発生させない。
actual live開始時は、dirty tree、
HEAD不一致、test失敗、能力UNKNOWN、position/order不一致のいずれかで停止する。

## 5. 安全状態

```text
actual_post=false
entry_post=false
settlement_post=false
post_count=0
broker_read=false
broker_write=false
credential_read=false
resident_process=false
cron=false
raw_id_value_exposure=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```
