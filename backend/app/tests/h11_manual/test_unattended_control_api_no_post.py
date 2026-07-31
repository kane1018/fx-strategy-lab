from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.h11_manual import api as manual_api
from app.h11_manual import unattended_control_api as subject
from app.main_h11_manual import app
from app.services.h11_v4_unattended_live_arm_state import V4UnattendedLiveArmStore

_GENERATION = "sha256:" + "a" * 64
_REVIEWED = "sha256:" + "b" * 64


def _install_contract(monkeypatch, tmp_path: Path, *, supported: bool = True) -> None:
    generation = SimpleNamespace(
        digest=_GENERATION,
        generation_label="H11_AUTO_30M_TEST",
        live_ready=supported,
        unattended_live_supported=supported,
        maximum_entries_per_day=30,
    )
    contract = subject._CurrentContract(
        reviewed_files_digest=_REVIEWED,
        generation=generation,
    )
    monkeypatch.setattr(subject, "_load_current_contract", lambda: contract)
    monkeypatch.setattr(
        subject,
        "_arm_store",
        lambda _contract: V4UnattendedLiveArmStore(tmp_path / "arm-state.json"),
    )
    monkeypatch.setattr(
        subject,
        "v4_unattended_live_arm_state_path",
        lambda **_kw: tmp_path / "arm-state.json",
    )
    monkeypatch.setattr(subject, "require_clean_main", lambda **_kw: None)
    if supported:
        monkeypatch.setattr(
            subject,
            "verify_g038_generation_activation",
            lambda **_kw: SimpleNamespace(successor_activation_released=True),
        )
        monkeypatch.setattr(
            subject,
            "verify_g038_scheduler_binding",
            lambda **_kw: None,
        )
    else:
        monkeypatch.setattr(
            subject,
            "verify_g038_generation_activation",
            lambda **_kw: (_ for _ in ()).throw(
                subject.V4G038ActivationError("G038_GENERATION_NOT_ACTIVATED")
            ),
        )


