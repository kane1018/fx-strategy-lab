"""Generation-bound one-use activation contract for the H-11 v4 canary.

The production issuer is deliberately separated from the transport.  A permit
can only be issued after two opaque, current-process proofs and an atomic local
marker.  This module never reads credentials and never performs broker I/O.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from app.h11_auto.v4_gmo_contracts import V4GmoAction
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root


class V4GmoCanaryActivationError(RuntimeError):
    """Fixed safe activation failure."""


_RESUME_TOKEN = object()
_CONFIRMATION_TOKEN = object()
_PERMIT_TOKEN = object()
_SCOPE_TOKEN = object()
_RESUME_PHRASE = "I APPROVE H11 V4 MAJOR INCIDENT RESUME FOR THIS REVIEWED GENERATION ONLY"


@dataclass(frozen=True, repr=False)
class V4GmoCanaryIntent:
    generation_digest: str
    cycle_ref: str
    side: str
    exact_order_sheet_digest: str
    size: int = 1_000
    symbol: str = "USD_JPY"
    execution_type: str = "MARKET"
    action: V4GmoAction = V4GmoAction.MARKET_ENTRY

    def __post_init__(self) -> None:
        if (
            not _valid_digest(self.generation_digest)
            or not _valid_digest(self.exact_order_sheet_digest)
            or not _valid_cycle_ref(self.cycle_ref)
            or self.side not in {"BUY", "SELL"}
            or self.size != 1_000
            or self.symbol != "USD_JPY"
            or self.execution_type != "MARKET"
            or self.action is not V4GmoAction.MARKET_ENTRY
        ):
            raise V4GmoCanaryActivationError("V4_CANARY_INTENT_INVALID")

    @property
    def digest(self) -> str:
        canonical = json.dumps(
            {
                "action": self.action.value,
                "cycle_ref": self.cycle_ref,
                "execution_type": self.execution_type,
                "exact_order_sheet_digest": self.exact_order_sheet_digest,
                "generation_digest": self.generation_digest,
                "side": self.side,
                "size": self.size,
                "symbol": self.symbol,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    def __repr__(self) -> str:
        return "V4GmoCanaryIntent(<generation-cycle-bound-redacted>)"

    def __bool__(self) -> bool:
        return False


class V4MajorIncidentResumeProof:
    __slots__ = ("_token", "_generation_digest", "_consumed")

    def __init__(self, *, token: object, generation_digest: str) -> None:
        if token is not _RESUME_TOKEN or not _valid_digest(generation_digest):
            raise V4GmoCanaryActivationError("V4_CANARY_RESUME_PROOF_INVALID")
        self._token = token
        self._generation_digest = generation_digest
        self._consumed = False

    def __repr__(self) -> str:
        return "V4MajorIncidentResumeProof(<redacted-one-use>)"

    def __bool__(self) -> bool:
        return False


def confirm_v4_major_incident_resume_exact(
    *, phrase: str, generation_digest: str
) -> V4MajorIncidentResumeProof:
    if not hmac.compare_digest(phrase, _RESUME_PHRASE):
        raise V4GmoCanaryActivationError("V4_CANARY_RESUME_CONFIRMATION_MISMATCH")
    return V4MajorIncidentResumeProof(
        token=_RESUME_TOKEN,
        generation_digest=generation_digest,
    )


@dataclass(frozen=True, repr=False)
class V4CurrentTurnChallenge:
    intent_digest: str
    _nonce: str

    @classmethod
    def create(cls, *, intent: V4GmoCanaryIntent) -> V4CurrentTurnChallenge:
        return cls(intent_digest=intent.digest, _nonce=secrets.token_hex(16))

    def phrase_for_operator_internal(self) -> str:
        return f"H11 V4 G013 CANARY {self.intent_digest[-12:]} {self._nonce}"

    def __repr__(self) -> str:
        return "V4CurrentTurnChallenge(<redacted-current-turn>)"

    def __bool__(self) -> bool:
        return False


class V4CurrentTurnConfirmationProof:
    __slots__ = ("_token", "_intent_digest", "_consumed")

    def __init__(self, *, token: object, intent_digest: str) -> None:
        if token is not _CONFIRMATION_TOKEN or not _valid_digest(intent_digest):
            raise V4GmoCanaryActivationError("V4_CANARY_CURRENT_TURN_PROOF_INVALID")
        self._token = token
        self._intent_digest = intent_digest
        self._consumed = False

    def __repr__(self) -> str:
        return "V4CurrentTurnConfirmationProof(<redacted-one-use>)"

    def __bool__(self) -> bool:
        return False


def confirm_v4_current_turn_exact(
    *,
    typed_phrase: str,
    challenge: V4CurrentTurnChallenge,
    intent: V4GmoCanaryIntent,
) -> V4CurrentTurnConfirmationProof:
    if (
        not isinstance(challenge, V4CurrentTurnChallenge)
        or challenge.intent_digest != intent.digest
        or not hmac.compare_digest(
            typed_phrase,
            challenge.phrase_for_operator_internal(),
        )
    ):
        raise V4GmoCanaryActivationError("V4_CANARY_CURRENT_TURN_CONFIRMATION_MISMATCH")
    return V4CurrentTurnConfirmationProof(
        token=_CONFIRMATION_TOKEN,
        intent_digest=intent.digest,
    )


class V4GmoActualActivationPermit:
    __slots__ = (
        "_token",
        "_generation_digest",
        "_cycle_ref",
        "_intent_digest",
        "_side",
        "_size",
        "_symbol",
        "_execution_type",
        "_expires_monotonic",
        "_marker_path",
        "_consumed",
    )

    def __init__(
        self,
        *,
        token: object,
        intent: V4GmoCanaryIntent,
        expires_monotonic: float,
        marker_path: Path,
    ) -> None:
        if token is not _PERMIT_TOKEN:
            raise V4GmoCanaryActivationError("V4_CANARY_ACTIVATION_PERMIT_INVALID")
        self._token = token
        self._generation_digest = intent.generation_digest
        self._cycle_ref = intent.cycle_ref
        self._intent_digest = intent.digest
        self._side = intent.side
        self._size = intent.size
        self._symbol = intent.symbol
        self._execution_type = intent.execution_type
        self._expires_monotonic = expires_monotonic
        self._marker_path = marker_path
        self._consumed = False

    def __repr__(self) -> str:
        return "V4GmoActualActivationPermit(<redacted-one-use>)"

    def __bool__(self) -> bool:
        return False


class V4ActivatedRuntimeScope:
    __slots__ = (
        "_token",
        "generation_digest",
        "cycle_ref",
        "intent_digest",
        "side",
        "size",
        "symbol",
        "execution_type",
        "entry_expires_monotonic",
    )

    def __init__(
        self,
        *,
        token: object,
        generation_digest: str,
        cycle_ref: str,
        intent_digest: str,
        side: str,
        size: int,
        symbol: str,
        execution_type: str,
        entry_expires_monotonic: float,
    ) -> None:
        if token is not _SCOPE_TOKEN:
            raise V4GmoCanaryActivationError("V4_ACTIVATED_RUNTIME_SCOPE_INVALID")
        self._token = token
        self.generation_digest = generation_digest
        self.cycle_ref = cycle_ref
        self.intent_digest = intent_digest
        self.side = side
        self.size = size
        self.symbol = symbol
        self.execution_type = execution_type
        self.entry_expires_monotonic = entry_expires_monotonic

    def __repr__(self) -> str:
        return "V4ActivatedRuntimeScope(<redacted-generation-cycle-bound>)"

    def __bool__(self) -> bool:
        return False


def require_v4_activated_runtime_scope_internal(
    scope: V4ActivatedRuntimeScope,
) -> V4ActivatedRuntimeScope:
    if (
        not isinstance(scope, V4ActivatedRuntimeScope)
        or getattr(scope, "_token", None) is not _SCOPE_TOKEN
    ):
        raise V4GmoCanaryActivationError("V4_ACTIVATED_RUNTIME_SCOPE_INVALID")
    return scope


def require_v4_actual_activation_permit_binding_internal(
    permit: V4GmoActualActivationPermit,
    *,
    generation_digest: str,
    cycle_ref: str,
    state_root: Path,
) -> None:
    """Verify the opaque permit before a canonical runtime consumes it."""

    if (
        not isinstance(permit, V4GmoActualActivationPermit)
        or getattr(permit, "_token", None) is not _PERMIT_TOKEN
        or permit._consumed
        or permit._generation_digest != generation_digest
        or permit._cycle_ref != cycle_ref
        or permit._marker_path.parent.resolve() != state_root.resolve()
        or state_root.is_symlink()
    ):
        raise V4GmoCanaryActivationError("V4_CANARY_ACTIVATION_BINDING_MISMATCH")


def issue_v4_gmo_actual_activation_permit(
    *,
    intent: V4GmoCanaryIntent,
    resume_proof: V4MajorIncidentResumeProof,
    current_turn_proof: V4CurrentTurnConfirmationProof,
    repository: Path,
    now_monotonic: float,
    lifetime_seconds: float = 30.0,
) -> V4GmoActualActivationPermit:
    if (
        not isinstance(resume_proof, V4MajorIncidentResumeProof)
        or getattr(resume_proof, "_token", None) is not _RESUME_TOKEN
        or resume_proof._consumed
        or resume_proof._generation_digest != intent.generation_digest
        or not isinstance(current_turn_proof, V4CurrentTurnConfirmationProof)
        or getattr(current_turn_proof, "_token", None) is not _CONFIRMATION_TOKEN
        or current_turn_proof._consumed
        or current_turn_proof._intent_digest != intent.digest
        or not _valid_monotonic(now_monotonic)
        or not _valid_lifetime(lifetime_seconds)
        or not repository.is_dir()
    ):
        raise V4GmoCanaryActivationError("V4_CANARY_ACTIVATION_GATE_NOT_CLEAR")
    state_root = v4_gmo_runtime_state_root(
        repository=repository.resolve(),
        generation_digest=intent.generation_digest,
    )
    if state_root.is_symlink():
        raise V4GmoCanaryActivationError("V4_CANARY_ACTIVATION_GATE_NOT_CLEAR")
    # Keyed by cycle_ref (not a fixed generation-wide filename): cycle_ref is
    # already unique per (generation, signal) because the signal fingerprint
    # embeds its exact observation timestamp, so this is naturally one-use per
    # trading day under daily rollover without needing a separate day parameter.
    marker_path = state_root / f"activation-permit-issued.{intent.cycle_ref}.json"
    payload = {
        "generation_digest": intent.generation_digest,
        "intent_digest": intent.digest,
        "cycle_ref": intent.cycle_ref,
        "side": intent.side,
        "size": intent.size,
        "symbol": intent.symbol,
        "execution_type": intent.execution_type,
        "status": "ISSUED_ONE_USE_NOT_POSTED",
    }
    _write_exclusive_marker(marker_path, payload)
    resume_proof._consumed = True
    current_turn_proof._consumed = True
    return V4GmoActualActivationPermit(
        token=_PERMIT_TOKEN,
        intent=intent,
        expires_monotonic=float(now_monotonic) + float(lifetime_seconds),
        marker_path=marker_path,
    )


def consume_v4_gmo_actual_activation_permit(
    permit: V4GmoActualActivationPermit,
    *,
    now_monotonic: float,
) -> V4ActivatedRuntimeScope:
    if (
        not isinstance(permit, V4GmoActualActivationPermit)
        or getattr(permit, "_token", None) is not _PERMIT_TOKEN
        or permit._consumed
        or not _valid_monotonic(now_monotonic)
        or now_monotonic > permit._expires_monotonic
        or not permit._marker_path.is_file()
        or permit._marker_path.is_symlink()
    ):
        raise V4GmoCanaryActivationError("V4_CANARY_ACTIVATION_PERMIT_INVALID")
    try:
        marker = json.loads(permit._marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4GmoCanaryActivationError(
            "V4_CANARY_ACTIVATION_PERMIT_INVALID"
        ) from error
    if marker != {
        "cycle_ref": permit._cycle_ref,
        "execution_type": permit._execution_type,
        "generation_digest": permit._generation_digest,
        "intent_digest": permit._intent_digest,
        "side": permit._side,
        "size": permit._size,
        "status": "ISSUED_ONE_USE_NOT_POSTED",
        "symbol": permit._symbol,
    }:
        raise V4GmoCanaryActivationError("V4_CANARY_ACTIVATION_PERMIT_INVALID")
    # Keyed by cycle_ref for the same reason as the issued-permit marker above:
    # a fixed filename here would permanently latch after the first cycle ever
    # bound under this generation, defeating daily rollover from day 2 onward.
    consumed_path = permit._marker_path.with_name(
        f"activation-runtime-bound.{permit._cycle_ref}.json"
    )
    _write_exclusive_marker(
        consumed_path,
        {
            "generation_digest": permit._generation_digest,
            "intent_digest": permit._intent_digest,
            "status": "RUNTIME_BOUND_POST_NOT_ATTEMPTED",
        },
    )
    permit._consumed = True
    return V4ActivatedRuntimeScope(
        token=_SCOPE_TOKEN,
        generation_digest=permit._generation_digest,
        cycle_ref=permit._cycle_ref,
        intent_digest=permit._intent_digest,
        side=permit._side,
        size=permit._size,
        symbol=permit._symbol,
        execution_type=permit._execution_type,
        entry_expires_monotonic=permit._expires_monotonic,
    )


def _write_exclusive_marker(path: Path, payload: dict[str, str]) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise V4GmoCanaryActivationError("V4_CANARY_MARKER_PATH_INVALID")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except FileExistsError as error:
        raise V4GmoCanaryActivationError("V4_CANARY_ACTIVATION_ALREADY_USED") from error
    except OSError as error:
        raise V4GmoCanaryActivationError("V4_CANARY_MARKER_WRITE_FAILED") from error


def _valid_digest(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    body = value.removeprefix("sha256:")
    return len(body) == 64 and all(character in "0123456789abcdef" for character in body)


def _valid_cycle_ref(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _valid_monotonic(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _valid_lifetime(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 < value <= 60
    )
