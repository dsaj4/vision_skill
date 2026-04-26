from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolchain.common import compact_text, load_json
from toolchain.deep_evals.quality_rubric import build_rubric_contract, normalize_rubric_items


RUN_ARTIFACTS = [
    "request.json",
    "transcript.json",
    "raw_response.json",
    "timing.json",
    "grading.json",
]


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = load_json(path)
    return data if isinstance(data, dict) else {"value": data}


def _read_optional_text(path: Path, max_chars: int) -> str:
    if not path.exists():
        return ""
    return compact_text(path.read_text(encoding="utf-8"), max_chars)


def _load_package_metadata(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "metadata" / "package.json"
    return _load_optional_json(path) if path.exists() else {}


def _load_package_quality_rubric(package_dir: Path, package_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    metadata_items = normalize_rubric_items(package_metadata.get("quality_rubric"))
    rubric_path = package_dir / "metadata" / "quality-rubric.json"
    if not rubric_path.exists():
        return metadata_items
    data = _load_optional_json(rubric_path)
    file_items = normalize_rubric_items(data.get("package_specific", data.get("quality_rubric", data)))
    return [*metadata_items, *file_items]


def _load_run(run_dir: Path) -> dict[str, Any]:
    grading = _load_optional_json(run_dir / "grading.json")
    output_path = Path(grading.get("output_file", "")) if grading.get("output_file") else run_dir / "outputs" / "final_response.md"
    if not output_path.exists():
        output_path = run_dir / "outputs" / "final_response.md"
    latest_output_path = run_dir / "outputs" / "latest_assistant_response.md"

    return {
        "configuration": run_dir.parent.name,
        "run_number": int(run_dir.name.split("-", 1)[1]) if "-" in run_dir.name else 0,
        "run_dir": str(run_dir),
        "final_response": _read_optional_text(output_path, 1800),
        "latest_assistant_response": _read_optional_text(latest_output_path, 1200),
        "request": _load_optional_json(run_dir / "request.json"),
        "transcript_excerpt": compact_text(
            json.dumps(_load_optional_json(run_dir / "transcript.json"), ensure_ascii=False, separators=(",", ":")),
            1800,
        ),
        "raw_response_excerpt": compact_text(
            json.dumps(_load_optional_json(run_dir / "raw_response.json"), ensure_ascii=False, separators=(",", ":")),
            1200,
        ),
        "timing": _load_optional_json(run_dir / "timing.json"),
        "grading_summary": grading.get("summary", {}),
        "expectations": grading.get("expectations", []),
        "evidence_paths": {
            name.replace(".json", ""): str(run_dir / name)
            for name in RUN_ARTIFACTS
            if (run_dir / name).exists()
        }
        | {
            "final_response": str(output_path),
            "latest_assistant_response": str(latest_output_path),
        },
    }


def _load_eval(eval_dir: Path) -> dict[str, Any]:
    eval_metadata = _load_optional_json(eval_dir / "eval_metadata.json")
    runs: list[dict[str, Any]] = []
    for configuration in ("with_skill", "without_skill"):
        config_dir = eval_dir / configuration
        if not config_dir.exists():
            continue
        for run_dir in sorted(config_dir.glob("run-*")):
            if run_dir.is_dir():
                runs.append(_load_run(run_dir))
    return {
        "eval_id": eval_metadata.get("eval_id"),
        "eval_name": eval_metadata.get("eval_name", eval_dir.name),
        "prompt": eval_metadata.get("prompt", ""),
        "expected_output": eval_metadata.get("expected_output", ""),
        "assertions": eval_metadata.get("assertions", []),
        "quality_rubric": normalize_rubric_items(eval_metadata.get("quality_rubric")),
        "execution_eval": eval_metadata.get("execution_eval", {}),
        "host_eval": eval_metadata.get("host_eval", {}),
        "runs": runs,
    }


def build_deep_eval_packet(iteration_dir: str | Path, package_dir: str | Path) -> dict[str, Any]:
    """Build the compact evidence packet for deep quality evaluation.

    This packet intentionally reads raw model answers and run artifacts directly.
    Quantitative artifacts are not the main signal here; they are listed only as
    context paths so the model can understand what other files exist.
    """

    iteration_path = Path(iteration_dir)
    package_path = Path(package_dir)
    package_metadata = _load_package_metadata(package_path)
    package_quality_rubric = _load_package_quality_rubric(package_path, package_metadata)
    skill_text = _read_optional_text(package_path / "SKILL.md", 2400)

    evals = [
        _load_eval(eval_dir)
        for eval_dir in sorted(iteration_path.glob("eval-*"))
        if eval_dir.is_dir()
    ]

    return {
        "metadata": {
            "package_name": package_metadata.get("package_name", package_path.name),
            "skill_name": package_metadata.get("skill_name", package_path.name),
            "iteration_dir": str(iteration_path),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "quality_primary_mode": "deep-quality",
        },
        "quality_task": {
            "language": "zh-CN",
            "instruction": (
                "直接基于原始回答和 run artifacts 判断 skill 内容质量。"
                "不要把 benchmark 分数当作质量结论，只把它们当作辅助线索。"
            ),
            "comparison_focus": [
                "with_skill 是否真正提升用户价值",
                "是否减少协议表演、模板摩擦和泛泛建议",
                "是否帮助用户更会思考并保留判断权",
                "失败应归因到 source / blueprint-spec / template / skill-content",
            ],
        },
        "skill_protocol_summary": skill_text,
        "rubric": build_rubric_contract(package_specific=package_quality_rubric),
        "evals": evals,
        "supporting_artifact_paths": {
            "hard_gate": str(iteration_path / "hard-gate.json"),
            "quantitative_summary": str(iteration_path / "quantitative-summary.json"),
            "benchmark": str(iteration_path / "benchmark.json"),
            "differential_benchmark": str(iteration_path / "differential-benchmark.json"),
            "level3_summary": str(iteration_path / "level3-summary.json"),
            "stability": str(iteration_path / "stability.json"),
        },
    }
