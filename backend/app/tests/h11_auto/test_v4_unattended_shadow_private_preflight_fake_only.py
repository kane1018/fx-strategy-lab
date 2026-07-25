from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import httpx
import pytest

from app.h11_auto.v4_gmo_contracts import V4GmoPreflightSnapshot
from app.services import h11_v4_unattended_shadow_private_preflight as subject


@dataclass(frozen=True)
class _FakeCredentialPair:
    key: str = "synthetic-key"
    secret: str = "synthetic-secret"

    def unseal_for_internal_request_only(
        self,
    ) -> tuple[subject.V4UnattendedShadowSealedSecret, subject.V4UnattendedShadowSealedSecret]:
        return (
            subject.V4UnattendedShadowSealedSecret(self.key),
            subject.V4UnattendedShadowSealedSecret(self.secret),
        )


@dataclass
class _RaisingCredentialPair:
    def unseal_for_internal_request_only(self) -> tuple[object, object]:
        raise RuntimeError("synthetic keychain failure")


class _ManualClock:
    """Advances only via explicit .tick(); never auto-advances on its own.

    Pairing ``now`` with a ``sleep`` that calls ``.tick()`` simulates a working
    sleep; pairing it with a no-op ``sleep`` simulates an interrupted one that
    never advances the clock, so the cadence re-check must fail closed.
    """

    def __init__(self, *, start: float = 0.0) -> None:
        self._value = start

    def now(self) -> float:
        return self._value

    def tick(self, seconds: float) -> None:
        self._value += seconds


def _envelope(data: object) -> dict[str, object]:
    return {"status": 0, "data": data, "responsetime": "2026-07-24T00:00:00.000Z"}


def _rows(count: int) -> list[dict[str, str]]:
    return [{"symbol": "USD_JPY"} for _ in range(count)]


def _handler(*, latest: int, positions: int, active: int) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/latestExecutions"):
            return httpx.Response(200, json=_envelope(_rows(latest)))
        if path.endswith("/openPositions"):
            return httpx.Response(200, json=_envelope(_rows(positions)))
        if path.endswith("/activeOrders"):
            return httpx.Response(200, json=_envelope(_rows(active)))
        return httpx.Response(404, json=_envelope(None))

    return httpx.MockTransport(handle)


def _client(transport: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(base_url=subject.GMO_V4_PRIVATE_BASE_URL, transport=transport)


def _read(
    *,
    transport: httpx.MockTransport,
    credential_pair: object | None = None,
) -> subject.V4UnattendedShadowPrivateSnapshot:
    # A working sleep (clock.tick) genuinely exercises the sleep-then-recheck
    # cadence path on every call, not just a dedicated cadence test.
    clock = _ManualClock()
    return subject.read_v4_unattended_shadow_private_snapshot(
        credential_pair=credential_pair or _FakeCredentialPair(),
        client=_client(transport),
        monotonic_factory=clock.now,
        sleep=clock.tick,
    )


def test_flat_account_snapshot_is_derived_from_three_fake_gets() -> None:
    snapshot = _read(transport=_handler(latest=2, positions=0, active=0))
    assert snapshot.broker_get_count == 3
    assert snapshot.latest_executions_count == 2
    assert snapshot.open_positions_count == 0
    assert snapshot.active_orders_count == 0
    assert snapshot.account_flat is True
    assert snapshot.active_orders_zero is True
    assert snapshot.credential_read_performed is True
    assert snapshot.broker_read_performed is True
    assert snapshot.status == "SHADOW_PRIVATE_SNAPSHOT_OBSERVED"
    assert snapshot.raw_response_retained is False
    assert snapshot.identifier_exposed is False
    assert snapshot.broker_write_performed is False
    assert snapshot.broker_post_count == 0
    assert bool(snapshot) is False
    assert "sanitized" in repr(snapshot)
    assert snapshot.to_safe_dict()["open_positions_count"] == 0


def test_non_flat_and_active_order_counts_are_reported_honestly() -> None:
    snapshot = _read(transport=_handler(latest=5, positions=1, active=2))
    assert snapshot.open_positions_count == 1
    assert snapshot.active_orders_count == 2
    assert snapshot.account_flat is False
    assert snapshot.active_orders_zero is False


def test_empty_data_null_is_zero_rows() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope(None))

    snapshot = _read(transport=httpx.MockTransport(handle))
    assert snapshot.open_positions_count == 0
    assert snapshot.account_flat is True


