from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from toolchain.hard_gates.artifact_gate import run_hard_gate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run hard gate checks for a Vision Skill iteration.")
    parser.add_argument("--iteration-dir", required=True, help="Path to the iteration directory.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_hard_gate(Path(args.iteration_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
