# H-11 Auto Frozen Generation Manifest Template（draft / no-POST）

Date: 2026-07-15

Status: `OPERATOR_FIELDS_APPROVED_EXTERNAL_PROOF_PENDING_NOT_RUNTIME_BOUND`

## 1. Purpose

signal、risk、execution、exit、data、hostを別々の可変設定として扱わず、1つのgeneration manifestへ固定する。
結果を見た後の一部field差し替えや、旧state directoryの再利用を防止する。

現在のPhase B SQLite manifestはgeneration / signal / risk / dead-man identityを固定済み。本templateは
execution profile選定後に必要となる完全manifestの上位仕様であり、現runtimeへbindingしない。

## 2. Draft template

```yaml
manifest_schema: H11_AUTO_GENERATION_V1_DRAFT
manifest_status: PENDING_OPERATOR_APPROVAL

identity:
  generation_label: H11_AUTO_30M_YYYYMMDD_GNNN
  project: H11_AUTO_PARALLEL
  strategy_version: SHORT_V1
  implementation_digest: PENDING_CODE_FREEZE

signal:
  selected_horizon: 30m
  signal_config_hash: sha256:ca08df187ae11b89192f1bbb4f77adc712ad41dc07d06d85bd67c9c7bcf6135d
  buy_threshold: "0.58"
  sell_threshold: "0.42"
  formal_only: true
  rolling_allowed: false
  h24_allowed: false

data_clock:
  source_profile_label: PENDING
  finalized_m1_required: true
  finalization_margin_seconds: PENDING
  maximum_m1_age_seconds: PENDING
  maximum_ticker_age_seconds: PENDING
  maximum_clock_skew_seconds: 5
  missed_signal_backfill_allowed: false

position:
  symbol: USD_JPY
  quantity_units: 10000
  maximum_open_positions: 1
  maximum_entries_per_jst_day: 1
  scale_in_allowed: false
  hedging_allowed: false

risk:
  policy_label: H11_AUTO_INITIAL_MINIMUM_LIVE_V1
  per_trade_loss_bound_jpy: 5000
  daily_loss_limit_jpy: 10000
  monthly_loss_limit_jpy: 50000
  maximum_consecutive_losses: 5
  automatic_resume_after_stop: false

entry:
  execution_profile_label: H11_V4_GMO_MARKET_THEN_EXACT_OCO_NO_POST_V1
  execution_profile_hash: RUNNER_DERIVED_FROM_FROZEN_PROFILE
  entry_style: MARKET
  short_pending_expiry_or_no_pending_entry_required: true
  full_fill_or_atomic_protection_size_match_required: false
  partial_fill_reconciliation_cancel_reprotect_required: true
  maximum_unprotected_seconds: 15
  server_side_stop_required: true
  server_side_take_profit_required: true
  maximum_attempts_per_intent: 1
  retry_allowed: false
  repost_allowed: false
  blocked_hours_jst: [5, 6, 7, 8]
  friday_entry_allowed: false
  weekend_entry_allowed: false

exit:
  exit_profile_label: H11_V4_EXACT_OCO_POSITION_SPECIFIC_23H_EXIT_V1
  position_specific_route_required: true
  generic_close_allowed: false
  opposite_entry_as_exit_allowed: false
  maximum_attempts_per_intent: 1
  retry_allowed: false
  repost_allowed: false
  stop_loss_contract: H11_V4_GMO_PROTECTION_CONTRACT_SHA256_48344AEB
  take_profit_contract: H11_V4_GMO_PROTECTION_CONTRACT_SHA256_48344AEB
  maximum_hold_seconds: 82800
  time_exit_route: POSITION_SPECIFIC_MARKET_AFTER_EXACT_OCO_CANCEL
  fresh_public_market_open_at_oco_cancel_transport_boundary_required: true
  public_market_open_maximum_age_seconds: 2
  market_unknown_retains_oco_and_halts: true
  formal_edge_exit_enabled: false

reconciliation:
  boot_required: true
  before_entry_required: true
  after_entry_required: true
  periodic_position_monitor_required: true
  before_exit_required: true
  after_exit_required: true
  after_websocket_reconnect_required: true
  after_process_restart_required: true
  maximum_age_seconds: PENDING
  unknown_result_halts: true

dead_man:
  policy_label: H11_AUTO_DEAD_MAN_15_60_V1
  heartbeat_interval_seconds: 15
  maximum_heartbeat_age_seconds: 60
  automatic_resume: false

notification:
  primary_profile_label: PUSHOVER_EMERGENCY_RECEIPT_ACK_V1
  secondary_profile_label: EMAIL_SECONDARY_V1
  entry_requires_primary_ready: true
  delivery_failure_blocks_new_entry: true

ownership:
  account_mode: EXCLUSIVE_DURING_AUTO
  manual_trading_while_auto_enabled: false
  other_private_api_client_while_auto_enabled: false
  external_or_manual_position_halts: true

host:
  host_profile_label: CURRENT_MAC_SUPERVISED_FAKE_REHEARSAL
  supervisor_profile_label: DISABLED_LAUNCHD_TEMPLATE_NOT_INSTALLED
  clock_monitor_required: true
  operator_kill_required: true

credential_permission:
  credential_profile_label: PENDING
  permission_profile_label: PENDING
  env_fallback_allowed: false
  raw_secret_logging_allowed: false

safety:
  actual_post_authorized: false
  live_ready: false
  unattended_live_supported: false
```

