# Step 6B Real Approval Artifact Generation

## Summary

Step 6B adds a dry-run-only approval artifact generation model. It consumes the
Step 6A `LiveOrderRealApprovalGateEnablementState` and, only when the source
state, explicit Step 6B request snapshot, and sanitized safety snapshot are safe,
can generate internal model artifacts:

```text
approval_id_generated=true
approval_command_generated=true
approval_artifact_generated=true
```

These artifacts are for future Step 6C validation only. They are not live order
permission and they do not authorize HTTP POST.

## Scope

Step 6B records:

- the ready Step 6A enablement state used as source evidence
- an explicit Step 6B request acknowledgement snapshot
- a sanitized artifact-generation safety snapshot
- an internal approval ID derived only from sanitized fields
- an internal one-line approval command for future validation
- the approval command sha256, fingerprint, and redacted representation
- TTL, same-session, exact-match, and ACK-token requirements
- future Step 6C handoff conditions and blockers
- check results proving no API, no copyable approval text, and no POST

## What this step does

Step 6B may generate an internal `approval_id` and internal `approval_command`
inside the model. The command is not rendered in full, not copied, not saved, and
not executable in this step.

## What this step does not do

Step 6B does not:

- set `allowed_for_live=true`
- issue a real approval gate
- render the full approval command
- create copyable approval text
- copy approval text to the clipboard
- save approval text to a file
- call read-only API
- call public API
- call Private API
- call broker code
- call `live_order_once`
- read or write ledger files
- execute HTTP POST
- place, close, cancel, or change an order

## Input: LiveOrderRealApprovalGateEnablementState

The source Step 6A state must be ready:

- `REAL_APPROVAL_GATE_ENABLED_NO_ARTIFACTS`
- `enablement_state_ready=true`
- `eligible_for_future_step6b_approval_artifact_generation=true`
- `approval_gate_enabled=true`
- `allowed_for_live=false`
- `approval_gate_issued=false`
- no prior approval ID or approval command
- no copyable or executable approval text
- no usable real approval artifacts
- no API, broker, read-only API, public API, or `live_order_once` calls
- `post_allowed_this_step=false`
- `post_executed=false`

Blocked or unsafe Step 6A states fail closed before any Step 6B artifact is
ready.

## Input: ArtifactGenerationRequestSnapshot

`LiveOrderRealApprovalArtifactGenerationRequestSnapshot` is sanitized operator
intent only. It must confirm:

- explicit Step 6B user instruction received
- real-money risk understood
- no API in Step 6B understood
- no POST in Step 6B understood
- no `live_order_once` in Step 6B understood
- artifact generation only understood
- approval command is not copyable in Step 6B understood
- Step 6C is required for validation
- Step 6D or later is required for API preflight
- Step 6E or later is required for POST
- unknown means stop understood
- request scope label is
  `approval_artifact_generation_only_no_api_no_post_no_copyable_display`

Any missing acknowledgement blocks with `BLOCKED_STEP6B_ARTIFACT_REQUEST`.

## Input: ArtifactGenerationSafetySnapshot

`LiveOrderRealApprovalArtifactGenerationSafetySnapshot` is input only. It does
not fetch current market state and does not call any API.

Required safe values include:

- source enablement state age within `300` seconds
- `approval_gate_enabled=true`
- `allowed_for_live=false`
- no prior approval ID, approval command, copyable command, executable command,
  or usable artifacts before Step 6B
- `timezone=Asia/Tokyo`
- `market_hours_source=sanitized_snapshot_only`
- `market_session_state=OPEN`
- `is_weekend_jst=false`
- `market_window_allowed=true`
- `broker_maintenance_active=false`
- holiday and unknown flags false
- market-hours snapshot age within max age
- `fresh_pre_approval_preflight_source=sanitized_snapshot_only`
- `fresh_pre_approval_preflight_status=READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW`
- `fresh_pre_approval_preflight_passed=true`
- fresh preflight unknown false and age within max age
- `open_positions_count=0`
- `active_orders_count=0`
- `result_unknown=false`
- `raw_response_saved=false`
- `raw_response_displayed=false`
- `secret_scan_passed=true`

Unsafe, stale, missing, or unknown values block with
`BLOCKED_STEP6B_ARTIFACT_SAFETY_SNAPSHOT`.

## Output: LiveOrderRealApprovalArtifact

Ready output means:

```text
APPROVAL_ARTIFACT_GENERATED_NO_API_NO_POST
artifact_ready=true
eligible_for_step6c_validation=true
approval_gate_enabled=true
approval_gate_issued=false
approval_id_generated=true
approval_command_generated=true
approval_command_copyable=false
approval_command_displayed=false
approval_command_persisted=false
approval_command_copied_to_clipboard=false
approval_command_executable=false
allowed_for_live=false
post_allowed_this_step=false
post_executed=false
```

The generated approval command remains an internal model field for future Step
6C validation. It is not displayed as a complete command in Step 6B.

## Approval ID Generation

The approval ID uses only sanitized inputs:

- created timestamp
- source enablement state ID
- symbol
- side
- size
- execution type
- same-session label

It does not use credentials, API responses, order IDs, execution IDs, position
IDs, request URLs, raw requests, or raw responses.

## Approval Command Generation

The internal approval command is one line and includes sanitized values for the
generated approval ID, symbol, side, size, execution type, TTL, same-session
label, and required ACK tokens. Step 6B does not render the complete command and
does not make it copyable.

## Approval Command Redaction Policy

Step 6B exposes only:

- `approval_command_sha256`
- `approval_command_fingerprint`
- `approval_command_redacted`
- `approval_id_redacted`
- `approval_id_fingerprint`

The redacted representation intentionally omits the full approval ID and full
approval command. This keeps Step 6B from becoming an approval gate.

## Why Full Approval Command Is Not Rendered In Step 6B

Step 6B is artifact generation only. If the full command were displayed in a
copyable form, the step could be confused with an approval gate. That boundary
is reserved for future Step 6C validation and later explicit approval flow.

## TTL / Same Session / Exact Match

Step 6B fixes:

- `ttl_seconds=300`
- `same_session_required=true`
- `approval_command_exact_match_required=true`
- `approval_command_one_line=true` for ready artifacts

## Required ACK Tokens

The internal command must include these ACK tokens:

- `ACK_RISK=YES`
- `ACK_NO_POST_IN_STEP6B=YES`
- `ACK_NO_API_IN_STEP6B=YES`
- `ACK_NO_LIVE_ORDER_ONCE=YES`
- `ACK_NO_RETRY=YES`
- `ACK_NO_LOOP=YES`
- `ACK_NO_ADD=YES`
- `ACK_NO_CHANGE=YES`
- `ACK_NO_CANCEL=YES`
- `ACK_NO_CLOSE=YES`
- `ACK_UNKNOWN_MEANS_STOP=YES`

## Ready Artifact Meaning

`APPROVAL_ARTIFACT_GENERATED_NO_API_NO_POST` means only that Step 6B produced a
sanitized internal artifact for future Step 6C validation. It is not approval,
not API preflight, and not live POST permission.

## Blocked Request Meaning

`BLOCKED_STEP6B_ARTIFACT_REQUEST` means the explicit Step 6B request or operator
acknowledgements were missing or outside scope.

## Blocked Safety Snapshot Meaning

`BLOCKED_STEP6B_ARTIFACT_SAFETY_SNAPSHOT` means the sanitized safety snapshot was
stale, unsafe, unknown, or indicated prior artifacts/state that would make Step
6B unsafe.

## Blocked Source State Meaning

`BLOCKED_STEP6B_SOURCE_ENABLEMENT_STATE` means the Step 6A source state was
missing or not ready for Step 6B artifact generation.

## Future Step 6C Handoff

Future Step 6C must be a separate explicit task. It may validate the artifact and
compare command identity, but it still must keep `allowed_for_live=false` unless
a later separately scoped step changes that boundary.

Step 6C handoff conditions include:

- user explicitly requests Step 6C
- Step 6C remains no API and no POST unless separately scoped
- Step 6C validates approval artifact exact match
- Step 6C may compare user-provided command with generated command
- Step 6C must enforce TTL 300 seconds
- Step 6C must enforce same session
- Step 6C must enforce one-line command
- Step 6C must reject newline, extra token, or missing ACK token
- Step 6C must keep `allowed_for_live=false`
- Step 6D or later is required for real API preflight
- Step 6E or later is required for any POST

## Safety Defaults

Step 6B keeps:

- `allowed_for_live=false`
- `approval_gate_issued=false`
- `approval_command_copyable=false`
- `approval_command_displayed=false`
- `approval_command_persisted=false`
- `approval_command_copied_to_clipboard=false`
- `approval_command_executable=false`
- `real_approval_artifacts_available=false`
- `post_allowed_this_step=false`
- `post_attempt_limit=1`
- `post_executed=false`
- `live_order_once_called=false`
- `private_api_called=false`
- `broker_called=false`
- `read_only_api_called=false`
- `public_api_called=false`
- retry, loop, add, change, cancel, and close all false

