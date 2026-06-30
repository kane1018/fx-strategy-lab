from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

from app.live_verification.live_order_real_signing_contract import (
    LiveOrderRealSigningContractStatus,
    LiveOrderRealSigningInputContract,
    build_live_order_real_signing_contract,
    build_redacted_private_order_header_contract,
    render_live_order_real_signing_contract_markdown,
)


def _build(**overrides):
    return build_live_order_real_signing_contract(**overrides)


def test_valid_metadata_builds_ready_signing_contract_without_values() -> None:
    result = _build()

    assert (
        result.status
        is LiveOrderRealSigningContractStatus.SIGNING_CONTRACT_READY_NO_CREDENTIAL_NO_SIGNATURE
    )
    assert result.signing_contract_ready is True
    assert result.redacted_header_contract_ready is True
    assert result.method == "POST"
    assert result.path == "/v1/order"
    assert result.credential_values_provided is False
    assert result.signature_value_generated is False
    assert result.header_values_redacted is True
    assert result.no_api_executed is True
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False


def test_redacted_header_contract_is_names_only_and_serializable() -> None:
    header = build_redacted_private_order_header_contract()

    assert header.redacted_header_contract_ready is True
    assert header.allowed_header_names == ("API-KEY", "API-TIMESTAMP", "API-SIGN")
    assert header.header_values_present is False
    assert header.header_values_redacted is True
    assert header.signature_value_present is False
    assert header.credential_value_present is False
    assert header.safe_to_render is True
    assert header.safe_to_serialize is True


def test_method_path_mismatch_blocks_input() -> None:
    result = _build(input_contract=LiveOrderRealSigningInputContract(method="GET"))

    assert result.status is LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_INPUT
    assert "method_not_post" in result.blocked_reasons


def test_body_contract_not_ready_blocks_input() -> None:
    result = _build(
        input_contract=LiveOrderRealSigningInputContract(
            stable_serialized_body_contract_ready=False,
        ),
    )

    assert result.status is LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_INPUT
    assert "body_contract_not_ready" in result.blocked_reasons


def test_timestamp_value_generation_blocks_as_signature_value() -> None:
    result = _build(
        input_contract=LiveOrderRealSigningInputContract(timestamp_value_generated=True),
    )

    assert (
        result.status
        is LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_SIGNATURE_VALUE
    )
    assert "timestamp_value_generated" in result.blocked_reasons


def test_credential_values_provided_blocks_credential_value() -> None:
    result = _build(
        input_contract=LiveOrderRealSigningInputContract(credential_values_provided=True),
    )

    assert (
        result.status
        is LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_CREDENTIAL_VALUE
    )
    assert "credential_values_provided" in result.blocked_reasons


def test_credential_value_present_blocks_credential_value() -> None:
    result = _build(
        header_contract=replace(
            build_redacted_private_order_header_contract(),
            credential_value_present=True,
        ),
    )

    assert (
        result.status
        is LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_CREDENTIAL_VALUE
    )
    assert "credential_value_present" in result.blocked_reasons


def test_signature_value_generated_blocks_signature_value() -> None:
    result = _build(
        input_contract=LiveOrderRealSigningInputContract(signature_value_generated=True),
    )

    assert (
        result.status
        is LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_SIGNATURE_VALUE
    )
    assert "signature_value_generated" in result.blocked_reasons


def test_signature_value_present_blocks_signature_value() -> None:
    result = _build(
        header_contract=replace(
            build_redacted_private_order_header_contract(),
            signature_value_present=True,
        ),
    )

    assert (
        result.status
        is LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_SIGNATURE_VALUE
    )
    assert "signature_value_present" in result.blocked_reasons


def test_header_values_present_blocks_header_value_exposure() -> None:
    result = _build(
        header_contract=replace(
            build_redacted_private_order_header_contract(),
            header_values_present=True,
        ),
    )

    assert (
        result.status
        is LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_HEADER_VALUE_EXPOSURE
    )
    assert "header_values_present" in result.blocked_reasons


def test_display_or_save_flags_block_without_values() -> None:
    header_status = (
        LiveOrderRealSigningContractStatus
        .BLOCKED_SIGNING_CONTRACT_HEADER_VALUE_EXPOSURE
    )
    credential_status = (
        LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_CREDENTIAL_VALUE
    )
    signature_status = (
        LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_SIGNATURE_VALUE
    )
    for field_name, expected_status in [
        ("headers_displayed", header_status),
        ("headers_saved", header_status),
        ("credentials_displayed", credential_status),
        ("credentials_saved", credential_status),
        ("signature_displayed", signature_status),
        ("signature_saved", signature_status),
    ]:
        contract = replace(LiveOrderRealSigningInputContract(), **{field_name: True})
        result = _build(input_contract=contract)

        assert result.status is expected_status


def test_env_or_dotenv_access_request_blocks() -> None:
    for field_name in ("env_access_requested", "dotenv_access_requested"):
        contract = replace(LiveOrderRealSigningInputContract(), **{field_name: True})
        result = _build(input_contract=contract)

        assert (
            result.status
            is LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_ENV_ACCESS
        )


def test_unsupported_algorithm_blocks() -> None:
    result = _build(
        input_contract=LiveOrderRealSigningInputContract(signature_algorithm_label="UNSUPPORTED"),
    )

    assert result.status is LiveOrderRealSigningContractStatus.BLOCKED_SIGNING_CONTRACT_UNSUPPORTED


def test_renderer_does_not_include_credential_signature_or_header_values() -> None:
    result = _build()
    rendered = render_live_order_real_signing_contract_markdown(result)

    assert "This signing contract does not use real credentials." in rendered
    assert "This signing contract does not generate real signatures." in rendered
    assert "does not execute HTTP POST" in rendered
    assert "does not call live_order_once" in rendered
    assert "actual_credential_value" not in rendered
    assert "actual_signature_value" not in rendered
    assert "actual_header_value" not in rendered
    assert "serialized body" not in rendered.lower()


def test_asdict_does_not_contain_credential_signature_or_header_values() -> None:
    result = _build()
    payload = repr(asdict(result))

    assert "actual_credential_value" not in payload
    assert "actual_signature_value" not in payload
    assert "actual_header_value" not in payload
    assert "actual_raw_response_value" not in payload


def test_new_module_does_not_import_env_http_private_broker_or_live_order_once() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_signing_contract.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app.brokers",
        "app.private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "getenv",
        "GMO_FX_API_KEY",
        "GMO_FX_API_SECRET",
        "Authorization",
        "speedOrder",
        "live_order_once",
        "pbcopy",
    }
    blocked_attrs = {"environ", "getenv"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name not in blocked_modules for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in blocked_modules
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
