# APPROVED ENTRY INTERNAL VALUE SOURCE (sealed, operator-supplied, no-POST)

Step (interface): `STEP_6G_PC_OX_U_APPROVED_ENTRY_INTERNAL_VALUE_SOURCE_SELF_DRIVE_NO_POST_C`
Step (supply channel): `STEP_6G_PC_OX_V_FINAL_ACTUAL_ENTRY_POST_GATE_WITH_SEALED_INTERNAL_VALUE_SUPPLY_C`
Date: 2026-07-07

Status: no-POST record. Nothing here grants an actual POST.
`actual_entry_POST_allowed` remains false everywhere. The raw numeric size
is never written in this document.

## 1. Sealed interface

Module: `backend/app/services/gmo_live_approved_entry_internal_value_source.py`
(`SealedApprovedEntryInternalValueSource`)

- Default state: NOT CONFIGURED →
  `INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE`; the actual gate
  blocks.
- Configured state: presence only is reported
  (`INTERNAL_RAW_VALUE_SOURCE_PRESENT_NOT_EXPOSED`). The values are sealed:
  `__slots__`, sanitized `repr`/`str`, never truthy, no public value
  accessor; the single internal consumer is
  `build_bound_entry_request_plan_internal` (entry-only plan builder → the
  injected actual sender). Validation errors never echo supplied values.
- A source-scan test enforces that the module contains no multi-digit
  literal, so a raw size can never be committed inside it.

## 2. The one sanctioned operator supply channel

The value must never appear in chat, docs, reports, or logs, so the ONLY
supply channel is an operator-created LOCAL file:

- File name: `.approved_entry_internal_value.local.json`
  (constant `OPERATOR_LOCAL_VALUE_FILE_NAME`)
- Location: repo root (operator's machine only). The name is gitignored, so
  it can never be committed; a test pins the gitignore entry.
- Content: a JSON object with exactly the string keys `symbol` and `size`
  (symbol must equal the approved safe label `USD_JPY`; size must be the
  positive numeric string the operator decided — GMO's minimum allowed
  unit per the approved profile).
- Loader:
  `load_sealed_approved_entry_internal_value_source_from_operator_local_file`
  — missing file returns the fail-closed NOT CONFIGURED source; malformed
  content raises sanitized errors that never echo the file contents; loaded
  values go straight into the sealed holder and are never printed.
- The operator creates and deletes this file in their own terminal, outside
  the assistant conversation, so the value never enters the chat log.

## 3. Gate record (STEP_6G_PC_OX_V)

At the OX_V actual gate the operator asserted supply via the sealed
interface, but no local value file existed and no other sanctioned channel
carried a value, so the sealed source was NOT CONFIGURED and the gate
stopped safe (`RESULT_BLOCKED_BEFORE_POST_SANITIZED`, POST count 0, no
runtime private GET). The AI did not infer the value. This loader was added
in that step as the no-POST fix so the next fresh actual gate can proceed
without any code change once the operator creates the local file.

## 4. Unchanged requirements

Presence of the local file is never a POST permission. The next actual gate
still requires, fresh in its own turn: the current-turn operator input, the
fresh read-only runtime safe read, market/ticker/spread safe labels, the
current-turn request plan binding, final preflight, sanitized preview, real
sender injection review, one-use permit/activation, and the hard guard —
with at most one entry POST and no retry/repost/second POST on any outcome.
