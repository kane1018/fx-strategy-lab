from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import httpx
import pytest

from app.services import h11_v4_gmo_g013_canary as canary_module
from app.services.h11_v4_gmo_actual_transport import V4GmoSealedCredentialPair


def _fake_session() -> SimpleNamespace:
    return SimpleNamespace(
        _use=SimpleNamespace(consume_once=lambda: None),
        store=SimpleNamespace(reserve_entry_cycle=lambda **_kwargs: None),
        generation=SimpleNamespace(digest="sha256:" + "a" * 64),
        formal_input=SimpleNamespace(signal=object(), frozen_atr_24=Decimal("0.1")),
        intent=object(),
        challenge=object(),
        repository=Path("/nonexistent"),
    )


def _fake_credential_pair() -> V4GmoSealedCredentialPair:
    return cast(
        V4GmoSealedCredentialPair,
        SimpleNamespace(api_key=object(), api_secret=object()),
    )


def test_signature_requires_credential_pair_and_client_with_no_default() -> None:
    signature = inspect.signature(
        canary_module.run_g013_actual_canary_after_unattended_authorization
    )
    for name in ("credential_pair", "client"):
        parameter = signature.parameters[name]
        assert parameter.default is inspect.Parameter.empty, name


@pytest.mark.parametrize(
    ("credential_pair", "client"),
    (
        (None, cast(httpx.Client, object())),
        (None, None),
    ),
)
def test_explicit_none_credential_or_client_is_rejected_at_runtime(
    credential_pair: object, client: object
) -> None:
    # Type hints alone don't stop a caller writing credential_pair=None/client=None
    # explicitly -- this must be checked at runtime, fail closed, rather than
    # silently reaching bind_v4_gmo_actual_runtime's own real-Keychain default.
    with pytest.raises(
        canary_module.V4GmoG013CanaryError,
        match="G013_UNATTENDED_CREDENTIAL_OR_CLIENT_REQUIRED",
    ):
        canary_module.run_g013_actual_canary_after_unattended_authorization(
            session=cast(canary_module.V4GmoG013PreparedSession, _fake_session()),
            resume_proof=cast(canary_module.V4MajorIncidentResumeProof, object()),
            confirmation_proof=cast(canary_module.V4CurrentTurnConfirmationProof, object()),
            credential_pair=cast(V4GmoSealedCredentialPair, credential_pair),
            client=cast(httpx.Client, client),
        )


def test_explicit_none_client_alone_is_also_rejected_at_runtime() -> None:
    with pytest.raises(
        canary_module.V4GmoG013CanaryError,
        match="G013_UNATTENDED_CREDENTIAL_OR_CLIENT_REQUIRED",
    ):
        canary_module.run_g013_actual_canary_after_unattended_authorization(
            session=cast(canary_module.V4GmoG013PreparedSession, _fake_session()),
            resume_proof=cast(canary_module.V4MajorIncidentResumeProof, object()),
            confirmation_proof=cast(canary_module.V4CurrentTurnConfirmationProof, object()),
            credential_pair=_fake_credential_pair(),
            client=cast(httpx.Client, None),
        )


def test_unattended_path_never_calls_the_phrase_confirmation_functions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    confirm_resume = MagicMock()
    confirm_current = MagicMock()
    monkeypatch.setattr(canary_module, "confirm_v4_major_incident_resume_exact", confirm_resume)
    monkeypatch.setattr(canary_module, "confirm_v4_current_turn_exact", confirm_current)
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda _session: None)
    monkeypatch.setattr(canary_module, "_refresh_session_evidence_before_permit", lambda s: s)
    monkeypatch.setattr(
        canary_module,
        "_run_g013_actual_canary_from_refreshed_session",
        lambda **_kwargs: (_ for _ in ()).throw(
            canary_module.V4GmoG013CanaryError("STOP_AFTER_DISPATCH")
        ),
    )
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="STOP_AFTER_DISPATCH"):
        canary_module.run_g013_actual_canary_after_unattended_authorization(
            session=cast(canary_module.V4GmoG013PreparedSession, _fake_session()),
            resume_proof=cast(canary_module.V4MajorIncidentResumeProof, object()),
            confirmation_proof=cast(canary_module.V4CurrentTurnConfirmationProof, object()),
            credential_pair=_fake_credential_pair(),
            client=cast(httpx.Client, object()),
        )
    confirm_resume.assert_not_called()
    confirm_current.assert_not_called()


