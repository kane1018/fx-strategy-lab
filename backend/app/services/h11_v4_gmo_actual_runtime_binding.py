"""Generation-bound H-11 v4 actual runtime assembly.

This module assembles the already-reviewed coordinated path around a consumed
one-use activation permit.  It never issues a permit and has no fallback or
environment-based activation path.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import DeadManStore, PhaseBRiskStore
from app.h11_auto.v4_gmo_actual_coordinator import V4GmoActualCoordinatorStore
from app.h11_auto.v4_gmo_canary_activation import (
    V4GmoActualActivationPermit,
    require_v4_actual_activation_permit_binding_internal,
)
from app.h11_auto.v4_gmo_generation import (
    V4GmoFrozenGeneration,
    v4_gmo_dead_man_policy,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_gmo_actual_adapter import V4GmoActualAdapter
from app.services.h11_v4_gmo_actual_runtime_driver import V4GmoActualRuntimeDriver
from app.services.h11_v4_gmo_actual_transport import (
    V4GmoHttpxPrivateTransport,
    V4GmoKeychainCredentialPair,
    V4GmoSealedCredentialPair,
    V4GmoSignedRequestFactory,
)
from app.services.h11_v4_gmo_coordinated_actual_path import V4GmoCoordinatedActualPath
from app.services.h11_v4_gmo_exit_dispatcher import V4GmoExitDispatcher


class V4GmoActualRuntimeBindingError(RuntimeError):
    """Fixed safe runtime assembly failure."""


@dataclass(repr=False)
class V4GmoActualRuntimeBinding:
    coordinated_path: V4GmoCoordinatedActualPath
    transport: V4GmoHttpxPrivateTransport
    process_lock: H11AutoProcessLock

    def build_exit_dispatcher(self) -> V4GmoExitDispatcher:
        return V4GmoExitDispatcher(
            coordinated_path=self.coordinated_path,
            state_root=self.coordinated_path.store.path.parent,
        )

    def build_foreground_lifecycle_driver(self) -> V4GmoActualRuntimeDriver:
        dispatcher = self.build_exit_dispatcher()
        return V4GmoActualRuntimeDriver(
            coordinated_path=self.coordinated_path,
            dispatcher=dispatcher,
        )

    def close(self) -> None:
        self.transport.close()
        self.process_lock.release()

    def __enter__(self) -> V4GmoActualRuntimeBinding:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.close()

    def __repr__(self) -> str:
        return "V4GmoActualRuntimeBinding(<generation-bound-redacted>)"

    def __bool__(self) -> bool:
        return False


def bind_v4_gmo_actual_runtime(
    *,
    repository: Path,
    generation: V4GmoFrozenGeneration,
    activation_permit: V4GmoActualActivationPermit,
    credential_pair: V4GmoSealedCredentialPair | None = None,
    client: httpx.Client | None = None,
    monotonic_factory: Callable[[], float] = time.monotonic,
) -> V4GmoActualRuntimeBinding:
    """Consume one permit and assemble only canonical generation state paths."""

    repository = repository.resolve()
    state_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=generation.digest,
    )
    if state_root.is_symlink():
        raise V4GmoActualRuntimeBindingError("V4_RUNTIME_STATE_ROOT_INVALID")
    store = V4GmoActualCoordinatorStore(state_root / "coordinator.sqlite3")
    store.bind_generation(generation)
    signal_fingerprint = store.load_single_signal_fingerprint_internal()
    cycle_ref = store.cycle_ref_for_signal_internal(signal_fingerprint)
    require_v4_actual_activation_permit_binding_internal(
        activation_permit,
        generation_digest=generation.digest,
        cycle_ref=cycle_ref,
        state_root=state_root,
    )
    process_lock = H11AutoProcessLock(state_root / "process.lock")
    if not process_lock.acquire():
        raise V4GmoActualRuntimeBindingError("V4_RUNTIME_PROCESS_ALREADY_ACTIVE")
    transport: V4GmoHttpxPrivateTransport | None = None
    try:
        transport = V4GmoHttpxPrivateTransport(
            activation_permit=activation_permit,
            signed_request_factory=V4GmoSignedRequestFactory(
                credential_pair=(
                    credential_pair
                    if credential_pair is not None
                    else V4GmoKeychainCredentialPair()
                )
            ),
            client=client,
            monotonic_factory=monotonic_factory,
            unknown_post_callback=store.engage_unknown_halt,
        )
        risk_policy = v4_gmo_risk_policy()
        risk_store = PhaseBRiskStore(state_root / "risk.json", policy=risk_policy)
        dead_man_store = DeadManStore(
            state_root / "dead-man.json",
            policy=v4_gmo_dead_man_policy(),
        )
        coordinated_path = V4GmoCoordinatedActualPath(
            repository=repository,
            store=store,
            adapter=V4GmoActualAdapter(transport=transport),
            process_lock=process_lock,
            generation=generation,
            risk_store=risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man_store,
            monotonic_clock=monotonic_factory,
        )
    except BaseException:
        if transport is not None:
            transport.close()
        process_lock.release()
        raise
    return V4GmoActualRuntimeBinding(
        coordinated_path=coordinated_path,
        transport=transport,
        process_lock=process_lock,
    )
