from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Sequence

from toolchain.common import load_json, parse_eval_ids, write_json, write_text
from toolchain.agent_hosts.run_host_eval import run_host_eval
from toolchain.agent_hosts.run_kimi_cli_differential_eval import run_kimi_cli_differential_eval
from toolchain.kimi_cycle.context import next_cycle_name
from toolchain.kimi_cycle.eval_generation import apply_eval_draft, generate_eval_draft
from toolchain.kimi_cycle.skill_rewrite import apply_skill_rewrite, generate_skill_rewrite


def _next_host_iteration_number(workspace_dir: Path) -> int:
    numbers: list[int] = []
    pattern = re.compile(r"^iteration-(\d+)$")
    for path in workspace_dir.iterdir():
        if not path.is_dir():
            continue
        match = pattern.match(path.name)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers or [0]) + 1


def _cycle_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Kimi Production Cycle",
        "",
        f"- Controller: {summary['controller']}",
        f"- Package: {summary['package_name']}",
        f"- Cycle Name: {summary['cycle_name']}",
        "",
        "## Stages",
        "",
        f"- Eval Draft Generated: {summary['stages']['eval_generation']['generated']}",
        f"- Eval Draft Applied: {summary['stages']['eval_generation']['applied']}",
        f"- Skill Draft Generated: {summary['stages']['skill_rewrite']['generated']}",
        f"- Skill Draft Valid: {summary['stages']['skill_rewrite']['valid']}",
        f"- Skill Draft Applied: {summary['stages']['skill_rewrite']['applied']}",
        f"- Differential Eval Ran: {summary['stages']['evaluation']['ran']}",
        f"- Host Eval Ran: {summary['stages']['host_validation']['ran']}",
        "",
        "## Artifacts",
        "",
    ]
    for key, value in summary.get("artifacts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    if summary.get("notes"):
        lines.append("## Notes")
        lines.append("")
        for note in summary["notes"]:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def run_kimi_production_cycle(
    package_dir: str | Path,
    workspace_dir: str | Path,
    *,
    cycle_name: str | None = None,
    model: str | None = None,
    timeout_seconds: int | None = None,
    generate_evals: bool = True,
    apply_generated_evals: bool = False,
    rewrite_skill: bool = True,
    apply_skill: bool = False,
    run_eval: bool = False,
    run_host_validation: bool = False,
    eval_ids: list[int] | None = None,
    max_evals: int | None = None,
    host_eval_ids: list[int] | None = None,
    host_max_evals: int | None = None,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    workspace_path = Path(workspace_dir)
    workspace_path.mkdir(parents=True, exist_ok=True)
    package_meta = load_json(package_path / "metadata" / "package.json")
    resolved_cycle_name = cycle_name or next_cycle_name()
    cycle_dir = workspace_path / "cycles" / resolved_cycle_name
    cycle_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "controller": "codex",
        "generation_backend": "kimi-cli",
        "evaluation_backend": "kimi-code",
        "package_name": package_meta.get("package_name", package_path.name),
        "skill_name": package_meta.get("skill_name", package_path.name),
        "cycle_name": resolved_cycle_name,
        "cycle_dir": str(cycle_dir),
        "stages": {
            "eval_generation": {"generated": False, "applied": False},
            "skill_rewrite": {"generated": False, "valid": False, "applied": False},
            "evaluation": {"ran": False},
            "host_validation": {"ran": False},
        },
        "artifacts": {},
        "notes": [],
    }

    if generate_evals:
        eval_result = generate_eval_draft(
            package_path,
            workspace_path,
            cycle_dir,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        summary["stages"]["eval_generation"]["generated"] = True
        summary["artifacts"]["eval_draft"] = eval_result["draft_path"]
        if apply_generated_evals:
            apply_result = apply_eval_draft(package_path, eval_result["draft_path"])
            summary["stages"]["eval_generation"]["applied"] = bool(apply_result["applied"])
            summary["artifacts"]["package_evals"] = apply_result["output_path"]

    if rewrite_skill:
        rewrite_result = generate_skill_rewrite(
            package_path,
            workspace_path,
            cycle_dir,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        validation = load_json(Path(rewrite_result["validation_path"]))
        summary["stages"]["skill_rewrite"]["generated"] = True
        summary["stages"]["skill_rewrite"]["valid"] = bool(rewrite_result["valid"])
        summary["artifacts"]["skill_draft"] = rewrite_result["generated_skill_path"]
        summary["artifacts"]["skill_validation"] = rewrite_result["validation_path"]
        if apply_skill:
            if rewrite_result["valid"]:
                apply_result = apply_skill_rewrite(package_path, rewrite_result["generated_skill_path"])
                summary["stages"]["skill_rewrite"]["applied"] = bool(apply_result["applied"])
                summary["artifacts"]["applied_skill_paths"] = apply_result["applied_paths"]
            else:
                summary["notes"].append("Skill rewrite was not applied because validation failed.")
                summary["notes"].append(
                    f"Package validator errors: {validation['package_validator']['summary']['errors']}; "
                    f"protocol validator errors: {validation['protocol_validator']['summary']['errors']}."
                )

    if run_eval:
        eval_result = run_kimi_cli_differential_eval(
            package_path,
            workspace_path,
            iteration_name=f"{resolved_cycle_name}-eval",
            eval_ids=eval_ids,
            max_evals=max_evals,
            timeout_seconds=timeout_seconds or 240,
        )
        summary["stages"]["evaluation"]["ran"] = True
        summary["artifacts"]["kimi_differential_summary"] = eval_result["summary_path"]
        summary["artifacts"]["kimi_differential_iteration_dir"] = eval_result["iteration_dir"]

    if run_host_validation:
        host_result = run_host_eval(
            package_path,
            workspace_path,
            iteration_number=_next_host_iteration_number(workspace_path),
            host_backend="kimi-code",
            eval_ids=host_eval_ids,
            max_evals=host_max_evals,
            timeout_seconds=timeout_seconds or 180,
        )
        summary["stages"]["host_validation"]["ran"] = True
        summary["artifacts"]["host_benchmark"] = host_result["host_benchmark_path"]
        summary["artifacts"]["host_iteration_dir"] = host_result["iteration_dir"]

    write_json(cycle_dir / "cycle-summary.json", summary)
    write_text(cycle_dir / "cycle-summary.md", _cycle_summary_markdown(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Codex-controlled Kimi production cycle.")
    parser.add_argument("--package-dir", required=True, help="Path to the package directory.")
    parser.add_argument("--workspace-dir", required=True, help="Path to the package workspace directory.")
    parser.add_argument("--cycle-name", default=None, help="Optional explicit cycle name.")
    parser.add_argument("--model", default=None, help="Optional Kimi CLI model override.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Optional per-stage timeout override.")
    parser.add_argument("--skip-eval-generation", action="store_true", help="Skip Kimi eval draft generation.")
    parser.add_argument("--apply-generated-evals", action="store_true", help="Apply generated eval draft into package evals/evals.json.")
    parser.add_argument("--skip-skill-rewrite", action="store_true", help="Skip Kimi skill rewrite generation.")
    parser.add_argument("--apply-skill", action="store_true", help="Apply generated skill draft if validation passes.")
    parser.add_argument("--run-eval", action="store_true", help="Run Kimi differential evaluation after generation/apply stages.")
    parser.add_argument("--run-host-validation", action="store_true", help="Run Kimi host validation after the main cycle.")
    parser.add_argument("--eval-ids", default=None, help="Optional comma-separated eval ids for Kimi differential evaluation.")
    parser.add_argument("--max-evals", type=int, default=None, help="Optional max eval count for Kimi differential evaluation.")
    parser.add_argument("--host-eval-ids", default=None, help="Optional comma-separated host eval ids.")
    parser.add_argument("--host-max-evals", type=int, default=None, help="Optional max host eval count.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_kimi_production_cycle(
        args.package_dir,
        args.workspace_dir,
        cycle_name=args.cycle_name,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
        generate_evals=not args.skip_eval_generation,
        apply_generated_evals=args.apply_generated_evals,
        rewrite_skill=not args.skip_skill_rewrite,
        apply_skill=args.apply_skill,
        run_eval=args.run_eval,
        run_host_validation=args.run_host_validation,
        eval_ids=parse_eval_ids(args.eval_ids),
        max_evals=args.max_evals,
        host_eval_ids=parse_eval_ids(args.host_eval_ids),
        host_max_evals=args.host_max_evals,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
