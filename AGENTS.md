# Scope of this public edition

This directory is the synthetic Potter Code Showcase, not the private product.
Keep every stage executable and keep the fixture-only and synthetic boundaries
visible. Never add credentials, provider clients, private prompts, working books,
real speech models, desktop distribution code, or parent-directory imports.

Five files are unmodified originals and are pinned in `provenance.json`. Do not
edit them here; make an explicitly adapted copy instead. Run the unit tests and
`python tools/release.py --check` after relevant changes. Keep
`public-files.json` exact: release archives are built only from that allowlist.
