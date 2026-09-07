# Capability and evidence map

Every row describes this public edition. `REAL PRIVATE / DOCUMENTED` means the
capability exists in the private product but its implementation is not evidence
provided by the public repository.

| Capability | Public status | Executable evidence or omission |
|---|---|---|
| Stable paragraph IDs and lossless rendering | REAL PUBLIC | `aitran/contracts.py`; used by translation and verification |
| Atomic text, JSON and binary artifacts | REAL PUBLIC | `aitran/artifacts.py`; every stage writes through it |
| Exclusive workspace writer | REAL PUBLIC | `aitran/process_lock.py` |
| Chapter-aware bounded speech chunks | REAL PUBLIC | `aitran/speech_chunking.py`; offsets and hashes are checked |
| Explicit Russian pronunciations | REAL PUBLIC | `aitran/speech_pronunciation.py`; text integrity invariant |
| Book translation | SIMULATED PUBLIC | exact fixture mapping; unknown books are rejected |
| Structural translation verification | REAL PUBLIC | tagged IDs, order, source hash, ordinary/tagged agreement |
| Character and dialogue attribution | SIMULATED PUBLIC | fixed roles grounded in the fictional fixture |
| Audio scene planning | ADAPTED + REAL PUBLIC | public plan contract plus real bounded chunker |
| Audio rendering | SIMULATED PUBLIC | deterministic valid WAV tone containers; not speech |
| Playlist and audiobook manifest | SIMULATED PUBLIC | derived from files created during the run |
| Checkpoint resume and idempotent repeat | ADAPTED PUBLIC | artifact hashes are verified before reuse |
| Controlled interruption and failure | ADAPTED PUBLIC | CLI controls and regression tests |
| Network, provider, or paid calls | ABSENT BY DESIGN | standard library only; network is blocked in a scenario test |
| Full text/ebook/PDF import | REAL PRIVATE / DOCUMENTED | public demo ships one embedded text fixture |
| Translation prompts and long-range context | REAL PRIVATE / DOCUMENTED | no prompts, profiles, or model client are shipped |
| Naming continuity and story memory | REAL PRIVATE / DOCUMENTED | contracts and algorithms are withheld |
| Automated repair and readiness policy | REAL PRIVATE / DOCUMENTED | no repair engine is shipped |
| Real multi-voice speech synthesis | REAL PRIVATE / DOCUMENTED | public tones prove orchestration, not speech quality |
| Desktop library, player, diagnostics, setup | REAL PRIVATE / DOCUMENTED | excluded from the code showcase |

This table does not claim universal language support, acoustic quality, deployment
readiness, or business outcomes for the synthetic edition.
