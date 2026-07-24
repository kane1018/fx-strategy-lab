# H-11 v4 Unattended Live Adapter — Design (Phase 4), Design-Only

Date: 2026-07-24

Status: **design document only. No implementation code exists for this phase.
No permit is issued, no credential is read, no broker write occurs. This
document is not an activation, not a permit, and not authorization for any
of the actions it describes.**

## 1. Objective

Design the successor to the G012/G013 human-confirmed canary: a fixed-small-size,
generation-bound, unattended live order path. "Unattended" means no human
reads a freshly generated challenge and types it back at the moment of entry —
that is the one load-bearing property G012/G013's permit chain provides today,
and the one thing this document must design a structural replacement for.
Everything else in the G012/G013 write path is generic and reusable as-is.

This document also folds in Phase 5 preparation: machine-checkable
shadow-to-live promotion criteria (§7), so a later step can check them rather
than invent them under time pressure.

## 2. What is already reusable, unchanged

A codebase survey (2026-07-24) found that most of the G012/G013 write-path
machinery has no coupling to the human-confirmation step and can carry over to
an unattended path without modification:

| Component | File | Reuse |
|---|---|---|
| Permit / scope types + consumption/binding verification | `backend/app/h11_auto/v4_gmo_canary_activation.py` — `V4GmoActualActivationPermit`, `V4ActivatedRuntimeScope`, `issue_v4_gmo_actual_activation_permit`, `consume_v4_gmo_actual_activation_permit`, `require_v4_actual_activation_permit_binding_internal` | As-is. `issue_v4_gmo_actual_activation_permit(*, intent, resume_proof, current_turn_proof, repository, now_monotonic, lifetime_seconds=30.0)` only requires two *typed proof objects* of the right consumed-once shape — it does not care how those proofs were produced. |
| Persisted one-use action-proof chain | `backend/app/h11_auto/v4_gmo_persisted_authorization.py` | As-is. DB-commit-driven, digest-bound to `(cycle_ref, action, request_binding_digest)`. No G013 dependency at all. |
| Real coordinator + orchestration facade | `backend/app/h11_auto/v4_gmo_actual_coordinator.py` (`V4GmoActualCoordinatorStore`), `backend/app/services/h11_v4_gmo_coordinated_actual_path.py` (`V4GmoCoordinatedActualPath`) | As-is. Neither imports anything from `v4_gmo_canary_activation.py` or `h11_v4_gmo_g013_canary.py` — generation-bound but issuer-agnostic. (Correction to an earlier draft assumption: `V4GmoCycleState`/`require_v4_transition` in `v4_gmo_contracts.py` is **shadow/simulation-engine machinery** — `v4_gmo_engine.py`/`v4_gmo_runtime.py`/`v4_gmo_soak.py` via `V4GmoStateStore` — not what drives the real coordinator.) |
| Exact-size OCO calculation | `backend/app/h11_auto/v4_gmo_protection.py` — `build_exact_fill_oco_plan_no_post` | As-is. Pure function; nothing in the file gates it; the plan type actively forbids `actual_post_allowed`/`credential_read_allowed`/`network_access_allowed`. |
| Exit lifecycle dispatcher | `backend/app/services/h11_v4_gmo_exit_dispatcher.py` — `V4GmoExitDispatcher.dispatch_once` | As-is. One-use O_EXCL claim per `cycle_day_jst`, cancel→reconcile→close sequence, engages `store.engage_unknown_halt()` on any exception. Generation-bound via `coordinated_path.generation.digest`, not human-confirmation-bound. |
| Friday/weekend policy + time math | `backend/app/h11_auto/v4_gmo_contracts.py` — `v4_gmo_scheduled_time_exit_at`, `v4_gmo_weekend_flat_target_at`, the frozen hour/weekday constants | As-is. |
| Hard guard | `backend/app/security/real_broker_post_hard_guard.py` — `assert_real_broker_post_allowed(*, allow: bool)` | As-is. Default-deny on one literal boolean; no env/config bypass exists anywhere in the repo. In the h11_v4_gmo path, the `allow=True` that reaches it is a hardcoded literal *inside* `V4GmoHttpxPrivateTransport`, gated by permit + persisted-authorization consumption, not by anything a caller controls directly. |

