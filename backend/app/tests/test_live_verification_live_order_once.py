from __future__ import annotations

import json
import stat
from dataclasses import asdict, fields
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.live_verification.errors import LiveVerificationLiveOrderOnceError
from app.live_verification.live_order_once import (
    LIVE_ORDER_APPROVAL_ACK_TOKENS,
    LIVE_ORDER_APPROVAL_ID_PREFIX,
    LIVE_ORDER_APPROVAL_TTL_SECONDS,
    LIVE_ORDER_BODY_FIELDS,
    LIVE_ORDER_ENDPOINT_URL,
    LIVE_ORDER_EXECUTION_TYPE,
    LIVE_ORDER_METHOD,
    LIVE_ORDER_SIGNING_PATH,
    LIVE_ORDER_SIZE,
    LiveOrderAttemptLedger,
    LiveOrderAttemptState,
    LiveOrderOutboundBody,
    LiveOrderSide,
    LiveOrderTransportResponse,
    OneShotLiveOrderPrepared,
    OneShotLiveOrderResult,
    Step4ApprovalDecision,
    Step4ApprovalGate,
    build_live_order_outbound_body,
    build_step4_approval_gate,
    evaluate_step4_approval,
    execute_one_shot_live_order,
    expire_prepared_attempt_if_needed,
    load_live_order_attempt_ledger,
    mark_live_order_post_completed,
    mark_live_order_post_started,
    mark_live_order_result_unknown,
    prepare_live_order_attempt,
    prepare_one_shot_live_order,
    serialize_live_order_body_for_signing,
)