def test_unattended_path_reaches_the_same_shared_helper_as_the_phrase_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda _session: None)
    monkeypatch.setattr(canary_module, "_refresh_session_evidence_before_permit", lambda s: s)
    monkeypatch.setattr(
        canary_module,
        "confirm_v4_major_incident_resume_exact",
        lambda **_kwargs: "phrase-resume",
    )
    monkeypatch.setattr(
        canary_module,
        "confirm_v4_current_turn_exact",
        lambda **_kwargs: "phrase-confirmation",
    )

    def _fake_shared(**kwargs: object) -> str:
        calls.append(kwargs)
        return "OK"

    monkeypatch.setattr(
        canary_module, "_run_g013_actual_canary_from_refreshed_session", _fake_shared
    )

    canary_module.run_g013_actual_canary_after_exact_confirmation(
        session=cast(canary_module.V4GmoG013PreparedSession, _fake_session()),
        major_incident_resume_phrase="ok",
        current_turn_phrase="ok",
    )
    credential_pair = _fake_credential_pair()
    client = cast(httpx.Client, object())
    canary_module.run_g013_actual_canary_after_unattended_authorization(
        session=cast(canary_module.V4GmoG013PreparedSession, _fake_session()),
        resume_proof=cast(canary_module.V4MajorIncidentResumeProof, "proof-resume"),
        confirmation_proof=cast(canary_module.V4CurrentTurnConfirmationProof, "proof-confirmation"),
        credential_pair=credential_pair,
        client=client,
    )

    assert len(calls) == 2
    phrase_call, proof_call = calls
    # Both paths reach the identical shared helper with the identical keyword shape --
    # proving there is exactly one implementation of the post-confirmation sequence,
    # not two independently written ones.
    assert set(phrase_call) == set(proof_call) == {
        "session",
        "resume",
        "confirmation",
        "on_protected",
        "credential_pair",
        "client",
    }
    assert phrase_call["resume"] == "phrase-resume"
    assert phrase_call["confirmation"] == "phrase-confirmation"
    assert phrase_call["credential_pair"] is None
    assert phrase_call["client"] is None
    assert proof_call["resume"] == "proof-resume"
    assert proof_call["confirmation"] == "proof-confirmation"
    assert proof_call["credential_pair"] is credential_pair
    assert proof_call["client"] is client


def test_phrase_path_still_passes_none_credential_and_client_to_bind_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pins the single safety-critical property this whole change hinges on: the
    # existing human-interactive path's real-Keychain-on-None behavior must be
    # reproduced explicitly, never silently changed by this refactor.
    bind_calls: list[dict[str, object]] = []
    session = _fake_session()
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda _s: None)
    monkeypatch.setattr(canary_module, "_refresh_session_evidence_before_permit", lambda s: s)
    monkeypatch.setattr(
        canary_module, "confirm_v4_major_incident_resume_exact", lambda **_k: "resume"
    )
    monkeypatch.setattr(
        canary_module, "confirm_v4_current_turn_exact", lambda **_k: "confirmation"
    )
    monkeypatch.setattr(canary_module, "_ensure_signal_postable", lambda **_k: None)
    monkeypatch.setattr(canary_module, "_execution_policy", lambda _g: SimpleNamespace())
    monkeypatch.setattr(canary_module, "_require_fresh_monitor_heartbeat", lambda **_k: None)
    monkeypatch.setattr(
        canary_module,
        "issue_v4_gmo_actual_activation_permit",
        lambda **_k: "permit",
    )

    def _fake_bind(**kwargs: object) -> None:
        bind_calls.append(kwargs)
        raise canary_module.V4GmoG013CanaryError("STOP_AFTER_BIND")

    monkeypatch.setattr(canary_module, "bind_v4_gmo_actual_runtime", _fake_bind)

    with pytest.raises(canary_module.V4GmoG013CanaryError, match="STOP_AFTER_BIND"):
        canary_module.run_g013_actual_canary_after_exact_confirmation(
            session=cast(canary_module.V4GmoG013PreparedSession, session),
            major_incident_resume_phrase="ok",
            current_turn_phrase="ok",
        )
    assert len(bind_calls) == 1
    assert bind_calls[0]["credential_pair"] is None
    assert bind_calls[0]["client"] is None


