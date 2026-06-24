import httpx

from app.private_api.auth import create_signature
from scripts import check_private_readonly_connection as script


def test_confirm_flag_is_required_before_connection(monkeypatch, capsys) -> None:
    monkeypatch.setenv("GMO_FX_API_KEY", "dummy-key")
    monkeypatch.setenv("GMO_FX_API_SECRET", "dummy-secret")

    def runner(**_kwargs):
        raise AssertionError("runner must not be called without explicit confirmation")

    exit_code = script.main([], runner=runner)

    out = capsys.readouterr().out
    assert exit_code == 2
    assert "connection_result: failure" in out
    assert "account_assets: not_run" in out
    assert "dummy-key" not in out
    assert "dummy-secret" not in out


def test_missing_env_does_not_connect(monkeypatch, capsys) -> None:
    monkeypatch.delenv("GMO_FX_API_KEY", raising=False)
    monkeypatch.delenv("GMO_FX_API_SECRET", raising=False)

    def runner(**_kwargs):
        raise AssertionError("runner must not be called without credentials")

    exit_code = script.main(["--confirm-readonly"], runner=runner)

    out = capsys.readouterr().out
    assert exit_code == 2
    assert "connection_result: failure" in out
    assert "open_positions: not_run" in out


def test_run_connection_check_uses_only_three_get_readonly_endpoints() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/private/v1/account/assets":
            return httpx.Response(
                200,
                json={"status": 0, "data": {"actualAmount": "1000000"}},
            )
        if request.url.path == "/private/v1/openPositions":
            return httpx.Response(200, json={"status": 0, "data": []})
        if request.url.path == "/private/v1/activeOrders":
            return httpx.Response(200, json={"status": 0, "data": []})
        return httpx.Response(404, json={"status": 1})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    summary = script.run_connection_check(
        api_key="dummy-key",
        api_secret="dummy-secret",
        symbol="USD_JPY",
        http_client=client,
        timestamp_factory=lambda: "1700000000000",
    )

    assert summary.connection_result == "success"
    assert summary.account_assets == "success"
    assert summary.open_positions == "success"
    assert summary.active_orders == "success"
    assert summary.account_assets_count == 1
    assert summary.open_positions_count == 0
    assert summary.active_orders_count == 0
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/private/v1/account/assets"),
        ("GET", "/private/v1/openPositions"),
        ("GET", "/private/v1/activeOrders"),
    ]
    assert requests[1].url.params["symbol"] == "USD_JPY"
    assert requests[2].url.params["symbol"] == "USD_JPY"
    expected_signature = create_signature(
        api_secret="dummy-secret",
        timestamp="1700000000000",
        method="GET",
        path="/v1/account/assets",
    )
    assert requests[0].headers["API-SIGN"] == expected_signature


def test_diagnose_open_positions_stops_before_active_orders() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/private/v1/account/assets":
            return httpx.Response(200, json={"status": 0, "data": {"actualAmount": "1000000"}})
        if request.url.path == "/private/v1/openPositions":
            return httpx.Response(200, json={"status": 0, "data": []})
        raise AssertionError("diagnostic mode must not call activeOrders")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    summary = script.run_connection_check(
        api_key="dummy-key",
        api_secret="dummy-secret",
        symbol="USD_JPY",
        http_client=client,
        timestamp_factory=lambda: "1700000000000",
        diagnose_open_positions=True,
    )

    assert summary.connection_result == "success"
    assert summary.account_assets == "success"
    assert summary.open_positions == "success"
    assert summary.active_orders == "not_run"
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/private/v1/account/assets"),
        ("GET", "/private/v1/openPositions"),
    ]


def test_diagnose_open_positions_accepts_object_list_shape() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/private/v1/account/assets":
            return httpx.Response(200, json={"status": 0, "data": {"actualAmount": "1000000"}})
        if request.url.path == "/private/v1/openPositions":
            return httpx.Response(
                200,
                json={
                    "status": 0,
                    "data": {
                        "list": [
                            {
                                "positionId": "pos-1",
                                "symbol": "USD_JPY",
                                "side": "BUY",
                                "size": "100",
                                "API-KEY": "dummy-key",
                            }
                        ],
                    },
                },
            )
        raise AssertionError("diagnostic mode must not call activeOrders")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    summary = script.run_connection_check(
        api_key="dummy-key",
        api_secret="dummy-secret",
        symbol="USD_JPY",
        http_client=client,
        timestamp_factory=lambda: "1700000000000",
        diagnose_open_positions=True,
    )

    assert summary.connection_result == "success"
    assert summary.open_positions == "success"
    assert summary.active_orders == "not_run"
    assert summary.open_positions_count == 1
    assert summary.response_data_shape == "object"
    assert summary.response_top_level_keys == "data,status"
    assert summary.response_data_keys == "list"
    assert summary.response_data_item_keys == "positionId,redacted_key,side,size,symbol"
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/private/v1/account/assets"),
        ("GET", "/private/v1/openPositions"),
    ]
    dumped = "\n".join(summary.to_stdout_lines())
    assert "dummy-key" not in dumped
    assert "API-KEY" not in dumped
    assert "pos-1" not in dumped
    assert "USD_JPY" not in dumped