DUMMY_API_KEY = "DUMMYAPIKEYVALUE"
DUMMY_API_SECRET = "DUMMYAPISECRETVALUE"
DUMMY_SIGNATURE = "DUMMYSIGNATUREVALUE"
DUMMY_RAW_REQUEST = "DUMMY_RAW_REQUEST_VALUE"
DUMMY_RAW_RESPONSE = "DUMMY_RAW_RESPONSE_VALUE"
FIXED_APPROVAL_ID = "STEP4F-1234ABCD"
LEGACY_STEP4_APPROVAL_ID = "STEP4-1234ABCD"
FIXED_CLIENT_ORDER_ID = "S420260625100000ABCD1234"
FIXED_NOW = datetime(2026, 6, 25, 10, 0, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
EXPECTED_APPROVAL_TTL_SECONDS = 300
EXPECTED_BUY_APPROVAL_COMMAND = (
    f"STEP4_APPROVE {FIXED_APPROVAL_ID} SIDE=BUY SYMBOL=USD_JPY SIZE=100 "
    "ACK_RISK=YES ACK_OPEN_POSITION=YES ACK_API_SCOPE=YES "
    "ACK_ORDER_PERMISSION=YES ACK_IP_ACCOUNT_CHECK=YES ACK_NO_EVENT=YES "
    "ACK_NO_RETRY=YES ACK_NO_LOOP=YES ACK_NO_ADD=YES ACK_NO_CHANGE=YES "
    "ACK_NO_CANCEL=YES ACK_NO_CLOSE=YES ACK_STOP_ON_UNKNOWN=YES"
)
EXPECTED_SELL_APPROVAL_COMMAND = EXPECTED_BUY_APPROVAL_COMMAND.replace(
    "SIDE=BUY",
    "SIDE=SELL",
)
LEGACY_COMPACT_BUY_APPROVAL_COMMAND = (
    f"STEP4_APPROVE {FIXED_APPROVAL_ID} SIDE=BUY SYMBOL=USD_JPY SIZE=100 "
    "ACK_RISK=YES ACK_OPEN_POSITION=YES ACK_API_SCOPE=YES ACK_NO_EVENT=YES "
    "ACK_NO_RETRY=YES ACK_NO_LOOP=YES ACK_NO_ADD=YES ACK_NO_CHANGE=YES "
    "ACK_NO_CANCEL=YES ACK_NO_CLOSE=YES ACK_STOP_ON_UNKNOWN=YES"
)
OLD_JAPANESE_BUY_APPROVAL_PHRASE = (
    f"STEP4_APPROVE {FIXED_APPROVAL_ID}: USD_JPY 100通貨 BUY "
    "の1回限定実注文を承認します。実資金損失、API手数料、スプレッド、OPEN建玉が残る可能性を理解しています。"
    "外国為替FX専用APIキーの注文に必要な最小権限、IP制限、漏洩疑いなしを確認しました。"
    "重要経済指標の前後ではないことを確認しました。retry、loop、追加注文、注文変更、取消、決済は禁止し、"
    "結果不明時は停止します。"
)

EXPECTED_BODY_FIELDS = {
    "symbol",
    "side",
    "size",
    "clientOrderId",
    "executionType",
}
EXPECTED_GATE_FIELDS = {
    "approval_id",
    "issued_at_jst",
    "expires_at_jst",
    "buy_approval_phrase",
    "sell_approval_phrase",
}
EXPECTED_DECISION_FIELDS = {
    "approval_passed",
    "approval_id",
    "side",
    "fail_reasons",
}
EXPECTED_LEDGER_FIELDS = {
    "ledger_path",
    "state",
    "attempt_count",
    "prepared_at",
    "approval_id_hash",
    "clientOrderId",
    "post_started_at",
    "post_finished_at",
    "result_category",
}
EXPECTED_PREPARED_FIELDS = {
    "approval_gate",
    "ledger",
    "clientOrderId",
    "http_post_enabled",
    "live_order_allowed_now",
    "raw_request_saved",
    "raw_response_saved",
    "credential_values_logged",
}
EXPECTED_RESULT_FIELDS = {
    "http_post_attempted",
    "http_post_count",
    "transport_result",
    "api_status_success",
    "response_data_present",
    "result_unknown",
    "retry_count",
    "loop_count",
    "raw_request_saved",
    "raw_response_saved",
    "headers_saved",
    "signature_saved",
    "credential_values_logged",
    "state_before",
    "state_after",
    "fail_reasons",
}


def _ledger_path(tmp_path: Path) -> Path:
    return tmp_path / "2026-06-25.json"


def _gate(*, issued_at_jst: datetime = FIXED_NOW) -> Step4ApprovalGate:
    return build_step4_approval_gate(
        issued_at_jst=issued_at_jst,
        approval_id=FIXED_APPROVAL_ID,
    )


def _prepare(tmp_path: Path, *, issued_at_jst: datetime = FIXED_NOW) -> OneShotLiveOrderPrepared:
    return prepare_one_shot_live_order(
        ledger_path=_ledger_path(tmp_path),
        issued_at_jst=issued_at_jst,
        approval_id=FIXED_APPROVAL_ID,
        client_order_id=FIXED_CLIENT_ORDER_ID,
    )


def test_live_order_outbound_body_uses_allowlist_and_stable_json() -> None:
    body = build_live_order_outbound_body(
        side=LiveOrderSide.BUY,
        client_order_id=FIXED_CLIENT_ORDER_ID,
    )

    body_json = serialize_live_order_body_for_signing(body)
    same_body_json = serialize_live_order_body_for_signing(body)
    parsed = json.loads(body_json)

    assert isinstance(body, LiveOrderOutboundBody)
    assert body.symbol == "USD_JPY"
    assert body.side is LiveOrderSide.BUY
    assert body.size == LIVE_ORDER_SIZE == "100"
    assert body.executionType == LIVE_ORDER_EXECUTION_TYPE == "MARKET"
    assert set(parsed) == LIVE_ORDER_BODY_FIELDS == EXPECTED_BODY_FIELDS
    assert parsed == {
        "clientOrderId": FIXED_CLIENT_ORDER_ID,
        "executionType": "MARKET",
        "side": "BUY",
        "size": "100",
        "symbol": "USD_JPY",
    }
    assert body_json == same_body_json
    assert "timeInForce" not in parsed
    assert "settleType" not in parsed
    assert "orderType" not in parsed
    assert "limitPrice" not in parsed
    assert "stopPrice" not in parsed
    assert set(asdict(body)) == EXPECTED_BODY_FIELDS
    assert {field.name for field in fields(LiveOrderOutboundBody)} == EXPECTED_BODY_FIELDS


def test_live_order_outbound_body_rejects_unknown_side() -> None:
    with pytest.raises(LiveVerificationLiveOrderOnceError):
        build_live_order_outbound_body(
            side="EITHER",
            client_order_id=FIXED_CLIENT_ORDER_ID,
        )


@pytest.mark.parametrize(
    "client_order_id",
    [
        "",
        "not-alpha-numeric-123",
        "A" * 37,
    ],
)
def test_live_order_outbound_body_rejects_invalid_client_order_id(
    client_order_id: str,
) -> None:
    with pytest.raises(LiveVerificationLiveOrderOnceError):
        build_live_order_outbound_body(
            side="BUY",
            client_order_id=client_order_id,
        )


def test_approval_gate_generates_exact_buy_and_sell_commands() -> None:
    gate = _gate()

    assert isinstance(gate, Step4ApprovalGate)
    assert LIVE_ORDER_APPROVAL_TTL_SECONDS == EXPECTED_APPROVAL_TTL_SECONDS
    assert LIVE_ORDER_APPROVAL_ID_PREFIX == "STEP4F-"
    assert gate.approval_id == FIXED_APPROVAL_ID
    assert gate.issued_at_jst == "2026-06-25T10:00:00+09:00"
    assert gate.expires_at_jst == "2026-06-25T10:05:00+09:00"
    assert LIVE_ORDER_APPROVAL_ACK_TOKENS == (
        "ACK_RISK=YES",
        "ACK_OPEN_POSITION=YES",
        "ACK_API_SCOPE=YES",
        "ACK_ORDER_PERMISSION=YES",
        "ACK_IP_ACCOUNT_CHECK=YES",
        "ACK_NO_EVENT=YES",
        "ACK_NO_RETRY=YES",
        "ACK_NO_LOOP=YES",
        "ACK_NO_ADD=YES",
        "ACK_NO_CHANGE=YES",
        "ACK_NO_CANCEL=YES",
        "ACK_NO_CLOSE=YES",
        "ACK_STOP_ON_UNKNOWN=YES",
    )
    assert gate.buy_approval_phrase == EXPECTED_BUY_APPROVAL_COMMAND
    assert gate.sell_approval_phrase == EXPECTED_SELL_APPROVAL_COMMAND
    assert "\n" not in gate.buy_approval_phrase
    assert "  " not in gate.buy_approval_phrase
    assert gate.buy_approval_phrase.isascii()
    assert gate.sell_approval_phrase.isascii()
    assert set(asdict(gate)) == EXPECTED_GATE_FIELDS


def test_approval_gate_expires_at_issued_plus_300_seconds() -> None:
    issued_at = datetime(2026, 6, 25, 10, 12, 34, tzinfo=ZoneInfo("Asia/Tokyo"))

    gate = _gate(issued_at_jst=issued_at)

    assert gate.issued_at_jst == "2026-06-25T10:12:34+09:00"
    assert gate.expires_at_jst == "2026-06-25T10:17:34+09:00"


@pytest.mark.parametrize(
    ("phrase_attr", "expected_side"),
    [
        ("buy_approval_phrase", "BUY"),
        ("sell_approval_phrase", "SELL"),
    ],
)
def test_approval_exact_phrase_passes(
    phrase_attr: str,
    expected_side: str,
) -> None:
    gate = _gate()

    decision = evaluate_step4_approval(
        gate=gate,
        approval_phrase=getattr(gate, phrase_attr),
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )

    assert isinstance(decision, Step4ApprovalDecision)
    assert decision.approval_passed is True
    assert decision.side == expected_side
    assert decision.fail_reasons == ()
    assert set(asdict(decision)) == EXPECTED_DECISION_FIELDS


@pytest.mark.parametrize("elapsed_seconds", [121, 299, 300])
def test_approval_within_300_seconds_passes(elapsed_seconds: int) -> None:
    gate = _gate()

    decision = evaluate_step4_approval(
        gate=gate,
        approval_phrase=gate.buy_approval_phrase,
        now_jst=FIXED_NOW + timedelta(seconds=elapsed_seconds),
    )

    assert decision.approval_passed is True
    assert decision.side == "BUY"
    assert decision.fail_reasons == ()


def test_approval_id_mismatch_fails() -> None:
    gate = _gate()
    phrase = gate.buy_approval_phrase.replace(FIXED_APPROVAL_ID, "STEP4F-FFFF0000")

    decision = evaluate_step4_approval(
        gate=gate,
        approval_phrase=phrase,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )

    assert decision.approval_passed is False
    assert "approval_phrase_mismatch" in decision.fail_reasons
    assert "approval_id_mismatch" in decision.fail_reasons
    assert decision.side == "unknown"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda phrase: phrase.replace("SIDE=BUY", "SIDE=HOLD"),
        lambda phrase: phrase.replace("SYMBOL=USD_JPY", "SYMBOL=EUR_JPY"),
        lambda phrase: phrase.replace("SIZE=100", "SIZE=1000"),
        lambda phrase: phrase.replace("ACK_RISK=YES", "ACK_RISK=NO"),
        lambda phrase: phrase.replace("ACK_ORDER_PERMISSION=YES", "ACK_ORDER_PERMISSION=NO"),
        lambda phrase: phrase.replace("ACK_IP_ACCOUNT_CHECK=YES", "ACK_IP_ACCOUNT_CHECK=NO"),
        lambda phrase: f"{phrase} EXTRA=YES",
        lambda phrase: phrase.replace(" SIZE=100 ", "  SIZE=100 "),
        lambda phrase: phrase.replace(" ACK_RISK=YES ", "\nACK_RISK=YES "),
    ],
)
def test_buy_approval_command_requires_exact_tokens(mutation: object) -> None:
    gate = _gate()
    phrase = mutation(gate.buy_approval_phrase)

    decision = evaluate_step4_approval(
        gate=gate,
        approval_phrase=phrase,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )

    assert decision.approval_passed is False
    assert "approval_phrase_mismatch" in decision.fail_reasons
    assert decision.side == "unknown"