PENDINGを1つでも含むmanifestはactual profileとして有効化できない。

## 3. Canonicalization

digest対象はmanifestの機械fieldだけ。説明文、コメント、review note、署名欄を含めない。

```text
serialization=UTF-8 JSON
object keys=lexicographic sort
whitespace=none
separator=(',', ':')
decimal thresholds=canonical decimal strings
integers=JSON integers, boolean不可
timestamps=RFC3339 UTC
null=PENDING manifest only; approved manifestでは禁止
hash=SHA-256
display prefix=sha256:
```

YAML templateを直接hashせず、schema validatorが生成したcanonical JSONだけをhashする。将来runnerが自動生成し、
operatorがdigestを手入力しない。

## 4. Immutable generation rule

以下のいずれかを変更した場合、同generationを更新せず新generationを作る。

- horizon / model / threshold
- data freshness / clock margin
- quantity / budget / stop
- entry / exit profile
- SL / TP / max hold
- reconciliation cadence
- dead-man / notification
- account ownership
- host / supervisor
- credential permission
- implementation digest

旧SQLite、journal、checkpointを新generationへcopyしない。比較用safe aggregateだけを参照する。

## 5. Approval records

```yaml
operator_policy_approval: APPROVED_2026_07_15
broker_capability_review: SAFE_SUMMARY_ACCEPTED_V4_SELECTED
independent_safety_review: PENDING
host_rehearsal_result: PENDING
fault_soak_result: PENDING
actual_activation_authorization: false
```

approval recordはmanifest digestと完全一致させる。別digestのapprovalを再利用しない。

## 6. Current Phase B relationship

現在コードがSQLiteへ固定しているもの:

```text
generation_label
strategy_version
selected_horizon
signal_config_hash
risk_policy_label / digest
dead_man_policy_label / digest
```

完全manifestとのgap:

```text
execution profile
quantity
exit thresholds
data / clock thresholds
reconciliation profile
notification destination
ownership
host / supervisor
credential permission
implementation digest binding to generation
```

このgapはGMO回答・operator決定・host rehearsal前に推測で埋めない。

## 7. Safety boundary

本templateはconfig file生成、runtime binding、credential、broker read/write、POST、liveを許可しない。
承認済み完全manifestを将来作成する場合も、actual activationは別Stepである。

## 8. Offline validator / hash CLI（implemented no-POST）

```bash
cd backend

# PENDINGを許す構造確認。frozen digestは出力しない
python3 -m scripts.h11_auto_generation_manifest \
  --manifest /absolute/path/to/draft-manifest.json \
  --mode draft

# PENDINGを一切許さず、canonical JSONのSHA-256を生成
python3 -m scripts.h11_auto_generation_manifest \
  --manifest /absolute/path/to/frozen-manifest.json \
  --mode frozen
```

入力はUTF-8 JSONのregular non-symlink fileだけで、最大256 KiB。YAML templateを直接hashしない。
`execution_profile_hash`は`scripts.h11_auto_profile_freeze --mode frozen`の出力だけを転記し、
profile labelだけでbroker contractを識別しない。

`draft` mode:

```text
manifest_schema=H11_AUTO_GENERATION_V1_DRAFT
manifest_status=PENDING_OPERATOR_APPROVAL
PENDING field=allowed
manifest_digest=not emitted
```

`frozen` mode:

```text
manifest_schema=H11_AUTO_GENERATION_V1
manifest_status=OPERATOR_FROZEN_NOT_ACTIVATED
PENDING field=forbidden
manifest_digest=sha256:<64 lowercase hex>
actual_post_authorized=false
live_ready=false
unattended_live_supported=false
```

validatorはexact nested schema、canonical decimal threshold、hash形式、1建玉・1日1entry・各1attempt、
no scale-in / hedge / retry / repost / generic close、risk上限順序、dead-man、専用口座、通知・reconciliation、
env fallback禁止、安全flag falseをfail-closedで検証する。safe outputへquantity、risk値、credential labelを
出さない。

```text
implementation=backend/scripts/h11_auto_generation_manifest.py
focused_tests=40 passed
network_import=false
credential_import=false
env_read=false
broker_read=false
broker_write=false
actual_post=false
```

本CLIはmanifestをruntimeへbindingせず、activation permissionも生成しない。現在の24h soakが固定する
`app/h11_auto/*.py` source digestは変更していない。将来の完全generationでは、このvalidatorを含む承認済み
code commit / implementation digestを別途manifestへ固定する。
