from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.eval_factory.catalog import export_certified_bundle, load_factory, validate_certified_bundle


FACTORY_DIR = PROJECT_ROOT / "eval-factory"
BUNDLE_PATH = FACTORY_DIR / "certified-evals" / "swot-analysis" / "swot-analysis-certified-batch-v0.1.json"


def test_load_factory_indexes_first_certified_bundle() -> None:
    catalog = load_factory(FACTORY_DIR)

    assert catalog["counts"] == {
        "source_bank": 3,
        "scenario_cards": 3,
        "eval_candidates": 6,
        "certified_bundles": 1,
        "calibration_reports": 1,
    }
    assert catalog["certified_bundles"][0]["bundle_id"] == "swot-analysis-certified-batch-v0.1"
    assert catalog["certified_bundles"][0]["eval_count"] == 6
    assert catalog["certified_bundles"][0]["package_name"] == "swot-analysis"


def test_validate_certified_bundle_checks_links_and_thresholds() -> None:
    result = validate_certified_bundle(BUNDLE_PATH, factory_dir=FACTORY_DIR)

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["summary"]["eval_count"] == 6
    assert result["summary"]["variant_types"] == ["base", "boundary-stress", "info-missing", "paraphrase"]
    assert result["summary"]["calibration_report_id"] == "swot-analysis-certified-batch-v0.1"


def test_export_certified_bundle_writes_package_evals_json(tmp_path: Path) -> None:
    output_path = tmp_path / "generated-evals.json"

    result = export_certified_bundle(BUNDLE_PATH, output_path)
    exported = json.loads(output_path.read_text(encoding="utf-8"))

    assert result["exported_eval_count"] == 6
    assert exported["skill_name"] == "SWOT Analysis"
    assert exported["bundle_id"] == "swot-analysis-certified-batch-v0.1"
    assert len(exported["evals"]) == 6
    assert exported["evals"][0]["id"] == 101
    assert exported["evals"][0]["prompt"]
    assert exported["evals"][0]["expectations"]
