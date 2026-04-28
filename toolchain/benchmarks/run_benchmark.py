from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from toolchain.benchmarks.aggregate_benchmark import generate_benchmark, generate_markdown
from toolchain.common import is_active_run_dir, write_json, write_text
from toolchain.graders.capability_grader import grade_run


def grade_iteration_runs(
    iteration_path: str | Path,
    skill_name: str = "",
    skill_path: str = "",
) -> dict[str, Any]:
    iteration_dir = Path(iteration_path)
    graded_runs: list[str] = []

    for eval_dir in sorted(iteration_dir.glob("eval-*")):
        for configuration_dir in sorted(eval_dir.iterdir()):
            if not configuration_dir.is_dir() or configuration_dir.name == "__pycache__":
                continue
            for run_dir in sorted(configuration_dir.glob("run-*")):
                if not is_active_run_dir(run_dir, iteration_dir):
                    continue
                outputs_dir = run_dir / "outputs"
                if not outputs_dir.exists():
                    continue
                try:
                    grade_run(run_dir)
                except FileNotFoundError:
                    continue
                graded_runs.append(str(run_dir))

    benchmark = generate_benchmark(iteration_dir, skill_name=skill_name, skill_path=skill_path)
    benchmark_path = iteration_dir / "benchmark.json"
    benchmark_markdown_path = iteration_dir / "benchmark.md"
    write_json(benchmark_path, benchmark)
    write_text(benchmark_markdown_path, generate_markdown(benchmark))

    return {
        "iteration_dir": str(iteration_dir),
        "graded_runs": graded_runs,
        "benchmark": benchmark,
        "benchmark_path": str(benchmark_path),
        "benchmark_markdown_path": str(benchmark_markdown_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Grade an iteration and generate benchmark artifacts.")
    parser.add_argument("--iteration-dir", required=True, help="Path to the iteration directory.")
    parser.add_argument("--skill-name", default="", help="Optional skill name for benchmark metadata.")
    parser.add_argument("--skill-path", default="", help="Optional skill path for benchmark metadata.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = grade_iteration_runs(
        args.iteration_dir,
        skill_name=args.skill_name,
        skill_path=args.skill_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
