# Step 6C Real Approval Artifact Validation

## Summary

Step 6C adds a dry-run-only approval artifact validation model. It consumes the
Step 6B `LiveOrderRealApprovalArtifact`, an explicit Step 6C request snapshot, a
provided command snapshot, and a sanitized validation safety snapshot.

Ready validation returns
`APPROVAL_ARTIFACT_VALIDATED_NO_API_NO_POST` and may set these model-only fields
to true:

- `approval_artifact_validated`
- `approval_command_exact_match_validated`
- `approval_command_ttl_validated`
- `approval_command_same_session_validated`
- `eligible_for_step6d_api_preflight_planning`
- `approval_gate_enabled`

These fields are validation evidence only. They do not authorize live POST,
API access, `live_order_once`, or a real approval gate.
`approval_gate_enabled=true` means the Step 6A state-only enablement carried
through Step 6B into Step 6C validation. It is not live permission, not approval
gate issuance, not copyable approval text, and not POST authorization.

## Scope

Step 6C validates:

- the Step 6B artifact ready state
- explicit Step 6C request acknowledgements
- provided command exact match
- command sha256 and fingerprint
- TTL 300 seconds
- same session label
- one-line shape
- newline rejection
- extra token rejection
- ACK token completeness
- sanitized safety snapshot freshness

## What This Step Does

Step 6C builds `LiveOrderRealApprovalArtifactValidation` and its supporting
snapshots:

- `LiveOrderRealApprovalArtifactValidationRequestSnapshot`
- `LiveOrderRealApprovalProvidedCommandSnapshot`
- `LiveOrderRealApprovalArtifactValidationSafetySnapshot`
- `LiveOrderRealApprovalArtifactValidationCheckResult`

It also renders a sanitized Markdown report that includes only redacted command
shape, sha256, and fingerprint.

## What This Step Does Not Do

Step 6C does not call read-only API, public API, Private API, broker, ledgers,
or `live_order_once`. It does not execute HTTP POST, issue a real approval gate,
display the full generated approval command, display the full provided approval
command, make approval text copyable, call `pbcopy`, or save approval text.

## Input: LiveOrderRealApprovalArtifact

The source artifact must be a ready Step 6B artifact:

- `artifact_status=APPROVAL_ARTIFACT_GENERATED_NO_API_NO_POST`
- `artifact_ready=true`
- `eligible_for_step6c_validation=true`
- `allowed_for_live=false`
- `approval_gate_enabled=true`
- internal `approval_id` and `approval_command` generated
- full command not displayed, not copyable, not persisted, not executable

Unsafe source artifacts block fail-closed.

## Input: ArtifactValidationRequestSnapshot

The request snapshot requires explicit Step 6C intent and operator
acknowledgements for real-money risk, no API, no POST, no `live_order_once`,
validation-only scope, non-copyable command handling, Step 6D for future API
preflight planning, Step 6E or later for any POST, and unknown-means-stop.

The required scope label is:

```text
approval_artifact_validation_only_no_api_no_post_no_copyable_display
```

## Input: ProvidedCommandSnapshot

The provided command snapshot stores the full command only for internal exact
match comparison. Rendered output uses:

- `provided_command_sha256`
- `provided_command_fingerprint`
- `provided_command_redacted`

Markdown and final reports must not show the full generated or provided
approval command.

## Input: ArtifactValidationSafetySnapshot

The safety snapshot is sanitized input only. It records artifact age, validation
age, market-hours/preflight snapshot freshness, open position count, active
order count, result-unknown status, raw response flags, and secret scan status.
It does not call APIs or read ledgers.

## Output: LiveOrderRealApprovalArtifactValidation

Ready output keeps:

- `approval_gate_enabled=true` as Step 6A state-only enablement evidence
- `allowed_for_live=false`
- `approval_gate_issued=false`
- `approval_command_copyable=false`
- `approval_command_displayed=false`
- `approval_command_display_mode=redacted_only_in_step6c`
- `approval_command_persisted=false`
- `approval_command_copied_to_clipboard=false`
- `approval_command_executable=false`
- `post_allowed_this_step=false`
- `post_attempt_limit=1`
- `post_executed=false`
- `live_order_once_called=false`
- `private_api_called=false`
- `broker_called=false`
- `read_only_api_called=false`
- `public_api_called=false`