@pytest.mark.parametrize("token", LIVE_ORDER_APPROVAL_ACK_TOKENS)
def test_approval_command_rejects_missing_ack_token(token: str) -> None:
    gate = _gate()
    phrase = gate.buy_approval_phrase.replace(f" {token}", "")

    decision = evaluate_step4_approval(
        gate=gate,
        approval_phrase=phrase,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )

    assert decision.approval_passed is False
    assert "approval_phrase_mismatch" in decision.fail_reasons
    assert decision.side == "unknown"


def test_legacy_compact_approval_command_without_step4f_ack_tokens_fails() -> None:
    decision = evaluate_step4_approval(
        gate=_gate(),
        approval_phrase=LEGACY_COMPACT_BUY_APPROVAL_COMMAND,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )

    assert decision.approval_passed is False
    assert "approval_phrase_mismatch" in decision.fail_reasons
    assert decision.side == "unknown"


def test_step4_approval_id_prefix_fails_for_step4f_gate() -> None:
    with pytest.raises(LiveVerificationLiveOrderOnceError):
        build_step4_approval_gate(
            issued_at_jst=FIXED_NOW,
            approval_id=LEGACY_STEP4_APPROVAL_ID,
        )


def test_old_japanese_approval_phrase_fails() -> None:
    decision = evaluate_step4_approval(
        gate=_gate(),
        approval_phrase=OLD_JAPANESE_BUY_APPROVAL_PHRASE,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )

    assert decision.approval_passed is False
    assert "approval_phrase_mismatch" in decision.fail_reasons
    assert decision.side == "unknown"


