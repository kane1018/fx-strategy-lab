"""Incident-response regression guard: Step 6G controlled/safe modules must
never reach a real network call.

Context: an audit found that `app.live_verification.live_order_once` and a
small number of "*_controlled.py" modules contain genuine httpx-based HTTP
POST capability toward real GMO FX endpoints, while the rest of the Step 6G
"controlled"/"safe" family are pure dataclass simulations with no I/O. This
test enumerates every module in `app.live_verification`, calls every public
`build_*` / `render_*` / `construct_*` / `make_*` function that accepts zero
required arguments, and fails loudly if any of them ever triggers a real
`httpx.Client` network call. It does not perform any real POST, does not
read credentials or `.env`, and does not inspect ledger file contents.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import httpx
import pytest

import app.live_verification as live_verification_package

_NETWORK_SENTINEL_MESSAGE = "NETWORK_CALL_BLOCKED_IN_TEST"


class _NetworkCallAttempted(RuntimeError):
    pass


def _block_network(*_args: object, **_kwargs: object) -> None:
    raise _NetworkCallAttempted(_NETWORK_SENTINEL_MESSAGE)


def _discover_modules() -> list[str]:
    package_path = live_verification_package.__path__
    prefix = live_verification_package.__name__ + "."
    names = [
        module_info.name
        for module_info in pkgutil.iter_modules(package_path, prefix)
        if not module_info.ispkg
    ]
    return sorted(names)


def _zero_arg_candidates(module: object) -> list[tuple[str, object]]:
    candidates = []
    for name, member in vars(module).items():
        if not inspect.isfunction(member):
            continue
        if not (
            name.startswith("build_")
            or name.startswith("render_")
            or name.startswith("construct_")
            or name.startswith("make_")
            or name.startswith("execute_")
        ):
            continue
        try:
            signature = inspect.signature(member)
        except (TypeError, ValueError):
            continue
        required = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.default is inspect.Parameter.empty
            and parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        ]
        if required:
            continue
        candidates.append((name, member))
    return candidates


def test_no_controlled_or_simulation_module_reaches_real_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx.Client, "send", _block_network, raising=True)
    monkeypatch.setattr(httpx.Client, "request", _block_network, raising=True)
    monkeypatch.setattr(httpx.Client, "post", _block_network, raising=True)

    module_names = _discover_modules()
    assert len(module_names) > 100, "expected the full live_verification module set"

    network_attempts: list[str] = []
    exercised_functions = 0

    for module_name in module_names:
        module = importlib.import_module(module_name)
        for func_name, func in _zero_arg_candidates(module):
            exercised_functions += 1
            try:
                func()
            except _NetworkCallAttempted:
                network_attempts.append(f"{module_name}.{func_name}")
            except Exception:
                # Any non-network failure (validation errors, missing
                # optional runtime, etc.) is out of scope for this guard.
                continue

    assert exercised_functions > 0, "no zero-arg safe entrypoints were discovered"
    assert network_attempts == [], (
        "Step 6G safe/controlled entrypoints must never reach a real "
        f"network call by default; offending entrypoints: {network_attempts}"
    )


def test_known_real_post_capable_entrypoints_require_explicit_dangerous_args() -> None:
    """Document + pin the exact functions capable of a real broker POST.

    Each of these must remain unreachable with zero arguments (i.e. they are
    not part of the `_zero_arg_candidates` sweep above), and must require an
    explicit transport/credential/allow flag supplied by the caller.
    """
    from app.live_verification.live_order_once import execute_one_shot_live_order

    signature = inspect.signature(execute_one_shot_live_order)
    required_params = {
        name
        for name, parameter in signature.parameters.items()
        if parameter.default is inspect.Parameter.empty
    }
    assert required_params == {
        "gate",
        "approval_phrase",
        "ledger_path",
        "api_key",
        "api_secret",
        "timestamp_factory",
    }
    assert signature.parameters["allow_live_http_post"].default is False
    assert signature.parameters["transport"].default is None

    from app.live_verification.live_order_real_official_settlement_actual_transport_no_post_controlled import (  # noqa: E501
        OfficialSettlementActualTransportHttpxClient,
    )

    init_signature = inspect.signature(OfficialSettlementActualTransportHttpxClient.__init__)
    init_required = {
        name
        for name, parameter in init_signature.parameters.items()
        if name != "self" and parameter.default is inspect.Parameter.empty
    }
    assert init_required == {"api_key", "api_secret", "timestamp_factory"}

    from app.live_verification.live_order_real_one_shot_post_real_delegate_controlled import (
        LiveOrderRealOneShotPostTransportInput,
        make_live_order_real_one_shot_post_real_delegate,
    )

    delegate_signature = inspect.signature(make_live_order_real_one_shot_post_real_delegate)
    assert all(
        parameter.default is None
        for parameter in delegate_signature.parameters.values()
    )
    runner_signature = inspect.signature(
        make_live_order_real_one_shot_post_real_delegate()
    )
    runner_required = {
        name
        for name, parameter in runner_signature.parameters.items()
        if parameter.default is inspect.Parameter.empty
    }
    assert runner_required == {"input_snapshot"}, (
        "the materialized real-post delegate runner must still require an "
        "explicit input_snapshot; it must never be callable with zero args"
    )
    assert set(LiveOrderRealOneShotPostTransportInput.__init__.__annotations__) - {
        "return"
    }, "transport input schema must declare fields (sanity check only)"


def test_real_delegate_fails_closed_without_env_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no GMO_FX_API_KEY/SECRET in the environment, the materialized
    real-post delegate must raise a safe validation error before ever
    constructing a request or touching the network — never silently proceed.
    """
    monkeypatch.setattr(httpx.Client, "send", _block_network, raising=True)
    monkeypatch.setattr(httpx.Client, "request", _block_network, raising=True)
    monkeypatch.setattr(httpx.Client, "post", _block_network, raising=True)
    monkeypatch.delenv("GMO_FX_API_KEY", raising=False)
    monkeypatch.delenv("GMO_FX_API_SECRET", raising=False)

    from app.live_verification.live_order_real_one_shot_post_real_delegate_controlled import (
        LiveOrderRealOneShotPostTransportInput,
        make_live_order_real_one_shot_post_real_delegate,
    )

    runner = make_live_order_real_one_shot_post_real_delegate()
    input_snapshot = LiveOrderRealOneShotPostTransportInput(
        execution_step="test_only",
        symbol="USD_JPY",
        side="BUY",
        order_type="MARKET",
        size=100,
        time_in_force_label="test_only",
        environment_label="test_only",
        risk_label="test_only",
        one_post_max=True,
        retry_allowed=False,
        timeout_fail_closed=True,
    )
    result = runner(input_snapshot)
    assert not getattr(result, "http_post_executed", False)
    assert not getattr(result, "network_transport_used", False)