## Exact Match Validation

The provided command must exactly match the Step 6B generated command. Any
mismatch in approval id, symbol, side, size, execution type, TTL, same session,
sha256, fingerprint, missing ACK token, extra token, or newline blocks
fail-closed.

## TTL / Same Session Validation

Step 6C validates TTL 300 seconds and same-session label through the provided
command and sanitized safety snapshot. Stale source artifacts or stale received
validation snapshots block.

## One-line / Newline / Extra Token Validation

The command must be one line. Newline characters, extra token names, duplicate
or surplus token count, and empty command input are blocked.

## ACK Token Validation

Step 6C requires the Step 6B ACK token set:

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

Missing ACK tokens block.

## Redaction Policy

Step 6C renderers display redacted command shape, sha256, and short fingerprint
only. Full generated and provided approval commands are intentionally omitted.

## Why Full Commands Are Not Rendered In Step 6C

Step 6C is validation-only. Showing copyable approval text here could be
mistaken for a real approval gate. The full command remains internal test/model
data and is not Markdown-rendered, copied, persisted, or made executable.

## Ready Validation Meaning

`APPROVAL_ARTIFACT_VALIDATED_NO_API_NO_POST` means the artifact passed dry-run
validation and can be handed to a future explicit Step 6D API preflight planning
task. It does not authorize live POST.
In ready state, `approval_gate_enabled=true` is preserved from the Step 6A
state-only model through the Step 6B artifact. This does not issue a real
approval gate and does not permit API access or POST.

## Blocked Meanings

- `BLOCKED_STEP6C_VALIDATION_REQUEST`: explicit Step 6C request or ACKs missing.
- `BLOCKED_STEP6C_PROVIDED_COMMAND`: provided command missing, malformed, stale,
  or mismatched.
- `BLOCKED_STEP6C_VALIDATION_SAFETY_SNAPSHOT`: sanitized safety snapshot unsafe
  or stale.
- `BLOCKED_STEP6C_SOURCE_ARTIFACT`: Step 6B artifact missing or not ready.
- `BLOCKED_STEP6C_UNSAFE_MISMATCH`: fail-closed mismatch outside the above
  buckets.

## Future Step 6D Handoff

Future Step 6D remains a separate explicit task. It must remain no POST unless
separately scoped, rerun market-hours and fresh preflight snapshots, reconfirm
open positions and active orders, and keep `allowed_for_live=false` unless a
later controlled step explicitly changes that boundary.

Step 6E or later remains the earliest place to consider a one-shot POST.

## Safety Defaults

Step 6C keeps no API, no POST, no copyable approval text, no `pbcopy`, no
approval text file save, no `live_order_once`, no ledgers, no retry, no loop, no
add/change/cancel/close, and `allowed_for_live=false`.
Ready validation preserves `approval_gate_enabled=true` only as state-only
enablement evidence from Step 6A. Blocked validation remains fail-closed.

## Markdown Rendering

The renderer includes warnings that Step 6C is dry-run only, does not authorize
live POST, keeps `allowed_for_live=false`, does not issue a real approval gate,
does not display full generated/provided approval commands, does not provide
copyable approval text, does not call APIs, and does not execute HTTP POST.

## Do-not-cross Boundaries

Do not connect Step 6C to API clients, brokers, `live_order_once`, ledgers,
clipboard, files, real approval gate issuance, or HTTP POST.

## Tests

Tests cover ready validation, blocked request, blocked provided command, source
artifact unsafe states, safety snapshot blockers, command redaction, sha256,
fingerprint, check results, future Step 6D handoff, no-order imports, forbidden
inputs, and Markdown sanitization.

## Handoff Summary

Step 6C is complete when approval artifact validation can pass internally while
full commands remain unrendered and non-copyable, all live/API surfaces remain
off, and future Step 6D handoff conditions are documented.