def test_approval_expiry_after_300_seconds_fails() -> None:
    gate = _gate()

    decision = evaluate_step4_approval(
        gate=gate,
        approval_phrase=gate.buy_approval_phrase,
        now_jst=FIXED_NOW + timedelta(seconds=301),
    )

    assert decision.approval_passed is False
    assert decision.fail_reasons == ("approval_expired",)
    assert decision.side == "unknown"


@pytest.mark.parametrize(
    "phrase",
    [
        "STEP4_APPROVE STEP4F-1234ABCD",
        "OK",
        "続行",
        "任せる",
        "どちらでも",
        "USD_JPY 100通貨を承認",
    ],
)
def test_approval_partial_or_ambiguous_phrase_fails(phrase: str) -> None:
    decision = evaluate_step4_approval(
        gate=_gate(),
        approval_phrase=phrase,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )

    assert decision.approval_passed is False
    assert "approval_phrase_mismatch" in decision.fail_reasons
    assert decision.side == "unknown"


def test_ledger_missing_to_prepared(tmp_path: Path) -> None:
    prepared = _prepare(tmp_path)
    ledger = load_live_order_attempt_ledger(_ledger_path(tmp_path))

    assert isinstance(prepared, OneShotLiveOrderPrepared)
    assert isinstance(ledger, LiveOrderAttemptLedger)
    assert ledger.state == LiveOrderAttemptState.PREPARED.value
    assert ledger.attempt_count == 0
    assert ledger.clientOrderId == FIXED_CLIENT_ORDER_ID
    assert ledger.approval_id_hash != FIXED_APPROVAL_ID
    assert len(ledger.approval_id_hash) == 64
    assert prepared.http_post_enabled is False
    assert prepared.live_order_allowed_now is False
    assert stat.S_IMODE(_ledger_path(tmp_path).stat().st_mode) == 0o600
    assert set(asdict(ledger)) == EXPECTED_LEDGER_FIELDS
    assert set(asdict(prepared)) == EXPECTED_PREPARED_FIELDS


