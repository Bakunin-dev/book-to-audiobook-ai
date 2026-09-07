# Source provenance

The private Potter implementation was inspected locally. Only five deterministic,
provider-independent files were selected for direct publication.

## Unmodified original source

- `aitran/artifacts.py`
- `aitran/contracts.py`
- `aitran/process_lock.py`
- `aitran/speech_chunking.py`
- `aitran/speech_pronunciation.py`

Their SHA-256 values are stored in `provenance.json`. The public release checker
rejects any drift in these files.

## Adapted public code

`aitran/errors.py` exposes only errors required by the selected utilities and the
synthetic run. It is not represented as an unchanged original.

The small models and checkpoint state in `aitran/showcase/` reproduce public
interfaces and invariants without copying private orchestration.

## Newly written synthetic code

The fictional book, fixture translator, fixture cast analyzer, tone WAV renderer,
public pipeline, CLI, release checker, and public regression tests were written for
this edition.

No private importer, model client, prompt, context selector, request journal,
translation runner, cast engine, repair engine, speech provider, desktop runtime,
installer, or diagnostic collector was copied into this tree.
