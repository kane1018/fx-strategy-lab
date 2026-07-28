"""Synthetic-only V2 predecessor marker producer with no live dependency."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

V2_FAKE_ONLY_SCHEMA = "H11_V4_PREDECESSOR_COMPLETION_V2_FAKE_ONLY_V1"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_STARTED_NAME = "predecessor-completion-v2-fake.started.json"
_PASSED_NAME = "predecessor-completion-v2-fake.passed.json"


class V4PredecessorCompletionV2FakeOnlyError(ValueError):
    """Fixed failures for synthetic marker production only."""


@dataclass(frozen=True)
class V4FakeOnlyReconciliationResult:
    fake_only: bool
    result_known: bool
    subject_entry_observed: bool
    account_flat: bool
    active_orders_zero: bool
    broker_read_count: int
    broker_write_attempt_count: int
    raw_response_retained: bool
    identifier_exposed: bool


@dataclass(frozen=True)
class V4FakeOnlyV2Evidence:
    schema: str
    origin_generation_digest: str
    target_generation_digest: str
    started_marker_digest: str
    passed_marker_digest: str
    commissioning_eligible: bool = False
    broker_write: bool = False
    actual_post_count: int = 0

    def __post_init__(self) -> None:
        if (
            self.schema != V2_FAKE_ONLY_SCHEMA
            or not _SHA256.fullmatch(self.origin_generation_digest)
            or not _SHA256.fullmatch(self.target_generation_digest)
            or not _SHA256.fullmatch(self.started_marker_digest)
            or not _SHA256.fullmatch(self.passed_marker_digest)
            or type(self.commissioning_eligible) is not bool
            or type(self.broker_write) is not bool
            or type(self.actual_post_count) is not int
            or self.commissioning_eligible is not False
            or self.broker_write is not False
            or self.actual_post_count != 0
        ):
            raise V4PredecessorCompletionV2FakeOnlyError(
                "V4_V2_FAKE_EVIDENCE_INVALID"
            )

    def __bool__(self) -> bool:
        return False


def produce_fake_only_v2_evidence(
    *,
    runtime_root: Path,
    origin_generation_digest: str,
    target_generation_digest: str,
    result: V4FakeOnlyReconciliationResult,
) -> V4FakeOnlyV2Evidence:
    """Write a one-use synthetic pair that no commissioning binder may accept."""

    _require_digest(origin_generation_digest)
    _require_digest(target_generation_digest)
    expected_name = "generation-" + target_generation_digest.removeprefix("sha256:")
    if runtime_root.name != expected_name or not _result_is_synthetic_and_clear(result):
        raise V4PredecessorCompletionV2FakeOnlyError("V4_V2_FAKE_EVIDENCE_REJECTED")

    try:
        runtime_root.mkdir(parents=True, exist_ok=False)
        started = runtime_root / _STARTED_NAME
        _write_once(
            started,
            {
                "schema": V2_FAKE_ONLY_SCHEMA,
                "synthetic_evidence": True,
                "origin_generation_digest": origin_generation_digest,
                "target_generation_digest": target_generation_digest,
                "broker_write_attempt_count": 0,
            },
        )
        passed = runtime_root / _PASSED_NAME
        _write_once(
            passed,
            {
                "schema": V2_FAKE_ONLY_SCHEMA,
                "synthetic_evidence": True,
                "origin_generation_digest": origin_generation_digest,
                "target_generation_digest": target_generation_digest,
                "started_marker_digest": _file_digest(started),
                "status": "V4_V2_FAKE_RECONCILIATION_FLAT_CONFIRMED",
                "result_known": True,
                "subject_entry_observed": True,
                "account_flat": True,
                "active_orders_zero": True,
                "broker_read_count": result.broker_read_count,
                "broker_write_attempt_count": 0,
                "raw_response_retained": False,
                "identifier_exposed": False,
                "commissioning_eligible": False,
            },
        )
    except (OSError, ValueError):
        raise V4PredecessorCompletionV2FakeOnlyError(
            "V4_V2_FAKE_EVIDENCE_UNAVAILABLE"
        ) from None
    return V4FakeOnlyV2Evidence(
        schema=V2_FAKE_ONLY_SCHEMA,
        origin_generation_digest=origin_generation_digest,
        target_generation_digest=target_generation_digest,
        started_marker_digest=_file_digest(started),
        passed_marker_digest=_file_digest(passed),
    )


def _result_is_synthetic_and_clear(result: V4FakeOnlyReconciliationResult) -> bool:
    return (
        result.fake_only is True
        and result.result_known is True
        and result.subject_entry_observed is True
        and result.account_flat is True
        and result.active_orders_zero is True
        and type(result.broker_read_count) is int
        and result.broker_read_count >= 0
        and type(result.broker_write_attempt_count) is int
        and result.broker_write_attempt_count == 0
        and result.raw_response_retained is False
        and result.identifier_exposed is False
    )


def _require_digest(value: str) -> None:
    if not _SHA256.fullmatch(value):
        raise V4PredecessorCompletionV2FakeOnlyError("V4_V2_FAKE_EVIDENCE_REJECTED")


def _write_once(path: Path, payload: dict[str, object]) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
