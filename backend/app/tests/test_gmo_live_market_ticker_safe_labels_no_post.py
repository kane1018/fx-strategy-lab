"""No-POST tests for the market / ticker / spread safe labels.

These tests pin that the mapper is fail-closed (missing ticker, UNKNOWN,
STALE, CLOSED, and OUT_OF_LIMIT all block; only OPEN + FRESH + WITHIN_LIMIT
passes), that the input and result types structurally cannot carry a raw
bid/ask/price/spread/timestamp value, that results are never truthy, and
that the module has no HTTP/env surface. Only synthetic safe inputs are
used; no public GET is performed.
"""

from __future__ import annotations

import pathlib
from dataclasses import fields

import pytest

from app.services.gmo_live_market_ticker_safe_labels import (
    GmoMarketStatusSafeLabel,
    GmoSpreadStatusSafeLabel,
    GmoTickerFreshnessSafeLabel,
    MarketTickerSafeInput,
    MarketTickerSafeResult,
    evaluate_market_ticker_safe_labels,
)
from app.services.gmo_live_runtime_safe_read import (
    GmoRuntimeMarketSafeStatus,
    GmoRuntimeSafeReadSnapshot,
    GmoRuntimeSpreadSafeStatus,
    GmoRuntimeTickerFreshnessSafeStatus,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_market_ticker_safe_labels.py"
)


def _all_safe_input(**overrides: object) -> MarketTickerSafeInput:
    base = dict(
        ticker_present=True,
        market_status=GmoRuntimeMarketSafeStatus.OPEN,
        ticker_status=GmoRuntimeTickerFreshnessSafeStatus.FRESH,
        spread_status=GmoRuntimeSpreadSafeStatus.WITHIN_LIMIT,
    )
    base.update(overrides)
    return MarketTickerSafeInput(**base)  # type: ignore[arg-type]


class TestPassAndBlock:
    def test_open_fresh_within_limit_passes(self) -> None:
        result = evaluate_market_ticker_safe_labels(_all_safe_input())
        assert result.market_status_safe_label is (
            GmoMarketStatusSafeLabel.MARKET_OPEN_SAFE
        )
        assert result.ticker_freshness_safe_label is (
            GmoTickerFreshnessSafeLabel.TICKER_FRESH_SAFE
        )
        assert result.spread_status_safe_label is (
            GmoSpreadStatusSafeLabel.SPREAD_WITHIN_LIMIT_SAFE
        )
        assert result.passes_entry_gate is True
        assert result.blocked_reasons == ()
        assert not result  # never truthy even when passing

    def test_default_input_blocks_with_unknown_labels(self) -> None:
        result = evaluate_market_ticker_safe_labels(MarketTickerSafeInput())
        assert result.market_status_safe_label is (
            GmoMarketStatusSafeLabel.MARKET_UNKNOWN_SAFE
        )
        assert result.ticker_freshness_safe_label is (
            GmoTickerFreshnessSafeLabel.TICKER_UNKNOWN_SAFE
        )
        assert result.spread_status_safe_label is (
            GmoSpreadStatusSafeLabel.SPREAD_UNKNOWN_SAFE
        )
        assert result.passes_entry_gate is False

    def test_market_closed_blocks(self) -> None:
        result = evaluate_market_ticker_safe_labels(
            _all_safe_input(market_status=GmoRuntimeMarketSafeStatus.CLOSED)
        )
        assert result.market_status_safe_label is (
            GmoMarketStatusSafeLabel.MARKET_CLOSED_SAFE
        )
        assert result.passes_entry_gate is False
        assert "MARKET_NOT_OPEN_SAFE_BLOCKED" in result.blocked_reasons

    def test_market_unknown_blocks(self) -> None:
        result = evaluate_market_ticker_safe_labels(
            _all_safe_input(market_status=GmoRuntimeMarketSafeStatus.UNKNOWN)
        )
        assert result.market_status_safe_label is (
            GmoMarketStatusSafeLabel.MARKET_UNKNOWN_SAFE
        )
        assert result.passes_entry_gate is False

    def test_ticker_stale_blocks(self) -> None:
        result = evaluate_market_ticker_safe_labels(
            _all_safe_input(
                ticker_status=GmoRuntimeTickerFreshnessSafeStatus.STALE
            )
        )
        assert result.ticker_freshness_safe_label is (
            GmoTickerFreshnessSafeLabel.TICKER_STALE_SAFE
        )
        assert result.passes_entry_gate is False
        assert "TICKER_NOT_FRESH_SAFE_BLOCKED" in result.blocked_reasons

    def test_spread_unknown_blocks(self) -> None:
        result = evaluate_market_ticker_safe_labels(
            _all_safe_input(spread_status=GmoRuntimeSpreadSafeStatus.UNKNOWN)
        )
        assert result.spread_status_safe_label is (
            GmoSpreadStatusSafeLabel.SPREAD_UNKNOWN_SAFE
        )
        assert result.passes_entry_gate is False
        assert "SPREAD_NOT_WITHIN_LIMIT_SAFE_BLOCKED" in result.blocked_reasons

    def test_spread_out_of_limit_blocks(self) -> None:
        result = evaluate_market_ticker_safe_labels(
            _all_safe_input(spread_status=GmoRuntimeSpreadSafeStatus.OUT_OF_LIMIT)
        )
        assert result.spread_status_safe_label is (
            GmoSpreadStatusSafeLabel.SPREAD_OUT_OF_LIMIT_SAFE
        )
        assert result.passes_entry_gate is False

    def test_missing_ticker_blocks_and_degrades_to_unknown(self) -> None:
        result = evaluate_market_ticker_safe_labels(
            _all_safe_input(ticker_present=False)
        )
        assert "TICKER_MISSING_BLOCKED" in result.blocked_reasons
        assert result.ticker_freshness_safe_label is (
            GmoTickerFreshnessSafeLabel.TICKER_UNKNOWN_SAFE
        )
        assert result.spread_status_safe_label is (
            GmoSpreadStatusSafeLabel.SPREAD_UNKNOWN_SAFE
        )
        assert result.passes_entry_gate is False


