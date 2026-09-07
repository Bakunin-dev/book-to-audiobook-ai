"""Run the offline Potter Code Showcase."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile

from aitran.errors import DemoInterrupted, ShowcaseError
from aitran.showcase.models import Stage
from aitran.showcase.pipeline import run_showcase


def _print_summary(summary) -> None:
    print("Potter Code Showcase · synthetic offline execution")
    for event in summary.events:
        print(f"[{event.action.upper():9}] {event.stage.value:10} · {event.detail}")
    print(
        f"READY · chapters={summary.chapter_count} scenes={summary.scene_count} "
        f"audio_files={len(summary.audio_files)}"
    )
    print("BOUNDARY · translation=fixture-only audio=synthetic-tones network_calls=0")
    print(f"WORKSPACE · {summary.workspace}")


def _tour() -> int:
    with tempfile.TemporaryDirectory(prefix="potter-showcase-") as name:
        workspace = Path(name)
        print("Potter Code Showcase · interruption and resume tour")
        try:
            run_showcase(workspace, stop_after=Stage.TRANSLATE)
        except DemoInterrupted as exc:
            print(f"[PAUSED   ] {exc}")
        summary = run_showcase(workspace)
        _print_summary(summary)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("demo-output"))
    parser.add_argument("--stop-after", choices=[stage.value for stage in Stage])
    parser.add_argument("--fail-before", choices=[stage.value for stage in Stage])
    parser.add_argument("--tour", action="store_true", help="Run an interruption/resume tour.")
    parser.add_argument("--json", action="store_true", help="Print the final summary as JSON.")
    args = parser.parse_args()
    if args.tour:
        return _tour()
    try:
        summary = run_showcase(
            args.workspace,
            stop_after=args.stop_after,
            fail_before=args.fail_before,
        )
    except DemoInterrupted as exc:
        print(str(exc))
        return 2
    except ShowcaseError as exc:
        print(f"SHOWCASE BLOCKED: {exc}")
        return 1
    if args.json:
        value = asdict(summary)
        value["workspace"] = str(value["workspace"])
        value["status_file"] = str(value["status_file"])
        value["audio_files"] = [str(path) for path in value["audio_files"]]
        value["events"] = [
            {**event, "stage": event["stage"].value}
            for event in value["events"]
        ]
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        _print_summary(summary)
    return 0


if __name__ == "__main__":
    # Keep Russian progress messages readable in redirected Windows output too.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