def test_list_wrapped_data_shape_is_accepted() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_envelope({"list": _rows(3)}))

    snapshot = _read(transport=httpx.MockTransport(handle))
    assert snapshot.latest_executions_count == 3
    assert snapshot.open_positions_count == 3
    assert snapshot.active_orders_count == 3


def test_requests_are_issued_against_the_callers_own_client_base_url() -> None:
    # Regression test: the module must never hardcode or fall back to the
    # real GMO host. A caller-configured non-production base_url must be the
    # actual destination for every request, proven by inspecting each
    # request's resolved host inside the fake transport.
    seen_hosts: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen_hosts.append(request.url.host)
        path = request.url.path
        if path.endswith("/latestExecutions"):
            return httpx.Response(200, json=_envelope(_rows(0)))
        if path.endswith("/openPositions"):
            return httpx.Response(200, json=_envelope(_rows(0)))
        if path.endswith("/activeOrders"):
            return httpx.Response(200, json=_envelope(_rows(0)))
        return httpx.Response(404, json=_envelope(None))

    sandbox_client = httpx.Client(
        base_url="https://sandbox.invalid.example",
        transport=httpx.MockTransport(handle),
    )
    clock = _ManualClock()
    snapshot = subject.read_v4_unattended_shadow_private_snapshot(
        credential_pair=_FakeCredentialPair(),
        client=sandbox_client,
        monotonic_factory=clock.now,
        sleep=clock.tick,
    )
    assert bool(snapshot) is False
    assert seen_hosts == ["sandbox.invalid.example"] * 3
    assert "forex-api.coin.z.com" not in seen_hosts


def test_cadence_fails_closed_when_sleep_does_not_advance_the_clock() -> None:
    # If the requested sleep does not actually advance the clock (interrupted
    # sleep, broken clock, future implementer's mistake), the module must
    # refuse to fire the next signed request rather than silently proceeding
    # closer together than the fixed cadence requires.
    clock = _ManualClock()
    with pytest.raises(
        subject.V4UnattendedShadowPrivateError,
        match="SHADOW_PRIVATE_GET_CADENCE_NOT_REACHED",
    ):
        subject.read_v4_unattended_shadow_private_snapshot(
            credential_pair=_FakeCredentialPair(),
            client=_client(_handler(latest=0, positions=0, active=0)),
            monotonic_factory=clock.now,
            sleep=lambda _seconds: None,  # never advances the clock
        )


def test_cadence_sleep_is_invoked_with_the_expected_durations() -> None:
    clock = _ManualClock()
    requested_sleeps: list[float] = []

    def spying_sleep(seconds: float) -> None:
        requested_sleeps.append(seconds)
        clock.tick(seconds)

    subject.read_v4_unattended_shadow_private_snapshot(
        credential_pair=_FakeCredentialPair(),
        client=_client(_handler(latest=0, positions=0, active=0)),
        monotonic_factory=clock.now,
        sleep=spying_sleep,
    )
    # First request needs no wait (target_offset=0); the next two each wait
    # the fixed cadence since the clock only advances via sleep here.
    assert requested_sleeps == [
        subject._READ_CADENCE_SECONDS,
        subject._READ_CADENCE_SECONDS,
    ]


def test_non_finite_clock_is_fail_closed() -> None:
    with pytest.raises(
        subject.V4UnattendedShadowPrivateError,
        match="SHADOW_PRIVATE_GET_CADENCE_CLOCK_INVALID",
    ):
        subject.read_v4_unattended_shadow_private_snapshot(
            credential_pair=_FakeCredentialPair(),
            client=_client(_handler(latest=0, positions=0, active=0)),
            monotonic_factory=lambda: float("nan"),
            sleep=lambda _seconds: None,
        )


