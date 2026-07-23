# H-11 v4 G013 Post-Canary Reconciliation Design

Date: 2026-07-23

## Purpose

The protected G013 canary subject is reconciled through a new, one-use,
generation-bound lane after a reported natural OCO settlement. This lane is not
the existing exit dispatcher and it cannot initiate a new entry.

## Fixed boundary

- The target reviewed generation is marked `entry_disabled=true` in the dedicated contract. `prepare_g013_canary_session` rejects that target before it can obtain formal inputs or create an order sheet.
- The contract binds the target reviewed digest and target generation digest to one immutable origin generation digest. The origin cycle reference is loaded only in memory from the origin coordinator state and is never emitted.
- The concrete broker client exposes only three fixed GET methods: `latestExecutions`, `openPositions`, and `activeOrders`. It has no generic request surface and no action, permit, dispatcher, cancel, close, or order dependency.
- The three reads occur once in fixed order with 0.25 second spacing. There is no retry. Broker data is reduced immediately to booleans and aggregate counts; credentials, raw payloads, headers, signatures, and identifiers are neither returned nor persisted.

## Result rules

- A terminal success requires the origin entry to be observed and both account positions and active orders to be zero.
- A known non-flat result returns a persistent-HALT status and performs no broker action.
- An unknown, rejected, malformed, missing-subject, or result-write failure is fail-closed. The one-use started marker remains, so the same target generation cannot retry.
- The only local writes are a new target-generation started marker and one terminal sanitized result marker under the existing shared runtime-root convention. The origin ledger is opened only through SQLite `mode=ro` after the existing ledger path is validated. Origin monitor, HALT, OCO, coordinator, and no-retry markers are never altered.

## Operational sequence

1. Review, test, freeze, and publish this corrective target generation.
2. Run its external preparation from operation 00 with fresh evidence.
3. Invoke the dedicated reconciliation CLI once only after the operator grants the subject-specific read-only action.
4. If flat is confirmed, retain both generations and report only the sanitized terminal status. If not, retain persistent HALT and do not invoke the exit dispatcher under this authority.
