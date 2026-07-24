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

### 9.3 Operator daily authorization artifact-creation CLI (2026-07-24)

The prior batch's exception text explicitly deferred artifact *creation* to
"the operator's own explicit CLI/manual operation, designed as a separate
Step" (§9.2 item 1 area, and the component exception's own prohibited-list).
That separate step is implemented here, under its own new AGENTS.md exception
scoped to creation only:

- `backend/app/services/h11_v4_unattended_live_paths.py` — a canonical,
  generation-bound path helper (mirrors `v4_gmo_runtime_paths.py`'s
  digest-validated state-root pattern), under the already-gitignored
  `backend/market_data/` root. Both this CLI (writer) and the future wiring
  step (reader) are expected to converge on this one function rather than
  accept an arbitrary caller-supplied path — this directly addresses §9.2
  item 2's "canonical path" obligation for the artifact's location (though
  the wiring step must still enforce it defensively, since a canonical helper
  existing does not by itself prevent a future caller from ignoring it).
- `backend/scripts/h11_auto_v4_unattended_live_create_daily_authorization.py`
  — the operator-run CLI. The JST trading day is always the real current
  day (no override flag exists); `--generation-digest` has no default; an
  existing file at the canonical path is never overwritten without
  `--force`; a symlinked destination is refused. The script only writes the
  artifact -- it calls the existing, unmodified `check_operator_daily_authorization`
  to report the result and never imports or calls the consume function.

**Update (2026-07-24, later the same day): §9.2 item 3 is now resolved.** A
read-only check on the actual development machine confirmed iCloud Desktop &
Documents sync is genuinely active (`com.apple.bird`/`com.apple.cloudd`
running, `FXICloudDriveDesktop` preference set, and this repository lives
under the synced `~/Desktop`) -- the risk §9.2 item 3 warned about was not
hypothetical. The canonical state root (`h11_v4_unattended_live_paths.py`)
was changed from a repository-relative path (`backend/market_data/...`,
inheriting whatever sync state the checkout happens to be in) to
`~/Library/Application Support/fx-strategy-lab-h11-v4-unattended-live/`,
overridable but no longer defaulting anywhere under `~/Desktop` or
`~/Documents` -- the only two locations iCloud Desktop & Documents sync
touches. `Path.home()`-relative, not tied to where the repository checkout
sits. Verified end-to-end against the real (non-test) default location, not
just overridden test paths. This resolves the precondition for *this specific
new component*; it does not retroactively relocate the pre-existing G012/G013
runtime state root (`v4_gmo_runtime_paths.py`, still repository-relative),
which remains a separate, out-of-scope, pre-existing condition affecting the
whole project, not something this track's components can fix unilaterally.

A same-day independent review found one Medium finding: the CLI's atomic-write
`.tmp` intermediate was created with `O_CREAT|O_WRONLY|O_TRUNC` rather than
`O_EXCL`, unlike `consume_operator_daily_authorization_once`'s own marker
write -- a local, co-resident attacker with write access to the exact
canonical directory could in principle plant a symlink at the `.tmp` path
between a check and the open call. Fixed to use `O_CREAT|O_EXCL`, matching
the consume function's pattern exactly; a pre-existing `.tmp` file (leftover
crash or a planted symlink) now fails closed with
`AUTHORIZATION_ARTIFACT_TEMP_FILE_ALREADY_EXISTS` rather than being silently
removed and reopened, with a regression test pinning that a symlinked `.tmp`
target is never written to.

Tests: `backend/app/tests/h11_auto/test_v4_unattended_live_authorization_create_cli_no_post.py`
(16 tests) cover path generation-binding and digest validation, artifact
creation and its resulting content, the no-overwrite-without-force,
symlinked-destination, and symlinked-temp-file behavior, and that the CLI
writes exactly one file, exactly at the canonical path, and nowhere else.

## 10. Unattended proof constructor — design (2026-07-24, design-only, no code)

This is the item this document has repeatedly deferred: "creating them (inside
the G013 permit module, under its private-token discipline) is its own
future, separately authorized and separately reviewed step" (§2). It is the
**only G012/G013 code change anywhere in this track** — every other component
so far is new, additive code in `app/services/`. This section is design only;
no implementation exists yet.

### 10.1 Why this must live inside `v4_gmo_canary_activation.py`

`issue_v4_gmo_actual_activation_permit` validates its two proof arguments by
checking `getattr(proof, "_token", None) is _RESUME_TOKEN` /
`_CONFIRMATION_TOKEN` — module-private sentinel objects
(`v4_gmo_canary_activation.py:27-28`). No code outside this file can construct
a valid `V4MajorIncidentResumeProof` or `V4CurrentTurnConfirmationProof`
without either modifying this file or reaching into its private names from
outside (the latter would be exactly the kind of back door this design
exists to prevent, and the existing import-graph isolation tests across this
track would flag it). The two proof-minting lines must physically live here.

