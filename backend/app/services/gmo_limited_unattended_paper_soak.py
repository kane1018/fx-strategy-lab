"""Limited unattended paper soak orchestrator (synthetic only, no-POST).

Runs a bounded, deterministic, immediate (no waiting loops, no daemon, no
cron, no scheduler) paper soak on top of the existing readiness pieces:

- the fixed 21-scenario readiness suite, plus
- a deterministic mixed batch that repeats the scenario families until the
  planned synthetic cycle count is reached.

Everything stays inside the paper/fake/synthetic boundary of the underlying
modules: fake transports only, in-memory fake notifier only, safe paper
attempt ledger only. The report carries safe counts / safe categories only
and validates the soak invariants (one paper entry and one paper settlement
maximum per cycle, no retry on any outcome, duplicates blocked).

A passed soak is a PAPER result: it is never a live-performance claim, never
a POST permission, and never "unattended live completed".
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.services.gmo_paper_auto_cycle_runner import AutoPreviewSignal
from app.services.gmo_supervised_auto_live_preview import (
    GmoAutoTrendSafeLabel,
    SupervisedAutoPreviewSafeInput,
    build_gmo_supervised_auto_live_preview,
)
from app.services.gmo_unattended_paper_soak_runner import (
    GmoPaperSoakScenarioOutcome,
    PaperSoakScenario,
    PaperSoakScenarioResult,
    build_default_paper_soak_scenario_suite,
    run_paper_soak_scenario,
)

LIMITED_SOAK_MODE_SAFE_LABEL = "SYNTHETIC_LIMITED_PAPER_SOAK"
LIMITED_SOAK_TRANSPORT_SAFE_LABEL = "FAKE_TRANSPORT_ONLY"
LIMITED_SOAK_NOTIFIER_SAFE_LABEL = "IN_MEMORY_FAKE_NOTIFIER_ONLY"
LIMITED_SOAK_RUNTIME_SAFE_LABEL = "NO_SLEEP_IMMEDIATE_SYNTHETIC"
LIMITED_SOAK_FIXTURE_SAFE_LABEL = "SAFE_SYNTHETIC_DETERMINISTIC"
LIMITED_SOAK_MIN_CYCLE_COUNT = 50


class GmoLimitedPaperSoakStatus(str, Enum):
    LIMITED_PAPER_SOAK_PASSED = "LIMITED_PAPER_SOAK_PASSED"
    LIMITED_PAPER_SOAK_FAILED_SAFE = "LIMITED_PAPER_SOAK_FAILED_SAFE"
    LIMITED_PAPER_SOAK_BLOCKED_SAFE = "LIMITED_PAPER_SOAK_BLOCKED_SAFE"


@dataclass(frozen=True)
class GmoLimitedPaperSoakPlan:
    """Fixed safe-label plan for one limited soak. Default values ARE the
    only supported values; validation blocks anything else fail-closed."""

    mode_safe_label: str = LIMITED_SOAK_MODE_SAFE_LABEL
    transport_safe_label: str = LIMITED_SOAK_TRANSPORT_SAFE_LABEL
    notifier_safe_label: str = LIMITED_SOAK_NOTIFIER_SAFE_LABEL
    runtime_safe_label: str = LIMITED_SOAK_RUNTIME_SAFE_LABEL
    deterministic_fixture_safe_label: str = LIMITED_SOAK_FIXTURE_SAFE_LABEL
    target_synthetic_cycle_count: int = 55
    max_paper_entry_attempt_per_cycle: int = 1
    max_paper_settlement_attempt_per_cycle: int = 1
    retry_within_cycle_allowed: bool = False
    halt_on_unknown: bool = True
    halt_on_rejected: bool = True
    halt_on_timeout: bool = True
    halt_on_guard: bool = True
    duplicate_attempt_block: bool = True
    illegal_transition_block: bool = True

    def __bool__(self) -> bool:
        return False


def validate_limited_paper_soak_plan(
    plan: GmoLimitedPaperSoakPlan,
) -> tuple[bool, tuple[str, ...]]:
    """Validate the plan fail-closed. Returns (ok, blocked_reasons)."""

    reasons: list[str] = []
    expected_labels = (
        ("mode_safe_label", LIMITED_SOAK_MODE_SAFE_LABEL),
        ("transport_safe_label", LIMITED_SOAK_TRANSPORT_SAFE_LABEL),
        ("notifier_safe_label", LIMITED_SOAK_NOTIFIER_SAFE_LABEL),
        ("runtime_safe_label", LIMITED_SOAK_RUNTIME_SAFE_LABEL),
        (
            "deterministic_fixture_safe_label",
            LIMITED_SOAK_FIXTURE_SAFE_LABEL,
        ),
    )
    for field_name, expected in expected_labels:
        if getattr(plan, field_name) != expected:
            reasons.append(f"PLAN_{field_name.upper()}_NOT_SUPPORTED")
    if plan.target_synthetic_cycle_count < LIMITED_SOAK_MIN_CYCLE_COUNT:
        reasons.append("PLAN_CYCLE_COUNT_BELOW_MINIMUM")
    if plan.max_paper_entry_attempt_per_cycle != 1:
        reasons.append("PLAN_ENTRY_ATTEMPT_MAX_NOT_ONE")
    if plan.max_paper_settlement_attempt_per_cycle != 1:
        reasons.append("PLAN_SETTLEMENT_ATTEMPT_MAX_NOT_ONE")
    if plan.retry_within_cycle_allowed:
        reasons.append("PLAN_RETRY_REQUESTED_BLOCKED")
    for flag_name in (
        "halt_on_unknown",
        "halt_on_rejected",
        "halt_on_timeout",
        "halt_on_guard",
        "duplicate_attempt_block",
        "illegal_transition_block",
    ):
        if not getattr(plan, flag_name):
            reasons.append(f"PLAN_{flag_name.upper()}_MUST_BE_TRUE")
    return (not reasons, tuple(reasons))


def build_limited_soak_scenario_batch(
    target_cycle_count: int,
) -> tuple[PaperSoakScenario, ...]:
    """Deterministically extend the readiness suite to the target count.

    The 21-family readiness suite always runs first; the remaining cycles
    repeat the families in a fixed order with a ``_MIX_<n>`` name suffix so
    every synthetic cycle stays uniquely identifiable and deterministic.
    """

    base = build_default_paper_soak_scenario_suite()
    batch: list[PaperSoakScenario] = list(base)
    index = 0
    while len(batch) < target_cycle_count:
        template = base[index % len(base)]
        batch.append(
            replace(
                template,
                scenario_name_safe_label=(
                    f"{template.scenario_name_safe_label}_MIX_{index:03d}"
                ),
            )
        )
        index += 1
    return tuple(batch)


def _distribution(labels: list[str]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return tuple(sorted(counts.items()))


@dataclass(frozen=True)
class GmoPreviewSignalObservation:
    """Safe-count observation of the supervised preview derivation."""

    preview_signal_distribution: tuple[tuple[str, int], ...]
    auto_preview_signal_is_operator_signal: bool = False
    any_preview_was_permission: bool = False

    def __bool__(self) -> bool:
        return False


def observe_preview_signal_distribution() -> GmoPreviewSignalObservation:
    """Derive preview signals over a fixed deterministic input grid.

    Observation only: counts per AUTO_PREVIEW_SIGNAL_* label, plus the fixed
    confirmation that no preview is an operator signal or a permission.
    """

    trends = (
        GmoAutoTrendSafeLabel.UPTREND,
        GmoAutoTrendSafeLabel.DOWNTREND,
        GmoAutoTrendSafeLabel.FLAT,
        GmoAutoTrendSafeLabel.UNKNOWN,
    )
    labels: list[str] = []
    any_operator_signal = False
    any_permission = False
    for trend in trends:
        for gates_safe in (True, False):
            package = build_gmo_supervised_auto_live_preview(
                SupervisedAutoPreviewSafeInput(
                    trend_safe_label=trend,
                    position_flat_safe=gates_safe,
                    market_open_safe=gates_safe,
                    ticker_fresh_safe=gates_safe,
                    spread_within_limit_safe=gates_safe,
                    active_pending_clear_safe=gates_safe,
                )
            )
            labels.append(package.auto_preview_signal.value)
            any_operator_signal |= package.auto_preview_signal_is_operator_signal
            any_permission |= (
                package.actual_entry_POST_allowed
                or package.actual_settlement_POST_allowed
            )
    return GmoPreviewSignalObservation(
        preview_signal_distribution=_distribution(labels),
        auto_preview_signal_is_operator_signal=any_operator_signal,
        any_preview_was_permission=any_permission,
    )


@dataclass(frozen=True)
class GmoLimitedPaperSoakReport:
    """Safe counts / safe categories only. Never truthy, never a permission."""

    status: GmoLimitedPaperSoakStatus
    plan: GmoLimitedPaperSoakPlan
    blocked_reasons: tuple[str, ...]
    synthetic_cycle_count: int
    matched_cycle_count: int
    mismatched_scenarios_safe: tuple[str, ...]
    outcome_distribution: tuple[tuple[str, int], ...]
    guard_halt_distribution: tuple[tuple[str, int], ...]
    terminal_state_distribution: tuple[tuple[str, int], ...]
    notification_distribution: tuple[tuple[str, int], ...]
    soak_signal_distribution: tuple[tuple[str, int], ...]
    preview_observation: GmoPreviewSignalObservation
    attempt_invariant_ok: bool
    no_retry_invariant_ok: bool
    duplicate_blocked_cycle_count: int
    max_entry_attempts_observed: int
    max_settlement_attempts_observed: int
    real_post_count: int = 0
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False
    broker_write_performed: bool = False
    real_http_performed: bool = False
    runtime_private_get_performed: bool = False
    credential_value_read: bool = False
    env_read_performed: bool = False
    raw_id_value_exposure: bool = False
    unattended_live_supported: bool = False
    unattended_full_auto_completed: bool = False
    live_performance_claim: bool = False

    def __bool__(self) -> bool:
        return False


def _blocked_report(
    plan: GmoLimitedPaperSoakPlan, reasons: tuple[str, ...]
) -> GmoLimitedPaperSoakReport:
    return GmoLimitedPaperSoakReport(
        status=GmoLimitedPaperSoakStatus.LIMITED_PAPER_SOAK_BLOCKED_SAFE,
        plan=plan,
        blocked_reasons=reasons,
        synthetic_cycle_count=0,
        matched_cycle_count=0,
        mismatched_scenarios_safe=(),
        outcome_distribution=(),
        guard_halt_distribution=(),
        terminal_state_distribution=(),
        notification_distribution=(),
        soak_signal_distribution=(),
        preview_observation=observe_preview_signal_distribution(),
        attempt_invariant_ok=False,
        no_retry_invariant_ok=False,
        duplicate_blocked_cycle_count=0,
        max_entry_attempts_observed=0,
        max_settlement_attempts_observed=0,
    )


def run_limited_unattended_paper_soak(
    plan: GmoLimitedPaperSoakPlan | None = None,
) -> GmoLimitedPaperSoakReport:
    """Run one bounded deterministic paper soak and classify the outcome.

    PASSED requires: plan valid, every synthetic cycle matched its expected
    safe outcome, the one-attempt-per-kind invariant held on every cycle,
    and no retry/repost/second-attempt flag was ever set.
    """

    soak_plan = plan if plan is not None else GmoLimitedPaperSoakPlan()
    plan_ok, plan_reasons = validate_limited_paper_soak_plan(soak_plan)
    if not plan_ok:
        return _blocked_report(soak_plan, plan_reasons)

    batch = build_limited_soak_scenario_batch(
        soak_plan.target_synthetic_cycle_count
    )
    results: list[PaperSoakScenarioResult] = [
        run_paper_soak_scenario(scenario) for scenario in batch
    ]

    mismatched = tuple(
        result.scenario_name_safe_label
        for result in results
        if not result.matched_expectation
    )
    attempt_invariant_ok = all(
        result.paper_entry_attempt_count
        <= soak_plan.max_paper_entry_attempt_per_cycle
        and result.paper_settlement_attempt_count
        <= soak_plan.max_paper_settlement_attempt_per_cycle
        for result in results
    )
    no_retry_invariant_ok = all(
        not (
            result.retry_performed
            or result.repost_performed
            or result.second_post_performed
        )
        for result in results
    )
    duplicate_blocked_cycles = sum(
        1
        for result in results
        if result.outcome
        is GmoPaperSoakScenarioOutcome.SCENARIO_DUPLICATE_BLOCKED_SAFE
    )

    guard_halts = [
        result.guard_decision_safe_label
        for result in results
        if result.outcome
        is GmoPaperSoakScenarioOutcome.SCENARIO_GUARD_HALTED_SAFE
    ]
    notifications: list[str] = []
    for result in results:
        notifications.extend(result.notifications_safe)

    passed = bool(
        not mismatched and attempt_invariant_ok and no_retry_invariant_ok
    )
    return GmoLimitedPaperSoakReport(
        status=(
            GmoLimitedPaperSoakStatus.LIMITED_PAPER_SOAK_PASSED
            if passed
            else GmoLimitedPaperSoakStatus.LIMITED_PAPER_SOAK_FAILED_SAFE
        ),
        plan=soak_plan,
        blocked_reasons=(),
        synthetic_cycle_count=len(results),
        matched_cycle_count=len(results) - len(mismatched),
        mismatched_scenarios_safe=mismatched,
        outcome_distribution=_distribution(
            [result.outcome.value for result in results]
        ),
        guard_halt_distribution=_distribution(guard_halts),
        terminal_state_distribution=_distribution(
            [result.final_state_safe_label for result in results]
        ),
        notification_distribution=_distribution(notifications),
        soak_signal_distribution=_distribution(
            [scenario.auto_preview_signal.value for scenario in batch]
        ),
        preview_observation=observe_preview_signal_distribution(),
        attempt_invariant_ok=attempt_invariant_ok,
        no_retry_invariant_ok=no_retry_invariant_ok,
        duplicate_blocked_cycle_count=duplicate_blocked_cycles,
        max_entry_attempts_observed=max(
            (result.paper_entry_attempt_count for result in results), default=0
        ),
        max_settlement_attempts_observed=max(
            (result.paper_settlement_attempt_count for result in results),
            default=0,
        ),
    )


# Re-exported for callers that only need the signal enum for observations.
__all__ = [
    "AutoPreviewSignal",
    "GmoLimitedPaperSoakPlan",
    "GmoLimitedPaperSoakReport",
    "GmoLimitedPaperSoakStatus",
    "GmoPreviewSignalObservation",
    "build_limited_soak_scenario_batch",
    "observe_preview_signal_distribution",
    "run_limited_unattended_paper_soak",
    "validate_limited_paper_soak_plan",
]
