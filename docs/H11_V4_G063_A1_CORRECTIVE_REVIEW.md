# H-11 v4 G063 A1 corrective review

- generation: `H11_AUTO_30M_20260731_G063`
- reviewed-files digest: `sha256:5424bc1244273b177037503e5b580c80633acf421d07314f509cb723833918c4`
- generation digest: `sha256:cd3472868472e68dcac0eb313e9aab93f9075140906bc03b0ef4f8fb824499ca`
- generation manifest digest: `sha256:cd3472868472e68dcac0eb313e9aab93f9075140906bc03b0ef4f8fb824499ca`
- evidence artifact digest: `sha256:7eaa3511ec9c3b58f7630f10085c5ba78ac0a3fe5fdd98efdf554bd2cbf03dd9`
- attestation artifact digest: `sha256:33ba763a2d7fb6011d01dd2e02be80a818fdef33ed8ad151b25f533ef4c5a7e8`

## Canonical digest contract

Each declared digest is computed from canonical JSON after removing only its own digest field. This avoids impossible self-reference and is independently reproducible.

## Scope

G063 adds a generation-bound local sanitized position/protection evidence bridge. Missing, stale, malformed, symlinked, generation-mismatched, or incomplete evidence fails closed. It cannot authorize broker activity.

## Review boundary

Architecture, Safety, and Operations review remain pending external confirmation. `live_ready=false`, `actual_post_authorized=false`, and broker/private/credential read counts remain zero.
