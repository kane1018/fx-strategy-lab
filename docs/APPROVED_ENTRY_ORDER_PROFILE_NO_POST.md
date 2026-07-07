# APPROVED ENTRY ORDER PROFILE (safe labels only, no-POST)

Step: `STEP_6G_PC_OX_T_APPROVED_ENTRY_ORDER_PROFILE_AND_BINDING_SOURCE_NO_POST_C`
Date: 2026-07-07

Status: no-POST record. Nothing here grants an actual POST.
`actual_entry_POST_allowed` remains false everywhere.

## 1. Profile safe labels

Source module: `backend/app/services/gmo_live_approved_entry_order_profile.py`

- `approved_symbol_safe_label`: `USD_JPY`
- `approved_size_profile_safe_label`: `GMO_MINIMUM_ALLOWED_SIZE`
- `approved_execution_type_safe_label`: `MARKET`
- `approved_profile_status`: `APPROVED_ENTRY_ORDER_PROFILE_SAFE_LABELS_READY`
- `profile_source_safe_label`:
  `REPO_APPROVED_ENTRY_ORDER_PROFILE_MODULE_SAFE_LABELS_ONLY`

The operator decision "size is fixed to GMO's minimum allowed unit"
(per `docs/GMO_LIVE_AUTOMATION_RESUME_DESIGN.md` §5) is represented ONLY as
the `GMO_MINIMUM_ALLOWED_SIZE` safe label. The raw numeric size is never
written in this document, in any report, or in the profile module (the
module contains no digit literals at all, enforced by a source-scan test).

## 2. What the profile is — and is not

- The profile is a safe-label SOURCE for the entry request plan binding.
- The profile is NOT an actual POST permission, not an allow bridge, and
  never truthy. Entry-only: settlement / close / generic / retry / repost /
  second-POST are hardcoded false.
- The AI must never infer the size, the symbol, or the executionType; when
  the profile is not configured, binding stays `NOT_BOUND` fail-closed.

## 3. Internal raw value source (separate concern, currently MISSING)

An actual send additionally needs a reviewed INTERNAL raw value source for
the numeric values the broker body requires. That source does not exist in
the repository yet, so:

- `internal_raw_value_source_status`:
  `INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE`
- request plan binding stops at
  `ENTRY_REQUEST_PLAN_PRESENT_BUT_NEEDS_INTERNAL_VALUE_SOURCE`
- final preflight stops at
  `WAITING_FOR_APPROVED_ENTRY_INTERNAL_VALUE_SOURCE`
- every actual gate must block (`APPROVED_SIZE_RUNTIME_VALUE_SOURCE_MISSING`
  family) until the internal source is added in an explicitly reviewed
  no-POST step. When it is added, its value must be used internally only and
  never displayed, logged, or reported.

## 4. Actual gate requirements unchanged

The profile does not relax any actual-gate requirement:

- fresh current-turn operator input (never banked, never substituted)
- fresh read-only runtime safe read in the same turn
- market / ticker / spread safe labels fresh and passing
- one-use activation / one-use permit / hard guard default-deny
- actual POST at most once; no retry / repost / second POST
- no settlement / close / generic route in the entry step
- no raw request/response, ID, quantity, price, P/L, credential, signature,
  or header exposure
