from __future__ import annotations

import ast
import inspect
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.services import h11_v4_unattended_account_snapshot_producer_no_post as subject
from app.services import h11_v4_unattended_account_snapshot_store_no_post as store_module
from app.services.h11_v4_unattended_account_snapshot_store_no_post import (
    V4AccountSnapshotStoreNoPost,
    V4AccountSnapshotStoreNoPostError,
)
from app.services.h11_v4_unattended_shadow_private_preflight import (
    V4UnattendedShadowSealedSecret,
)
from scripts import h11_auto_v4_g026_private_snapshot_producer as cli

_REVIEWED = "sha256:" + ("a" * 64)
_GENERATION = "sha256:" + ("b" * 64)


@dataclass
class _Credentials:
    directory: Path
    reads: int = 0

    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4UnattendedShadowSealedSecret, V4UnattendedShadowSealedSecret]:
        assert (self.directory / "producer.started.json").is_file()
        self.reads += 1
        return (
            V4UnattendedShadowSealedSecret("synthetic-key"),
            V4UnattendedShadowSealedSecret("synthetic-secret"),
        )


class _Clock:
    def __init__(self, values: list[datetime]) -> None:
        self.values = values

    def __call__(self) -> datetime:
        return self.values.pop(0)


def _client_factory(seen: list[tuple[str, str]]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return httpx.Response(200, json={"status": 0, "data": []})

    return lambda: httpx.Client(
        base_url="https://sandbox.invalid.example",
        transport=httpx.MockTransport(handler),
    )


def test_success_is_started_first_exactly_three_gets_and_loadable(tmp_path: Path) -> None:
    now = datetime(2026, 7, 29, 1, 12, 10, tzinfo=UTC)
    credentials = _Credentials(tmp_path)
    seen: list[tuple[str, str]] = []
    result = subject.produce_account_snapshot_once_no_post(
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
        store_directory=tmp_path,
        credential_pair=credentials,
        client_factory=_client_factory(seen),
        now_factory=_Clock(
            [now, now + timedelta(seconds=1), now + timedelta(seconds=2)]
        ),
    )
    assert result.status == "ACCOUNT_SNAPSHOT_PRODUCED_NO_POST"
    assert credentials.reads == 1
    assert seen == [
        ("GET", "/private/v1/latestExecutions"),
        ("GET", "/private/v1/openPositions"),
        ("GET", "/private/v1/activeOrders"),
    ]
    evidence = V4AccountSnapshotStoreNoPost(tmp_path).load_completed(
        expected_reviewed_files_digest=_REVIEWED,
        expected_generation_digest=_GENERATION,
    )
    assert evidence is not None
    assert evidence.account_flat is True
    assert evidence.active_orders_zero is True
    assert evidence.broker_write is False
    assert evidence.broker_post_count == 0


def test_second_invocation_refuses_before_credentials_or_network(tmp_path: Path) -> None:
    now = datetime(2026, 7, 29, 1, 12, 10, tzinfo=UTC)
    subject.produce_account_snapshot_once_no_post(
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
        store_directory=tmp_path,
        credential_pair=_Credentials(tmp_path),
        client_factory=_client_factory([]),
        now_factory=_Clock(
            [now, now + timedelta(seconds=1), now + timedelta(seconds=2)]
        ),
    )
    credentials = _Credentials(tmp_path)
    seen: list[tuple[str, str]] = []
    with pytest.raises(Exception, match="ALREADY_ATTEMPTED"):
        subject.produce_account_snapshot_once_no_post(
            reviewed_files_digest=_REVIEWED,
            generation_digest=_GENERATION,
            store_directory=tmp_path,
            credential_pair=credentials,
            client_factory=_client_factory(seen),
            now_factory=lambda: now,
        )
    assert credentials.reads == 0
    assert seen == []


def test_get_failure_is_terminal_and_never_retried(tmp_path: Path) -> None:
    now = datetime(2026, 7, 29, 1, 12, 10, tzinfo=UTC)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(503, json={"status": 1})

    client = httpx.Client(
        base_url="https://sandbox.invalid.example",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(
        subject.V4AccountSnapshotProducerNoPostError,
        match="FAILED_NO_RETRY",
    ):
        subject.produce_account_snapshot_once_no_post(
            reviewed_files_digest=_REVIEWED,
            generation_digest=_GENERATION,
            store_directory=tmp_path,
            credential_pair=_Credentials(tmp_path),
            client_factory=lambda: client,
            now_factory=_Clock([now, now + timedelta(seconds=1)]),
        )
    assert seen == ["/private/v1/latestExecutions"]
    assert (tmp_path / "producer.started.json").is_file()
    assert (tmp_path / "producer.failed.json").is_file()


def test_cycle_rollover_is_terminal(tmp_path: Path) -> None:
    before = datetime(2026, 7, 29, 1, 12, 59, tzinfo=UTC)
    after = datetime(2026, 7, 29, 1, 13, 0, tzinfo=UTC)
    with pytest.raises(
        subject.V4AccountSnapshotProducerNoPostError,
        match="FAILED_NO_RETRY",
    ):
        subject.produce_account_snapshot_once_no_post(
            reviewed_files_digest=_REVIEWED,
            generation_digest=_GENERATION,
            store_directory=tmp_path,
            credential_pair=_Credentials(tmp_path),
            client_factory=_client_factory([]),
            now_factory=_Clock([before, after, after]),
        )
    assert (tmp_path / "producer.failed.json").is_file()
    assert not (tmp_path / "producer.passed.json").exists()


def test_producer_and_cli_have_no_write_endpoint_or_authorization_reachability() -> None:
    combined = inspect.getsource(subject) + inspect.getsource(cli)
    for forbidden in (
        '"POST"',
        ".post(",
        "closeOrder",
        "cancelOrders",
        "changeOrder",
        "assert_real_broker_post_allowed",
        "ActualPushover",
        "ActualEmail",
        "set_desired_state",
        "install_unattended",
    ):
        assert forbidden not in combined
    tree = ast.parse(inspect.getsource(cli))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "app.services.h11_v4_gmo_actual_transport" not in imported


def test_safe_cli_failure_never_claims_external_activity() -> None:
    result = cli._safe_failure()
    assert result["attempt_started"] is None
    assert result["broker_get_count"] is None
    assert result["credential_read_count"] is None
    assert result["broker_write"] is False
    assert result["broker_post_count"] == 0
    assert result["persistent_arm_changed"] is False
    assert result["notification_send_count"] == 0
    assert result["raw_response_retained"] is False
    assert result["identifier_exposed"] is False


def test_completed_store_rejects_symlinked_directory(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "redirected"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(Exception, match="PATH_INVALID"):
        V4AccountSnapshotStoreNoPost(link).load_completed(
            expected_reviewed_files_digest=_REVIEWED,
            expected_generation_digest=_GENERATION,
        )


def test_completed_store_rejects_dangling_symlink_directory(tmp_path: Path) -> None:
    link = tmp_path / "dangling"
    link.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(Exception, match="PATH_INVALID"):
        V4AccountSnapshotStoreNoPost(link).load_completed(
            expected_reviewed_files_digest=_REVIEWED,
            expected_generation_digest=_GENERATION,
        )


@pytest.mark.parametrize(
    "failing_path",
    (
        "/private/v1/latestExecutions",
        "/private/v1/openPositions",
        "/private/v1/activeOrders",
    ),
)
def test_each_get_failure_stops_without_later_request(
    tmp_path: Path, failing_path: str
) -> None:
    now = datetime(2026, 7, 29, 1, 12, 10, tzinfo=UTC)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == failing_path:
            return httpx.Response(503, json={"status": 1})
        return httpx.Response(200, json={"status": 0, "data": []})

    with pytest.raises(subject.V4AccountSnapshotProducerNoPostError):
        subject.produce_account_snapshot_once_no_post(
            reviewed_files_digest=_REVIEWED,
            generation_digest=_GENERATION,
            store_directory=tmp_path,
            credential_pair=_Credentials(tmp_path),
            client_factory=lambda: httpx.Client(
                base_url="https://sandbox.invalid.example",
                transport=httpx.MockTransport(handler),
            ),
            now_factory=_Clock([now, now + timedelta(seconds=1)]),
        )
    sequence = [
        "/private/v1/latestExecutions",
        "/private/v1/openPositions",
        "/private/v1/activeOrders",
    ]
    assert seen == sequence[: sequence.index(failing_path) + 1]
    assert (tmp_path / "producer.failed.json").is_file()


def test_cli_import_graph_excludes_permit_bearing_modules() -> None:
    command = (
        "import sys; "
        "import scripts.h11_auto_v4_g026_private_snapshot_producer; "
        "print(int('app.h11_auto.v4_actual_preparation_guard' in sys.modules)); "
        "print(int('app.services.h11_v4_gmo_readonly_preflight' in sys.modules)); "
        "print(int('app.services.h11_v4_gmo_actual_transport' in sys.modules))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", command],
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.splitlines() == ["0", "0", "0"]


@pytest.mark.parametrize("failing_stage", ("evidence", "passed", "failure"))
def test_artifact_write_failure_preserves_no_retry_before_next_external_access(
    monkeypatch, tmp_path: Path, failing_stage: str
) -> None:
    now = datetime(2026, 7, 29, 1, 12, 10, tzinfo=UTC)
    original_write_once = store_module._write_once

    if failing_stage == "evidence":
        monkeypatch.setattr(
            store_module,
            "_write_atomic",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                V4AccountSnapshotStoreNoPostError(
                    "ACCOUNT_SNAPSHOT_PRODUCER_ARTIFACT_WRITE_FAILED"
                )
            ),
        )
        first_client_factory = _client_factory([])
    elif failing_stage == "passed":
        def fail_passed(path, payload):
            if path.name == "producer.passed.json":
                raise V4AccountSnapshotStoreNoPostError(
                    "ACCOUNT_SNAPSHOT_PRODUCER_MARKER_WRITE_FAILED"
                )
            return original_write_once(path, payload)

        monkeypatch.setattr(store_module, "_write_once", fail_passed)
        first_client_factory = _client_factory([])
    else:
        def fail_failure_marker(path, payload):
            if path.name == "producer.failed.json":
                raise V4AccountSnapshotStoreNoPostError(
                    "ACCOUNT_SNAPSHOT_PRODUCER_MARKER_WRITE_FAILED"
                )
            return original_write_once(path, payload)

        monkeypatch.setattr(store_module, "_write_once", fail_failure_marker)

        def failed_get_client() -> httpx.Client:
            return httpx.Client(
                base_url="https://sandbox.invalid.example",
                transport=httpx.MockTransport(
                    lambda _request: httpx.Response(503, json={"status": 1})
                ),
            )

        first_client_factory = failed_get_client

    with pytest.raises(subject.V4AccountSnapshotProducerNoPostError):
        subject.produce_account_snapshot_once_no_post(
            reviewed_files_digest=_REVIEWED,
            generation_digest=_GENERATION,
            store_directory=tmp_path,
            credential_pair=_Credentials(tmp_path),
            client_factory=first_client_factory,
            now_factory=_Clock(
                [now, now + timedelta(seconds=1)]
                + (
                    []
                    if failing_stage == "failure"
                    else [now + timedelta(seconds=2), now + timedelta(seconds=3)]
                )
            ),
        )
    assert (tmp_path / "producer.started.json").is_file()

    credentials = _Credentials(tmp_path)
    seen: list[tuple[str, str]] = []
    with pytest.raises(Exception, match="ALREADY_ATTEMPTED"):
        subject.produce_account_snapshot_once_no_post(
            reviewed_files_digest=_REVIEWED,
            generation_digest=_GENERATION,
            store_directory=tmp_path,
            credential_pair=credentials,
            client_factory=_client_factory(seen),
            now_factory=lambda: now,
        )
    assert credentials.reads == 0
    assert seen == []
