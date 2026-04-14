from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any


def build_host_benchmark(
    *,
    package_name: str,
    skill_name: str,
    iteration_dir: Path,
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_trigger_cases = [item for item in runs if item["expected_trigger"] is True]
    expected_non_trigger_cases = [item for item in runs if item["expected_trigger"] is False]
    protocol_cases = [item for item in runs if item["expected_protocol_path"]]
    direct_cases = [item for item in runs if "direct-result" in item["expected_protocol_path"]]
    followup_cases = [item for item in runs if "missing-info" in item["expected_protocol_path"]]
    staged_cases = [item for item in runs if item["expected_protocol_path"].startswith("staged")]
    pass_rates = [float(item["grading"]["summary"]["pass_rate"]) for item in runs]

    trigger_summary = {
        "trigger_success_rate": _safe_rate(
            sum(1 for item in expected_trigger_cases if item["trigger_report"]["triggered"]),
            len(expected_trigger_cases),
        ),
        "false_trigger_rate": _safe_rate(
            sum(1 for item in expected_non_trigger_cases if item["trigger_report"]["triggered"]),
            len(expected_non_trigger_cases),
        ),
        "skill_read_before_first_answer_rate": _safe_rate(
            sum(1 for item in runs if item["signal_report"]["trigger_signals"]["skill_read_before_first_answer"]),
            len(runs),
        ),
        "canonical_skill_read_rate": _safe_rate(
            sum(1 for item in runs if item["signal_report"]["trigger_signals"]["canonical_skill_read"]),
            len(runs),
        ),
    }

    protocol_summary = {
        "protocol_path_match_rate": _safe_rate(
            sum(1 for item in protocol_cases if item["protocol_path_match"]),
            len(protocol_cases),
        ),
        "direct_result_compliance_rate": _safe_rate(
            sum(1 for item in direct_cases if item["protocol_report"]["observed_protocol_path"] == "direct-result -> no-checkpoint"),
            len(direct_cases),
        ),
        "followup_precision": _safe_rate(
            sum(1 for item in followup_cases if item["protocol_report"]["observed_protocol_path"] == "missing-info -> ask-followup"),
            len(followup_cases),
        ),
        "checkpoint_obedience_rate": _safe_rate(
            sum(1 for item in staged_cases if "skipped-checkpoint" not in item["protocol_report"]["observed_protocol_path"]),
            len(staged_cases),
        ),
        "premature_full_answer_rate": _safe_rate(
            sum(1 for item in runs if item["protocol_report"]["observed_protocol_path"] == "missing-info -> premature-full-answer"),
            len(runs),
        ),
        "branch_recovery_rate": _safe_rate(
            sum(
                1
                for item in staged_cases
                if item["protocol_report"]["observed_protocol_path"] in {"staged -> continue-loop", "staged -> revise-loop"}
            ),
            len(staged_cases),
        ),
    }

    host_environment_summary = {
        "noise_presence_rate": _safe_rate(
            sum(1 for item in runs if any(item["noise_flags"].values())),
            len(runs),
        ),
        "noise_before_first_answer_rate": _safe_rate(
            sum(1 for item in runs if item["noise_flags"]["external_noise_before_first_answer"]),
            len(runs),
        ),
        "plugin_interference_rate": _safe_rate(
            sum(1 for item in runs if item["noise_flags"]["plugin_sync_noise_present"]),
            len(runs),
        ),
        "network_interference_rate": _safe_rate(
            sum(1 for item in runs if item["noise_flags"]["cloudflare_or_html_challenge_present"]),
            len(runs),
        ),
    }

    return {
        "metadata": {
            "package_name": package_name,
            "skill_name": skill_name,
            "iteration_dir": str(iteration_dir),
            "total_evals": len(runs),
        },
        "runs": runs,
        "trigger_summary": trigger_summary,
        "protocol_summary": protocol_summary,
        "host_environment_summary": host_environment_summary,
        "summary": {
            **trigger_summary,
            **protocol_summary,
            **host_environment_summary,
            "avg_host_pass_rate": round(mean(pass_rates), 4) if pass_rates else 0.0,
            "host_value_delta": None,
        },
    }


def benchmark_markdown(benchmark: dict[str, Any]) -> str:
    trigger = benchmark["trigger_summary"]
    protocol = benchmark["protocol_summary"]
    environment = benchmark["host_environment_summary"]
    summary = benchmark["summary"]
    lines = [
        "# Host Benchmark",
        "",
        "## Trigger Summary",
        "",
        f"- Trigger success rate: {trigger['trigger_success_rate']:.4f}",
        f"- False trigger rate: {trigger['false_trigger_rate']:.4f}",
        f"- Skill read before first answer rate: {trigger['skill_read_before_first_answer_rate']:.4f}",
        f"- Canonical skill read rate: {trigger['canonical_skill_read_rate']:.4f}",
        "",
        "## Protocol Summary",
        "",
        f"- Protocol path match rate: {protocol['protocol_path_match_rate']:.4f}",
        f"- Direct-result compliance rate: {protocol['direct_result_compliance_rate']:.4f}",
        f"- Followup precision: {protocol['followup_precision']:.4f}",
        f"- Checkpoint obedience rate: {protocol['checkpoint_obedience_rate']:.4f}",
        f"- Premature full answer rate: {protocol['premature_full_answer_rate']:.4f}",
        f"- Branch recovery rate: {protocol['branch_recovery_rate']:.4f}",
        "",
        "## Host Environment Summary",
        "",
        f"- Noise presence rate: {environment['noise_presence_rate']:.4f}",
        f"- Noise before first answer rate: {environment['noise_before_first_answer_rate']:.4f}",
        f"- Plugin interference rate: {environment['plugin_interference_rate']:.4f}",
        f"- Network interference rate: {environment['network_interference_rate']:.4f}",
        "",
        f"- Avg host pass rate: {summary['avg_host_pass_rate']:.4f}",
        "",
    ]
    return "\n".join(lines)


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


__all__ = ["benchmark_markdown", "build_host_benchmark"]