def test_ledger_prepared_expiry_transitions_to_expired(tmp_path: Path) -> None:
    _prepare(tmp_path, issued_at_jst=FIXED_NOW)

    expired = expire_prepared_attempt_if_needed(
        ledger_path=_ledger_path(tmp_path),
        now_jst=FIXED_NOW + timedelta(seconds=301),
    )

    assert expired.state == LiveOrderAttemptState.EXPIRED.value
    assert expired.attempt_count == 0
    assert expired.result_category == "approval_expired"


def test_ledger_prepared_at_300_seconds_is_not_expired(tmp_path: Path) -> None:
    _prepare(tmp_path, issued_at_jst=FIXED_NOW)

    ledger = expire_prepared_attempt_if_needed(
        ledger_path=_ledger_path(tmp_path),
        now_jst=FIXED_NOW + timedelta(seconds=300),
    )

    assert ledger.state == LiveOrderAttemptState.PREPARED.value
    assert ledger.attempt_count == 0
    assert ledger.result_category == "prepared"


def test_expired_ledger_allows_new_prepare(tmp_path: Path) -> None:
    _prepare(tmp_path, issued_at_jst=FIXED_NOW)
    expire_prepared_attempt_if_needed(
        ledger_path=_ledger_path(tmp_path),
        now_jst=FIXED_NOW + timedelta(seconds=301),
    )
    new_gate = build_step4_approval_gate(
        issued_at_jst=FIXED_NOW + timedelta(seconds=360),
        approval_id="STEP4F-ABCDEF12",
    )

    ledger = prepare_live_order_attempt(
        ledger_path=_ledger_path(tmp_path),
        approval_gate=new_gate,
        client_order_id="S420260625100300ABCD1234",
        now_jst=FIXED_NOW + timedelta(seconds=360),
    )

    assert ledger.state == LiveOrderAttemptState.PREPARED.value
    assert ledger.attempt_count == 0
    assert ledger.approval_id_hash != load_live_order_attempt_ledger(
        _ledger_path(tmp_path)
    ).clientOrderId


