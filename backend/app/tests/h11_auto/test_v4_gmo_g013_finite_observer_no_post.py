from __future__ import annotations

from pathlib import Path

from app.services.h11_v4_gmo_signal_preview import G013SignalPreviewReport
from scripts import h11_auto_v4_g013_finite_observer as observer


def _report(*, candidate_actionable: bool) -> G013SignalPreviewReport:
    return G013SignalPreviewReport(
        candidate_actionable=candidate_actionable,
        signal_fresh=True,
        signal_age_seconds=20.0,
    )


def test_candidate_attempts_only_the_fixed_local_sound(monkeypatch) -> None:
    captured: list[object] = []
    monkeypatch.setattr(
        observer.subprocess,
        "run",
        lambda *args, **kwargs: captured.append((args, kwargs)),
    )

    output = observer._safe_output(_report(candidate_actionable=True))

    assert output["status"] == "G013_PUBLIC_SIGNAL_OBSERVER_ACTIONABLE_ALERT_ATTEMPTED"
    assert output["candidate_actionable"] is True
    assert output["local_sound_attempted"] is True
    assert captured == [
        (
            (["/usr/bin/afplay", "/System/Library/Sounds/Glass.aiff"],),
            {
                "check": False,
                "stdout": observer.subprocess.DEVNULL,
                "stderr": observer.subprocess.DEVNULL,
                "timeout": 5.0,
            },
        )
    ]


def test_stay_does_not_attempt_sound(monkeypatch) -> None:
    monkeypatch.setattr(
        observer.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError),
    )

    output = observer._safe_output(_report(candidate_actionable=False))

    assert output["candidate_actionable"] is False
    assert output["local_sound_attempted"] is False


def test_observer_source_isolated_from_private_and_actual_paths() -> None:
    source = Path(observer.__file__).read_text(encoding="utf-8")
    forbidden = (
        "actual_canary",
        "h11_v4_gmo_g013_canary",
        "Private",
        "Keychain",
        "Pushover",
        "SMTP",
        "ActivationPermit",
        "cancelOrders",
        "closeOrder",
        "latestExecutions",
        "openPositions",
        "activeOrders",
        "while ",
        "sleep(",
        "http",
    )
    assert all(token not in source for token in forbidden)
    assert source.count("/usr/bin/afplay") == 1
