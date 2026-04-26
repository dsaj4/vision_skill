from __future__ import annotations

from pathlib import Path
from typing import Any

from toolchain.common import load_json, write_json

ALLOWED_VARIANT_TYPES = {"base", "paraphrase", "info-missing", "boundary-stress"}


def _json_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.rglob("*.json") if path.is_file())


def _resolve_factory_dir(bundle_path: Path, factory_dir: str | Path | None = None) -> Path:
    if factory_dir is not None:
        return Path(factory_dir)

    for parent in bundle_path.parents:
        if parent.name == "certified-evals":
            return parent.parent
    raise ValueError(f"Could not infer eval-factory root from {bundle_path}")


def _required_fields(record: dict[str, Any], fields: list[str], prefix: str) -> list[str]:
    errors: list[str] = []
    for field in fields:
        if field not in record or record[field] in ("", None, []):
            errors.append(f"{prefix} missing required field: {field}")
    return errors


def load_factory(factory_dir: str | Path) -> dict[str, Any]:
    root = Path(factory_dir)
    source_files = _json_files(root / "source-bank")
    scenario_files = _json_files(root / "scenario-cards")
    candidate_files = _json_files(root / "eval-candidates")
    certified_bundle_files = _json_files(root / "certified-evals")
    calibration_files = _json_files(root / "calibration-reports")

    bundles: list[dict[str, Any]] = []
    for bundle_path in certified_bundle_files:
        bundle = load_json(bundle_path)
        metadata = bundle.get("metadata", {})
        bundles.append(
            {
                "bundle_id": metadata.get("bundle_id", bundle_path.stem),
                "package_name": metadata.get("package_name", ""),
                "skill_name": metadata.get("skill_name", ""),
                "path": str(bundle_path),
                "eval_count": len(bundle.get("evals", [])),
                "certification_status": metadata.get("certification_status", ""),
            }
        )

    return {
        "factory_dir": str(root),
        "counts": {
            "source_bank": len(source_files),
            "scenario_cards": len(scenario_files),
            "eval_candidates": len(candidate_files),
            "certified_bundles": len(certified_bundle_files),
            "calibration_reports": len(calibration_files),
        },
        "certified_bundles": bundles,
    }