@pytest.mark.parametrize(
    "state_func",
    [
        "post_started",
        "post_completed",
        "result_unknown",
    ],
)
def test_ledger_blocks_second_post_states(tmp_path: Path, state_func: str) -> None:
    _prepare(tmp_path)
    mark_live_order_post_started(
        ledger_path=_ledger_path(tmp_path),
        approval_id=FIXED_APPROVAL_ID,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )
    if state_func == "post_completed":
        mark_live_order_post_completed(
            ledger_path=_ledger_path(tmp_path),
            now_jst=FIXED_NOW + timedelta(seconds=35),
        )
    elif state_func == "result_unknown":
        mark_live_order_result_unknown(
            ledger_path=_ledger_path(tmp_path),
            now_jst=FIXED_NOW + timedelta(seconds=35),
        )

    with pytest.raises(LiveVerificationLiveOrderOnceError):
        prepare_live_order_attempt(
            ledger_path=_ledger_path(tmp_path),
            approval_gate=_gate(issued_at_jst=FIXED_NOW + timedelta(seconds=60)),
            client_order_id="S420260625100100ABCD1234",
            now_jst=FIXED_NOW + timedelta(seconds=60),
        )


def test_ledger_attempt_count_blocks_prepare(tmp_path: Path) -> None:
    _prepare(tmp_path)
    mark_live_order_post_started(
        ledger_path=_ledger_path(tmp_path),
        approval_id=FIXED_APPROVAL_ID,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )
    ledger = load_live_order_attempt_ledger(_ledger_path(tmp_path))

    assert ledger.state == LiveOrderAttemptState.POST_STARTED.value
    assert ledger.attempt_count == 1
    with pytest.raises(LiveVerificationLiveOrderOnceError):
        prepare_live_order_attempt(
            ledger_path=_ledger_path(tmp_path),
            approval_gate=_gate(issued_at_jst=FIXED_NOW + timedelta(seconds=60)),
            client_order_id="S420260625100100ABCD1234",
            now_jst=FIXED_NOW + timedelta(seconds=60),
        )


def test_ledger_file_does_not_save_credentials_headers_signature_or_raw(
    tmp_path: Path,
) -> None:
    _prepare(tmp_path)
    text = _ledger_path(tmp_path).read_text(encoding="utf-8")

    assert DUMMY_API_KEY not in text
    assert DUMMY_API_SECRET not in text
    assert DUMMY_SIGNATURE not in text
    assert DUMMY_RAW_REQUEST not in text
    assert DUMMY_RAW_RESPONSE not in text
    assert "headers" not in text
    assert "signature" not in text
    assert "raw_request" not in text
    assert "raw_response" not in text


def test_prepare_one_shot_live_order_does_not_call_transport(tmp_path: Path) -> None:
    prepared = _prepare(tmp_path)

    assert prepared.ledger.state == LiveOrderAttemptState.PREPARED.value
    assert prepared.http_post_enabled is False
    assert prepared.raw_request_saved is False
    assert prepared.raw_response_saved is False
    assert prepared.credential_values_logged is False


def test_execute_requires_explicit_approval_and_transport(tmp_path: Path) -> None:
    prepared = _prepare(tmp_path)

    result = execute_one_shot_live_order(
        gate=prepared.approval_gate,
        approval_phrase=prepared.approval_gate.buy_approval_phrase,
        ledger_path=_ledger_path(tmp_path),
        api_key=DUMMY_API_KEY,
        api_secret=DUMMY_API_SECRET,
        timestamp_factory=lambda: "1770000000000",
        transport=None,
        allow_live_http_post=False,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )

    assert result.http_post_attempted is False
    assert result.http_post_count == 0
    assert result.retry_count == 0
    assert result.loop_count == 0
    assert result.state_after == LiveOrderAttemptState.PREPARED.value
    assert "live_http_post_not_explicitly_allowed" in result.fail_reasons


