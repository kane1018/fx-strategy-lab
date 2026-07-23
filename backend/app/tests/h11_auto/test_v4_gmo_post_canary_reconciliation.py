from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from app.services import h11_v4_gmo_post_canary_reconciliation as subject


class _FakeClient:
    def __init__(
        self,
        *,
        executions: dict[str, object],
        positions: dict[str, object],
        active: dict[str, object],
    ) -> None:
        self.executions = executions
        self.positions = positions
        self.active = active
        self.calls: list[str] = []

    def get_latest_executions(self) -> dict[str, object]:
        self.calls.append("executions")
        return self.executions

    def get_open_positions(self) -> dict[str, object]:
        self.calls.append("positions")
        return self.positions

    def get_active_orders(self) -> dict[str, object]:
        self.calls.append("active")
        return self.active


def _client(
    *,
    positions: list[dict[str, object]] | None = None,
    active: list[dict[str, object]] | None = None,
) -> _FakeClient:
    cycle_ref = "a" * 64
    return _FakeClient(
        executions={"list": [{"symbol": "USD_JPY", "clientOrderId": "H11V4E" + cycle_ref[:30]}]},
        positions={"list": positions or []},
        active={"list": active or []},
    )


def _reconciler(
    tmp_path: Path, client: _FakeClient, waits: list[float]
) -> subject.V4GmoPostCanaryReconciler:
    return subject.V4GmoPostCanaryReconciler(
        repository=tmp_path,
        target_generation_digest="sha256:" + "b" * 64,
        origin_generation_digest="sha256:" + "a" * 64,
        cycle_ref="a" * 64,
        client=client,
        wait=waits.append,
    )


def test_flat_subject_is_confirmed_with_exact_three_gets(tmp_path: Path) -> None:
    waits: list[float] = []
    client = _client()
    result = _reconciler(tmp_path, client, waits).reconcile_once()
    assert result.safe_dict() == {
        "status": "G013_POST_CANARY_FLAT_CONFIRMED",
        "result_known": True,
        "subject_entry_observed": True,
        "account_flat": True,
        "active_orders_zero": True,
        "broker_read_count": 3,
        "broker_write_attempt_count": 0,
        "raw_response_retained": False,
        "identifier_exposed": False,
    }
    assert client.calls == ["executions", "positions", "active"]
    assert waits == [0.25, 0.25]


def test_nonflat_result_preserves_halt_without_a_broker_write(tmp_path: Path) -> None:
    client = _client(positions=[{"symbol": "USD_JPY"}])
    result = _reconciler(tmp_path, client, []).reconcile_once()
    assert result.status == "G013_POST_CANARY_NOT_FLAT_PERSISTENT_HALT"
    assert result.result_known is True
    assert result.broker_write_attempt_count == 0


def test_unknown_subject_is_fail_closed_and_the_marker_cannot_be_reused(tmp_path: Path) -> None:
    client = _FakeClient(
        executions={"list": []}, positions={"list": []}, active={"list": []}
    )
    reconciler = _reconciler(tmp_path, client, [])
    result = reconciler.reconcile_once()
    assert result.status == "G013_POST_CANARY_RESULT_UNKNOWN_PERSISTENT_HALT"
    with pytest.raises(subject.V4GmoPostCanaryReconciliationError, match="ALREADY_CONSUMED"):
        reconciler.reconcile_once()


def test_unknown_after_one_read_reports_only_the_completed_read_count(tmp_path: Path) -> None:
    class _BrokenClient(_FakeClient):
        def get_open_positions(self) -> dict[str, object]:
            raise subject.V4GmoPostCanaryReconciliationError("G013_POST_CANARY_READ_UNKNOWN")

    client = _BrokenClient(
        executions={"list": [{"symbol": "USD_JPY", "clientOrderId": "H11V4E" + "a" * 30}]},
        positions={"list": []},
        active={"list": []},
    )
    result = _reconciler(tmp_path, client, []).reconcile_once()
    assert result.result_known is False
    assert result.broker_read_count == 1


def test_account_snapshot_queries_match_the_proven_preflight_contract() -> None:
    assert subject._ENDPOINTS[1][3] == {"count": "100"}
    assert subject._ENDPOINTS[2][3] == {"count": "100"}


@pytest.mark.parametrize(
    ("data", "expected"),
    (
        (None, {"list": []}),
        ([], {"list": []}),
        ([{"symbol": "USD_JPY"}], {"list": [{"symbol": "USD_JPY"}]}),
        ({"list": []}, {"list": []}),
    ),
)
def test_broker_row_shapes_are_normalized_without_retaining_the_envelope(
    data: object, expected: dict[str, object]
) -> None:
    assert subject._normalize_rows_data(data) == expected


def test_invalid_broker_row_shape_is_rejected() -> None:
    with pytest.raises(
        subject.V4GmoPostCanaryReconciliationError, match="READ_SCHEMA_INVALID"
    ):
        subject._normalize_rows_data({"list": ["raw"]})


def test_reconciliation_module_has_no_existing_write_path_dependency() -> None:
    source = inspect.getsource(subject)
    for forbidden in (
        "V4GmoHttpxPrivateTransport",
        "V4GmoActualAdapter",
        "V4GmoExitDispatcher",
        "perform_once",
        "cancelOrders",
        "closeOrder",
        "/private/v1/order",
    ):
        assert forbidden not in source


def test_script_reads_the_origin_ledger_in_sqlite_read_only_mode() -> None:
    script = (
        Path(__file__).resolve().parents[3]
        / "scripts/h11_auto_v4_g013_post_canary_reconciliation.py"
    )
    source = script.read_text(encoding="utf-8")
    assert "?mode=ro" in source
    assert "V4GmoActualCoordinatorStore" not in source


def test_reconciliation_only_contract_disables_entry(tmp_path: Path) -> None:
    contract = tmp_path / "docs/templates/h11_v4_g013_post_canary_reconciliation.json"
    contract.parent.mkdir(parents=True)
    contract.write_text(json.dumps({
        "reviewed_files_digest": "sha256:" + "b" * 64,
        "generation_digest": "sha256:" + "c" * 64,
        "origin_generation_digest": "sha256:" + "a" * 64,
        "entry_disabled": True,
    }), encoding="utf-8")
    with pytest.raises(subject.V4GmoPostCanaryReconciliationError, match="ENTRY_DISABLED"):
        subject.require_g013_entry_enabled(
            repository=tmp_path,
            reviewed_files_digest="sha256:" + "b" * 64,
            generation_digest="sha256:" + "c" * 64,
        )