**What is G013-specific and needs a new unattended design** — narrowly, two
functions in `v4_gmo_canary_activation.py`:

- `confirm_v4_major_incident_resume_exact(*, phrase, generation_digest)` —
  checks a hardcoded literal phrase via `hmac.compare_digest`.
- `confirm_v4_current_turn_exact(*, typed_phrase, challenge, intent)` — checks
  a freshly generated, per-call challenge string typed back in the same
  process turn.

Both exist to answer one question: *does a human, right now, agree this
specific order should be sent?* An unattended system has no human present at
that moment, so it needs a **structurally different answer to the same
question** — not a weaker version of the same mechanism. §3 is the proposal.

Also G013-specific and not reused: `app/services/h11_v4_gmo_g013_canary.py`'s
`prepare_g013_canary_session` / `run_g013_actual_canary_after_exact_confirmation`
orchestration — the module that wires human confirmation → permit issuance →
runtime binding. An unattended equivalent needs its own orchestration module
wiring the §3 replacement → the same, unmodified `issue_v4_gmo_actual_activation_permit`.

## 3. The core design question: what replaces real-time human confirmation

This is the single most safety-relevant decision in this document. It is
presented as a **proposal requiring explicit operator review and agreement**
before any implementation begins — not a decision this document makes
unilaterally.

### 3.1 Why this is inherently weaker than G013's model, and how to compensate

A human reading the exact order sheet and typing a fresh challenge phrase
back is, by construction, the single most information-rich safety check this
system can have: it catches anything the human notices, including things no
programmed check anticipated. Removing it is a real reduction in safety
margin, not a neutral architecture change. The compensation is not "one
clever automated check" but **several independent, narrow, structural checks
that together approximate what a human's glance would catch**, plus keeping
the human meaningfully in control at a *different* point in time (in advance
and after the fact, if not in the exact moment).

### 3.2 Proposed structural replacement

An unattended permit-issuance decision (replacing the two proof constructors,
feeding the same unmodified `issue_v4_gmo_actual_activation_permit`) should
require **all** of the following, each independently checkable and each
fail-closed:

1. **A pre-authorized window, set in advance by the operator, not at trade time.**
   The operator explicitly authorizes a fixed calendar window (e.g. "7 days
   from generation freeze") and a fixed cumulative entry cap across that whole
   window (e.g. "at most 10 unattended entries before this authorization
   expires and requires a fresh one"). A permit request outside the window or
   over the cap is refused, unconditionally. This is the closest unattended
   analogue to "a human agreed to this" — the agreement is real, it is just
   made in advance and bounded, rather than per-trade. **This artifact must be
   operator-write-only**, symmetric with item 5's HALT: the unattended system
   itself must have no code path that extends the window, raises the cap, or
   re-issues its own authorization. Only a fresh, separate operator action can
   do that — otherwise item 1 degrades into the automation approving its own
   continued operation, which defeats the point of a pre-authorized bound.
2. **Every existing G013 fail-closed gate, unchanged**: fresh formal signal
   within its age window, fresh sanitized Private GET preflight (account
   flat, active orders zero), fresh quote/spread/deviation bounds, frozen
   contract match (`SHORT_V1`/30m/`USD_JPY`/1,000/`MARKET`/exact protection
   contract hash), entry-time-window check, 1-entry-per-day cap. None of
   these are weakened; they are the same checks G013 already has.
3. **A realized-P&L risk ledger with real content** (new — does not exist
   today for the live path in a generic form). `daily_stop_clear` /
   `monthly_stop_clear` / `consecutive_loss_stop_clear` must be computed from
   an actual persisted ledger of realized outcomes from prior unattended
   entries, not left at a permissive default. This reuses the same one-use
   SQLite-ledger pattern already used throughout this codebase (e.g.
   `v4_gmo_persisted_authorization.py`, the shadow controller's own ledger) —
   a new table, not new architecture. **Cold-start is an explicit open
   question, not an implicit default**: with an empty ledger, all three
   `*_stop_clear` fields are vacuously "clear" until enough realized history
   accumulates. Whether that bootstrap gap is accepted as-is, or whether the
   first unattended entries need a manual conservative floor (e.g. a smaller
   entry cap for the first N trades), is a decision the operator must make
   explicitly at implementation time — it must not be decided silently by
   whichever default the implementer happens to pick.
4. **A supervisor health/dead-man check.** The supervising process must have
   been continuously healthy (heartbeat present, no unexplained gap) for a
   fixed minimum duration immediately before permit issuance. A host that
   just woke from sleep, just restarted, or has a stale heartbeat must not be
   trusted to have observed the world correctly in the preceding minutes;
   refuse in that case. This is the "host/dead-man state" dimension deferred
   from the shadow track (§ decision below) — it has real protective meaning
   here, because a live position now exists to protect.
5. **An operator-settable persistent HALT the operator can raise at any time**,
   checked immediately before permit issuance, structurally identical in
   spirit to the shadow ledger's sticky HALT (latch-only, no auto-clear) but
   scoped to the live adapter's own ledger. This is the closest unattended
   analogue to "the human can still stop this" — not real-time per-trade
   control, but real-time veto power that does not depend on the automation
   noticing anything itself.
6. **Notify before or immediately upon permit issuance**, via the existing
   reviewed `H11V4DisabledDualRouteNotifier` (Phase 3 slice 2's
   `SHADOW_ACTIONABLE_OBSERVED`/`SHADOW_HALT_ENGAGED` pattern extends
   naturally here with new live-specific event labels). This does not gate
   the permit — a failed notification should itself be a fail-closed
   condition (per the original handoff's D: "通知失敗時にentryへ進まない設計"),
   which is a genuine behavioral difference from Phase 3 slice 2, where
   notification is currently decision-only and never blocks anything.

None of items 1–6 exist today. All of them are new, bounded, independently
testable components — not a rewrite of anything reusable in §2.

### 3.3 What this explicitly does not attempt

This proposal does not claim to be equivalent in safety to G013's real-time
human confirmation. It cannot be — that is an inherent property of removing a
human from the loop, not a gap in this design. The claim is narrower: that
items 1–6, taken together, are the most defensible structural approximation
available, and that the residual risk they leave is one the operator accepts
explicitly (as a documented, dated, revocable decision — see §6) rather than
implicitly.

### 3.4 Operator decisions (2026-07-24)

The operator reviewed §3.2 and decided:

- **Six-item structure: approved** for implementation as fake-only,
  independently reviewed slices.
- **Item 1 window: one JST trading day per authorization.** Combined with the
  frozen 1-entry-per-day cap, each authorization artifact therefore permits at
  most **one** entry, and every trading day of unattended operation requires a
  fresh, separate operator authorization action. This is deliberately more
  conservative than the 7-day example sketched in §3.2 — it keeps a human
  decision within one day of every order the system could ever place, which is
  the closest an unattended design can get to G013's per-trade human
  confirmation.
- **Item 3 cold-start: accepted as-is** (an empty realized-P&L ledger counts as
  stops-clear). This is coherent *because of* the 1-day window decision: the
  maximum exposure an empty ledger can permit is a single entry bounded by the
  frozen 5,000-yen per-trade loss cap before the operator is back in the loop
  for the next authorization.

These decisions are revocable by the operator at any time and are themselves
not a permit, generation freeze, or activation.

## 4. Fixed contract (unchanged)

`SHORT_V1`, `30m`, `USD_JPY`, `1,000` units, `MARKET` entry, existing
protection contract hash (`sha256:2b2a5d86…`), existing signal config hash
(`sha256:ca08df18…`), 1 entry/day, entry/OCO/cancel/exit each at most 1
attempt per action per cycle (enforced by the existing, unmodified
`v4_gmo_persisted_authorization.py` chain — see §2). No field in this
contract changes for the unattended path; only the *issuance* mechanism
changes.

## 5. Module boundary

Per the original handoff's explicit requirement ("live adapterはshadow
adapterと別module"), the unattended live orchestration module is separate
from every Phase 1–3 shadow module:

- New: `app/services/h11_v4_unattended_live_activation.py` (proposed name) —
  implements §3.2's six checks and calls the *unmodified*
  `issue_v4_gmo_actual_activation_permit`.
- New: `app/services/h11_v4_unattended_live_orchestration.py` (proposed name)
  — the unattended equivalent of `h11_v4_gmo_g013_canary.py`'s session
  wiring, calling the *unmodified* coordinator/coordinated-path/exit
  dispatcher.
- No import from any Phase 1–3 shadow module into these, and no import from
  these back into any shadow module. A shadow intent or shadow observation is
  never accepted as input to permit issuance — the unattended live path
  independently re-derives its own fresh formal signal and fresh Private GET
  preflight, exactly as G013 already does.

## 6. What stays out of scope for every design/implementation step until explicitly authorized

- No environment variable, `.env` value, or config flag ever enables real
  posting. (Already structurally impossible per §2's hard-guard review; this
  is a restatement, not a new control.)
- No generic "allow bridge" function that converts multiple booleans into a
  single `allow` value — already explicitly rejected project-wide (AGENTS.md,
  "Step 6G-PC-OX-R-POST-INCIDENT-LIVE-ALLOW-BRIDGE-NO-POST-C").
  §3.2's checks must each independently gate a *specific, non-reusable* proof
  object (mirroring `V4MajorIncidentResumeProof`/`V4CurrentTurnConfirmationProof`'s
  shape), not collapse into one boolean.
- No scheduler/resident process is installed by this document or by any
  implementation slice until that slice is separately, explicitly authorized
  and independently reviewed (per the existing G012 LaunchAgent precedent's
  own review history).
- Real Keychain access and real Private API calls remain something the
  implementer of a future slice does not execute directly either (per the
  boundary already established for this entire unattended track): a real
  activation event requires the operator's own action, not an assistant's.
- This document, once written, is **not** itself a permit, a generation
  freeze, or a promotion decision. It is input to a future explicit
  operator decision.

## 7. Phase 5 preparation: machine-checkable promotion criteria

Per the original handoff §5H, promotion from shadow to live-adapter-implementation
should be checked by machine-verifiable criteria, not judgment calls made
under time pressure. Proposed checklist (all must hold before Phase 4
implementation begins in earnest, checked against the shadow ledger's actual
accumulated history):

- Duplicate signal entries recorded: 0 (already enforced structurally by the
  shadow controller's `UNIQUE(signal_fingerprint)` constraint — verify the
  ledger has zero rows contradicting this over the full observation period).
- Same-day second actionable signals: 0 actionable admits (the daily cap logic
  is exercised only synthetically today per Phase 3 slice 1's documented
  limitation — this criterion cannot be satisfied by live observation alone
  until the full operational, Private-GET-informed preflight exists and an
  actionable cycle occurs naturally).
- Retry/repost of any action: 0 (structurally enforced; verify no code path
  added since review permits it).
- Writes after an unknown result: 0 (not yet applicable — no writes exist in
  the shadow path; becomes checkable once Phase 4's write path exists).
- Contract drift acceptance: 0 (the frozen contract's `__post_init__`
  invariants have never been relaxed; re-verify at generation freeze time).
- Stale signal/quote acceptance: 0 (verify the ledger's recorded ages never
  exceed the frozen bounds — spot-checkable via the existing sanitized ledger
  fields).
- Restart-after-crash ledger bypass: 0 (validated in Phase 2's stress test,
  §Phase 2 report — real kill/restart showed no duplicate, no corruption).
- HALT bypass: 0 (validated in Phase 2's stress test — sticky HALT has no
  clear/reset path, confirmed via `hasattr`).
- Unreviewed dependency reachability: 0 (every shadow slice's import-graph
  isolation test remains green; re-run before any promotion decision).
- Every actionable cycle has a deterministic sanitized terminal classification:
  holds today (`V4ShadowControllerReport.status` is always one of five fixed
  enum values; the report's own `__post_init__` enforces this).
- Notifications do not change authorization: holds by construction (Phase 3
  slice 2's decision function never touches the controller or ledger; it only
  reads a `V4ShadowControllerReport` already recorded).
- Broker POST count remains 0 throughout shadow observation: holds today,
  verified directly against the ledger and the live 1-hour observation run
  (2026-07-24).

This checklist intentionally does not include anything about strategy
profitability. Per the original handoff: "shadowで安全に動いたことは、strategyの
収益性証明ではない" — operational safety and performance are not to be
conflated, here or anywhere else in this project.

## 8. Recommended next steps (not authorized by this document)

1. Operator reviews §3.2's six-item proposal and either approves it, modifies
   it, or requests a different structural replacement.
2. Once agreed, implementation proceeds as separate, independently reviewed
   slices (matching the Phase 1–3 pattern): (a) the realized-P&L ledger, (b)
   the supervisor health/dead-man check, (c) the pre-authorized-window +
   cumulative-cap type, (d) the operator-settable persistent HALT for the
   live ledger, (e) the unattended permit-issuance orchestration module
   wiring (a)-(d) into the *unmodified* `issue_v4_gmo_actual_activation_permit`,
   each fake-only/structurally-no-POST in its own implementation pass, per
   this project's established pattern.
3. Real Keychain/Private-API/broker-write wiring, and any resident/scheduler
   process, remain separate, explicitly authorized steps after all of the
   above are implemented and reviewed.

## 9. Implementation status (2026-07-24, fake-only, unwired)

The §8-step-2 components were implemented the same day, with one significant
correction to the plan: a codebase survey found that **items (a) and (d)
already exist, reviewed and tested**, in
`backend/app/h11_auto/runtime_safety.py` — `PhaseBRiskPolicy/State/Store` with
`evaluate_risk_before_entry` / `record_closed_result_once` is precisely the
persistent realized-P&L ledger §3.2 item 3 calls for (JST day/month rollover,
per-cycle_ref dedup, daily/monthly/consecutive-loss stops against the frozen
limits, and a per-trade-bound discipline violation engaging latch-only
`KILLED`), and `engage_risk_kill` + `AutoRiskStopState.KILLED` (which never
auto-clears and has no un-kill API) is item 5's operator persistent HALT.
Duplicating either would have repeated the drift anti-pattern flagged in the
Phase 3 slice 1 review, so both are **reused unchanged** and the decision
layer consumes them through their existing types.

What was genuinely new, implemented fake-only and wired into nothing:

- `backend/app/services/h11_v4_unattended_live_heartbeat_chain.py` — item 4's
  *continuity* requirement. The existing `DeadManStore` proves heartbeat
  recency only; the chain store additionally tracks when unbroken continuity
  started, restarts the chain on any gap beyond the policy maximum, and
  reports `HEARTBEAT_CHAIN_CONTINUITY_INSUFFICIENT` until the minimum
  continuous duration has genuinely elapsed. Both are consumed side by side.
- `backend/app/services/h11_v4_unattended_live_authorization.py` — item 1's
  operator-write-only daily artifact. Read-and-consume only: the module's
  entire public surface is `check_operator_daily_authorization` and
  `consume_operator_daily_authorization_once` (a test pins this), so the
  automation structurally cannot mint, extend, re-date, or re-issue an
  authorization. Consumption is a one-use O_EXCL marker beside the artifact.
- `backend/app/services/h11_v4_unattended_live_permit_decision.py` — the pure
  decision layer composing all six conditions. It performs no I/O, and its
  output type pins `permit_issued=False` / `broker_post_authorized=False` /
  `live_ready=False` unconstructibly-otherwise. It cannot call
  `issue_v4_gmo_actual_activation_permit` even in principle: the proof
  constructors that function requires do not exist for the unattended path
  yet, deliberately — creating them (inside the G013 permit module, under its
  private-token discipline) is its own future, separately authorized and
  separately reviewed step.

Tests: `backend/app/tests/h11_auto/test_v4_unattended_live_components_fake_only.py`
(41 tests) covers the chain lifecycle (fresh/sustained/gap-reset/stale/missing/
future/corrupt/backwards/policy-mismatch, inclusive gap and continuity
boundaries), every authorization artifact defect, one-use consumption, the
six-condition decision matrix including composition with the real reused
`runtime_safety` machinery (operator KILL and a per-trade-bound discipline
violation both block end-to-end), forged/inconsistent-input rejection,
duck-typed input rejection, and import-graph isolation from every actual/
canary/coordinator/transport/hard-guard/private-api module.

### 9.1 Independent review outcome (2026-07-24) and the fix it forced

An adversarial Safety review VETOED the first version of this batch with one
Critical finding, since fixed and regression-pinned: the decision layer's
risk-gate branch appended only the gate's own `blocked_reasons` when
`allowed=False`. `PhaseBRiskGateResult` carries no internal consistency
invariant, so `allowed=False` with an *empty* reasons tuple is constructible —
and that combination contributed nothing to the decision's reason set,
producing `allowed=True` despite a blocked risk gate. That branch is exactly
where the realized-P&L stops (§3.2 item 3) and the operator KILL (§3.2 item 5)
flow, i.e. the operator's veto could have been silently ignored by any future
wiring, refactor, or deserialization that produced an inconsistent gate
object. The fix appends an unconditional `PERSISTENT_RISK_GATE_NOT_CLEAR`
sentinel whenever the gate is not allowed, and independently blocks on any
`stop_state` other than `ACTIVE` regardless of `allowed`
(`PERSISTENT_RISK_STOP_STATE_NOT_ACTIVE`); the analogous
`dead_man.halt_required` inconsistency now also blocks independently of
`alive`. All three are pinned by dedicated forged-input regression tests.

### 9.2 Named obligations for the future wiring step (from the same reviews)

These are documented obligations, not implemented behavior. The wiring step
must not begin without addressing each one:

1. **Risk-state bootstrap discipline (High).** `PhaseBRiskStore.load()`
   fabricates a fresh `ACTIVE` state when its file is missing — fine for
   Phase B paper, backwards for an unattended live veto: a lost/deleted state
   file would silently clear a latched `KILLED`. The wiring must treat a
   missing risk-state file as *refuse to run* (operator-initialized state
   required), and pin that with a test. Until then, "KILLED never auto-clears"
   is true of the API surface but not of the persistence layer.
2. **Canonical artifact path (Medium).** One-use consumption is keyed by the
   artifact's *directory* + day. Copying a same-day artifact to a second
   directory would permit a second consumption. The wiring must pin exactly
   one canonical artifact path per generation and never accept a
   caller-supplied one.
3. **Local, unsynced artifact directory (Medium).** The consumption marker
   lives beside the artifact. On a cloud-synced directory (note: macOS syncs
   `~/Desktop` — where this repository lives — to iCloud by default),
   sync conflict/restore could delete or resurrect the marker, and O_EXCL
   atomicity is not dependable on synced filesystems. The canonical artifact
   directory must be local and unsynced, or the marker must move to a
   dedicated local state root.
4. **`entry_gate_blocked_reasons=()` and `notification_ready=True` are
   unverifiable claims to this layer (High).** The decision cannot
   distinguish "gates ran and passed" from "gates never ran", nor "notifier
   verified" from a hardcoded `True`. The wiring must derive both from the
   real evaluations in the same cycle, and §3.2 item 6 additionally requires
   verifying the actual *send* at issuance time — readiness-before-decision
   alone quietly under-implements it.
5. **Single-writer assumption for the risk store (Medium).** The JSON
   load-mutate-save pattern has no cross-process lock; overlapping processes
   could both read `ACTIVE`. The wiring must enforce the existing
   single-process lock convention around every risk-state read/mutate/save.
6. **Daily auto-clear is acceptable only because of the 1-day window
   (Low, load-bearing).** `_roll_calendar` auto-clears `STOPPED_DAILY_BUDGET`
   on day rollover. That is safe here *only because* §3.4's decision requires
   a fresh operator artifact every JST day. Relaxing the window later (e.g.
   back toward the 7-day example) would silently invalidate this and must
   revisit the rollover semantics.
7. **`decision.allowed` must never collapse into proof construction (Medium).**
   §6's no-allow-bridge rule applies: the future proof constructors must each
   independently re-verify their own condition from primary state, not accept
   this layer's boolean as a substitute.