def test_execute_uses_fake_transport_once_after_post_started(tmp_path: Path) -> None:
    prepared = _prepare(tmp_path)
    calls: list[tuple[str, str, str]] = []

    def fake_transport(
        endpoint_url: str,
        body_serialization: str,
        sensitive_headers: object,
    ) -> LiveOrderTransportResponse:
        ledger = load_live_order_attempt_ledger(_ledger_path(tmp_path))
        calls.append((endpoint_url, body_serialization, repr(sensitive_headers)))
        assert ledger.state == LiveOrderAttemptState.POST_STARTED.value
        assert ledger.attempt_count == 1
        assert endpoint_url == LIVE_ORDER_ENDPOINT_URL
        assert json.loads(body_serialization)["side"] == "BUY"
        assert DUMMY_API_KEY not in repr(sensitive_headers)
        assert DUMMY_API_SECRET not in repr(sensitive_headers)
        return LiveOrderTransportResponse(
            transport_result="success",
            api_status_success="true",
            response_data_present="true",
        )

    result = execute_one_shot_live_order(
        gate=prepared.approval_gate,
        approval_phrase=prepared.approval_gate.buy_approval_phrase,
        ledger_path=_ledger_path(tmp_path),
        api_key=DUMMY_API_KEY,
        api_secret=DUMMY_API_SECRET,
        timestamp_factory=lambda: "1770000000000",
        transport=fake_transport,
        allow_live_http_post=True,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )

    assert len(calls) == 1
    assert result.http_post_attempted is True
    assert result.http_post_count == 1
    assert result.transport_result == "success"
    assert result.api_status_success == "true"
    assert result.response_data_present == "true"
    assert result.result_unknown is False
    assert result.retry_count == 0
    assert result.loop_count == 0
    assert result.raw_request_saved is False
    assert result.raw_response_saved is False
    assert result.headers_saved is False
    assert result.signature_saved is False
    assert result.credential_values_logged is False
    assert result.state_before == LiveOrderAttemptState.PREPARED.value
    assert result.state_after == LiveOrderAttemptState.POST_COMPLETED.value
    assert result.fail_reasons == ()
    assert set(asdict(result)) == EXPECTED_RESULT_FIELDS


def test_execute_fails_without_exact_approval(tmp_path: Path) -> None:
    prepared = _prepare(tmp_path)
    calls: list[str] = []

    def fake_transport(
        endpoint_url: str,
        body_serialization: str,
        sensitive_headers: object,
    ) -> LiveOrderTransportResponse:
        calls.append(endpoint_url)
        return LiveOrderTransportResponse(
            transport_result="success",
            api_status_success="true",
            response_data_present="true",
        )

    result = execute_one_shot_live_order(
        gate=prepared.approval_gate,
        approval_phrase="任せる",
        ledger_path=_ledger_path(tmp_path),
        api_key=DUMMY_API_KEY,
        api_secret=DUMMY_API_SECRET,
        timestamp_factory=lambda: "1770000000000",
        transport=fake_transport,
        allow_live_http_post=True,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )

    assert calls == []
    assert result.http_post_attempted is False
    assert result.http_post_count == 0
    assert "approval_failed" in result.fail_reasons
    assert "approval_phrase_mismatch" in result.fail_reasons
    assert load_live_order_attempt_ledger(_ledger_path(tmp_path)).state == (
        LiveOrderAttemptState.PREPARED.value
    )


