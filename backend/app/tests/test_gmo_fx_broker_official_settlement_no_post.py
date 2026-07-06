"""No-POST tests for GmoFxBroker.official_settlement_order() and the
settlement side provenance gate.

official_settlement_order() is a dedicated, size-based settlement skeleton
separate from market_order(): it never places a fresh order in a reverse
direction and calls that a close, it uses the pure official settlement
builder (never the entry builder), and it must pass the settlement side
provenance gate before a request plan is even built, then the shared
real-broker-post hard guard before any transport could be attempted. No
production caller sets allow_real_broker_post=True, and no real HTTP
transport is implemented yet.
"""

from __future__ import annotations

import inspect
import pathlib

import httpx
import pytest

from app.brokers.gmo_fx_broker import (
    ENTRY_SIDE_SAFE_LABEL_BUY,
    ENTRY_SIDE_SAFE_LABEL_SELL,
    GmoFxBroker,
    GmoFxBrokerError,
    GmoFxSettlementSideProvenanceStatus,
    derive_settlement_side_from_entry_side_safe_label,
)
from app.config import Settings

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "brokers" / "gmo_fx_broker.py"

FORBIDDEN_SENTINELS = (
    "RAW_RESPONSE_SHOULD_NOT_SURFACE",
    "BROKER_RESPONSE_SHOULD_NOT_SURFACE",
    "ACCOUNT_ID_SHOULD_NOT_SURFACE",
    "ORDER_ID_SHOULD_NOT_SURFACE",
    "POSITION_ID_SHOULD_NOT_SURFACE",
    "TRADE_ID_SHOULD_NOT_SURFACE",
    "QUANTITY_VALUE_SHOULD_NOT_SURFACE",
    "PRICE_VALUE_SHOULD_NOT_SURFACE",
    "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE",
    "SIGNATURE_VALUE_SHOULD_NOT_SURFACE",
    "HEADERS_VALUE_SHOULD_NOT_SURFACE",
)


def _settings() -> Settings:
    return Settings(_env_file=None, gmo_fx_max_units=100)


def _refusing_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError(
            "official_settlement_order must never perform any HTTP request"
        )

    return httpx.Client(
        base_url="https://forex-api.coin.z.com/public",
        transport=httpx.MockTransport(handler),
    )


# --- side provenance gate ----------------------------------------------------


def test_provenance_blocked_when_entry_side_missing() -> None:
    result = derive_settlement_side_from_entry_side_safe_label(None)
    assert result.settlement_side_ready is False
    assert result.status is GmoFxSettlementSideProvenanceStatus.BLOCKED_MISSING_ENTRY_SIDE
    assert result.settlement_side_safe_label is None
    assert result.codex_inferred_settlement_side is False


def test_provenance_blocked_when_entry_side_unknown() -> None:
    result = derive_settlement_side_from_entry_side_safe_label("HOLD")
    assert result.settlement_side_ready is False
    assert result.status is GmoFxSettlementSideProvenanceStatus.BLOCKED_UNKNOWN_ENTRY_SIDE
    assert result.settlement_side_safe_label is None


@pytest.mark.parametrize(
    ("entry_label", "expected_settlement_side"),
    [
        (ENTRY_SIDE_SAFE_LABEL_BUY, "SELL"),
        (ENTRY_SIDE_SAFE_LABEL_SELL, "BUY"),
    ],
)
def test_provenance_derives_from_entry_safe_label_only(
    entry_label: str, expected_settlement_side: str,
) -> None:
    result = derive_settlement_side_from_entry_side_safe_label(entry_label)
    assert result.settlement_side_ready is True
    assert result.status is GmoFxSettlementSideProvenanceStatus.DERIVED_FROM_ENTRY_SAFE_LABEL
    assert result.settlement_side_safe_label == expected_settlement_side
    assert result.settlement_side_source_safe_label == "SETTLEMENT_SIDE_FROM_ENTRY_SAFE_LABEL"
    assert result.codex_inferred_settlement_side is False


def test_provenance_does_not_carry_ids_or_confirm_official_docs_semantics() -> None:
    result = derive_settlement_side_from_entry_side_safe_label(ENTRY_SIDE_SAFE_LABEL_BUY)
    # This Step never independently verifies the mapping against GMO's
    # official closeOrder docs -- it stays False until a human does that.
    assert result.settlement_side_official_docs_semantics_confirmed is False
    rendered = repr(result)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in rendered


# --- broker method ------------------------------------------------------------


def test_official_settlement_order_exists() -> None:
    assert hasattr(GmoFxBroker, "official_settlement_order")
    assert callable(GmoFxBroker.official_settlement_order)


def test_official_settlement_blocked_without_entry_side_makes_no_http_call() -> None:
    broker = GmoFxBroker(_settings(), client=_refusing_client())
    with pytest.raises(GmoFxBrokerError, match="side"):
        broker.official_settlement_order(
            symbol="USD_JPY", entry_side_safe_label=None, size=100,
        )


