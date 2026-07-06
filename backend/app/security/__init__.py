"""Cross-cutting production safety primitives.

This package holds safety checkpoints that real broker/order code must pass
through. Unlike `app.live_verification` (the Step 6G controlled/simulation
family, which production broker/service code must never import), modules
here are meant to be imported by real production broker code.
"""

from __future__ import annotations