def test_diagnose_open_positions_missing_data_returns_empty_shape_summary() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/private/v1/account/assets":
            return httpx.Response(200, json={"status": 0, "data": {"actualAmount": "1000000"}})
        if request.url.path == "/private/v1/openPositions":
            return httpx.Response(200, json={"status": 0})
        raise AssertionError("diagnostic mode must not call activeOrders")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    summary = script.run_connection_check(
        api_key="dummy-key",
        api_secret="dummy-secret",
        symbol="USD_JPY",
        http_client=client,
        timestamp_factory=lambda: "1700000000000",
        diagnose_open_positions=True,
    )

    assert summary.connection_result == "success"
    assert summary.open_positions == "success"
    assert summary.open_positions_count == 0
    assert summary.response_data_shape == "missing"
    assert summary.response_top_level_keys == "status"
    assert summary.response_data_keys == "unknown"
    assert summary.response_data_item_keys == "unknown"
    assert len(requests) == 2


def test_open_positions_failure_returns_sanitized_diagnostics_only() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/private/v1/account/assets":
            return httpx.Response(200, json={"status": 0, "data": {"actualAmount": "1000000"}})
        if request.url.path == "/private/v1/openPositions":
            return httpx.Response(
                403,
                json={
                    "status": 1,
                    "messages": [
                        {
                            "message_code": "ERR-PERMISSION",
                            "message_string": "permission denied",
                            "API-KEY": "dummy-key",
                        }
                    ],
                    "API-SIGN": "dummy-signature",
                },
            )
        raise AssertionError("diagnostic mode must not call activeOrders")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    summary = script.run_connection_check(
        api_key="dummy-key",
        api_secret="dummy-secret",
        symbol="USD_JPY",
        http_client=client,
        timestamp_factory=lambda: "1700000000000",
        diagnose_open_positions=True,
    )

    assert summary.connection_result == "failure"
    assert summary.account_assets == "success"
    assert summary.open_positions == "failure"
    assert summary.active_orders == "not_run"
    assert summary.failed_endpoint == "open_positions"
    assert summary.failed_method == "GET"
    assert summary.failed_path == "/private/v1/openPositions"
    assert summary.sanitized_http_status == "403"
    assert summary.sanitized_error_code == "ERR-PERMISSION"
    assert summary.sanitized_error_message == "permission denied"
    assert summary.diagnostic_reason_category == "permission_error"
    assert summary.response_data_shape == "missing"
    assert summary.response_top_level_keys == "messages,redacted_key,status"
    assert summary.response_data_keys == "unknown"
    assert summary.response_data_item_keys == "unknown"
    assert summary.raw_response_saved is False
    assert summary.headers_saved is False
    assert summary.credentials_printed is False
    assert summary.retry_attempted is False
    assert len(requests) == 2
    dumped = "\n".join(summary.to_stdout_lines())
    assert "dummy-key" not in dumped
    assert "dummy-signature" not in dumped
    assert "API-SIGN" not in dumped
    assert "API-KEY" not in dumped


def test_open_positions_schema_failure_returns_local_sanitized_message() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/private/v1/account/assets":
            return httpx.Response(200, json={"status": 0, "data": {"actualAmount": "1000000"}})
        if request.url.path == "/private/v1/openPositions":
            return httpx.Response(200, json={"status": 0, "data": {"unexpected": []}})
        raise AssertionError("diagnostic mode must not call activeOrders")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    summary = script.run_connection_check(
        api_key="dummy-key",
        api_secret="dummy-secret",
        symbol="USD_JPY",
        http_client=client,
        timestamp_factory=lambda: "1700000000000",
        diagnose_open_positions=True,
    )

    assert summary.connection_result == "failure"
    assert summary.failed_endpoint == "open_positions"
    assert summary.sanitized_http_status == "unknown"
    assert summary.sanitized_error_code == "schema_error"
    assert summary.sanitized_error_message == "openPositions data object has no list field"
    assert summary.diagnostic_reason_category == "schema_error"
    assert summary.response_data_shape == "object"
    assert summary.response_top_level_keys == "data,status"
    assert summary.response_data_keys == "unexpected"
    assert summary.response_data_item_keys == "unknown"
    assert len(requests) == 2


def test_connection_check_does_not_retry_after_error() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"status": 1, "messages": [{"message_code": "ERR-MOCK"}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    summary = script.run_connection_check(
        api_key="dummy-key",
        api_secret="dummy-secret",
        http_client=client,
        timestamp_factory=lambda: "1700000000000",
    )

    assert summary.connection_result == "failure"
    assert summary.account_assets == "failure"
    assert summary.failed_endpoint == "account_assets"
    assert summary.failed_method == "GET"
    assert summary.sanitized_error_code == "ERR-MOCK"
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/private/v1/account/assets"


def test_stdout_summary_is_sanitized(monkeypatch, capsys) -> None:
    monkeypatch.setenv("GMO_FX_API_KEY", "dummy-key")
    monkeypatch.setenv("GMO_FX_API_SECRET", "dummy-secret")

    def runner(**_kwargs):
        return script.SanitizedConnectionSummary(
            connection_result="success",
            account_assets="success",
            open_positions="success",
            active_orders="success",
            account_assets_count=1,
            open_positions_count=1,
            active_orders_count=0,
            has_open_positions=True,
            has_active_orders=False,
        )

    exit_code = script.main(["--confirm-readonly", "--symbol", "USD_JPY"], runner=runner)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "connection_result: success" in out
    assert "has_open_positions: true" in out
    assert "raw_response_saved: false" in out
    assert "headers_saved: false" in out
    assert "credentials_printed: false" in out
    assert "retry_attempted: false" in out
    assert "dummy-key" not in out
    assert "dummy-secret" not in out
    assert "positionId" not in out
    assert "orderId" not in out
