"""One-shot live order preparation and guarded execution primitives.

This module contains the first code path that can model a live order POST, but
it remains disabled by default. Tests use fake transports only. A caller must
pass an exact approval decision, an unused ledger, explicit credential values,
and an explicit transport before a single POST attempt can occur.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app.live_verification.errors import LiveVerificationLiveOrderOnceError
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

LIVE_ORDER_SIZE = str(SUPPORTED_UNITS)
LIVE_ORDER_EXECUTION_TYPE = "MARKET"
LIVE_ORDER_METHOD = "POST"
LIVE_ORDER_ENDPOINT_BASE = "https://forex-api.coin.z.com/private"
LIVE_ORDER_SIGNING_PATH = "/v1/order"
LIVE_ORDER_ENDPOINT_URL = f"{LIVE_ORDER_ENDPOINT_BASE}{LIVE_ORDER_SIGNING_PATH}"
LIVE_ORDER_APPROVAL_TTL_SECONDS = 300
LIVE_ORDER_HTTP_TIMEOUT_SECONDS = 10.0
LIVE_ORDER_LEDGER_DIR = Path.home() / ".local" / "state" / "fx-strategy-lab" / "live-order-attempts"
LIVE_ORDER_BODY_FIELDS = frozenset(
    {"symbol", "side", "size", "clientOrderId", "executionType"}
)
LIVE_ORDER_HEADER_NAMES = ("API-KEY", "API-TIMESTAMP", "API-SIGN")


class LiveOrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class LiveOrderAttemptState(str, Enum):
    MISSING = "MISSING"
    PREPARED = "PREPARED"
    POST_STARTED = "POST_STARTED"
    POST_COMPLETED = "POST_COMPLETED"
    RESULT_UNKNOWN = "RESULT_UNKNOWN"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class LiveOrderOutboundBody:
    symbol: str
    side: LiveOrderSide
    size: str
    clientOrderId: str
    executionType: str

    def __post_init__(self) -> None:
        _validate_live_order_body(self)


@dataclass(frozen=True)
class Step4ApprovalGate:
    approval_id: str
    issued_at_jst: str
    expires_at_jst: str
    buy_approval_phrase: str
    sell_approval_phrase: str

    def __post_init__(self) -> None:
        _require_non_empty("approval_id", self.approval_id)
        _parse_jst_datetime(self.issued_at_jst)
        _parse_jst_datetime(self.expires_at_jst)
        if self.buy_approval_phrase != _approval_phrase(self.approval_id, LiveOrderSide.BUY):
            raise LiveVerificationLiveOrderOnceError("BUY approval phrase mismatch")
        if self.sell_approval_phrase != _approval_phrase(
            self.approval_id,
            LiveOrderSide.SELL,
        ):
            raise LiveVerificationLiveOrderOnceError("SELL approval phrase mismatch")


@dataclass(frozen=True)
class Step4ApprovalDecision:
    approval_passed: bool
    approval_id: str
    side: str
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("approval_id", self.approval_id)
        if type(self.approval_passed) is not bool:
            raise LiveVerificationLiveOrderOnceError("approval_passed must be bool")
        if self.side not in {"BUY", "SELL", "unknown"}:
            raise LiveVerificationLiveOrderOnceError("side must be BUY, SELL, or unknown")
        if not isinstance(self.fail_reasons, tuple) or any(
            not isinstance(reason, str) or not reason for reason in self.fail_reasons
        ):
            raise LiveVerificationLiveOrderOnceError("fail_reasons must be tuple[str, ...]")
        if self.approval_passed and self.fail_reasons:
            raise LiveVerificationLiveOrderOnceError(
                "passed approval cannot contain fail reasons"
            )
        if not self.approval_passed and not self.fail_reasons:
            raise LiveVerificationLiveOrderOnceError(
                "failed approval requires fail reasons"
            )


@dataclass(frozen=True)
class LiveOrderAttemptLedger:
    ledger_path: str
    state: str
    attempt_count: int
    prepared_at: str
    approval_id_hash: str
    clientOrderId: str
    post_started_at: str
    post_finished_at: str
    result_category: str

    def __post_init__(self) -> None:
        _require_non_empty("ledger_path", self.ledger_path)
        if self.state not in {state.value for state in LiveOrderAttemptState}:
            raise LiveVerificationLiveOrderOnceError("ledger state is invalid")
        if type(self.attempt_count) is not int or self.attempt_count < 0:
            raise LiveVerificationLiveOrderOnceError("attempt_count must be non-negative int")
        for field_name, value in (
            ("prepared_at", self.prepared_at),
            ("approval_id_hash", self.approval_id_hash),
            ("clientOrderId", self.clientOrderId),
            ("post_started_at", self.post_started_at),
            ("post_finished_at", self.post_finished_at),
            ("result_category", self.result_category),
        ):
            if not isinstance(value, str):
                raise LiveVerificationLiveOrderOnceError(f"{field_name} must be str")


@dataclass(frozen=True)
class OneShotLiveOrderPrepared:
    approval_gate: Step4ApprovalGate
    ledger: LiveOrderAttemptLedger
    clientOrderId: str
    http_post_enabled: bool
    live_order_allowed_now: bool
    raw_request_saved: bool
    raw_response_saved: bool
    credential_values_logged: bool

    def __post_init__(self) -> None:
        _validate_client_order_id(self.clientOrderId)
        for name, value in {
            "http_post_enabled": self.http_post_enabled,
            "live_order_allowed_now": self.live_order_allowed_now,
            "raw_request_saved": self.raw_request_saved,
            "raw_response_saved": self.raw_response_saved,
            "credential_values_logged": self.credential_values_logged,
        }.items():
            if type(value) is not bool:
                raise LiveVerificationLiveOrderOnceError(f"{name} must be bool")
        if any((
            self.http_post_enabled,
            self.live_order_allowed_now,
            self.raw_request_saved,
            self.raw_response_saved,
            self.credential_values_logged,
        )):
            raise LiveVerificationLiveOrderOnceError(
                "prepared order cannot enable execution or leak artifacts"
            )


@dataclass(frozen=True)
class LiveOrderTransportResponse:
    transport_result: str
    api_status_success: str
    response_data_present: str

    def __post_init__(self) -> None:
        if self.transport_result not in {
            "success",
            "api_rejected",
            "transport_error",
            "result_unknown",
        }:
            raise LiveVerificationLiveOrderOnceError("transport_result is invalid")
        if self.api_status_success not in {"true", "false", "unknown"}:
            raise LiveVerificationLiveOrderOnceError("api_status_success is invalid")
        if self.response_data_present not in {"true", "false", "unknown"}:
            raise LiveVerificationLiveOrderOnceError("response_data_present is invalid")


@dataclass(frozen=True)
class OneShotLiveOrderResult:
    http_post_attempted: bool
    http_post_count: int
    transport_result: str
    api_status_success: str
    response_data_present: str
    result_unknown: bool
    retry_count: int
    loop_count: int
    raw_request_saved: bool
    raw_response_saved: bool
    headers_saved: bool
    signature_saved: bool
    credential_values_logged: bool
    state_before: str
    state_after: str
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in {
            "http_post_attempted": self.http_post_attempted,
            "result_unknown": self.result_unknown,
            "raw_request_saved": self.raw_request_saved,
            "raw_response_saved": self.raw_response_saved,
            "headers_saved": self.headers_saved,
            "signature_saved": self.signature_saved,
            "credential_values_logged": self.credential_values_logged,
        }.items():
            if type(value) is not bool:
                raise LiveVerificationLiveOrderOnceError(f"{name} must be bool")
        for name, value in {
            "http_post_count": self.http_post_count,
            "retry_count": self.retry_count,
            "loop_count": self.loop_count,
        }.items():
            if type(value) is not int or value < 0:
                raise LiveVerificationLiveOrderOnceError(f"{name} must be non-negative int")
        if self.http_post_count > 1:
            raise LiveVerificationLiveOrderOnceError("HTTP POST count exceeded one")
        for state in (self.state_before, self.state_after):
            if state not in {item.value for item in LiveOrderAttemptState}:
                raise LiveVerificationLiveOrderOnceError("result state is invalid")
        if not isinstance(self.fail_reasons, tuple) or any(
            not isinstance(reason, str) or not reason for reason in self.fail_reasons
        ):
            raise LiveVerificationLiveOrderOnceError("fail_reasons must be tuple[str, ...]")
        if any((
            self.retry_count,
            self.loop_count,
            self.raw_request_saved,
            self.raw_response_saved,
            self.headers_saved,
            self.signature_saved,
            self.credential_values_logged,
        )):
            raise LiveVerificationLiveOrderOnceError(
                "live order result crossed no-leak or no-retry boundary"
            )


class _SensitiveLiveOrderHeaders:
    __slots__ = ("_headers",)

    def __init__(
        self,
        *,
        api_key: str,
        timestamp: str,
        signature_digest: str,
    ) -> None:
        self._headers = {
            "API-KEY": api_key,
            "API-TIMESTAMP": timestamp,
            "API-SIGN": signature_digest,
            "Content-Type": "application/json",
        }

    def __repr__(self) -> str:
        return "_SensitiveLiveOrderHeaders(<redacted>)"

    __str__ = __repr__

    def as_mapping(self) -> Mapping[str, str]:
        return dict(self._headers)

    def header_names(self) -> tuple[str, ...]:
        return tuple(name for name in self._headers if name in LIVE_ORDER_HEADER_NAMES)


LiveOrderTransport = Callable[
    [str, str, _SensitiveLiveOrderHeaders],
    LiveOrderTransportResponse,
]


def build_live_order_outbound_body(
    *,
    side: str | LiveOrderSide,
    client_order_id: str,
) -> LiveOrderOutboundBody:
    """Build the exact live outbound body from an explicit side and client id."""
    return LiveOrderOutboundBody(
        symbol=SUPPORTED_SYMBOL,
        side=_normalize_side(side),
        size=LIVE_ORDER_SIZE,
        clientOrderId=client_order_id,
        executionType=LIVE_ORDER_EXECUTION_TYPE,
    )


def serialize_live_order_body_for_signing(body: LiveOrderOutboundBody) -> str:
    """Return stable JSON used both as signing input and outbound body."""
    _validate_live_order_body(body)
    payload = {
        "symbol": body.symbol,
        "side": body.side.value,
        "size": body.size,
        "clientOrderId": body.clientOrderId,
        "executionType": body.executionType,
    }
    if set(payload) != LIVE_ORDER_BODY_FIELDS:
        raise LiveVerificationLiveOrderOnceError("live outbound body allowlist mismatch")
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def build_step4_approval_gate(
    *,
    issued_at_jst: datetime | None = None,
    approval_id: str | None = None,
) -> Step4ApprovalGate:
    issued = issued_at_jst or _now_jst()
    if issued.tzinfo is None:
        raise LiveVerificationLiveOrderOnceError("issued_at_jst must be timezone-aware")
    normalized_issued = issued.astimezone(ZoneInfo("Asia/Tokyo"))
    expires = normalized_issued + timedelta(seconds=LIVE_ORDER_APPROVAL_TTL_SECONDS)
    generated_approval_id = approval_id or _generate_approval_id()
    _validate_approval_id(generated_approval_id)
    return Step4ApprovalGate(
        approval_id=generated_approval_id,
        issued_at_jst=normalized_issued.isoformat(timespec="seconds"),
        expires_at_jst=expires.isoformat(timespec="seconds"),
        buy_approval_phrase=_approval_phrase(generated_approval_id, LiveOrderSide.BUY),
        sell_approval_phrase=_approval_phrase(generated_approval_id, LiveOrderSide.SELL),
    )


def evaluate_step4_approval(
    *,
    gate: Step4ApprovalGate,
    approval_phrase: str,
    now_jst: datetime | None = None,
) -> Step4ApprovalDecision:
    _ensure_gate_type(gate)
    now = (now_jst or _now_jst()).astimezone(ZoneInfo("Asia/Tokyo"))
    expires = _parse_jst_datetime(gate.expires_at_jst)
    fail_reasons: list[str] = []
    side = "unknown"
    if now > expires:
        fail_reasons.append("approval_expired")
    if approval_phrase == gate.buy_approval_phrase:
        side = LiveOrderSide.BUY.value
    elif approval_phrase == gate.sell_approval_phrase:
        side = LiveOrderSide.SELL.value
    else:
        fail_reasons.append("approval_phrase_mismatch")
        if not approval_phrase.startswith(f"STEP4_APPROVE {gate.approval_id}:"):
            fail_reasons.append("approval_id_mismatch")
    fail_reasons = list(dict.fromkeys(fail_reasons))
    return Step4ApprovalDecision(
        approval_passed=not fail_reasons,
        approval_id=gate.approval_id,
        side=side if not fail_reasons else "unknown",
        fail_reasons=tuple(fail_reasons),
    )


def default_live_order_attempt_ledger_path(
    *,
    now_jst: datetime | None = None,
) -> Path:
    now = (now_jst or _now_jst()).astimezone(ZoneInfo("Asia/Tokyo"))
    return LIVE_ORDER_LEDGER_DIR / f"{now.date().isoformat()}.json"


def load_live_order_attempt_ledger(path: Path) -> LiveOrderAttemptLedger:
    if not path.exists():
        return _missing_ledger(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LiveVerificationLiveOrderOnceError("ledger is unreadable") from error
    if not isinstance(payload, dict):
        raise LiveVerificationLiveOrderOnceError("ledger must be an object")
    return LiveOrderAttemptLedger(
        ledger_path=str(path),
        state=str(payload.get("state", "MISSING")),
        attempt_count=_int_from_payload(payload.get("attempt_count", 0)),
        prepared_at=str(payload.get("prepared_at", "")),
        approval_id_hash=str(payload.get("approval_id_hash", "")),
        clientOrderId=str(payload.get("clientOrderId", "")),
        post_started_at=str(payload.get("post_started_at", "")),
        post_finished_at=str(payload.get("post_finished_at", "")),
        result_category=str(payload.get("result_category", "")),
    )


def expire_prepared_attempt_if_needed(
    *,
    ledger_path: Path,
    now_jst: datetime | None = None,
) -> LiveOrderAttemptLedger:
    ledger = load_live_order_attempt_ledger(ledger_path)
    if ledger.state != LiveOrderAttemptState.PREPARED.value:
        return ledger
    now = (now_jst or _now_jst()).astimezone(ZoneInfo("Asia/Tokyo"))
    prepared_at = _parse_jst_datetime(ledger.prepared_at)
    if now <= prepared_at + timedelta(seconds=LIVE_ORDER_APPROVAL_TTL_SECONDS):
        return ledger
    expired = _replace_ledger(
        ledger,
        state=LiveOrderAttemptState.EXPIRED.value,
        result_category="approval_expired",
    )
    _write_ledger_atomic(ledger_path, expired)
    return expired


def prepare_live_order_attempt(
    *,
    ledger_path: Path,
    approval_gate: Step4ApprovalGate,
    client_order_id: str,
    now_jst: datetime | None = None,
) -> LiveOrderAttemptLedger:
    _ensure_gate_type(approval_gate)
    _validate_client_order_id(client_order_id)
    ledger = expire_prepared_attempt_if_needed(ledger_path=ledger_path, now_jst=now_jst)
    _ensure_can_prepare(ledger)
    prepared = LiveOrderAttemptLedger(
        ledger_path=str(ledger_path),
        state=LiveOrderAttemptState.PREPARED.value,
        attempt_count=0,
        prepared_at=approval_gate.issued_at_jst,
        approval_id_hash=_approval_id_hash(approval_gate.approval_id),
        clientOrderId=client_order_id,
        post_started_at="",
        post_finished_at="",
        result_category="prepared",
    )
    _write_ledger_atomic(ledger_path, prepared)
    return prepared


def mark_live_order_post_started(
    *,
    ledger_path: Path,
    approval_id: str,
    now_jst: datetime | None = None,
) -> LiveOrderAttemptLedger:
    ledger = load_live_order_attempt_ledger(ledger_path)
    now = (now_jst or _now_jst()).astimezone(ZoneInfo("Asia/Tokyo"))
    _ensure_can_start_post(ledger=ledger, approval_id=approval_id, now_jst=now)
    started = _replace_ledger(
        ledger,
        state=LiveOrderAttemptState.POST_STARTED.value,
        attempt_count=1,
        post_started_at=now.isoformat(timespec="seconds"),
        result_category="post_started",
    )
    _write_ledger_atomic(ledger_path, started)
    return started


def mark_live_order_post_completed(
    *,
    ledger_path: Path,
    result_category: str = "success",
    now_jst: datetime | None = None,
) -> LiveOrderAttemptLedger:
    ledger = load_live_order_attempt_ledger(ledger_path)
    if ledger.state != LiveOrderAttemptState.POST_STARTED.value:
        raise LiveVerificationLiveOrderOnceError("ledger must be POST_STARTED")
    finished_at = (now_jst or _now_jst()).astimezone(ZoneInfo("Asia/Tokyo"))
    completed = _replace_ledger(
        ledger,
        state=LiveOrderAttemptState.POST_COMPLETED.value,
        post_finished_at=finished_at.isoformat(timespec="seconds"),
        result_category=result_category,
    )
    _write_ledger_atomic(ledger_path, completed)
    return completed


def mark_live_order_result_unknown(
    *,
    ledger_path: Path,
    now_jst: datetime | None = None,
) -> LiveOrderAttemptLedger:
    ledger = load_live_order_attempt_ledger(ledger_path)
    if ledger.state != LiveOrderAttemptState.POST_STARTED.value:
        raise LiveVerificationLiveOrderOnceError("ledger must be POST_STARTED")
    finished_at = (now_jst or _now_jst()).astimezone(ZoneInfo("Asia/Tokyo"))
    unknown = _replace_ledger(
        ledger,
        state=LiveOrderAttemptState.RESULT_UNKNOWN.value,
        post_finished_at=finished_at.isoformat(timespec="seconds"),
        result_category="result_unknown",
    )
    _write_ledger_atomic(ledger_path, unknown)
    return unknown


def prepare_one_shot_live_order(
    *,
    ledger_path: Path | None = None,
    issued_at_jst: datetime | None = None,
    approval_id: str | None = None,
    client_order_id: str | None = None,
) -> OneShotLiveOrderPrepared:
    gate = build_step4_approval_gate(
        issued_at_jst=issued_at_jst,
        approval_id=approval_id,
    )
    generated_client_order_id = client_order_id or _generate_client_order_id(
        issued_at_jst=issued_at_jst,
    )
    path = ledger_path or default_live_order_attempt_ledger_path(
        now_jst=issued_at_jst,
    )
    ledger = prepare_live_order_attempt(
        ledger_path=path,
        approval_gate=gate,
        client_order_id=generated_client_order_id,
        now_jst=issued_at_jst,
    )
    return OneShotLiveOrderPrepared(
        approval_gate=gate,
        ledger=ledger,
        clientOrderId=generated_client_order_id,
        http_post_enabled=False,
        live_order_allowed_now=False,
        raw_request_saved=False,
        raw_response_saved=False,
        credential_values_logged=False,
    )


def execute_one_shot_live_order(
    *,
    gate: Step4ApprovalGate,
    approval_phrase: str,
    ledger_path: Path,
    api_key: str,
    api_secret: str,
    timestamp_factory: Callable[[], str],
    transport: LiveOrderTransport | None = None,
    allow_live_http_post: bool = False,
    now_jst: datetime | None = None,
) -> OneShotLiveOrderResult:
    """Execute one approved order with an explicit transport; disabled by default."""
    _ensure_gate_type(gate)
    state_before = load_live_order_attempt_ledger(ledger_path).state
    if not allow_live_http_post:
        return _blocked_result(
            state_before=state_before,
            state_after=state_before,
            fail_reason="live_http_post_not_explicitly_allowed",
        )
    if transport is None:
        return _blocked_result(
            state_before=state_before,
            state_after=state_before,
            fail_reason="transport_required",
        )
    decision = evaluate_step4_approval(
        gate=gate,
        approval_phrase=approval_phrase,
        now_jst=now_jst,
    )
    if not decision.approval_passed:
        return _blocked_result(
            state_before=state_before,
            state_after=state_before,
            fail_reason="approval_failed",
            extra_reasons=decision.fail_reasons,
        )
    _require_non_empty("api_key", api_key)
    _require_non_empty("api_secret", api_secret)
    timestamp = timestamp_factory()
    _require_non_empty("timestamp", timestamp)
    started = mark_live_order_post_started(
        ledger_path=ledger_path,
        approval_id=gate.approval_id,
        now_jst=now_jst,
    )
    body = build_live_order_outbound_body(
        side=decision.side,
        client_order_id=started.clientOrderId,
    )
    body_serialization = serialize_live_order_body_for_signing(body)
    sensitive_headers = _build_sensitive_headers(
        api_key=api_key,
        api_secret=api_secret,
        timestamp=timestamp,
        body_serialization=body_serialization,
    )
    try:
        transport_response = transport(
            LIVE_ORDER_ENDPOINT_URL,
            body_serialization,
            sensitive_headers,
        )
    except Exception:
        unknown = mark_live_order_result_unknown(ledger_path=ledger_path, now_jst=now_jst)
        return OneShotLiveOrderResult(
            http_post_attempted=True,
            http_post_count=1,
            transport_result="result_unknown",
            api_status_success="unknown",
            response_data_present="unknown",
            result_unknown=True,
            retry_count=0,
            loop_count=0,
            raw_request_saved=False,
            raw_response_saved=False,
            headers_saved=False,
            signature_saved=False,
            credential_values_logged=False,
            state_before=state_before,
            state_after=unknown.state,
            fail_reasons=("result_unknown",),
        )
    completed = mark_live_order_post_completed(
        ledger_path=ledger_path,
        result_category=transport_response.transport_result,
        now_jst=now_jst,
    )
    return OneShotLiveOrderResult(
        http_post_attempted=True,
        http_post_count=1,
        transport_result=transport_response.transport_result,
        api_status_success=transport_response.api_status_success,
        response_data_present=transport_response.response_data_present,
        result_unknown=transport_response.transport_result == "result_unknown",
        retry_count=0,
        loop_count=0,
        raw_request_saved=False,
        raw_response_saved=False,
        headers_saved=False,
        signature_saved=False,
        credential_values_logged=False,
        state_before=state_before,
        state_after=completed.state,
        fail_reasons=()
        if transport_response.transport_result == "success"
        else (transport_response.transport_result,),
    )


def post_live_order_with_httpx(
    endpoint_url: str,
    body_serialization: str,
    sensitive_headers: _SensitiveLiveOrderHeaders,
) -> LiveOrderTransportResponse:
    """Real transport function; callers must pass it explicitly."""
    _require_non_empty("endpoint_url", endpoint_url)
    _require_non_empty("body_serialization", body_serialization)
    if endpoint_url != LIVE_ORDER_ENDPOINT_URL:
        raise LiveVerificationLiveOrderOnceError("unexpected live order endpoint")
    with httpx.Client(
        timeout=LIVE_ORDER_HTTP_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as client:
        response = client.post(
            endpoint_url,
            content=body_serialization,
            headers=sensitive_headers.as_mapping(),
        )
    try:
        payload = response.json()
    except ValueError as error:
        raise LiveVerificationLiveOrderOnceError("live order response was not JSON") from error
    if not isinstance(payload, Mapping):
        raise LiveVerificationLiveOrderOnceError("live order response was not an object")
    api_success = response.status_code < 400 and payload.get("status") == 0
    return LiveOrderTransportResponse(
        transport_result="success" if api_success else "api_rejected",
        api_status_success="true" if api_success else "false",
        response_data_present="true" if "data" in payload else "false",
    )


def _approval_phrase(approval_id: str, side: LiveOrderSide) -> str:
    return (
        f"STEP4_APPROVE {approval_id}: USD_JPY 100通貨 {side.value} "
        "の1回限定実注文を承認します。実資金損失、API手数料、スプレッド、OPEN建玉が残る可能性を理解しています。"
        "外国為替FX専用APIキーの注文に必要な最小権限、IP制限、漏洩疑いなしを確認しました。"
        "重要経済指標の前後ではないことを確認しました。retry、loop、追加注文、注文変更、取消、決済は禁止し、"
        "結果不明時は停止します。"
    )


def _build_sensitive_headers(
    *,
    api_key: str,
    api_secret: str,
    timestamp: str,
    body_serialization: str,
) -> _SensitiveLiveOrderHeaders:
    signature_digest = _create_live_order_signature(
        api_secret=api_secret,
        timestamp=timestamp,
        body_serialization=body_serialization,
    )
    return _SensitiveLiveOrderHeaders(
        api_key=api_key,
        timestamp=timestamp,
        signature_digest=signature_digest,
    )


def _create_live_order_signature(
    *,
    api_secret: str,
    timestamp: str,
    body_serialization: str,
) -> str:
    _require_non_empty("api_secret", api_secret)
    _require_non_empty("timestamp", timestamp)
    signing_source = (
        f"{timestamp}{LIVE_ORDER_METHOD}{LIVE_ORDER_SIGNING_PATH}{body_serialization}"
    )
    return hmac.new(
        api_secret.encode("utf-8"),
        signing_source.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _validate_live_order_body(body: LiveOrderOutboundBody) -> None:
    if body.symbol != SUPPORTED_SYMBOL:
        raise LiveVerificationLiveOrderOnceError("symbol must be USD_JPY")
    if not isinstance(body.side, LiveOrderSide):
        raise LiveVerificationLiveOrderOnceError("side must be BUY or SELL")
    if body.size != LIVE_ORDER_SIZE:
        raise LiveVerificationLiveOrderOnceError("size must be 100")
    if body.executionType != LIVE_ORDER_EXECUTION_TYPE:
        raise LiveVerificationLiveOrderOnceError("executionType must be MARKET")
    _validate_client_order_id(body.clientOrderId)


def _normalize_side(side: str | LiveOrderSide) -> LiveOrderSide:
    if isinstance(side, LiveOrderSide):
        return side
    if isinstance(side, str):
        try:
            return LiveOrderSide(side.strip().upper())
        except ValueError as error:
            raise LiveVerificationLiveOrderOnceError(
                "side must be BUY or SELL"
            ) from error
    raise LiveVerificationLiveOrderOnceError("side must be BUY or SELL")


def _validate_client_order_id(client_order_id: str) -> None:
    if not isinstance(client_order_id, str) or not client_order_id:
        raise LiveVerificationLiveOrderOnceError("clientOrderId is required")
    if len(client_order_id) > 36 or not client_order_id.isalnum():
        raise LiveVerificationLiveOrderOnceError(
            "clientOrderId must be alphanumeric and 36 chars or fewer"
        )


def _validate_approval_id(approval_id: str) -> None:
    if (
        not isinstance(approval_id, str)
        or not approval_id.startswith("STEP4-")
        or len(approval_id) != len("STEP4-") + 8
        or not approval_id.removeprefix("STEP4-").isalnum()
    ):
        raise LiveVerificationLiveOrderOnceError("approval_id is invalid")


def _ensure_gate_type(gate: Step4ApprovalGate) -> None:
    if not isinstance(gate, Step4ApprovalGate):
        raise LiveVerificationLiveOrderOnceError("approval gate is required")


def _ensure_can_prepare(ledger: LiveOrderAttemptLedger) -> None:
    if ledger.state in {
        LiveOrderAttemptState.POST_STARTED.value,
        LiveOrderAttemptState.POST_COMPLETED.value,
        LiveOrderAttemptState.RESULT_UNKNOWN.value,
    }:
        raise LiveVerificationLiveOrderOnceError("ledger already has a POST attempt")
    if ledger.attempt_count >= 1:
        raise LiveVerificationLiveOrderOnceError("ledger attempt_count already used")
    if ledger.state == LiveOrderAttemptState.PREPARED.value:
        raise LiveVerificationLiveOrderOnceError("ledger already has an active approval")


def _ensure_can_start_post(
    *,
    ledger: LiveOrderAttemptLedger,
    approval_id: str,
    now_jst: datetime,
) -> None:
    if ledger.state != LiveOrderAttemptState.PREPARED.value:
        raise LiveVerificationLiveOrderOnceError("ledger must be PREPARED")
    if ledger.attempt_count >= 1:
        raise LiveVerificationLiveOrderOnceError("ledger attempt_count already used")
    if ledger.approval_id_hash != _approval_id_hash(approval_id):
        raise LiveVerificationLiveOrderOnceError("approval_id hash mismatch")
    prepared_at = _parse_jst_datetime(ledger.prepared_at)
    if now_jst > prepared_at + timedelta(seconds=LIVE_ORDER_APPROVAL_TTL_SECONDS):
        raise LiveVerificationLiveOrderOnceError("approval expired")


def _missing_ledger(path: Path) -> LiveOrderAttemptLedger:
    return LiveOrderAttemptLedger(
        ledger_path=str(path),
        state=LiveOrderAttemptState.MISSING.value,
        attempt_count=0,
        prepared_at="",
        approval_id_hash="",
        clientOrderId="",
        post_started_at="",
        post_finished_at="",
        result_category="missing",
    )


def _replace_ledger(ledger: LiveOrderAttemptLedger, **updates: object) -> LiveOrderAttemptLedger:
    values = {
        "ledger_path": ledger.ledger_path,
        "state": ledger.state,
        "attempt_count": ledger.attempt_count,
        "prepared_at": ledger.prepared_at,
        "approval_id_hash": ledger.approval_id_hash,
        "clientOrderId": ledger.clientOrderId,
        "post_started_at": ledger.post_started_at,
        "post_finished_at": ledger.post_finished_at,
        "result_category": ledger.result_category,
    }
    values.update(updates)
    return LiveOrderAttemptLedger(**values)


def _write_ledger_atomic(path: Path, ledger: LiveOrderAttemptLedger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": ledger.state,
        "attempt_count": ledger.attempt_count,
        "prepared_at": ledger.prepared_at,
        "approval_id_hash": ledger.approval_id_hash,
        "clientOrderId": ledger.clientOrderId,
        "post_started_at": ledger.post_started_at,
        "post_finished_at": ledger.post_finished_at,
        "result_category": ledger.result_category,
    }
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
        os.chmod(path, 0o600)
    finally:
        tmp_path = Path(tmp_name)
        if tmp_path.exists():
            tmp_path.unlink()


def _blocked_result(
    *,
    state_before: str,
    state_after: str,
    fail_reason: str,
    extra_reasons: tuple[str, ...] = (),
) -> OneShotLiveOrderResult:
    return OneShotLiveOrderResult(
        http_post_attempted=False,
        http_post_count=0,
        transport_result="transport_error",
        api_status_success="unknown",
        response_data_present="unknown",
        result_unknown=False,
        retry_count=0,
        loop_count=0,
        raw_request_saved=False,
        raw_response_saved=False,
        headers_saved=False,
        signature_saved=False,
        credential_values_logged=False,
        state_before=state_before,
        state_after=state_after,
        fail_reasons=tuple(dict.fromkeys((fail_reason, *extra_reasons))),
    )


def _approval_id_hash(approval_id: str) -> str:
    _validate_approval_id(approval_id)
    return hashlib.sha256(approval_id.encode("utf-8")).hexdigest()


def _generate_approval_id() -> str:
    return "STEP4-" + secrets.token_hex(4).upper()


def _generate_client_order_id(*, issued_at_jst: datetime | None = None) -> str:
    now = (issued_at_jst or _now_jst()).astimezone(ZoneInfo("Asia/Tokyo"))
    return f"S4{now.strftime('%Y%m%d%H%M%S')}{secrets.token_hex(4).upper()}"


def _parse_jst_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise LiveVerificationLiveOrderOnceError("JST datetime is invalid") from error
    if parsed.tzinfo is None:
        raise LiveVerificationLiveOrderOnceError("JST datetime must be timezone-aware")
    return parsed.astimezone(ZoneInfo("Asia/Tokyo"))


def _now_jst() -> datetime:
    return datetime.now(ZoneInfo("Asia/Tokyo"))


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationLiveOrderOnceError(f"{field_name} is required")


def _int_from_payload(value: object) -> int:
    if type(value) is not int:
        raise LiveVerificationLiveOrderOnceError("ledger attempt_count must be int")
    return value