def test_shared_hard_guard_denies_everything_except_literal_true() -> None:
    from app.live_verification.real_broker_post_hard_guard import (
        RealBrokerPostHardGuardError,
        assert_real_broker_post_allowed,
    )

    for denied_value in (False, None, 0, 1, "true", "True", "yes"):
        with pytest.raises(RealBrokerPostHardGuardError):
            assert_real_broker_post_allowed(allow=denied_value)

    result = assert_real_broker_post_allowed(allow=True)
    assert result.allowed is True


def test_official_settlement_actual_transport_hard_guard_denies_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.live_verification.live_order_real_official_settlement_actual_transport_no_post_controlled import (  # noqa: E501
        OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_BLOCKED_RESULT,
        OfficialSettlementActualTransportHttpxClient,
        build_official_settlement_actual_transport_no_post_controlled,
    )

    monkeypatch.setattr(httpx.Client, "send", _block_network, raising=True)
    monkeypatch.setattr(httpx.Client, "request", _block_network, raising=True)
    monkeypatch.setattr(httpx.Client, "post", _block_network, raising=True)

    plan = build_official_settlement_actual_transport_no_post_controlled().actual_transport_plan
    assert plan is not None

    client = OfficialSettlementActualTransportHttpxClient(
        api_key="unused-in-denied-path",
        api_secret="unused-in-denied-path",
        timestamp_factory=lambda: "1700000000000",
    )

    for denied_kwargs in ({}, {"allow_real_broker_post": False}, {"allow_real_broker_post": None}):
        result = client.send_official_settlement(plan=plan, **denied_kwargs)
        assert result.sanitized_result_category == (
            OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_BLOCKED_RESULT
        )
        assert result.real_http_client_call_count == 0
        assert result.actual_transport_real_http_post_executed is False
        assert result.actual_transport_broker_write_executed is False

    # With explicit allow=True the guard opens, so code proceeds to the real
    # httpx.Client boundary — which this test blocks via monkeypatch, proving
    # the guard (not a network failure) is what stopped the denied cases above.
    with pytest.raises(_NetworkCallAttempted):
        client.send_official_settlement(plan=plan, allow_real_broker_post=True)


def test_live_verification_real_post_call_sites_are_all_hard_guarded() -> None:
    """Source scan: any live_verification file with an httpx .post( call must
    reference the shared hard guard. Fails if a future module adds an
    unguarded real POST call site.
    """
    import pathlib

    live_verification_dir = pathlib.Path(live_verification_package.__file__).parent
    offenders = []
    for path in sorted(live_verification_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        if ".post(" in text and "real_broker_post_hard_guard" not in text:
            offenders.append(path.name)
    assert offenders == [], (
        "found live_verification files with an unguarded .post( call site: "
        f"{offenders}"
    )
