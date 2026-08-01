"""G066 no-POST runtime projection primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class G066PositionEvidence:
    """Sanitized position facts; unknown facts remain false."""

    open_position_count: int
    active_order_count: int
    ownership_exact: bool = False
    quantity_matches: bool = False
    protection_confirmed: bool = False
    pending: bool = False
    unknown: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> G066PositionEvidence:
        if not isinstance(value, Mapping):
            return cls(0, 0, unknown=True)
        try:
            open_count = int(value.get("open_position_count", -1))
            active_count = int(value.get("active_order_count", -1))
        except (TypeError, ValueError):
            return cls(0, 0, unknown=True)
        if open_count < 0 or active_count < 0:
            return cls(0, 0, unknown=True)
        return cls(
            open_position_count=open_count,
            active_order_count=active_count,
            ownership_exact=value.get("ownership_exact") is True,
            quantity_matches=value.get("quantity_matches") is True,
            protection_confirmed=value.get("protection_confirmed") is True,
            pending=value.get("pending") is True,
            unknown=value.get("unknown") is True,
        )


def project_g066_runtime_state(
    *,
    arm_state: str,
    position: G066PositionEvidence | Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project ARM, effective state, entry gate and entry state independently."""

    normalized_arm = arm_state if arm_state in {"OFF", "ON"} else "OFF"
    evidence = (
        position
        if isinstance(position, G066PositionEvidence)
        else G066PositionEvidence.from_mapping(position)
    )
    has_position = evidence.open_position_count > 0
    is_flat = evidence.open_position_count == 0 and evidence.active_order_count == 0

    if evidence.unknown or evidence.pending:
        effective_state = "HALTED"
        entry_gate_open = False
        entry_state = "HALTED"
        safe_reason = "RUNTIME_EVIDENCE_UNKNOWN"
    elif has_position:
        entry_gate_open = False
        if (
            evidence.ownership_exact
            and evidence.quantity_matches
            and evidence.protection_confirmed
        ):
            effective_state = "ON_EXIT_ONLY" if normalized_arm == "ON" else "EXIT_ONLY"
            entry_state = "EXIT_ONLY"
            safe_reason = "PROTECTED_POSITION_EXIT_ONLY"
        else:
            effective_state = "HALTED"
            entry_state = "HALTED"
            safe_reason = "POSITION_SAFETY_NOT_CONFIRMED"
    elif not is_flat:
        effective_state = "HALTED"
        entry_gate_open = False
        entry_state = "HALTED"
        safe_reason = "FLAT_RECONCILIATION_NOT_CONFIRMED"
    elif normalized_arm == "ON":
        effective_state = "ON_WAITING"
        entry_gate_open = True
        entry_state = "WAITING"
        safe_reason = "ENTRY_GATE_WAITING"
    else:
        effective_state = "OFF"
        entry_gate_open = False
        entry_state = "OFF"
        safe_reason = "ARM_OFF"

    return {
        "arm_state": normalized_arm,
        "effective_state": effective_state,
        "entry_gate_open": entry_gate_open,
        "entry_state": entry_state,
        "safe_reason": safe_reason,
        "open_position_count": evidence.open_position_count,
        "active_order_count": evidence.active_order_count,
        "ownership_exact": evidence.ownership_exact,
        "quantity_matches": evidence.quantity_matches,
        "protection_confirmed": evidence.protection_confirmed,
        "broker_write": False,
        "actual_post_authorized": False,
    }


def safe_status_from_runtime_root(runtime_root: Any) -> dict[str, Any]:
    """Return only a safe projection from local runtime files."""

    import json
    from pathlib import Path

    root = Path(runtime_root)
    try:
        evidence = json.loads(
            (root / "position-reconciliation.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        evidence = {"unknown": True}
    arm_state = "OFF"
    try:
        raw_arm = json.loads((root / "arm-state.json").read_text(encoding="utf-8"))
        if isinstance(raw_arm, Mapping):
            arm_state = str(raw_arm.get("arm_state", "OFF"))
    except (OSError, ValueError):
        pass
    return project_g066_runtime_state(arm_state=arm_state, position=evidence)