def test_unattended_path_passes_its_credential_and_client_through_to_bind_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bind_calls: list[dict[str, object]] = []
    monkeypatch.setattr(canary_module, "_require_exact_session_binding", lambda _s: None)
    monkeypatch.setattr(canary_module, "_refresh_session_evidence_before_permit", lambda s: s)
    monkeypatch.setattr(canary_module, "_ensure_signal_postable", lambda **_k: None)
    monkeypatch.setattr(canary_module, "_execution_policy", lambda _g: SimpleNamespace())
    monkeypatch.setattr(canary_module, "_require_fresh_monitor_heartbeat", lambda **_k: None)
    monkeypatch.setattr(
        canary_module,
        "issue_v4_gmo_actual_activation_permit",
        lambda **_k: "permit",
    )

    def _fake_bind(**kwargs: object) -> None:
        bind_calls.append(kwargs)
        raise canary_module.V4GmoG013CanaryError("STOP_AFTER_BIND")

    monkeypatch.setattr(canary_module, "bind_v4_gmo_actual_runtime", _fake_bind)

    credential_pair = _fake_credential_pair()
    client = cast(httpx.Client, object())
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="STOP_AFTER_BIND"):
        canary_module.run_g013_actual_canary_after_unattended_authorization(
            session=cast(canary_module.V4GmoG013PreparedSession, _fake_session()),
            resume_proof=cast(canary_module.V4MajorIncidentResumeProof, "resume"),
            confirmation_proof=cast(canary_module.V4CurrentTurnConfirmationProof, "confirmation"),
            credential_pair=credential_pair,
            client=client,
        )
    assert len(bind_calls) == 1
    assert bind_calls[0]["credential_pair"] is credential_pair
    assert bind_calls[0]["client"] is client


def test_unattended_path_still_consumes_session_once_and_refreshes_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    session = SimpleNamespace(
        _use=SimpleNamespace(consume_once=lambda: order.append("consume")),
    )
    monkeypatch.setattr(
        canary_module,
        "_require_exact_session_binding",
        lambda _s: order.append("require_binding"),
    )

    def _refresh(_session: object) -> object:
        order.append("refresh")
        raise canary_module.V4GmoG013CanaryError("G013_REVALIDATION_BLOCKED")

    monkeypatch.setattr(canary_module, "_refresh_session_evidence_before_permit", _refresh)
    with pytest.raises(canary_module.V4GmoG013CanaryError, match="REVALIDATION_BLOCKED"):
        canary_module.run_g013_actual_canary_after_unattended_authorization(
            session=cast(canary_module.V4GmoG013PreparedSession, session),
            resume_proof=cast(canary_module.V4MajorIncidentResumeProof, object()),
            confirmation_proof=cast(canary_module.V4CurrentTurnConfirmationProof, object()),
            credential_pair=_fake_credential_pair(),
            client=cast(httpx.Client, object()),
        )
    assert order == ["consume", "require_binding", "refresh"]


def test_new_function_has_exactly_one_authorized_production_caller() -> None:
    # Scope note: this catches direct-name references (Name/Attribute) and
    # aliased imports (`import ... as X`, via ast.alias.name/asname); it does
    # NOT catch string-based/dynamic lookups (getattr with a computed string,
    # importlib by string). Originally this asserted zero production callers;
    # the unattended orchestration module (its own AGENTS.md exception, its
    # own review) is now the single authorized caller, so the pinned property
    # is: exactly that one module and nothing else.
    import ast

    target = "run_g013_actual_canary_after_unattended_authorization"
    authorized = "app/services/h11_v4_unattended_live_orchestration.py"
    module_path = Path(canary_module.__file__)
    repo_root = module_path.parents[2]
    hits: list[str] = []
    for path in repo_root.rglob("*.py"):
        if path == module_path or "/tests/" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (
                (isinstance(node, ast.Name) and node.id == target)
                or (isinstance(node, ast.Attribute) and node.attr == target)
                or (
                    isinstance(node, ast.alias)
                    and (node.name == target or node.asname == target)
                )
            ):
                hits.append(path.as_posix())
    unauthorized = [hit for hit in hits if not hit.endswith(authorized)]
    assert unauthorized == []
    assert any(hit.endswith(authorized) for hit in hits)


def test_module_docstring_and_new_functions_contain_no_dangerous_tokens() -> None:
    source = inspect.getsource(canary_module)
    for forbidden in (
        "os.environ",
        "os.getenv",
        "keyring",
        "find-generic-password",
        "load_dotenv",
    ):
        assert forbidden not in source, forbidden
