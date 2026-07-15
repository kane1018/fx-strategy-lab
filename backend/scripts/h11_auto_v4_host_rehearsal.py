"""Run one finite H-11 v4 fake-only host rehearsal."""

from __future__ import annotations

import argparse
import json

from app.h11_auto.v4_host_rehearsal import (
    V4HostRehearsalError,
    run_v4_host_rehearsal_no_post,
)
from app.services.h11_v4_notification_binding_no_post import (
    H11V4DisabledDualRouteNotifier,
    H11V4FakeEmailTransport,
    H11V4FakePushoverTransport,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Finite H-11 v4 host rehearsal (fake-only, no broker, no POST)"
    )
    parser.add_argument("--duration-seconds", type=float, default=15.0)
    args = parser.parse_args(argv)
    notifier = H11V4DisabledDualRouteNotifier(
        primary=H11V4FakePushoverTransport(),
        secondary=H11V4FakeEmailTransport(),
    )
    try:
        report = run_v4_host_rehearsal_no_post(
            duration_seconds=args.duration_seconds,
            notifier=notifier,
        )
    except V4HostRehearsalError as error:
        print(f"HOST_REHEARSAL_BLOCKED: {error}")
        return 2
    print(json.dumps(report.to_safe_dict(), ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report.status == "PASSED_FAKE_ONLY_NOT_ACTIVATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