class TestSnapshotLift:
    def test_fresh_performed_snapshot_lifts_market_fields(self) -> None:
        snapshot = GmoRuntimeSafeReadSnapshot(
            performed=True,
            fresh=True,
            market_status=GmoRuntimeMarketSafeStatus.OPEN,
            ticker_status=GmoRuntimeTickerFreshnessSafeStatus.FRESH,
            spread_status=GmoRuntimeSpreadSafeStatus.WITHIN_LIMIT,
        )
        safe_input = MarketTickerSafeInput.from_safe_snapshot(snapshot)
        assert safe_input.ticker_present is True
        result = evaluate_market_ticker_safe_labels(safe_input)
        assert result.passes_entry_gate is True

    @pytest.mark.parametrize(
        "overrides", [{"performed": False}, {"fresh": False}]
    )
    def test_stale_or_unperformed_snapshot_blocks(self, overrides: dict) -> None:
        snapshot = GmoRuntimeSafeReadSnapshot(
            performed=True,
            fresh=True,
            market_status=GmoRuntimeMarketSafeStatus.OPEN,
            ticker_status=GmoRuntimeTickerFreshnessSafeStatus.FRESH,
            spread_status=GmoRuntimeSpreadSafeStatus.WITHIN_LIMIT,
        )
        snapshot = GmoRuntimeSafeReadSnapshot(
            **{
                **{
                    field.name: getattr(snapshot, field.name)
                    for field in fields(snapshot)
                },
                **overrides,
            }
        )
        safe_input = MarketTickerSafeInput.from_safe_snapshot(snapshot)
        assert safe_input.ticker_present is False
        result = evaluate_market_ticker_safe_labels(safe_input)
        assert result.passes_entry_gate is False
        assert "TICKER_MISSING_BLOCKED" in result.blocked_reasons


class TestNoRawValueSurface:
    _FORBIDDEN_FIELD_TOKENS = ("bid", "ask", "price", "timestamp", "value", "raw_")

    def test_input_type_has_no_raw_value_field(self) -> None:
        names = {field.name for field in fields(MarketTickerSafeInput)}
        assert names == {
            "ticker_present",
            "market_status",
            "ticker_status",
            "spread_status",
        }

    def test_result_type_carries_labels_and_safe_booleans_only(self) -> None:
        for field in fields(MarketTickerSafeResult):
            assert field.type not in ("float", "int")
        result = evaluate_market_ticker_safe_labels(_all_safe_input())
        assert result.raw_bid_ask_exposed is False
        assert result.raw_spread_value_exposed is False
        assert result.raw_timestamp_exposed is False

    def test_result_repr_contains_no_numeric_market_values(self) -> None:
        result = evaluate_market_ticker_safe_labels(_all_safe_input())
        rendered = repr(result)
        assert "bid=" not in rendered
        assert "ask=" not in rendered
        assert "timestamp=" not in rendered


class TestSourceScan:
    def test_module_performs_no_http_and_reads_no_env(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        assert "httpx" not in text
        assert "requests" not in text
        assert "urllib" not in text
        assert "os.environ" not in text
        assert "getenv" not in text
        assert "load_dotenv" not in text

    def test_module_has_no_order_or_settlement_route(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        assert "closeOrder" not in text
        assert "settlePosition" not in text
        assert "live_order_once" not in text
        assert "/private/v1/order" not in text

    def test_module_has_no_allow_literals(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
        assert "actual_entry_POST_allowed=True" not in text
        assert "allow_real_broker_post=True" not in text
        assert "allow_live_http_post=True" not in text
