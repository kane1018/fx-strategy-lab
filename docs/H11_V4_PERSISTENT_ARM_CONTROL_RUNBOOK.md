# H-11 v4 Persistent Arm Control Runbook

Status: `NO_POST_VALIDATION_IN_PROGRESS`

## UI

Start the existing localhost UI. The header shows the unattended control
status and `ON` / `OFF` buttons.

## Expected current behavior

Until a separately reviewed and commissioned generation explicitly supports
unattended live operation, `ON` is disabled or refused. `OFF` remains the safe
default. The scheduler reports a sanitized disarmed status and exits before
constructing credentials or performing network work.

## Effective states

- `OFF`: no open position and new entry disabled.
- `ON_WAITING`: persistent arm is clear; every fresh runtime gate must still
  pass before an entry can be reserved.
- `EXIT_ONLY`: OFF is requested after an entry; no new entry, existing
  protection and exit lifecycle continue.
- `HALTED`: integrity, pending-result, counter, notification, or runtime state
  is not clear. ON does not clear HALT.

## Do not treat as activated

The control-plane slice is not complete unattended trading. Before activation:

- complete focused and related tests, Ruff, diff check, danger scan, and
  independent Architecture/Safety/Operations review;
- create a new reviewed-files digest and corrective generation;
- perform fresh external preparation and commissioning.

The first three implementation items are present, but they remain inactive
until the review, corrective generation, fresh preparation, and separate
commissioning steps are complete.
