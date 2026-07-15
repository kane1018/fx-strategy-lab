"""Broker-independent H-11 automatic execution research boundary.

The package is intentionally fake-only and no-POST.  It must remain isolated
from the localhost manual UI and every real broker transport until a separate
activation step is explicitly authorized.
"""

from app.h11_auto.contracts import (
    FormalHorizon,
    FormalSignal,
    PhaseAExecutionPolicy,
    SignalDecision,
)
from app.h11_auto.v4_gmo_contracts import V4GmoExecutionPolicy
from app.h11_auto.v4_gmo_engine import H11V4GmoNoPostEngine
from app.h11_auto.v4_gmo_evidence import H11_V4_GMO_CAPABILITY_EVIDENCE_HASH
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH

__all__ = [
    "FormalHorizon",
    "FormalSignal",
    "H11V4GmoNoPostEngine",
    "H11_V4_GMO_PROTECTION_CONTRACT_HASH",
    "H11_V4_GMO_CAPABILITY_EVIDENCE_HASH",
    "PhaseAExecutionPolicy",
    "SignalDecision",
    "V4GmoExecutionPolicy",
]