## Markdown Rendering

The renderer includes the required warnings:

```text
This Step 6B approval artifact generation is dry-run only.
This Step 6B artifact does not authorize live POST.
This Step 6B artifact keeps allowed_for_live=false.
This Step 6B artifact does not issue a real approval gate.
This Step 6B artifact may generate an internal approval_id and approval_command for future Step 6C validation only.
This Step 6B renderer does not display the full approval command.
This Step 6B renderer does not provide copyable approval text.
This Step 6B artifact does not call read-only API.
This Step 6B artifact does not call public API.
This Step 6B artifact does not call Private API.
This Step 6B artifact does not call live_order_once.
This Step 6B artifact does not execute HTTP POST.
```

It does not render the full approval command.

## Do-not-cross Boundaries

Step 6B does not cross into API calls, live runner execution, real approval gate
issuance, copyable approval command display, file persistence, clipboard use,
ledger operations, or HTTP POST.

## Tests

The Step 6B tests cover ready artifact generation, blocked request, blocked
safety snapshot, blocked source state, unsafe source mismatches, command
fingerprint/redaction, markdown sanitization, no-order imports, and forbidden
input rejection.

## Handoff Summary

Step 6B is complete when the model can generate an internal approval artifact
for future Step 6C validation while still keeping no API, no POST, no real
approval gate issuance, no copyable command display, and `allowed_for_live=false`.

## Step 6C Follow-up Status

Step 6C has now been implemented as
`LiveOrderRealApprovalArtifactValidation` in
`backend/app/live_verification/live_order_real_approval_artifact_validation.py`.
It validates the Step 6B artifact, explicit Step 6C request snapshot, provided
command snapshot, and sanitized validation safety snapshot.

Ready validation may set these model-only fields to true:

- `approval_artifact_validated`
- `approval_command_exact_match_validated`
- `approval_command_ttl_validated`
- `approval_command_same_session_validated`
- `eligible_for_step6d_api_preflight_planning`
- `approval_gate_enabled`

Those values remain internal Step 6C validation evidence only. Step 6C keeps
`approval_gate_enabled=true` only as Step 6A state-only enablement carried
through the Step 6B artifact. It also keeps `allowed_for_live=false`, does not
issue a real approval gate, does not render the full generated or provided
approval command, does not make approval text copyable, does not use `pbcopy`,
does not save approval text, does not call APIs or `live_order_once`, and does
not execute HTTP POST.

Details are in
[STEP6C_REAL_APPROVAL_ARTIFACT_VALIDATION.md](STEP6C_REAL_APPROVAL_ARTIFACT_VALIDATION.md).

## Step 6D Follow-up

Step 6D adds API preflight planning after Step 6C validation. A ready plan may
set `api_preflight_planned=true` and
`eligible_for_step6e_real_api_preflight_execution=true`, but it keeps
`allowed_for_live=false`, `api_preflight_executed=false`, all API/broker/
`live_order_once` flags false, and `post_executed=false`.

Step 6D defines future Step 6E planned checks and raw request/response handling
policy only. It does not call read-only/public/Private API, broker code,
`live_order_once`, ledgers, or HTTP POST, and it does not display/copy/save
approval commands. Details:
[STEP6D_REAL_API_PREFLIGHT_PLAN.md](STEP6D_REAL_API_PREFLIGHT_PLAN.md).

## Step 6E Follow-up

Step 6E adds read-only/preflight-only sanitized result evaluation after Step 6D.
Ready Step 6E output may mark `api_preflight_executed=true` and
`api_preflight_passed=true` only for sanitized preflight evidence, while keeping
`allowed_for_live=false`, no order endpoint, no order payload, no
`live_order_once`, no raw request/response display or save, and no HTTP POST.
The implementation pass did not run real API preflight because it was Sunday
JST. Details:
[STEP6E_REAL_API_PREFLIGHT_EXECUTION.md](STEP6E_REAL_API_PREFLIGHT_EXECUTION.md).

## Step 6F Follow-up

Step 6F adds post-readiness planning after a separate Step 6E-R2 sanitized pass.
It is still no POST and no order endpoint. Ready Step 6F output keeps
`allowed_for_live=false`, `post_allowed_this_step=false`, `post_executed=false`,
`live_order_once_called=false`, no order payload generation or send, and no
broker order path. It only prepares a stop-and-wait handoff for a future
explicit Step 6G request with fresh preflight.