Everything else about this file stays unchanged: `V4GmoCanaryIntent`,
`V4CurrentTurnChallenge`, `issue_v4_gmo_actual_activation_permit`,
`consume_v4_gmo_actual_activation_permit`, and the existing
`confirm_v4_major_incident_resume_exact` / `confirm_v4_current_turn_exact`
(the G013 human-confirmation path) are not touched. This is purely additive,
the same pattern already used for the Phase 3 slice 2 notification enum.

### 10.2 The verification-trust question, and the operator's decision

Two designs were considered for how much the new constructor trusts its
caller versus re-verifies itself:

- **Option B (rejected):** accept a pre-computed `V4UnattendedPermitDecision`
  plus a freshness/staleness bound (e.g. "computed within the last N
  seconds"). Smaller code footprint, but structurally weaker: it is still
  "accepting the boolean as a substitute" (§6's no-allow-bridge rule), just
  with an expiry attached, and correctly bounding staleness across process/
  clock boundaries is its own hard sub-problem that buys a weaker guarantee
  than it costs to build.
- **Option A (operator-approved 2026-07-24):** the new constructor takes
  references to the primary state stores themselves (the daily authorization
  artifact path, the risk store + policy, the dead-man store, the heartbeat
  chain store) and reads every one of them fresh, at the exact moment of
  proof-minting, then calls the already-reviewed pure
  `decide_unattended_permit_issuance` itself. It never accepts a
  pre-computed decision object. This satisfies §6/§9.2-item-7 literally: the
  trusted module re-derives the answer from primary state, not from anyone's
  claim about it.

Two inputs remain caller-supplied even under Option A:
`notification_ready: bool` and `entry_gate_blocked_reasons: tuple[str, ...]`.
This is a deliberate scope boundary, not an oversight: verifying notification
readiness for real requires an actual Pushover/SMTP send attempt (not built
yet -- named as §9.2 item 4's own gap), and verifying entry gates requires
the entire existing Public-market signal/quote pipeline, which this
historically network-free, minimal module has never touched even in the
human-confirmed G013 path (the human/caller has always been trusted to bring
a fresh, already-verified `V4GmoCanaryIntent`). The wiring step remains
responsible for both being genuinely fresh at call time, as already recorded
in §9.2 item 4.

### 10.3 The repeated-evaluation risk, and why it does not become unbounded reissuance

An operator review of this design surfaced a real risk: if the six-condition
check is re-run repeatedly (a retry loop, a re-evaluation, a bug) *before*
the daily authorization is actually consumed, each evaluation could
independently see `consumption_available=True` and mint a fresh, valid
resume/current-turn proof pair -- `issue_v4_gmo_actual_activation_permit`'s
own one-use marker is keyed by `cycle_ref` (derived from the signal), not by
the daily authorization artifact, so it would not by itself catch a second
mint against a *different* signal within the same day. This is a real
double-issue risk, not a recursion/hang risk -- `decide_unattended_permit_issuance`
is a pure, single-pass, always-terminating function; the danger is unbounded
*successful* re-attempts, not an infinite loop in the literal sense.

The fix is ordering, not new mechanism: **the new constructor consumes the
daily authorization as the first write action after the six-condition check
clears, before minting either proof.** Concretely, one function (not two
independent ones) performs the full sequence and returns both proofs
together:

1. Fresh-read authorization, risk, dead-man, and heartbeat state from their
   stores (§10.2). Combine with caller-supplied `notification_ready` and
   `entry_gate_blocked_reasons`. Call `decide_unattended_permit_issuance`.
2. If `not decision.allowed`, raise -- no write occurs.
3. If allowed, call `consume_operator_daily_authorization_once` immediately.
   Before its O_EXCL marker write, this function always performs its **own**
   fresh internal `check_operator_daily_authorization` call (verified in the
   existing code, `h11_v4_unattended_live_authorization.py:135-141`) rather
   than trusting any object the caller passed in. The **O_EXCL write itself**
   is the actual atomic mechanism that resolves a race between two callers;
   the internal check is what makes that write authoritative rather than
   trusting step 1's inputs.
4. Only after consumption succeeds, mint both
   `V4MajorIncidentResumeProof` and `V4CurrentTurnConfirmationProof` from the
   same evaluation and return them as a pair.

A second call for the same JST day -- whether from a genuine retry or a bug
in the same process -- reaches step 3 and finds `consumption_available=False`
via the fresh internal check, and refuses before any proof is minted; this
part is a plain repeated-filesystem-read property with no caching involved,
not something that needs its own proof.

**Two things this ordering does not yet fully close, both requiring
correction before this is treated as ready for implementation:**

- **Concurrency under O_EXCL is only as reliable as the filesystem.** This
  document has not yet run an adversarial concurrency test of the
  *authorization module's own* O_EXCL write specifically (an ad-hoc multi-
  thread verification was performed by a reviewer against the six-condition
  *decision layer* during the earlier component-batch review, not against
  this consume path, and citing it here as if it already covers this path was
  an error in an earlier draft of this section, now corrected). §9.2 item 3's
  underlying precondition (canonical artifact directory confirmed local and
  unsynced) **is now resolved** -- see §9.3's 2026-07-24 update: the
  authorization artifact's default state root was relocated to
  `~/Library/Application Support/...`, verified genuinely outside the
  actively-confirmed iCloud-synced `~/Desktop`/`~/Documents` trees. What
  remains outstanding is narrower: a real adversarial concurrency test for
  *this specific* consume-then-mint sequence, exercising true concurrent
  processes (not just repeated sequential calls), which still does not exist
  and must be written before this section's race-safety claim is treated as
  proven rather than designed.
- **Nothing yet prevents bypassing the new function entirely.** The existing
  `confirm_v4_major_incident_resume_exact` only requires matching a hardcoded,
  non-secret phrase constant, and `confirm_v4_current_turn_exact` only
  requires a challenge/intent pair a caller could construct itself. Nothing
  in this design stops a future implementer from calling those two existing
  functions directly, plus the unmodified `issue_v4_gmo_actual_activation_permit`,
  entirely skipping the new function's consume-first ordering -- which would
  silently reintroduce the exact double-issue risk this section exists to
  close. The future implementation step must make this bypass structurally
  unreachable from the unattended orchestration path (e.g. the unattended
  orchestration module must never import `confirm_v4_major_incident_resume_exact`/
  `confirm_v4_current_turn_exact` directly, enforced by its own import-graph
  isolation test, mirroring every other slice in this track) and must state
  this explicitly as a reviewed obligation, not leave it implicit.

The cost of the ordering itself, independent of the two gaps above: if step 4
or anything after it fails, the day's authorization is already spent with no
proof successfully used -- consistent with this project's established
fail-closed, no-retry philosophy (prefer wasting a day's authorization over
any risk of a second issuance).

### 10.4 What remains for the future implementation step

This section is design only. Implementing it requires its own new AGENTS.md
exception (mirroring the pattern of every prior implementation step in this
track), and must additionally:

- §9.2 item 3 (canonical authorization-artifact directory confirmed local and
  unsynced) is now resolved -- see §9.3's 2026-07-24 update. What remains: add
  a real adversarial concurrency test of the consume-then-mint sequence
  specifically -- true concurrent processes racing the new function, not
  sequential repeated calls -- before §10.3's race-safety claim is treated as
  proven rather than designed.
- **Structurally block the bypass path named in §10.3**: the unattended
  orchestration module must never import `confirm_v4_major_incident_resume_exact`
  or `confirm_v4_current_turn_exact` directly, and this must be enforced by
  its own import-graph isolation test (mirroring every other slice), not left
  as a documentation-only convention.
- Add fake-only tests proving the ordering in §10.3 -- especially that a
  second call within the same JST day, and concurrent calls, never mint a
  second proof pair, using fake stores/paths exactly as every other slice in
  this track has done.
- Pin the canonical authorization-artifact path via
  `v4_unattended_live_daily_authorization_path` (§9.3) inside the new
  constructor itself, rather than accepting an arbitrary caller-supplied
  path -- satisfying §9.2 item 2 at the point where it matters most (the
  actual consume call), not only at the CLI's write side.
- Prove import-graph isolation still holds for real transport/credential/
  broker-write surfaces (this addition only reaches local state stores, never
  network/Keychain/broker code).
- Not wire the new constructor into any real coordinator, transport, or
  runtime state root -- that remains a separate, later, explicitly authorized
  step per §9.2 and §8.

### 10.5 Implementation status (2026-07-24, fake-only, unwired)

`confirm_v4_unattended_authorization_once` is implemented in
`v4_gmo_canary_activation.py`, under its own AGENTS.md exception ("H-11 v4
unattended proof constructor 実装限定例外（唯一のG012/G013コード追記・未結線）").
It is the single new function added to that file; the diff against the four
pre-existing G012/G013 functions there
(`confirm_v4_major_incident_resume_exact`, `confirm_v4_current_turn_exact`,
`issue_v4_gmo_actual_activation_permit`, `consume_v4_gmo_actual_activation_permit`)
is empty -- the only removed line across the whole file is the old
single-line import statement, expanded to add `v4_gmo_trading_day_jst`.
`grep` across the repo confirms zero production callers; it is reachable
only from its own test file today.

§10.3/§10.4's first outstanding item is now resolved: a genuine
`threading.Barrier`-based concurrency test
(`test_concurrent_threads_racing_the_same_day_mint_exactly_one_proof_pair`,
`test_v4_gmo_canary_activation_unattended_fake_only.py`) races 8 threads
against the same shared authorization/risk/dead-man/heartbeat state and
asserts exactly one success, `worker_count - 1` failures, and exactly one
consumption marker on disk -- confirmed non-vacuous and stable across 15
repeated runs by an independent reviewer, who additionally probed it with 32
threads and an injected artificial delay inside the six-condition check to
widen the race window well beyond anything GIL scheduling alone could
produce, with the same result every time. The atomicity genuinely comes from
`consume_operator_daily_authorization_once`'s O_EXCL write, not from
timing luck.

§10.4's second item (structurally blocking the bypass path via import-graph
isolation) remains genuinely open, exactly as scoped: no orchestration module
exists yet for such a test to constrain, so today's only mitigation is the
function's own docstring warning plus a test asserting the docstring names
both bypassable functions and the word "bypass". This is accepted as correct
scoping for this step, not a gap in it -- the function is unreachable from
production code regardless, so there is no live exploit path yet. The future
wiring step must still add the import-graph isolation test before any
orchestration module is introduced.

**Independent review outcome and the fix it forced.** An adversarial Safety
review VETOED the first version of this function with one High finding,
since fixed and regression-pinned: `risk_store.load()` was called unwrapped,
unlike the two other external calls in the same function (`decide_unattended_permit_issuance`
and `consume_operator_daily_authorization_once`), which were already wrapped
to re-raise as this module's own `V4GmoCanaryActivationError`. A risk-state
file with a `policy_digest` that no longer matches the current
`PhaseBRiskPolicy` (realistic: a policy-constants change deployed without
migrating on-disk state, or corruption/tampering) let
`runtime_safety.H11AutoRuntimeSafetyError` propagate uncaught past this
module's boundary -- a contract-fidelity defect (a future caller catching
only this module's advertised error type would miss it), not a fund-safety
one, since the function still failed closed and minted no proof either way.
Fixed by wrapping `risk_store.load()` (re-raising
`V4_CANARY_UNATTENDED_RISK_STATE_INVALID`) and, defensively,
`check_operator_daily_authorization` (re-raising
`V4_CANARY_UNATTENDED_AUTHORIZATION_CHECK_INVALID`), matching the pattern
already used for the other two calls. Both fixes sit in the same execution
position as before the fix -- they translate exception types only, they do
not move any code across the consume-first ordering -- confirmed by the same
reviewer re-running the concurrency probes against the fixed code with no
change in outcome.

Additional test coverage added after the same review round: a non-`KILLED`
risk stop state (`STOPPED_DAILY_BUDGET`, reached via two accumulated
per-trade-bound losses) blocking exactly like `KILLED` does, confirming the
risk-gate veto is state-agnostic rather than special-cased; an
invalid-charset `entry_gate_blocked_reasons` string correctly wrapped as
`V4_CANARY_UNATTENDED_DECISION_INVALID` rather than leaking
`V4UnattendedLivePermitDecisionError`; and a wholly-missing (never-written)
heartbeat-chain file blocking, distinct from the already-covered
insufficient-continuity case. 25 tests total; full `h11_auto` suite passes
unchanged (761, up from 757 before this slice) alongside Ruff and a danger
scan for credential/transport/broker tokens.

## 11. Orchestration wiring — design (2026-07-24, design-only, no code)

§10.4's remaining bullet ("do not wire the new constructor into any real
coordinator, transport, or runtime state root") and §8's next-steps item 3
both name this as a separate, later, explicitly authorized step. This
section is that design, not that authorization.

### 11.1 What already exists and is reusable unchanged

The existing coordinator boundary is already exactly what this design needs,
and needs no new code to preserve:

- `v4_gmo_actual_coordinator.py`'s own docstring states its boundary: *"The
  coordinator stops before transport ... No credential, network client,
  activation permit, or broker method is imported here."* It only persists
  SQLite state (attempts, plans, pending-transport markers); it never calls
  a transport itself.
- One layer up, `V4GmoCoordinatedActualPath`
  (`h11_v4_gmo_coordinated_actual_path.py`) already has a **required,
  no-default** field `adapter: V4GmoActualAdapter`, and `V4GmoActualAdapter`
  (`h11_v4_gmo_actual_adapter.py`) already has a required, no-default field
  `transport: V4GmoPrivateTransport`. Neither type can be constructed without
  a caller supplying a concrete transport -- this is precisely the
  "required, no-default injection" convention this track has used everywhere
  else (Phase 1's `client` param, Phase 3 slice 1's `credential_pair`/
  `client`), already present in the existing coordinated-path code without
  any change needed.
- The existing, unmodified `issue_v4_gmo_actual_activation_permit`/
  `consume_v4_gmo_actual_activation_permit` (the two G012/G013 functions the
  proof constructor's output feeds) remain the only way to obtain/consume a
  `V4GmoActualActivationPermit`.

### 11.2 A real counterexample this design must not copy

`bind_v4_gmo_actual_runtime` (`h11_v4_gmo_actual_runtime_binding.py`) is the
function G013's interactive script actually calls to assemble a live-capable
runtime, and it **breaks** the "no defaults anywhere" assumption this track
otherwise relies on: `credential_pair: V4GmoSealedCredentialPair | None =
None` and `client: httpx.Client | None = None` both default to `None`, and a
`None` credential_pair is silently replaced with a real
`V4GmoKeychainCredentialPair()`. This function is reachable today only from
the human-interactive G013 script
(`backend/scripts/h11_auto_v4_g013_actual_canary.py`), which prompts the
operator via `getpass` with a 300-second fail-closed timeout -- not from any
fake-only/unattended-track module.

**This is a hard constraint on the new orchestration module's design, not
just a note**: it must never call `bind_v4_gmo_actual_runtime`, and its own
`adapter`/`transport`-equivalent parameter must have no default of any kind
-- neither a fake one nor one that silently resolves to something real. A
real activation continues to require a human to construct the real adapter
and pass it in explicitly, exactly as G013's script already does today; the
orchestration module's job is only to get from "six conditions verified" to
"permit obtained, ready to hand to *some* adapter," never further.

### 11.3 Correction: the existing end-to-end driver cannot simply be called with proofs

An earlier draft of this section assumed "wiring" would be a thin handoff:
mint proofs, call the existing single-call entry-cycle driver with them. That
assumption does not survive contact with the actual code and is corrected
here rather than carried forward silently.

`run_g013_actual_canary_after_exact_confirmation`
(`h11_v4_gmo_g013_canary.py:311-393`) already drives the *entire* sequence
end-to-end in one call -- `bind_v4_gmo_actual_runtime` →
`reconcile_once_fixed` → `record_canary_entry_preflight` →
`perform_market_once` → (conditional cancel/recover branch) →
`prepare_exact_protection_plan` → `perform_exact_protection_once` →
`confirm_exact_protection_once` → `run_until_flat()` monitoring handoff. This
is a real, complete, already-reviewed driver; nothing about the state
machine itself needs to be redesigned.

But its signature is `major_incident_resume_phrase: str,
current_turn_phrase: str` (lines 314-315), not proof objects -- it calls
`confirm_v4_major_incident_resume_exact`/`confirm_v4_current_turn_exact`
*itself*, internally, with those raw phrases (lines 323-331). There is no
version of this function that accepts an already-minted
`V4MajorIncidentResumeProof`/`V4CurrentTurnConfirmationProof` pair, which is
exactly what `confirm_v4_unattended_authorization_once` produces. The
unattended path cannot substitute a "phrase" for these proofs -- they are
different types entirely, and the two `confirm_v4_*_exact` functions
validate an actual human-typed phrase against a real secret constant, which
has no unattended equivalent.

### 11.4 The resulting fork -- an operator decision, not a default

Making unattended proofs actually drive this existing end-to-end sequence
requires one of two structurally different paths. Neither is a "just
proceed" continuation of this design; each has a real cost this document
should not minimize:

**Path 1 -- a second G013 code addition.** Add one more function next to
`run_g013_actual_canary_after_exact_confirmation` (or refactor its shared
body into a private helper both call) that accepts a pre-minted
`resume_proof`/`confirmation_proof` pair instead of phrases, then continues
identically into `_run_bound_g013_canary`. This keeps a single
implementation of the state machine (no duplicated logic to drift out of
sync) but directly contradicts this track's own repeated framing of the
proof constructor as *"本トラック全体で唯一のG012/G013コード変更"* (the
one and only G012/G013 code change in this entire track,
`AGENTS.md`'s proof-constructor exception, `v4_gmo_canary_activation.py`
diff). Reopening that boundary for a second addition is not something this
design chooses on its own; it would need its own fresh, explicit operator
authorization, separate from anything already granted.

**Path 2 -- an independent reimplementation.** A new, unattended-track-only
module calls `issue_v4_gmo_actual_activation_permit` directly with the
unattended proofs (never touching the two `confirm_v4_*_exact` phrase
functions), then `bind_v4_gmo_actual_runtime`, then re-drives its own copy
of the reconcile → preflight → market → cancel/recover → protect → confirm →
monitor sequence by calling the same lower-level `V4GmoCoordinatedActualPath`
methods `_run_bound_g013_canary` already calls. This never modifies any
existing G012/G013 file, but it duplicates roughly 300 lines of
extremely safety-critical sequencing logic into a second, independently
written and independently reviewed implementation -- introducing exactly
the kind of two-implementations-can-silently-diverge risk this project has
otherwise avoided everywhere else by reusing components verbatim rather
than re-deriving them.

Both paths are more work, and carry a different kind of risk, than the
"thin handoff" this section originally assumed. This document does not pick
between them -- the choice belongs to the operator, mirroring how the
1-day authorization window (§3.4) and the scheduler shape (§12) were
decided rather than assumed.

### 11.4a Operator decision (2026-07-24): Path 1

Path 1 is the direction to implement. This explicitly and knowingly
supersedes this track's prior framing of the proof constructor as
*"本トラック全体で唯一のG012/G013コード変更"* -- that framing is
retired by this decision, not silently contradicted. §11.4b below is the
concrete refactor plan this authorizes; it is scoped as narrowly as Path 1
allows.

### 11.4b Concrete refactor plan for Path 1

Read in full: `run_g013_actual_canary_after_exact_confirmation`
(`h11_v4_gmo_g013_canary.py:311-393`). Its structure splits cleanly:

- Lines 320-322: consume the session's one-use marker, verify exact session
  binding, refresh session evidence (clean-main + implementation/generation
  digest re-check). Identical regardless of how confirmation happens.
- Lines 323-331: the two phrase-based confirmations
  (`confirm_v4_major_incident_resume_exact`/`confirm_v4_current_turn_exact`),
  producing `resume`/`confirmation`. **This is the only part that differs
  between the phrase path and the proof path.**
- Lines 332-393: signal-postable re-check, monitor-heartbeat re-checks,
  cycle reservation, permit issuance (`issue_v4_gmo_actual_activation_permit`,
  unchanged, taking `resume`/`confirmation` positionally -- already
  proof-shaped, not phrase-shaped), `bind_v4_gmo_actual_runtime` (called
  **without** `credential_pair`/`client`, resolving to real Keychain by
  default -- the known counterexample from §11.2), then
  `_run_bound_g013_canary` (already fully generic on the resulting
  `binding`; confirmed by reading it in full that it never branches on how
  confirmation happened).

The refactor: extract lines 332-393 into a new private helper,
`_run_g013_actual_canary_from_refreshed_session(*, session, resume,
confirmation, on_protected, credential_pair, client)`, with one behavioral
change from today's inline code -- `bind_v4_gmo_actual_runtime` is called
with `credential_pair=credential_pair, client=client` passed through
explicitly, instead of omitted.

Two public functions call it:

```
def run_g013_actual_canary_after_exact_confirmation(
    *, session, major_incident_resume_phrase, current_turn_phrase, on_protected=None,
) -> V4GmoG013CanaryResult:
    session._use.consume_once()
    _require_exact_session_binding(session)
    session = _refresh_session_evidence_before_permit(session)
    resume = confirm_v4_major_incident_resume_exact(...)       # unchanged
    confirmation = confirm_v4_current_turn_exact(...)          # unchanged
    return _run_g013_actual_canary_from_refreshed_session(
        session=session, resume=resume, confirmation=confirmation,
        on_protected=on_protected, credential_pair=None, client=None,
    )

def run_g013_actual_canary_after_unattended_authorization(
    *, session, resume_proof, confirmation_proof, credential_pair, client, on_protected=None,
) -> V4GmoG013CanaryResult:
    session._use.consume_once()
    _require_exact_session_binding(session)
    session = _refresh_session_evidence_before_permit(session)
    return _run_g013_actual_canary_from_refreshed_session(
        session=session, resume=resume_proof, confirmation=confirmation_proof,
        on_protected=on_protected, credential_pair=credential_pair, client=client,
    )
```

Why this shape and not others:

- **The phrase-based function's behavior must be byte-identical, pinned by
  the full existing G013 test suite passing unchanged.** Passing
  `credential_pair=None, client=None` explicitly from it reproduces today's
  implicit omission exactly -- `bind_v4_gmo_actual_runtime`'s own
  `None`-defaulting logic (§11.2) is untouched and still applies only to
  this one, already-reviewed, human-interactive path.
- **The new function's `credential_pair`/`client` are required, no
  default -- ever.** This is the one property that must hold without
  exception: an unattended caller (now, and any future orchestration) must
  always supply them explicitly, exactly like every other injected
  dependency in this track (Phase 1's `client`, Phase 3 slice 1's
  `credential_pair`/`client`). There is no fake-default and no
  real-default; a caller that omits either gets a `TypeError` at the call
  site, not a silent real-Keychain resolution.
- **Session consume/binding/refresh is duplicated (3 lines) rather than
  folded into the shared helper.** The phrase path's confirm-calls need the
  *already-refreshed* session (they read `session.generation.digest`/
  `session.challenge`/`session.intent` post-refresh); duplicating three
  direct, non-branching calls is lower-risk than restructuring the
  refresh-then-confirm ordering to fit a callback shape.
- **`issue_v4_gmo_actual_activation_permit` and `_run_bound_g013_canary`
  are untouched, called identically from both paths.** Proof binding
  (`generation_digest`/`intent_digest` matching `session`) is enforced there
  exactly as today, regardless of which function produced the proofs.

This is now concrete enough to implement under its own new AGENTS.md
exception (§11.4a's decision recorded above); the exception must state the
above explicitly rather than treat this as an unscoped green light to
rewrite the module.

### 11.4c Implementation status (2026-07-24, second-ever G012/G013 change, unwired)

Implemented exactly per §11.4b, under AGENTS.md's "proof-accepting G013
entry-cycle driver 実装限定例外". `git diff --numstat` on
`h11_v4_gmo_g013_canary.py` shows 67 insertions, 0 deletions -- the
pre-existing function body was relocated into the new shared helper without
a single line altered, except the two new `credential_pair=`/`client=`
arguments added to the existing `bind_v4_gmo_actual_runtime` call. The full
pre-existing G013 test suite (40 tests across three files) passes unchanged,
which is the primary evidence that the human-interactive phrase path's
behavior did not change. 11 new tests pin: the new function's required,
no-default `credential_pair`/`client`; that both public functions dispatch
to the identical shared helper (proving one implementation, not two); that
the phrase path still passes `None`/`None` through to `bind_v4_gmo_actual_runtime`
explicitly (reproducing today's real-Keychain-default exactly); that the
new function passes its caller-supplied `credential_pair`/`client` through
unchanged; and that it has zero production callers today.

Two independent reviews (Safety; Architecture+Operations) returned PASS,
each after re-deriving the diff-minimality claim from `git diff` directly
rather than trusting this document, and after independently re-running the
full pre-existing G013 suite. Two findings from that round were fixed
before treating this slice as closed, both addressed in the shipped code
rather than deferred:

- **The "no silent real-Keychain fallback" guarantee was enforced only by
  an unchecked type hint.** Python does not stop a caller from writing
  `credential_pair=None`/`client=None` explicitly despite the hints not
  permitting `None` -- this is now also checked at runtime in
  `run_g013_actual_canary_after_unattended_authorization` itself, raising
  `G013_UNATTENDED_CREDENTIAL_OR_CLIENT_REQUIRED` fail-closed before doing
  anything else, matching this codebase's existing convention of
  runtime-checking beyond static type hints rather than trusting them alone.
- **The "no production callers" test had an AST blind spot for aliased
  imports** (`import ... as X`) and dynamic/string-based lookups. The
  alias case is now also checked (`ast.alias.name`/`asname`); the test's
  scope note now states plainly that string-based/dynamic lookups remain
  outside what it can catch, rather than implying broader coverage than it
  has.

72 tests total in the new-plus-fixed file's lineage (11 in the dedicated new
test file); full `h11_auto` suite: 772 passing (up from 761 before this
slice). Ruff clean; danger scan (credential/transport/scheduler tokens)
clean; `git status`/`git diff --stat` confirm only the one service file,
the new test file, `AGENTS.md`, and this design doc changed -- no other
G012/G013 file touched, matching the new exception's own claim exactly.

Remaining, still explicitly unauthorized: wiring
`run_g013_actual_canary_after_unattended_authorization` to anything that
actually calls it (an orchestration module still does not exist), the
scheduler (§12), and real Keychain/credential construction -- all separate,
later steps per §6/§8/§11.5 below.

### 11.5 Scope boundary for the eventual implementation step

Everything below must remain true of the *implementation*, not just this
design, mirroring exactly the boundary the proof-constructor exception
already enforces on itself. Note that §11.3/§11.4's correction changes what
"no import of `bind_v4_gmo_actual_runtime`" can mean -- Path 2 necessarily
calls it (that is the whole point of not touching G013 code), so the
constraint below is restated precisely rather than as a blanket ban:

- No default for the adapter/transport/credential parameter anywhere in the
  new module or anything it constructs -- ever, fake or real. If Path 2 is
  chosen and the new module itself calls `bind_v4_gmo_actual_runtime`, it
  must pass `credential_pair`/`client` explicitly (never rely on that
  function's own `None`-defaulting-to-real-Keychain behavior, §11.2).
  `V4GmoKeychainCredentialPair`/`V4GmoHttpxPrivateTransport` construction
  itself remains something only a human-supplied value can trigger, not
  something the new module defaults to.
- Whichever path is chosen, `confirm_v4_major_incident_resume_exact`/
  `confirm_v4_current_turn_exact` (the phrase-based functions) must remain
  unreachable from the unattended path -- Path 1's new sibling function and
  Path 2's direct `issue_v4_gmo_actual_activation_permit` call both satisfy
  this; calling the phrase functions from anywhere in this module would not.
- No scheduler/cron/LaunchAgent/launchd/resident-process wiring -- that is
  §12's separate, still-unauthorized question.
- Its own import-graph isolation test, following every prior slice's
  pattern, checked against this module's own forbidden-fragment list
  (adjusted per path: Path 1 forbids nothing new since it's still one
  driver; Path 2's isolation test must instead prove it never imports the
  two phrase-confirmation functions, rather than banning
  `bind_v4_gmo_actual_runtime` outright).
- A new, separately named AGENTS.md exception before any of this is written
  -- and, if Path 1 is chosen, that exception must explicitly acknowledge
  and supersede the "唯一のG012/G013コード変更" framing rather than silently
  contradicting it -- following this same design → operator decision →
  implementation-exception → fake-only-tests → independent review → doc
  update → approved commit/push rhythm used for every prior slice.

## 12. Resident/scheduler supervisor — design options (2026-07-24, design-only, no code)

No document in this track commits to a shape for a *live-order-issuing*
scheduler; §6 and every exception's prohibited-list ban installing one
outright pending separate authorization. This section lays out the two
structural precedents already in this repo, since a genuinely new shape
would need its own justification.

### 12.1 Option A -- resident LaunchAgent, monitor-only (G012 precedent)

`v4_gmo_launchd.py` (`render_v4_gmo_monitor_launchagent`,
`install_and_restart_v4_gmo_monitor_launchagent`), installed via the
human-run `h11_auto_v4_install_monitor_launchagent.py`, is a real, already-
reviewed resident daemon. Its result type fixes `heartbeat_broker_write:
bool` to always `False` in practice -- it is a monitor/heartbeat-only
daemon, never an order-placing one. Its cold-start/heartbeat-timing
behavior received its own independent review and fix (documented in
`docs/H11_V4_G013_CANARY_ACTIVATION_REPORT_20260717.md`).

If reused as a precedent for the unattended path, the daemon itself would
still never call `run_unattended_live_entry_attempt` (§11) directly --
it would only maintain the dead-man heartbeat / notification-check loop,
with actual entry evaluation staying a separate, human- or bounded-runner-
triggered action. This keeps a resident process's blast radius to
"can go stale and trip the dead-man gate," never "can place an order."

### 12.2 Option B -- bounded runner, no residency (Phase 1 precedent)

Phase 1's shadow runner (`h11_auto_v4_unattended_shadow_run.py`) is the
opposite shape: `--max-cycles`/`--interval-seconds`, never resident, no
auto-restart, invoked fresh each time (by a human, or by an external,
out-of-scope-here trigger). Applied to the live path, each invocation would
call `run_unattended_live_entry_attempt` at most once (the daily
authorization cap already enforces this even if invoked more than once) and
exit -- no daemon exists to go stale, be compromised, or drift from its
reviewed state.

### 12.3 Open question for the operator

Both keep the actual order-placing decision inside the already-reviewed,
fail-closed evaluation chain; they differ only in what triggers that
evaluation. Option A adds real residency (a long-lived process, its own
crash/restart surface, and the precedent that this project has already
independently reviewed once for G012) but keeps a live heartbeat warmer than
manual invocation allows. Option B adds no new operational surface at all
but means unattended really means "runs only when something outside this
design invokes it," which raises the question of what that external
trigger would be. This document does not choose between them; the operator
decision belongs in §3.4-style notes once made, mirroring how the 1-day
authorization window and cold-start acceptance were recorded there.

### 12.4 Operator decision (2026-07-24)

Option B (bounded runner, no residency) is the direction to continue
exploring. No new resident process is authorized by this decision -- it
only sets which shape a future, separately authorized scheduler
implementation step should target if and when that step is requested.
