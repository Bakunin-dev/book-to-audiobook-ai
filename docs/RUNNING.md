# Running and inspecting the showcase

## Requirements

- Python 3.11 or newer.
- No third-party packages.
- No API key, model download, or network connection.

## Interruption and resume tour

```sh
python demo.py --tour
```

The command uses a temporary workspace. It stops after the fixture translation,
then resumes and reports which checkpoints were reused.

## Persistent workspace

```sh
python demo.py --workspace demo-output
python demo.py --workspace demo-output
```

Inspect `demo-output/pipeline.json`, `source-manifest.json`,
`translation-manifest.json`, `verification.json`, `cast.json`, `audio-plan.json`,
`audiobook.json`, `audiobook.m3u8`, and the generated `audio/` directory. On the
second run all six stages should report `REUSED`.

Additional controls:

```sh
python demo.py --workspace demo-output --stop-after verify
python demo.py --workspace demo-output --fail-before render
python demo.py --workspace demo-output --json
```

Use a new workspace after a deliberate failure if you want an entirely clean tour.
Never treat the generated tones as speech or the fixture mapping as a translation
model.

## Tests and publication gate

```sh
python -m unittest discover -s tests -v
python tools/release.py --check
python tools/release.py --build
```

The release command reads only this public directory. The ZIP contains exactly the
paths in `public-files.json`; generated demo workspaces and release artifacts are
excluded.
