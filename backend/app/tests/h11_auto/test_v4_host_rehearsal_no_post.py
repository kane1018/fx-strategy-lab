from __future__ import annotations

import plistlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.h11_auto.v4_host_rehearsal import (
    render_disabled_launchd_template,
    run_v4_host_rehearsal_no_post,
)
from app.services.h11_v4_notification_binding_no_post import (
    H11V4DisabledDualRouteNotifier,
    H11V4FakeEmailTransport,
    H11V4FakePushoverTransport,
)


class FakeClock:
    def __init__(self) -> None:
        self.tick = 100.0
        self.wall = datetime(2026, 7, 15, 0, 0, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.tick

    def now_utc(self) -> datetime:
        return self.wall

    def wait(self, seconds: float) -> None:
        self.tick += seconds
        self.wall += timedelta(seconds=seconds)


def test_disabled_launchd_template_cannot_start_or_keep_alive() -> None:
    content = render_disabled_launchd_template(
        python_executable="/usr/bin/python3",
        repository=Path("/tmp/fx-strategy-lab"),
    )
    payload = plistlib.loads(content)
    assert payload["Disabled"] is True
    assert payload["RunAtLoad"] is False
    assert payload["KeepAlive"] is False
    assert "credential" not in content.decode().lower()
    assert "h11_auto_v4_gmo_no_post_run" not in content.decode()
    assert "activation" not in content.decode().lower()


def test_finite_host_rehearsal_passes_without_broker_or_external_io() -> None:
    primary = H11V4FakePushoverTransport()
    secondary = H11V4FakeEmailTransport()
    report = run_v4_host_rehearsal_no_post(
        duration_seconds=1.0,
        notifier=H11V4DisabledDualRouteNotifier(
            primary=primary,
            secondary=secondary,
        ),
        clock=FakeClock(),
    )
    assert report.status == "PASSED_FAKE_ONLY_NOT_ACTIVATED"
    assert report.observed_elapsed_seconds == 1.0
    assert report.heartbeat_count == 1
    assert report.clock_assessment_count >= 1
    assert report.primary_notification_ready is True
    assert report.secondary_notification_ready is True
    assert report.maximum_unprotected_window_contract_seconds == 15
    assert report.measured_fake_pipeline_seconds <= 15
    assert report.actual_post_count == 0
    assert report.broker_read_performed is False
    assert report.broker_write_performed is False
    assert report.credential_read_performed is False
    assert report.external_notification_send_performed is False
    assert report.resident_process_added is False
    assert report.launchd_installed is False
    assert report.cron is False
    assert report.actual_activation_ready is False