def test_status_and_on_off_are_local_state_only(monkeypatch, tmp_path) -> None:
    _install_contract(monkeypatch, tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    initial = client.get("/api/manual/unattended-control")
    assert initial.status_code == 200
    payload = initial.json()
    assert payload["effective_state"] == "OFF"
    assert payload["broker_write"] is False
    headers = {
        "Origin": "http://127.0.0.1:8765",
        "X-H11-V4-Control-CSRF": payload["csrf_token"],
    }
    armed = client.post(
        "/api/manual/unattended-control/on",
        headers=headers,
        json={
            "expected_revision": 0,
            "expected_generation_digest": _GENERATION,
            "expected_reviewed_files_digest": _REVIEWED,
        },
    )
    assert armed.status_code == 200
    assert armed.json()["desired_state"] == "ARMED"
    assert armed.json()["daily_authorization_required"] is False
    assert armed.json()["broker_write"] is False
    monkeypatch.setattr(
        subject,
        "_load_current_contract",
        lambda: (_ for _ in ()).throw(OSError("contract drift")),
    )
    disarmed = client.post(
        "/api/manual/unattended-control/off",
        headers=headers,
        json={
            "expected_revision": 1,
            "expected_generation_digest": _GENERATION,
            "expected_reviewed_files_digest": _REVIEWED,
        },
    )
    assert disarmed.status_code == 200
    assert disarmed.json()["desired_state"] == "DISARMED"
    assert disarmed.json()["actual_post_count"] == 0
    assert disarmed.json()["effective_state"] == "OFF_REQUESTED"


def test_unknown_contract_blocks_manual_private_get(monkeypatch) -> None:
    monkeypatch.setattr(
        subject,
        "_load_current_contract",
        lambda: (_ for _ in ()).throw(OSError("contract unavailable")),
    )
    assert subject.unattended_auto_mode_requested() is True


def test_manual_settlement_reader_is_restored_after_auto_mode_turns_off(
    monkeypatch,
) -> None:
    service = SimpleNamespace(settlement_reader=object())
    restored_reader = object()
    monkeypatch.setattr(manual_api, "_manual_signal_service", service)
    monkeypatch.setattr(manual_api, "_manual_settlement_reader_initialized", True)
    monkeypatch.setattr(manual_api, "unattended_auto_mode_requested", lambda: True)
    manual_api.get_manual_settlement_service(service)
    assert manual_api._manual_settlement_reader_initialized is False
    monkeypatch.setattr(manual_api, "unattended_auto_mode_requested", lambda: False)
    monkeypatch.setattr(
        manual_api,
        "build_keychain_manual_settlement_client",
        lambda: restored_reader,
    )
    manual_api.get_manual_settlement_service(service)
    assert service.settlement_reader is restored_reader
    assert manual_api._manual_settlement_reader_initialized is True


def test_arm_on_is_decoupled_from_runtime_entry_gate(
    monkeypatch, tmp_path
) -> None:
    _install_contract(monkeypatch, tmp_path, supported=False)
    monkeypatch.setattr(subject, "_runtime_projection", lambda _contract: ("HALTED", 3))
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    initial = client.get("/api/manual/unattended-control").json()
    body = {
        "expected_revision": 0,
        "expected_generation_digest": _GENERATION,
        "expected_reviewed_files_digest": _REVIEWED,
    }
    assert client.post("/api/manual/unattended-control/on", json=body).status_code == 403
    armed = client.post(
        "/api/manual/unattended-control/on",
        headers={
            "Origin": "http://127.0.0.1:8765",
            "X-H11-V4-Control-CSRF": initial["csrf_token"],
        },
        json=body,
    )
    assert armed.status_code == 200
    payload = armed.json()
    assert payload["desired_state"] == "ARMED"
    assert payload["arm_state"] == "ARMED"
    assert payload["effective_state"] == "HALTED"
    assert payload["entry_state"] == "HALTED"
    assert payload["entry_gate_open"] is False
    assert payload["broker_write"] is False


def test_armed_position_projects_exit_only_without_entry_gate(
    monkeypatch, tmp_path
) -> None:
    _install_contract(monkeypatch, tmp_path)
    monkeypatch.setattr(
        subject,
        "_runtime_projection",
        lambda _contract: ("POSITION_OPEN", 3),
    )
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    initial = client.get("/api/manual/unattended-control").json()
    headers = {
        "Origin": "http://127.0.0.1:8765",
        "X-H11-V4-Control-CSRF": initial["csrf_token"],
    }
    armed = client.post(
        "/api/manual/unattended-control/on",
        headers=headers,
        json={
            "expected_revision": 0,
            "expected_generation_digest": _GENERATION,
            "expected_reviewed_files_digest": _REVIEWED,
        },
    )
    assert armed.status_code == 200
    payload = armed.json()
    assert payload["arm_state"] == "ARMED"
    assert payload["effective_state"] == "ON_EXIT_ONLY"
    assert payload["entry_state"] == "POSITION_OPEN"
    assert payload["entry_gate_open"] is False


def test_public_application_does_not_expose_control_routes() -> None:
    from app.main_readonly import app as public_app

    client = TestClient(public_app)
    assert client.get("/api/manual/unattended-control").status_code == 404
    assert client.post("/api/manual/unattended-control/on").status_code == 404
    assert client.post("/api/manual/unattended-control/off").status_code == 404


def test_disarmed_open_position_projects_exit_only(monkeypatch, tmp_path) -> None:
    _install_contract(monkeypatch, tmp_path)
    monkeypatch.setattr(
        subject,
        "_runtime_projection",
        lambda _contract: ("POSITION_OPEN", 3),
    )
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    payload = client.get("/api/manual/unattended-control").json()
    assert payload["effective_state"] == "EXIT_ONLY"
    assert payload["entries_today"] == 3
    assert payload["broker_write"] is False
    assert subject.unattended_auto_mode_requested() is True
