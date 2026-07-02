# Step 6G Safe Pace Policy

## Summary

Step 6G safe pace-up policy is not permission to rush toward live execution.
It is a shared working policy for reducing duplicate review, repeated grep, and
unnecessarily small Step splits while preserving the existing safety boundary.

Future Codex prompts can refer to this policy with:

```text
このStepでは、docs/STEP6G_SAFE_PACE_POLICY.md の safe pace-up policy を前提にしてください。
レビュー済み安全境界内の重複調査は減らしてよいが、env / credential / actual execution / API / POST / live_order_once / real signing / real transport / fresh preflight / final confirmation / 実資金再試行に近づく場合は必ず停止してください。
```

## Basic Policy

- Safe pace-up means reducing duplicated work inside an already reviewed safety
  boundary.
- Safe pace-up does not permit entering unreviewed runtime, credential, API, or
  POST territory.
- Information confirmed in the immediately previous Step can be reconfirmed
  briefly when the repository state has not changed.
- Checks inside the same reviewed safety boundary can be grouped into one review
  Step when that does not weaken the stop conditions.
- If a task approaches execution, credentials, API calls, POST, or live order
  paths, Codex must stop instead of pacing up.

## Allowed Pace-Up

Codex may:

- keep repeated repository and docs checks concise when the relevant files have
  not changed;
- group checks from the same safety boundary into one review Step;
- avoid repeating the same failed command or the same grep without new evidence;
- in review-only Steps, report a concrete next-Step candidate when no issue is
  found;
- include a ChatGPT-ready handoff summary in the final report;
- for CASE 1 or CASE 2 outcomes, propose one next Step with its purpose,
  allowed scope, forbidden scope, and candidate files;
- execute the proposed next Step only after the user explicitly requests it in a
  separate prompt.

## Forbidden Pace-Up

Codex must stop before any of the following:

- env access
- `.env` access
- credential read
- credential injection
- actual checker execution
- actual result receipt
- real signing
- real headers generation
- real transport
- API call
- read-only API call
- public API call
- Private API call
- HTTP POST
- order endpoint
- `live_order_once`
- real order
- final confirmation
- fresh preflight
- live-money Step 6G retry

The Step 6G controlled one-shot POST exception in `AGENTS.md` remains explicit
and opt-in. It does not apply to docs, review, skeleton, contract, planning, or
policy hardening Steps.

## Fixed Semantics

- `READY_CONFIRMED` is not POST permission.
- `READY_CONFIRMED` is not final confirmation.
- `READY_CONFIRMED` does not mean fresh preflight has passed.
- `NOT_PROVIDED` is not actual result receipt.
- A receipt skeleton is not actual receipt handoff.
- Unknown, failed, unavailable, stale, timeout, reused, and previous-turn results
  fail closed and must not be retried as a shortcut.
- Step 4 approval phrases and ledger state must not be reused, spoofed, or
  adapted for Step 6G.

## Stop Conditions

Codex must stop and report instead of continuing when:

- docs-only work would require code, tests, settings, lockfile, or generated
  artifact changes;
- review-only work would require implementation;
- env or `.env` access would be needed;
- credential values or credential metadata would need to be inspected;
- actual checker execution or actual result receipt would be needed;
- API, read-only API, public API, Private API, broker, HTTP POST, order endpoint,
  or `live_order_once` access would be needed;
- real signing, real headers, or real transport would be needed;
- fresh preflight or final confirmation would be needed;
- the repository state is too different to safely isolate the requested Step;
- the same failure repeats twice without new evidence.

## Final Report Requirements

Final reports for Step 6G safe pace-up work should include:

- what was reviewed or changed in the current Step;
- where the work stopped and what it did not enter;
- evidence that the safety boundary was preserved;
- one recommended next Step;
- forbidden actions that must remain forbidden in the next Step;
- a ChatGPT-ready handoff summary that can be pasted into the next planning
  thread.

## Current Next-Step Direction

After Step 6G-PC-OX-R-ONE-SHOT-POST-APPROVED-PRIMITIVE-ACTUAL-SOURCE-SUPPLY-C,
the recommended next Step is a retry of the dedicated real POST execution gate
using the controlled route, approved primitive actual source boundary, approved
primitive source boundary, approved primitive boundary, and controlled real
transport binding. Route-ready, actual-source-ready, source-ready,
approved-primitive-ready, and binding-ready states are still not POST permission
by themselves:

```text
Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE-RETRY-6:
dedicated real POST gate retry / requires sanitized preview, controlled
approved primitive actual source boundary, approved primitive source boundary,
approved primitive boundary, controlled binding, and new POST-specific
confirmation first
```

That Step must not start with POST. It must first show the sanitized executable
order preview, obtain a new explicit POST-specific confirmation, and must still
keep HTTP POST separated from retry/repost, ledger update, actual result
receipt, and actual receipt handoff.
The POST-specific confirmation from RETRY-4 is not reusable.
The POST-specific confirmation state from RETRY-5 is also not reusable.
Until that separate step satisfies its own gates, Codex must still avoid env
value exposure, credential value exposure, signature value exposure, headers
value exposure, raw request/response exposure, broker/API response exposure,
order endpoints, `live_order_once`, ledger updates, attempt counter persistence,
actual receipt handoff, and live-money Step 6G retry.