def test_official_settlement_blocked_with_unknown_entry_side() -> None:
    broker = GmoFxBroker(_settings(), client=_refusing_client())
    with pytest.raises(GmoFxBrokerError, match="side"):
        broker.official_settlement_order(
            symbol="USD_JPY", entry_side_safe_label="UNKNOWN", size=100,
        )


def test_official_settlement_denied_by_default_hard_guard_makes_no_http_call() -> None:
    broker = GmoFxBroker(_settings(), client=_refusing_client())
    with pytest.raises(GmoFxBrokerError, match="hard guard"):
        broker.official_settlement_order(
            symbol="USD_JPY",
            entry_side_safe_label=ENTRY_SIDE_SAFE_LABEL_BUY,
            size=100,
        )


def test_official_settlement_allow_true_still_stops_at_missing_transport() -> None:
    broker = GmoFxBroker(_settings(), client=_refusing_client(), allow_real_broker_post=True)
    with pytest.raises(GmoFxBrokerError, match="not implemented"):
        broker.official_settlement_order(
            symbol="USD_JPY",
            entry_side_safe_label=ENTRY_SIDE_SAFE_LABEL_SELL,
            size=100,
        )


def test_official_settlement_uses_settlement_builder_not_entry_builder() -> None:
    import app.brokers.gmo_fx_broker as gmo_fx_broker_module

    entry_calls: list[str] = []
    settlement_calls: list[str] = []
    original_entry = gmo_fx_broker_module.build_gmo_fx_entry_request_plan
    original_settlement = gmo_fx_broker_module.build_gmo_fx_official_settlement_request_plan

    def entry_spy(*args: object, **kwargs: object):
        entry_calls.append("entry_builder_called")
        return original_entry(*args, **kwargs)

    def settlement_spy(*args: object, **kwargs: object):
        settlement_calls.append("settlement_builder_called")
        return original_settlement(*args, **kwargs)

    gmo_fx_broker_module.build_gmo_fx_entry_request_plan = entry_spy
    gmo_fx_broker_module.build_gmo_fx_official_settlement_request_plan = settlement_spy
    try:
        broker = GmoFxBroker(_settings(), client=_refusing_client())
        with pytest.raises(GmoFxBrokerError):
            broker.official_settlement_order(
                symbol="USD_JPY",
                entry_side_safe_label=ENTRY_SIDE_SAFE_LABEL_BUY,
                size=100,
            )
    finally:
        gmo_fx_broker_module.build_gmo_fx_entry_request_plan = original_entry
        gmo_fx_broker_module.build_gmo_fx_official_settlement_request_plan = (
            original_settlement
        )

    assert settlement_calls == ["settlement_builder_called"]
    assert entry_calls == []


def test_official_settlement_never_calls_market_order() -> None:
    import app.brokers.gmo_fx_broker as gmo_fx_broker_module

    original_market_order = gmo_fx_broker_module.GmoFxBroker.market_order
    called = []

    def spy(self, *args: object, **kwargs: object):
        called.append("market_order_called")
        return original_market_order(self, *args, **kwargs)

    gmo_fx_broker_module.GmoFxBroker.market_order = spy
    try:
        broker = GmoFxBroker(_settings(), client=_refusing_client())
        with pytest.raises(GmoFxBrokerError):
            broker.official_settlement_order(
                symbol="USD_JPY",
                entry_side_safe_label=ENTRY_SIDE_SAFE_LABEL_BUY,
                size=100,
            )
    finally:
        gmo_fx_broker_module.GmoFxBroker.market_order = original_market_order

    assert called == []


def test_official_settlement_method_does_not_reference_generic_close_or_position_id() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    method_source = text[text.index("def official_settlement_order") :]
    forbidden_terms = ("opposite", "position_id", "generic_close")
    for term in forbidden_terms:
        assert term.lower() not in method_source.lower()
    assert "position_specific_settlement_id" not in method_source


def test_official_settlement_signature_never_accepts_credential_parameters() -> None:
    signature = inspect.signature(GmoFxBroker.official_settlement_order)
    forbidden_names = {"api_key", "api_secret", "credential", "credentials", "signature"}
    overlap = set(signature.parameters) & forbidden_names
    assert overlap == set()


def test_official_settlement_error_messages_never_expose_sentinel_values() -> None:
    broker = GmoFxBroker(_settings(), client=_refusing_client())
    with pytest.raises(GmoFxBrokerError) as exc_info:
        broker.official_settlement_order(
            symbol="USD_JPY",
            entry_side_safe_label="POSITION_ID_SHOULD_NOT_SURFACE",
            size=100,
        )
    rendered = str(exc_info.value)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in rendered


def test_module_still_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_still_has_no_production_allow_true_wiring() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text


def test_module_does_not_read_env_or_call_http_client_directly() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "load_dotenv" not in text
