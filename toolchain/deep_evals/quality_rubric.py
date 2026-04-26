from __future__ import annotations


RUBRIC_SCHEMA_VERSION = "darwin-conservative-v1"

QUALITY_RUBRIC = [
    {
        "dimension": "Overall Structure",
        "source": "darwin-skill",
        "source_dimension": "overall_structure",
        "source_weight": 15,
        "question": (
            "Does the answer have clear structure, avoid redundancy and omissions, "
            "and stay consistent with the skill's declared workflow?"
        ),
    },
    {
        "dimension": "Live Test Performance",
        "source": "darwin-skill",
        "source_dimension": "live_test_performance",
        "source_weight": 25,
        "question": (
            "When compared with the baseline answer, does with_skill better complete "
            "the user's intent without adding negative side effects such as verbosity, "
            "format theater, drift, or unnecessary protocol friction?"
        ),
    },
]

ALLOWED_QUALITY_DECISIONS = {"pass", "revise", "hold"}
ALLOWED_REPAIR_LAYERS = {"source", "blueprint-spec", "template", "skill-content"}
DEFAULT_FAILURE_TAG = "skill-content.quality-unclear"


def normalize_rubric_items(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            items.append({"dimension": item.strip(), "question": item.strip()})
        elif isinstance(item, dict) and item.get("dimension"):
            items.append(dict(item))
    return items


def build_rubric_contract(
    *,
    package_specific: object = None,
) -> dict[str, object]:
    return {
        "schema_version": RUBRIC_SCHEMA_VERSION,
        "policy": {
            "deep_eval_scope": "conservative Darwin mapping",
            "global_dimensions": "Only Darwin dimensions 7 and 8 are first-class deep quality dimensions.",
            "quantitative_policy": "Darwin dimensions 1-6 belong to quantitative-summary structural diagnostics.",
            "release_policy": "Rubric evidence informs human review; it is not an automatic release score.",
            "eval_specific_location": "per_eval[].quality_rubric",
        },
        "global": QUALITY_RUBRIC,
        "package_specific": normalize_rubric_items(package_specific),
    }