@pytest.mark.parametrize(
    ("status_code", "body", "match"),
    (
        (503, {"status": 0, "data": []}, "SHADOW_PRIVATE_GET_HTTP_FAILED_NO_RETRY"),
        (200, {"status": 1, "data": []}, "SHADOW_PRIVATE_GET_RESPONSE_REJECTED"),
        (200, {"status": 0, "data": "not-a-list"}, "SHADOW_PRIVATE_GET_SCHEMA_INVALID"),
        (200, {"status": 0, "data": ["not-a-row"]}, "SHADOW_PRIVATE_GET_ROW_INVALID"),
    ),
)
def test_malformed_or_failed_response_is_fail_closed_no_retry(
    status_code: int, body: dict[str, object], match: str
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    with pytest.raises(subject.V4UnattendedShadowPrivateError, match=match):
        _read(transport=httpx.MockTransport(handle))


def test_unparsable_json_body_is_fail_closed_and_does_not_leak_raw_body() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json-a{a")

    with pytest.raises(
        subject.V4UnattendedShadowPrivateError, match="SHADOW_PRIVATE_GET_RESPONSE_INVALID"
    ) as exc_info:
        _read(transport=httpx.MockTransport(handle))
    # The raw broker response body must never be reachable via the exception
    # chain (this module guarantees raw_response_retained=False).
    assert exc_info.value.__cause__ is None


def test_network_error_is_fail_closed_no_retry_and_does_not_leak_signed_headers() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic network failure", request=request)

    with pytest.raises(
        subject.V4UnattendedShadowPrivateError,
        match="SHADOW_PRIVATE_GET_NETWORK_FAILED_NO_RETRY",
    ) as exc_info:
        _read(transport=httpx.MockTransport(handle))
    # The failed request's headers carry the real signed API-KEY value; they
    # must never be reachable via the exception chain.
    assert exc_info.value.__cause__ is None


def test_duck_typed_non_conforming_credential_pair_is_refused() -> None:
    with pytest.raises(
        subject.V4UnattendedShadowPrivateError,
        match="SHADOW_PRIVATE_CREDENTIAL_CONTRACT_INVALID",
    ):
        _read(transport=_handler(latest=0, positions=0, active=0), credential_pair=object())


def test_credential_unseal_failure_is_sanitized() -> None:
    with pytest.raises(
        subject.V4UnattendedShadowPrivateError,
        match="SHADOW_PRIVATE_CREDENTIAL_UNAVAILABLE",
    ) as exc_info:
        _read(
            transport=_handler(latest=0, positions=0, active=0),
            credential_pair=_RaisingCredentialPair(),
        )
    # A real credential reader's failure message could embed diagnostic
    # detail (service/account names, partial values); it must never be
    # reachable via the exception chain.
    assert exc_info.value.__cause__ is None


def test_credential_pair_returning_wrong_secret_type_is_refused() -> None:
    @dataclass
    class _WrongTypeCredentialPair:
        def unseal_for_internal_request_only(self) -> tuple[str, str]:
            return "plain-key", "plain-secret"

    with pytest.raises(
        subject.V4UnattendedShadowPrivateError,
        match="SHADOW_PRIVATE_CREDENTIAL_CONTRACT_INVALID",
    ):
        _read(
            transport=_handler(latest=0, positions=0, active=0),
            credential_pair=_WrongTypeCredentialPair(),
        )


def test_sealed_secret_is_masked_and_falsey() -> None:
    secret = subject.V4UnattendedShadowSealedSecret("real-value")
    assert secret.reveal_internal_only() == "real-value"
    assert "real-value" not in repr(secret)
    assert "real-value" not in str(secret)
    assert bool(secret) is False


def test_snapshot_rejects_inconsistent_flat_or_zero_flags() -> None:
    base = _read(transport=_handler(latest=0, positions=0, active=0))
    with pytest.raises(
        subject.V4UnattendedShadowPrivateError, match="SHADOW_PRIVATE_SNAPSHOT_FLAT_MISMATCH"
    ):
        replace(base, account_flat=False)
    with pytest.raises(
        subject.V4UnattendedShadowPrivateError, match="SHADOW_PRIVATE_SNAPSHOT_ZERO_MISMATCH"
    ):
        replace(base, active_orders_zero=False)


def test_snapshot_rejects_claimed_write_activity() -> None:
    base = _read(transport=_handler(latest=0, positions=0, active=0))
    with pytest.raises(
        subject.V4UnattendedShadowPrivateError,
        match="SHADOW_PRIVATE_SNAPSHOT_CANNOT_CLAIM_WRITE",
    ):
        replace(base, broker_write_performed=True)
    with pytest.raises(
        subject.V4UnattendedShadowPrivateError,
        match="SHADOW_PRIVATE_SNAPSHOT_CANNOT_CLAIM_WRITE",
    ):
        replace(base, broker_post_count=1)


def test_snapshot_rejects_wrong_get_count() -> None:
    base = _read(transport=_handler(latest=0, positions=0, active=0))
    with pytest.raises(
        subject.V4UnattendedShadowPrivateError,
        match="SHADOW_PRIVATE_SNAPSHOT_GET_COUNT_INVALID",
    ):
        replace(base, broker_get_count=4)


def _base_preflight(**overrides: object) -> V4GmoPreflightSnapshot:
    values: dict[str, object] = {
        "boot_reconciled": False,
        "process_lock_held": True,
        "data_fresh": True,
        "clock_synchronized": True,
        "notification_path_ready": False,
        "broker_snapshot_fresh": False,
        "position_count": 1,
        "active_order_count": 1,
        "entries_today": 1,
    }
    values.update(overrides)
    return V4GmoPreflightSnapshot(**values)  # type: ignore[arg-type]


def test_composer_replaces_only_the_private_get_observable_fields() -> None:
    base = _base_preflight()
    private = _read(transport=_handler(latest=1, positions=1, active=2))
    composed = subject.augment_shadow_preflight_with_private_snapshot(
        base=base, private=private
    )
    assert composed.boot_reconciled is True
    assert composed.broker_snapshot_fresh is True
    assert composed.position_count == 1
    assert composed.active_order_count == 2
    # Everything else passes through from base untouched.
    assert composed.notification_path_ready is base.notification_path_ready
    assert composed.process_lock_held is base.process_lock_held
    assert composed.data_fresh is base.data_fresh
    assert composed.clock_synchronized is base.clock_synchronized
    assert composed.entries_today == base.entries_today
    assert composed.daily_stop_clear == base.daily_stop_clear
    assert composed.monthly_stop_clear == base.monthly_stop_clear
    assert composed.consecutive_loss_stop_clear == base.consecutive_loss_stop_clear
    assert composed.operator_halt_clear == base.operator_halt_clear


def test_composer_rejects_duck_typed_inputs() -> None:
    base = _base_preflight()
    private = _read(transport=_handler(latest=0, positions=0, active=0))
    with pytest.raises(
        subject.V4UnattendedShadowPrivateError, match="SHADOW_PRIVATE_COMPOSE_INPUT_INVALID"
    ):
        subject.augment_shadow_preflight_with_private_snapshot(
            base=cast(V4GmoPreflightSnapshot, SimpleNamespace()), private=private
        )
    with pytest.raises(
        subject.V4UnattendedShadowPrivateError, match="SHADOW_PRIVATE_COMPOSE_INPUT_INVALID"
    ):
        subject.augment_shadow_preflight_with_private_snapshot(
            base=base,
            private=cast(subject.V4UnattendedShadowPrivateSnapshot, SimpleNamespace()),
        )


def test_module_has_no_real_keychain_or_write_capable_source_tokens() -> None:
    # Code-identifier tokens only: the module docstring legitimately explains
    # what it excludes (it says "No real Keychain reader..."), so a plain
    # substring scan would false-positive on that prose. The import-graph test
    # below is the authoritative isolation guard.
    source = inspect.getsource(subject)
    for forbidden in (
        "subprocess",
        "keyring",
        "find-generic-password",
        "os.environ",
        "os.getenv",
        "load_dotenv",
        "cancelOrders",
        "closeOrder",
        '"/private/v1/order"',
        "smtplib",
        "V4ExternalPreparationGate",
        "V4PreparationOperationPermit",
        "activation_permit",
        "hard_guard",
    ):
        assert forbidden not in source, forbidden


def test_module_reachable_app_imports_avoid_gated_and_write_capable_modules() -> None:
    reachable = _reachable_app_modules(
        root_module="app.services.h11_v4_unattended_shadow_private_preflight",
        app_root=Path(subject.__file__).parents[1],
    )
    forbidden_fragments = (
        "actual",
        "canary",
        "readonly_preflight",
        "post_canary",
        "coordinator",
        "hard_guard",
        "launchd",
        "notification",
        "private_api.credentials",
        "h11_manual",
    )
    for module_name in reachable:
        for fragment in forbidden_fragments:
            assert fragment not in module_name, module_name


def _reachable_app_modules(*, root_module: str, app_root: Path) -> set[str]:
    pending = [root_module]
    visited: set[str] = set()
    while pending:
        module_name = pending.pop()
        if module_name in visited:
            continue
        module_path = _app_module_path(module_name=module_name, app_root=app_root)
        if module_path is None:
            continue
        visited.add(module_name)
        parts = module_name.split(".")
        pending.extend(".".join(parts[:length]) for length in range(1, len(parts)))
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
                "app."
            ):
                pending.append(node.module)
            elif isinstance(node, ast.Import):
                pending.extend(
                    alias.name
                    for alias in node.names
                    if alias.name == "app" or alias.name.startswith("app.")
                )
    return visited


def _app_module_path(*, module_name: str, app_root: Path) -> Path | None:
    relative = module_name.split(".")[1:]
    if not relative:
        return None
    base = app_root.joinpath(*relative)
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None