def validate_certified_bundle(bundle_path: str | Path, *, factory_dir: str | Path | None = None) -> dict[str, Any]:
    bundle_file = Path(bundle_path)
    root = _resolve_factory_dir(bundle_file, factory_dir=factory_dir)
    bundle = load_json(bundle_file)
    errors: list[str] = []

    metadata = bundle.get("metadata", {})
    errors.extend(
        _required_fields(
            metadata,
            [
                "bundle_id",
                "package_name",
                "skill_name",
                "task_family",
                "certification_status",
                "calibration_report_path",
            ],
            "metadata",
        )
    )

    thresholds = bundle.get("thresholds", {})
    errors.extend(
        _required_fields(
            thresholds,
            ["strong_vs_weak_win_rate", "judge_agreement_score", "max_tie_rate"],
            "thresholds",
        )
    )

    if metadata.get("certification_status") != "certified":
        errors.append("metadata.certification_status must be 'certified'")

    calibration_report: dict[str, Any] = {}
    calibration_path = root / metadata.get("calibration_report_path", "")
    if not calibration_path.exists():
        errors.append(f"Missing calibration report: {calibration_path}")
    else:
        calibration_report = load_json(calibration_path)

    calibration_index = {
        item.get("eval_id"): item for item in calibration_report.get("per_eval", []) if isinstance(item, dict)
    }

    scenario_index = {}
    for scenario_path in _json_files(root / "scenario-cards"):
        scenario = load_json(scenario_path)
        scenario_id = scenario.get("scenario_id")
        if scenario_id:
            scenario_index[scenario_id] = scenario

    source_ids = set()
    for source_path in _json_files(root / "source-bank"):
        source = load_json(source_path)
        source_id = source.get("source_id")
        if source_id:
            source_ids.add(source_id)

    variant_types: set[str] = set()
    evals = bundle.get("evals", [])
    if not evals:
        errors.append("bundle.evals must not be empty")

    for item in evals:
        eval_id = item.get("eval_id")
        errors.extend(
            _required_fields(
                item,
                [
                    "eval_id",
                    "scenario_id",
                    "candidate_path",
                    "variant_type",
                    "certification_status",
                    "discriminative_score",
                    "judge_agreement_score",
                    "tie_rate",
                    "strong_vs_weak_win_rate",
                ],
                f"eval {eval_id or '<missing>'}",
            )
        )

        scenario = scenario_index.get(item.get("scenario_id"))
        if scenario is None:
            errors.append(f"Eval {eval_id} references missing scenario_id: {item.get('scenario_id')}")
        else:
            for source_id in scenario.get("source_ids", []):
                if source_id not in source_ids:
                    errors.append(f"Scenario {scenario['scenario_id']} references missing source_id: {source_id}")

        variant_type = item.get("variant_type")
        if variant_type not in ALLOWED_VARIANT_TYPES:
            errors.append(f"Eval {eval_id} has unsupported variant_type: {variant_type}")
        else:
            variant_types.add(variant_type)

        if item.get("certification_status") != "certified":
            errors.append(f"Eval {eval_id} certification_status must be 'certified'")

        candidate_path = root / item.get("candidate_path", "")
        if not candidate_path.exists():
            errors.append(f"Eval {eval_id} missing candidate file: {candidate_path}")
            continue

        candidate = load_json(candidate_path)
        errors.extend(
            _required_fields(
                candidate,
                [
                    "eval_id",
                    "scenario_id",
                    "task_family",
                    "variant_type",
                    "prompt",
                    "expected_output",
                    "judge_rubric",
                    "must_preserve",
                    "must_not_do",
                    "expectations",
                ],
                f"candidate {eval_id}",
            )
        )

        if candidate.get("eval_id") != eval_id:
            errors.append(f"Candidate {candidate_path.name} eval_id does not match bundle entry {eval_id}")
        if candidate.get("scenario_id") != item.get("scenario_id"):
            errors.append(f"Candidate {candidate_path.name} scenario_id does not match bundle entry {eval_id}")
        if candidate.get("variant_type") != variant_type:
            errors.append(f"Candidate {candidate_path.name} variant_type does not match bundle entry {eval_id}")
        if candidate.get("task_family") != metadata.get("task_family"):
            errors.append(f"Candidate {candidate_path.name} task_family does not match bundle task_family")

        strong_vs_weak = float(item.get("strong_vs_weak_win_rate", 0.0) or 0.0)
        judge_agreement = float(item.get("judge_agreement_score", 0.0) or 0.0)
        tie_rate = float(item.get("tie_rate", 1.0) or 1.0)

        if strong_vs_weak < float(thresholds.get("strong_vs_weak_win_rate", 0.0) or 0.0):
            errors.append(f"Eval {eval_id} strong_vs_weak_win_rate below threshold")
        if judge_agreement < float(thresholds.get("judge_agreement_score", 0.0) or 0.0):
            errors.append(f"Eval {eval_id} judge_agreement_score below threshold")
        if tie_rate >= float(thresholds.get("max_tie_rate", 1.0) or 1.0):
            errors.append(f"Eval {eval_id} tie_rate must stay below max_tie_rate")

        calibration_entry = calibration_index.get(eval_id)
        if calibration_entry is None:
            errors.append(f"Calibration report missing per_eval entry for eval_id {eval_id}")
        else:
            for metric_name in ("strong_vs_weak_win_rate", "judge_agreement_score", "tie_rate"):
                bundle_metric = round(float(item.get(metric_name, 0.0) or 0.0), 4)
                calibration_metric = round(float(calibration_entry.get(metric_name, 0.0) or 0.0), 4)
                if bundle_metric != calibration_metric:
                    errors.append(
                        f"Calibration mismatch for eval {eval_id}: {metric_name} bundle={bundle_metric} report={calibration_metric}"
                    )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "summary": {
            "bundle_id": metadata.get("bundle_id", bundle_file.stem),
            "package_name": metadata.get("package_name", ""),
            "eval_count": len(evals),
            "variant_types": sorted(variant_types),
            "calibration_report_id": calibration_report.get("metadata", {}).get("report_id", ""),
        },
    }


def export_certified_bundle(
    bundle_path: str | Path,
    output_path: str | Path,
    *,
    factory_dir: str | Path | None = None,
) -> dict[str, Any]:
    validation = validate_certified_bundle(bundle_path, factory_dir=factory_dir)
    if not validation["valid"]:
        joined_errors = "; ".join(validation["errors"])
        raise ValueError(f"Certified bundle validation failed: {joined_errors}")

    bundle_file = Path(bundle_path)
    root = _resolve_factory_dir(bundle_file, factory_dir=factory_dir)
    bundle = load_json(bundle_file)
    metadata = bundle["metadata"]

    exported_evals: list[dict[str, Any]] = []
    for item in sorted(bundle.get("evals", []), key=lambda current: current["eval_id"]):
        candidate = load_json(root / item["candidate_path"])
        exported_evals.append(
            {
                "id": candidate["eval_id"],
                "prompt": candidate["prompt"],
                "expected_output": candidate.get("expected_output", ""),
                "files": candidate.get("files", []),
                "expectations": candidate.get("expectations", []),
                "host_eval": candidate.get("host_eval", {}),
                "certified_metadata": {
                    "scenario_id": candidate["scenario_id"],
                    "variant_type": candidate["variant_type"],
                    "bundle_id": metadata["bundle_id"],
                },
            }
        )

    exported = {
        "skill_name": metadata["skill_name"],
        "package_name": metadata["package_name"],
        "bundle_id": metadata["bundle_id"],
        "generated_from": str(bundle_file),
        "evals": exported_evals,
    }
    write_json(Path(output_path), exported)

    return {
        "output_path": str(output_path),
        "bundle_id": metadata["bundle_id"],
        "exported_eval_count": len(exported_evals),
    }
