# ENTRY POST GATE EXECUTION BOUNDARY REQUIREMENTS

Status: no-POST requirements record. Nothing in this document grants an
actual POST. `actual_entry_POST_allowed` is false everywhere; an actual entry
POST may only happen in a separate, operator-confirmed actual gate step, at
most once, with no retry / repost / second POST on any outcome.

This document was previously referenced but missing; it consolidates the
requirements for the final actual entry POST gate so the actual gate step can
run without any code change.

## 1. Full gate list for the actual entry POST gate

The actual gate must satisfy ALL of the following, fresh, in the same turn:

1. Repository gate: branch=main, working tree clean, HEAD == origin/main ==
   remote main, fresh re-verification in the actual step itself.
2. Evidence gate: paper evidence confirmed (safe summary) and anomaly
   evidence confirmed beyond synthetic.
3. Fresh read-only runtime gate (executed in the actual step, never reused):
   - `NO_POSITION` / `COUNT_ZERO`
   - `NO_ACTIVE_PENDING_ORDERS` / `COUNT_ZERO`
   - credential presence safe boolean true (presence only, never a value)
4. Market / ticker / spread safe labels (fresh, from the same runtime read):
   - `MARKET_OPEN_SAFE`
   - `TICKER_FRESH_SAFE`
   - `SPREAD_WITHIN_LIMIT_SAFE`
5. Approved entry order profile present as a safe-label source
   (`gmo_live_approved_entry_order_profile`): symbol `USD_JPY`, size profile
   `GMO_MINIMUM_ALLOWED_SIZE`, executionType `MARKET`. The profile is never
   a POST permission, and the raw numeric size is never displayed. The
   INTERNAL raw values are supplied by the operator at the actual gate turn
   via the sealed interface in
   `gmo_live_approved_entry_internal_value_source` (values used internally
   only, never displayed); while they are not supplied the gate blocks with
   `INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE` /
   `WAITING_FOR_APPROVED_ENTRY_INTERNAL_VALUE_SOURCE`
   (see `docs/APPROVED_ENTRY_ORDER_PROFILE_NO_POST.md`).
6. Entry request plan current-turn binding: `ENTRY_REQUEST_PLAN_BOUND_SAFE`
   (see section 2).
7. Operator current-turn inputs (exact match, never banked, never
   substituted by the AI):
   - signal `ENTRY_BUY` or `ENTRY_SELL` (HOLD is never executable)
   - `CONFIRM_ONE_ENTRY_POST_MAX_NO_RETRY_NO_REPOST_NO_SETTLEMENT`
   - `OPERATOR_READY_FOR_ONE_ENTRY_POST_MAX_NO_RETRY_NO_REPOST`
   - `OPERATOR_ACKNOWLEDGES_ACTUAL_BROKER_WRITE_RISK`
   - `OPERATOR_ACKNOWLEDGES_SENDER_MAY_USE_CREDENTIALS_INTERNALLY_WITH_NO_VALUE_EXPOSURE`
     (canonical spelling; see section 8)
8. Written sign-off recorded (`docs/ACTUAL_ENTRY_SIGNOFF_RECORD_NO_POST.md`).
9. One-use entry permit usable, hard guard default-deny present, sanitized
   preview ready, real sender injection ready.
10. Final preflight status
   `READY_FOR_ENTRY_POST_GATE_WITH_CURRENT_TURN_CONFIRMATION`
   (`gmo_live_entry_final_preflight`). READY statuses are classifications,
   never POST permissions.

## 2. Entry request plan binding requirements

Implemented in `backend/app/services/gmo_live_entry_request_plan_binding.py`.

- `ENTRY_BUY` -> `ENTRY_OPEN_BUY`, `ENTRY_SELL` -> `ENTRY_OPEN_SELL` is a
  mechanical mapping. The AI never decides, infers, or defaults a direction.
- symbol / size / executionType must come from the existing approved builder
  configuration (`app.private_api.order_builders`); if AI inference would be
  required, binding is refused (`AI_INFERENCE_REQUIRED_BLOCKED`).
- Only the dedicated ENTRY request plan (`POST /private/v1/order`) is
  bindable. Settlement, close, and generic plans are rejected both at
  classification time and by `validate_entry_only_request_plan`.
- The bound internal plan is handed only to the injected actual sender. It
  is never reported, previewed, or logged. Safe previews carry only:
  request plan status safe label, order kind safe label, entry-only safe
  boolean, current-turn binding safe boolean.
