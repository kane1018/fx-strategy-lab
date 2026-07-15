"""Canonical sanitized GMO capability evidence selected by relaxed v4."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

V4_GMO_CAPABILITY_EVIDENCE_SCHEMA = "H11_V4_GMO_CAPABILITY_EVIDENCE_V1"


@dataclass(frozen=True)
class V4GmoCapabilityEvidence:
    schema: str = V4_GMO_CAPABILITY_EVIDENCE_SCHEMA
    source_label: str = "GMO_SUPPORT_OPERATOR_RELAY_2026_07_15"
    per_order_expiry_or_tif: str = "NO_REQUEST_FIELD"
    all_or_none_or_fok: str = "NOT_SUPPORTED"
    atomic_actual_fill_sized_protection: str = "NOT_SUPPORTED"
    second_oco_size_auto_adjust: str = "NOT_SUPPORTED"
    partial_fill_detection: str = "ORDER_EXECUTED_SIZE_PLUS_OPEN_POSITIONS"
    protection_size_change: str = "NOT_SUPPORTED"
    mismatch_remediation: str = "CANCEL_RECONCILE_REPLACE_EXACT_SIZE"
    excess_protection_behavior: str = "NOT_GUARANTEED_UNEXPECTED_OPERATION"
    client_order_linkage: str = "ORDER_AND_EXECUTION_RECORDS_WHEN_SET"
    open_positions_linkage: str = "POSITION_ID_ONLY"

    def __bool__(self) -> bool:
        return False

    @property
    def canonical_json(self) -> str:
        return json.dumps(
            self.to_safe_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical_json.encode()).hexdigest()

    def to_safe_dict(self) -> dict[str, str]:
        return {
            "all_or_none_or_fok": self.all_or_none_or_fok,
            "atomic_actual_fill_sized_protection": (
                self.atomic_actual_fill_sized_protection
            ),
            "client_order_linkage": self.client_order_linkage,
            "excess_protection_behavior": self.excess_protection_behavior,
            "mismatch_remediation": self.mismatch_remediation,
            "open_positions_linkage": self.open_positions_linkage,
            "partial_fill_detection": self.partial_fill_detection,
            "per_order_expiry_or_tif": self.per_order_expiry_or_tif,
            "protection_size_change": self.protection_size_change,
            "schema": self.schema,
            "second_oco_size_auto_adjust": self.second_oco_size_auto_adjust,
            "source_label": self.source_label,
        }


H11_V4_GMO_CAPABILITY_EVIDENCE = V4GmoCapabilityEvidence()
H11_V4_GMO_CAPABILITY_EVIDENCE_HASH = H11_V4_GMO_CAPABILITY_EVIDENCE.digest