def test_execute_fails_when_ledger_is_not_prepared(tmp_path: Path) -> None:
    gate = _gate()

    with pytest.raises(LiveVerificationLiveOrderOnceError):
        execute_one_shot_live_order(
            gate=gate,
            approval_phrase=gate.buy_approval_phrase,
            ledger_path=_ledger_path(tmp_path),
            api_key=DUMMY_API_KEY,
            api_secret=DUMMY_API_SECRET,
            timestamp_factory=lambda: "1770000000000",
            transport=lambda endpoint_url, body_serialization, sensitive_headers: (
                LiveOrderTransportResponse(
                    transport_result="success",
                    api_status_success="true",
                    response_data_present="true",
                )
            ),
            allow_live_http_post=True,
            now_jst=FIXED_NOW + timedelta(seconds=30),
        )


def test_execute_timeout_marks_result_unknown_without_retry(tmp_path: Path) -> None:
    prepared = _prepare(tmp_path)
    calls: list[str] = []

    def fake_timeout(
        endpoint_url: str,
        body_serialization: str,
        sensitive_headers: object,
    ) -> LiveOrderTransportResponse:
        calls.append(endpoint_url)
        raise TimeoutError("timeout")

    result = execute_one_shot_live_order(
        gate=prepared.approval_gate,
        approval_phrase=prepared.approval_gate.sell_approval_phrase,
        ledger_path=_ledger_path(tmp_path),
        api_key=DUMMY_API_KEY,
        api_secret=DUMMY_API_SECRET,
        timestamp_factory=lambda: "1770000000000",
        transport=fake_timeout,
        allow_live_http_post=True,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )

    ledger = load_live_order_attempt_ledger(_ledger_path(tmp_path))
    assert len(calls) == 1
    assert result.http_post_attempted is True
    assert result.http_post_count == 1
    assert result.transport_result == "result_unknown"
    assert result.result_unknown is True
    assert result.retry_count == 0
    assert result.loop_count == 0
    assert result.fail_reasons == ("result_unknown",)
    assert ledger.state == LiveOrderAttemptState.RESULT_UNKNOWN.value
    assert ledger.attempt_count == 1


def test_public_views_do_not_expose_credentials_headers_signature_or_raw(
    tmp_path: Path,
) -> None:
    prepared = _prepare(tmp_path)
    result = execute_one_shot_live_order(
        gate=prepared.approval_gate,
        approval_phrase="任せる",
        ledger_path=_ledger_path(tmp_path),
        api_key=DUMMY_API_KEY,
        api_secret=DUMMY_API_SECRET,
        timestamp_factory=lambda: "1770000000000",
        transport=None,
        allow_live_http_post=False,
        now_jst=FIXED_NOW + timedelta(seconds=30),
    )
    body = build_live_order_outbound_body(
        side="BUY",
        client_order_id=FIXED_CLIENT_ORDER_ID,
    )
    forbidden_values = {
        DUMMY_API_KEY,
        DUMMY_API_SECRET,
        DUMMY_SIGNATURE,
        DUMMY_RAW_REQUEST,
        DUMMY_RAW_RESPONSE,
    }
    public_views = (
        repr(prepared),
        str(prepared),
        repr(asdict(prepared)),
        str(asdict(prepared)),
        repr(result),
        str(result),
        repr(asdict(result)),
        str(asdict(result)),
        repr(body),
        str(body),
        repr(asdict(body)),
        str(asdict(body)),
    )

    for view in public_views:
        assert all(value not in view for value in forbidden_values)
    assert {field.name for field in fields(OneShotLiveOrderPrepared)} == (
        EXPECTED_PREPARED_FIELDS
    )
    assert {field.name for field in fields(OneShotLiveOrderResult)} == (
        EXPECTED_RESULT_FIELDS
    )


def test_live_order_constants_are_live_order_allowlisted() -> None:
    assert LIVE_ORDER_METHOD == "POST"
    assert LIVE_ORDER_SIGNING_PATH == "/v1/order"
    assert LIVE_ORDER_ENDPOINT_URL == "https://forex-api.coin.z.com/private/v1/order"
    assert LIVE_ORDER_BODY_FIELDS == EXPECTED_BODY_FIELDS