- No raw request body, size, price, P/L, ID, credential, signature, or
  header is ever displayed. Binding statuses:
  `ENTRY_REQUEST_PLAN_BOUND_SAFE` /
  `ENTRY_REQUEST_PLAN_PRESENT_BUT_NEEDS_FRESH_ACTUAL_GATE` /
  `ENTRY_REQUEST_PLAN_NOT_BOUND_NO_POST` /
  `ENTRY_REQUEST_PLAN_UNSAFE_TO_USE` /
  `ENTRY_REQUEST_PLAN_REVIEW_INCOMPLETE`.
- Binding is per-turn: a bound plan from a previous step is never reused
  (`CURRENT_TURN_BINDING_NOT_CONFIRMED` blocks).

## 3. Market / ticker / spread safe labels

Implemented in `backend/app/services/gmo_live_market_ticker_safe_labels.py`.

- Labels: `MARKET_OPEN_SAFE` / `MARKET_CLOSED_SAFE` / `MARKET_UNKNOWN_SAFE`,
  `TICKER_FRESH_SAFE` / `TICKER_STALE_SAFE` / `TICKER_UNKNOWN_SAFE`,
  `SPREAD_WITHIN_LIMIT_SAFE` / `SPREAD_OUT_OF_LIMIT_SAFE` /
  `SPREAD_UNKNOWN_SAFE`.
- The mapper input carries safe status enums only; there is structurally no
  field for a raw bid, ask, price, spread value, or timestamp, so raw market
  values cannot be reported.
- The freshness threshold and spread limit are owned by the real read-only
  safe-read client configuration. Safe-side default: when no configured
  limit exists, the client must report UNKNOWN, and UNKNOWN always blocks.
- Missing ticker degrades ticker and spread to UNKNOWN and blocks. Only
  `MARKET_OPEN_SAFE` + `TICKER_FRESH_SAFE` + `SPREAD_WITHIN_LIMIT_SAFE`
  passes. Without all three, an actual POST is forbidden.
- Labels must come from the actual gate's own fresh runtime read. This
  no-POST step performed no GET; the labels are produced fresh at the
  actual gate.

## 4. Real sender injection

- The real one-shot HTTP send, sealed credential unseal, and auth-header
  build live only inside the injected `ActualEntryOneShotSender`
  (`gmo_live_actual_entry_sender`). The execution boundary module never
  touches the network or a credential value.
- The sender uses credentials internally only; it never returns, stores, or
  logs a raw request/response, ID, size, price, P/L, credential, signature,
  or header. It returns sanitized outcome categories only.
- The default state is a refusing sender; a real sender is supplied only at
  the reviewed actual execution step.

## 5. One-use permit / activation / hard guard

- The activation (`build_actual_entry_execution_activation`) is granted only
  when every gate input including the entry request plan binding and the
  three market safe labels is satisfied. It is entry-only, one-use, never
  truthy, and its `grants_hard_guard_allow` is derived from `granted` only.
- The shared real-broker-post hard guard is called exactly once at the
  single reviewed call site (`send_actual_entry_post_once`). No literal
  `allow=True`, no reusable allow bridge, no persistent allow. The hard
  guard is never weakened.

## 6. No retry / repost / second POST

- On ANY outcome (accepted / rejected / unknown / timeout / network error /
  client error / server error) the flow returns immediately. There is no
  retry, repost, or second-POST branch, and the sender raises if invoked
  twice. Actual POST count is at most 1.

## 7. Forbidden routes and exposures

- Settlement / close / generic order routes are forbidden in the entry step:
  no `closeOrder`, no `settlePosition`, no generic opposite order as close,
  no `live_order_once`, no generic one-shot executor as settlement executor.
- No raw request/response, account/order/position/trade/transaction ID,
  quantity, price, P/L, credential value, signature, or header value is
  ever displayed. Safe labels, safe booleans, and safe counts only.
- No `.env` read, no `os.environ` secret read, no credential
  length/hash/fingerprint/prefix/suffix display.

## 8. Canonical operator credential-internal-use acknowledgement

Canonical value (code constant
`REQUIRED_ENTRY_CREDENTIAL_INTERNAL_USE_ACK` in
`gmo_live_actual_entry_execution_boundary`):

`OPERATOR_ACKNOWLEDGES_SENDER_MAY_USE_CREDENTIALS_INTERNALLY_WITH_NO_VALUE_EXPOSURE`

A misspelled variant ending in `..._EXPOSATION` appears in some historical
step logs. That variant is NOT canonical, must never be used as an actual
gate requirement or accepted as operator input, and exists in this document
only as a prohibited-value note.

## 9. Code-change rule

If the actual gate step finds that any code change is required, it must NOT
POST in that step. The change is made in a no-POST step, committed, pushed,
and the actual gate is re-entered fresh.
