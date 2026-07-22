"""Stdlib-only reviewed source digest used before monitor application imports."""

from __future__ import annotations

import hashlib
from pathlib import Path

REVIEWED_FILES = (
    "backend/app/services/h11_v4_gmo_signal_preview.py",
    "backend/scripts/h11_auto_v4_g013_signal_preview.py",
    "backend/app/tests/h11_auto/test_v4_gmo_g013_signal_preview_no_post.py",
    "AGENTS.md",
    "backend/requirements.txt",
    "backend/h11_v4_reviewed_digest.py",
    "backend/scripts/__init__.py",
    "backend/app/__init__.py",
    "backend/app/services/__init__.py",
    "backend/app/shadow/__init__.py",
    "backend/app/shadow/models.py",
    "backend/app/h11_manual/__init__.py",
    "backend/app/h11_auto/__init__.py",
    "backend/app/h11_auto/v4_actual_preparation_guard.py",
    "backend/app/h11_auto/v4_actual_host_kill_rehearsal.py",
    "backend/app/h11_auto/contracts.py",
    "backend/app/h11_auto/state_machine.py",
    "backend/app/h11_auto/persistence.py",
    "backend/app/h11_auto/v4_activation_preparation.py",
    "backend/app/h11_auto/v4_gmo_actual_coordinator.py",
    "backend/app/h11_auto/v4_gmo_canary_activation.py",
    "backend/app/h11_auto/v4_gmo_contracts.py",
    "backend/app/h11_auto/v4_gmo_engine.py",
    "backend/app/h11_auto/v4_gmo_boundary.py",
    "backend/app/h11_auto/v4_gmo_evidence.py",
    "backend/app/h11_auto/v4_gmo_generation.py",
    "backend/app/h11_auto/v4_gmo_persisted_authorization.py",
    "backend/app/h11_auto/v4_gmo_persistence.py",
    "backend/app/h11_auto/v4_gmo_protection.py",
    "backend/app/h11_auto/v4_gmo_runtime_paths.py",
    "backend/app/h11_auto/v4_gmo_monitor_supervisor.py",
    "backend/app/h11_auto/v4_gmo_launchd.py",
    "backend/app/h11_auto/v4_gmo_runtime.py",
    "backend/app/h11_auto/formal_signal_feed.py",
    "backend/app/h11_auto/signal_adapter.py",
    "backend/app/h11_auto/runtime_safety.py",
    "backend/app/h11_manual/contracts.py",
    "backend/app/h11_manual/data.py",
    "backend/app/h11_manual/short_model.py",
    "backend/app/private_api/auth.py",
    "backend/app/security/real_broker_post_hard_guard.py",
    "backend/app/services/h11_v4_gmo_actual_adapter.py",
    "backend/app/services/h11_v4_gmo_coordinated_actual_path.py",
    "backend/app/services/h11_v4_gmo_public_market_status.py",
    "backend/app/services/h11_v4_gmo_public_preflight.py",
    "backend/app/services/h11_v4_gmo_formal_canary_source.py",
    "backend/app/services/h11_v4_gmo_g013_canary.py",
    "backend/app/services/h11_v4_gmo_actual_transport.py",
    "backend/app/services/h11_v4_gmo_actual_runtime_binding.py",
    "backend/app/services/h11_v4_gmo_actual_runtime_driver.py",
    "backend/app/services/h11_v4_gmo_exit_dispatcher.py",
    "backend/app/services/h11_v4_notification_binding_no_post.py",
    "backend/app/services/h11_v4_notification_actual_preparation.py",
    "backend/app/services/h11_v4_gmo_readonly_preflight.py",
    "backend/app/shadow/gmo_public.py",
    "backend/scripts/h11_auto_v4_actual_preparation_presence.py",
    "backend/scripts/h11_auto_v4_keychain_access_rehearsal.py",
    "backend/scripts/h11_auto_v4_pushover_rehearsal.py",
    "backend/scripts/h11_auto_v4_smtp_rehearsal.py",
    "backend/scripts/h11_auto_v4_actual_host_kill_rehearsal.py",
    "backend/scripts/h11_auto_v4_coordinator_kill_probe.py",
    "backend/scripts/h11_auto_v4_email_delivery_confirm.py",
    "backend/scripts/h11_auto_v4_exclusivity_confirm.py",
    "backend/scripts/h11_auto_v4_private_get_preflight.py",
    "backend/scripts/h11_auto_v4_public_get_preflight.py",
    "backend/scripts/h11_auto_v4_g013_actual_canary.py",
    "backend/scripts/h11_auto_v4_monitor_supervisor.py",
    "backend/scripts/h11_auto_v4_install_monitor_launchagent.py",
    "backend/app/tests/h11_auto/test_v4_actual_preparation_fake_first.py",
    "backend/app/tests/h11_auto/test_v4_gmo_g013_fake_only.py",
    "backend/app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py",
    "backend/app/tests/h11_auto/test_v4_gmo_actual_adapter_fake_only.py",
    "backend/app/tests/h11_auto/test_v4_gmo_relaxed_no_post.py",
    "backend/app/tests/h11_auto/test_v4_gmo_g012_activation_fake_only.py",
    "backend/app/tests/h11_auto/test_v4_gmo_monitor_supervisor_no_post.py",
    "backend/app/tests/h11_auto/test_v4_gmo_launchagent_runner_no_post.py",
    "backend/app/tests/h11_auto/test_v4_notification_binding_fake_only.py",
    "backend/app/tests/test_h11_stage1_paper_wiring_no_post.py",
    "backend/app/tests/test_h11_v3_runtime_safety_no_post.py",
    "docs/H11_V4_ACTUAL_ACTIVATION_PREPARATION_REPORT_20260716.md",
    "docs/H11_V4_G012_CANARY_PREPARATION_REPORT_20260717.md",
    "docs/H11_V4_G013_CANARY_ACTIVATION_REPORT_20260717.md",
    "docs/H11_AUTO_OPERATOR_DECISION_SHEET_NO_POST_20260715.md",
    "docs/H11_V4_MAJOR_INCIDENT_RESUME_DECLARATION_DRAFT_NO_POST_20260715.md",
    "docs/H11_AUTO_FROZEN_GENERATION_MANIFEST_TEMPLATE_NO_POST_20260715.md",
    "docs/OPERATOR_V4_EDGE_IMPLEMENTATION_PROPOSAL_NO_POST_20260716.md",
)


class V4ReviewedDigestError(ValueError):
    """Fixed safe error for a missing or unsafe reviewed source file."""


def compute_reviewed_files_digest(*, repository: Path) -> str:
    digest = hashlib.sha256()
    root = repository.resolve()
    for relative in REVIEWED_FILES:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise V4ReviewedDigestError("REVIEWED_FILE_INVALID")
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"
