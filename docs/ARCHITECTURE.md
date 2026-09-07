# Architecture of the public slice

The public repository preserves the direction of the private workflow while
replacing product-critical engines at explicit ports.

```text
demo.py
  → showcase.pipeline
      → TextDocument / stable paragraph IDs       [REAL PUBLIC]
      → FixtureTranslator                         [SIMULATED PUBLIC]
      → structural tagged-text verification       [REAL PUBLIC]
      → FixtureCastAnalyzer                       [SIMULATED PUBLIC]
      → chapter-aware speech chunking             [REAL PUBLIC]
      → SyntheticWaveRenderer                     [SIMULATED PUBLIC]
      → atomic checkpoints and process lock       [REAL PUBLIC]
```

## State and recovery

Each stage writes its artifacts atomically. `pipeline.json` stores hashes for the
artifacts of every completed stage. A resumed run verifies those hashes before it
reuses work. Missing or changed outputs stop the run instead of silently mixing
incompatible state.

The process lock prevents two executions from updating one workspace concurrently.
An intentional stop happens only after a completed checkpoint. A controlled failure
leaves earlier stages available for a later run.

## Closed seams

The private implementations behind translation, book context, cast attribution,
quality recovery and speech rendering do not appear in this tree. The public ports
are deliberately small enough to understand, and the fixture adapters are complete
implementations rather than empty placeholders.

The desktop interface and installer are also excluded. They are presentation and
distribution layers around the same private workflow, not requirements for studying
this code slice.
