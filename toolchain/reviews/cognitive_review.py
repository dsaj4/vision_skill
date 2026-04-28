from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from toolchain.common import load_json, write_json, write_text
from toolchain.kimi_runtime import CommandRunner
from toolchain.kimi_workspace import read_workspace_text, run_kimi_workspace_task, write_workspace_task


Sender = Callable[[dict[str, Any]], dict[str, Any]]


RUBRIC_DIMENSIONS = [
    "Protocol Fidelity",
    "Structural Output",
    "Thinking Support",
    "Judgment Preservation",
    "Boundary Safety",
    "VisionTree Voice",
]

AUTHORIZATION_DECISIONS = {"pending", "approve", "revise", "hold"}
FINAL_AUTHORIZATION_DECISIONS = {"approve", "revise", "hold"}
LEGACY_DECISION_MAP = {
    "pass": "approve",
    "revise": "revise",
    "hold": "hold",
}
DEFAULT_CONVERSATION_REVIEWER = "conversation-user"
DEFAULT_REVIEW_TIMEOUT_SECONDS = 240


def _review_model(explicit: str | None = None) -> str:
    return explicit or os.getenv("VISION_REVIEW_MODEL") or os.getenv("VISION_ANALYZER_MODEL") or "kimi-cli-default"


def _index_benchmark_runs(benchmark: dict[str, Any]) -> dict[tuple[int, int, str], dict[str, Any]]:
    return {
        (int(run["eval_id"]), int(run["run_number"]), str(run["configuration"])): run
        for run in benchmark.get("runs", [])
    }


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = load_json(path)
    return data if isinstance(data, dict) else {}


def _load_eval_metadata(eval_dir: Path) -> dict[str, Any]:
    metadata = _load_optional_json(eval_dir / "eval_metadata.json")
    return {
        "eval_id": metadata.get("eval_id"),
        "eval_name": metadata.get("eval_name", eval_dir.name),
    }


def _run_number(run_dir: Path) -> int:
    try:
        return int(run_dir.name.split("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def _build_raw_run_meta(run_dir: Path, eval_metadata: dict[str, Any]) -> dict[str, Any]:
    grading = _load_optional_json(run_dir / "grading.json")
    return {
        "eval_id": eval_metadata.get("eval_id"),
        "eval_name": eval_metadata.get("eval_name", ""),
        "configuration": run_dir.parent.name,
        "run_number": _run_number(run_dir),
        "run_dir": str(run_dir),
        "pairwise_winner": "not_available",
        "pairwise_margin": 0.0,
        "judge_disagreement": False,
        "result": grading.get("summary", {}),
    }


def _raw_runs_by_configuration(iteration_dir: Path, configuration: str) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for eval_dir in sorted(iteration_dir.glob("eval-*")):
        if not eval_dir.is_dir():
            continue
        eval_metadata = _load_eval_metadata(eval_dir)
        config_dir = eval_dir / configuration
        if not config_dir.exists():
            continue
        for run_dir in sorted(config_dir.glob("run-*")):
            if run_dir.is_dir():
                runs.append(_build_raw_run_meta(run_dir, eval_metadata))
    return runs


def _build_run_meta(pair: dict[str, Any], configuration: str, benchmark_index: dict[tuple[int, int, str], dict[str, Any]]) -> dict[str, Any]:
    run = benchmark_index.get((int(pair["eval_id"]), int(pair["run_number"]), configuration), {})
    run_dir_key = "with_skill_run_dir" if configuration == "with_skill" else "without_skill_run_dir"
    return {
        "eval_id": pair["eval_id"],
        "eval_name": pair["eval_name"],
        "configuration": configuration,
        "run_number": pair["run_number"],
        "run_dir": pair.get(run_dir_key, ""),
        "pairwise_winner": pair.get("final_winner", "not_comparable"),
        "pairwise_margin": float(pair.get("avg_margin", 0.0) or 0.0),
        "judge_disagreement": bool(pair.get("judge_disagreement", False)),
        "result": run.get("result", {}),
    }


def _select_representative_runs(
    iteration_dir: Path,
    level3_summary: dict[str, Any],
    benchmark: dict[str, Any],
) -> dict[str, Any]:
    pairwise = level3_summary.get("per_eval", [])
    benchmark_index = _index_benchmark_runs(benchmark)
    wins = [pair for pair in pairwise if pair.get("final_winner") == "with_skill"]
    losses = [pair for pair in pairwise if pair.get("final_winner") == "without_skill"]
    comparable = [pair for pair in pairwise if pair.get("final_winner") != "not_comparable"]

    if not pairwise:
        with_skill_runs = _raw_runs_by_configuration(iteration_dir, "with_skill")
        without_skill_runs = _raw_runs_by_configuration(iteration_dir, "without_skill")
        best_with_skill = with_skill_runs[0] if with_skill_runs else {}
        worst_with_skill = with_skill_runs[-1] if with_skill_runs else {}
        baseline = {}
        if best_with_skill:
            baseline = next(
                (run for run in without_skill_runs if run.get("eval_id") == best_with_skill.get("eval_id")),
                without_skill_runs[0] if without_skill_runs else {},
            )
        return {
            "best_with_skill": best_with_skill,
            "worst_with_skill": worst_with_skill,
            "baseline_comparison": baseline,
        }

    best_pair = max(wins or comparable, key=lambda item: float(item.get("avg_margin", 0.0) or 0.0), default={})
    if losses:
        worst_pair = max(losses, key=lambda item: float(item.get("avg_margin", 0.0) or 0.0), default={})
    else:
        worst_pair = min(comparable, key=lambda item: float(item.get("avg_margin", 0.0) or 0.0), default={})
    baseline_pair = best_pair or (comparable[0] if comparable else {})
    return {
        "best_with_skill": _build_run_meta(best_pair, "with_skill", benchmark_index) if best_pair else {},
        "worst_with_skill": _build_run_meta(worst_pair, "with_skill", benchmark_index) if worst_pair else {},
        "baseline_comparison": _build_run_meta(baseline_pair, "without_skill", benchmark_index) if baseline_pair else {},
    }


def _suggested_scores(level3_summary: dict[str, Any], stability: dict[str, Any], analysis: dict[str, Any]) -> dict[str, int]:
    gate = level3_summary.get("gate_summary", {})
    pairwise = level3_summary.get("pairwise_summary", {})
    with_pass = gate.get("with_skill", {}).get("pass_rate", {}).get("mean", 0.0)
    win_rate = float(pairwise.get("win_rate", 0.0) or 0.0)
    cost_adjusted_value = float(pairwise.get("cost_adjusted_value", 0.0) or 0.0)
    instability_flags = set(stability.get("overall", {}).get("flags", []))
    failure_tags = set()
    for item in analysis.get("per_eval", []):
        failure_tags.update(item.get("failure_tags", []))

    protocol = 3 if with_pass >= 0.95 else 2 if with_pass >= 0.8 else 1 if with_pass >= 0.6 else 0
    structural = 3 if win_rate >= 0.75 else 2 if win_rate >= 0.5 else 1
    thinking = 2 if analysis.get("cross_eval_summary", {}).get("overall_winner") == "with_skill" and cost_adjusted_value > 0 else 1
    judgment = 2 if "template.checkpoint-fake" not in failure_tags else 1
    boundary = 1 if "skill-content.boundary-weak" in failure_tags else 2
    voice = 1 if "template.voice-drift" in failure_tags else 2

    if "unstable" in instability_flags or "weak_stability_value" in instability_flags or "instability_risk" in instability_flags:
        protocol = max(protocol - 1, 0)
        thinking = max(thinking - 1, 0)

    return {
        "Protocol Fidelity": protocol,
        "Structural Output": structural,
        "Thinking Support": thinking,
        "Judgment Preservation": judgment,
        "Boundary Safety": boundary,
        "VisionTree Voice": voice,
    }


def _suggested_scores_from_deep_eval(deep_eval: dict[str, Any], hard_gate: dict[str, Any]) -> dict[str, int]:
    signal = deep_eval.get("release_signal", {})
    decision = signal.get("decision", "revise")
    winners = [item.get("winner", "tie") for item in deep_eval.get("per_eval", [])]
    failure_tags = {
        tag
        for item in deep_eval.get("per_eval", [])
        for tag in item.get("failure_tags", [])
    }

    base = 3 if decision == "pass" else 2 if decision == "revise" else 1
    protocol = 2 if hard_gate.get("passed", True) else 0
    structural = 3 if winners and all(winner == "with_skill" for winner in winners) else 2 if "with_skill" in winners else 1
    thinking = base
    judgment = 1 if any("checkpoint-fake" in tag or "judgment" in tag for tag in failure_tags) else min(base, 2)
    boundary = 1 if any("boundary" in tag for tag in failure_tags) else 2
    voice = 1 if any("voice" in tag or "generic" in tag for tag in failure_tags) else 2

    return {
        "Protocol Fidelity": protocol,
        "Structural Output": structural,
        "Thinking Support": thinking,
        "Judgment Preservation": judgment,
        "Boundary Safety": boundary,
        "VisionTree Voice": voice,
    }


def _quantitative_risks(quantitative: dict[str, Any]) -> list[str]:
    risks = quantitative.get("supporting_risks", [])
    normalized: list[str] = []
    for item in risks if isinstance(risks, list) else []:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("summary") or item.get("risk") or item.get("issue") or "").strip()
        else:
            text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _suggested_human_decision(hard_gate: dict[str, Any], deep_eval: dict[str, Any]) -> str:
    if hard_gate and not hard_gate.get("passed", False):
        return "hold"
    deep_decision = deep_eval.get("release_signal", {}).get("decision", "revise") if deep_eval else "revise"
    if deep_decision == "hold":
        return "hold"
    if deep_decision == "revise":
        return "revise"
    return "approve"


def _build_key_findings(
    hard_gate: dict[str, Any],
    deep_eval: dict[str, Any],
    quantitative: dict[str, Any],
    level3_summary: dict[str, Any],
    representative_runs: dict[str, Any],
) -> list[str]:
    findings: list[str] = []
    deep_signal = deep_eval.get("release_signal", {})
    deep_decision = deep_signal.get("decision", "revise")
    if hard_gate:
        if hard_gate.get("passed", False):
            findings.append("Artifacts 已经完整落盘，当前 iteration 可以进入正式质量判断。")
        else:
            findings.append("Artifacts 不完整，当前 iteration 在进入人工放行前仍有硬门槛问题需要先修复。")
    if deep_decision == "pass":
        findings.append("机器侧主质量判断为 pass，说明当前回答质量已达到可进入人工批准判断的水平。")
    elif deep_decision == "revise":
        findings.append("机器侧主质量判断为 revise，说明当前版本有价值但仍存在明显可修问题。")
    else:
        findings.append("机器侧主质量判断为 hold，当前版本存在不建议人工直接放行的硬风险。")

    pairwise = level3_summary.get("pairwise_summary", {})
    if pairwise:
        win_rate = float(pairwise.get("win_rate", 0.0) or 0.0)
        findings.append(f"定量支持包显示 with_skill 的相对胜率为 {win_rate:.2f}，这只作为 supporting evidence，不替代 deep eval 结论。")

    risks = _quantitative_risks(quantitative)
    if risks:
        findings.append(f"当前定量支持包额外提示了 {len(risks)} 条风险信号，需要在人工审阅时一起核对。")

    best_run = representative_runs.get("best_with_skill", {})
    if best_run:
        findings.append(
            f"最值得先看的代表样本是 eval {best_run.get('eval_id')} 的 with_skill run-{best_run.get('run_number')}，它最能体现当前版本的上限表现。"
        )

    reasons = deep_signal.get("reasons", [])
    if reasons:
        findings.extend(str(reason).strip() for reason in reasons if str(reason).strip())

    deduped: list[str] = []
    for item in findings:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:5]


def _build_blocking_or_risky_issues(
    hard_gate: dict[str, Any],
    deep_eval: dict[str, Any],
    quantitative: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if hard_gate and not hard_gate.get("passed", False):
        items.append(
            {
                "severity": "blocking",
                "code": "hard_gate_failed",
                "human_overridable": False,
                "detail": "hard gate 未通过，说明 run artifacts 还不完整，不能直接作为放行依据。",
            }
        )
        for blocker in hard_gate.get("blockers", []):
            items.append(
                {
                    "severity": "blocking",
                    "code": str(blocker),
                    "human_overridable": False,
                    "detail": str(blocker),
                }
            )

    deep_signal = deep_eval.get("release_signal", {})
    deep_decision = deep_signal.get("decision", "revise")
    if deep_decision == "hold":
        items.append(
            {
                "severity": "blocking",
                "code": "deep_eval_decision:hold",
                "human_overridable": False,
                "detail": "deep eval 已明确给出 hold，这属于人工不可覆盖的硬阻塞。",
            }
        )
    elif deep_decision == "revise":
        items.append(
            {
                "severity": "risk",
                "code": "deep_eval_decision:revise",
                "human_overridable": True,
                "detail": "deep eval 建议 revise；人工可以在充分证据下批准，但需要明确承担这次覆盖判断。",
            }
        )

    for risk in _quantitative_risks(quantitative):
        items.append(
            {
                "severity": "risk",
                "code": "quantitative_supporting_risk",
                "human_overridable": True,
                "detail": risk,
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (str(item.get("code", "")), str(item.get("detail", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:6]


def build_agent_review_report_payload(iteration_dir: Path, package_dir: Path) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    package_path = Path(package_dir)
    benchmark = _load_optional_json(iteration_path / "benchmark.json")
    stability = _load_optional_json(iteration_path / "stability.json")
    analysis = _load_optional_json(iteration_path / "analysis.json")
    deep_eval = _load_optional_json(iteration_path / "deep-eval.json")
    hard_gate = _load_optional_json(iteration_path / "hard-gate.json")
    quantitative = _load_optional_json(iteration_path / "quantitative-summary.json")
    level3_summary = _load_optional_json(iteration_path / "level3-summary.json")
    representative_runs = _select_representative_runs(iteration_path, level3_summary, benchmark)
    repair_recommendations = deep_eval.get("repair_recommendations") or analysis.get("repair_recommendations", [])
    quality_primary_mode = deep_eval.get("metadata", {}).get("quality_primary_mode", "legacy-analysis")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report_id = f"{iteration_path.name}:{generated_at}"
    suggested_human_decision = _suggested_human_decision(hard_gate, deep_eval)

    report = {
        "metadata": {
            "package_name": package_path.name,
            "skill_name": level3_summary.get("metadata", {}).get("skill_name", package_path.name),
            "iteration": iteration_path.name,
            "generated_at": generated_at,
            "report_id": report_id,
            "quality_primary_mode": quality_primary_mode,
        },
        "summary": {
            "hard_gate_passed": hard_gate.get("passed"),
            "deep_eval_release_signal": deep_eval.get("release_signal", {}),
            "quantitative_supporting_risks": _quantitative_risks(quantitative),
            "pairwise_summary": level3_summary.get("pairwise_summary", {}),
            "suggested_human_decision": suggested_human_decision,
        },
        "key_findings": _build_key_findings(
            hard_gate,
            deep_eval,
            quantitative,
            level3_summary,
            representative_runs,
        ),
        "blocking_or_risky_issues": _build_blocking_or_risky_issues(
            hard_gate,
            deep_eval,
            quantitative,
        ),
        "repair_recommendations": repair_recommendations,
        "representative_runs": representative_runs,
        "suggested_scores": (
            _suggested_scores_from_deep_eval(deep_eval, hard_gate)
            if deep_eval
            else _suggested_scores(level3_summary, stability, analysis)
        ),
        "evidence_paths": {
            "hard_gate": str(iteration_path / "hard-gate.json"),
            "deep_eval": str(iteration_path / "deep-eval.json"),
            "deep_eval_markdown": str(iteration_path / "deep-eval.md"),
            "quantitative_summary": str(iteration_path / "quantitative-summary.json"),
            "level3_summary": str(iteration_path / "level3-summary.json"),
            "benchmark": str(iteration_path / "benchmark.json"),
            "stability": str(iteration_path / "stability.json"),
            "analysis": str(iteration_path / "analysis.json"),
        },
    }
    return report


def _review_render_system_prompt() -> str:
    return (
        "你是 Vision Skill 的人工审阅报告撰写助手。"
        "请基于给定 JSON 生成一份给人类 reviewer 阅读的中文 Markdown 审阅报告。"
        "要求：结论优先，证据随后；明确区分硬阻塞与可人工覆盖风险；"
        "不要输出 JSON，不要复述整份路径列表，不要编造结论。"
        "deep-eval 是主质量依据，quantitative 只作为 supporting diagnostics。"
    )


def _review_render_user_prompt(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "请把下面这份 agent review report 渲染成一份高可读的人类审阅报告。",
            "输出必须是中文 Markdown。",
            "建议结构：",
            "1. 报告头",
            "2. 最终审阅结论摘要",
            "3. 关键发现",
            "4. 主要风险与阻塞",
            "5. 代表性证据",
            "6. 修补建议",
            "7. 证据索引",
            "",
            json.dumps(report, ensure_ascii=False, indent=2),
        ]
    )


def _workspace_review_contract() -> str:
    return "\n".join(
        [
            "# Output Contract",
            "",
            "Required file: `outputs/human-review-packet.md`.",
            "",
            "Write a Chinese Markdown review report for a human reviewer.",
            "Do not output JSON.",
            "Do not put the full report in the terminal response.",
        ]
    )


def _workspace_review_task_markdown() -> str:
    return "\n".join(
        [
            "# Controlled Human Review Packet Rendering Task",
            "",
            "This is a workspace-file task. The terminal response is log-only.",
            "",
            "## Inputs",
            "",
            "- Read `inputs/agent-review-report.json`.",
            "- Render a readable Chinese Markdown review report for a human reviewer.",
            "- `deep-eval` is the primary quality basis.",
            "- `quantitative-summary` is supporting context only.",
            "",
            "## Required Output",
            "",
            "Write only `outputs/human-review-packet.md`.",
        ]
    )


def _render_human_review_packet_with_sender(report: dict[str, Any], *, sender: Sender, review_model: str) -> str:
    payload = {
        "model": review_model,
        "messages": [
            {"role": "system", "content": _review_render_system_prompt()},
            {"role": "user", "content": _review_render_user_prompt(report)},
        ],
    }
    raw_response = sender(payload)
    content = str(raw_response.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
    if not content:
        raise ValueError("Human review packet sender returned empty content.")
    return content if content.endswith("\n") else content + "\n"


def _render_human_review_packet_with_workspace(
    report: dict[str, Any],
    *,
    iteration_dir: Path,
    command_runner: CommandRunner | None,
    review_model: str | None,
    timeout_seconds: int | None,
) -> str:
    task_dir = iteration_dir / ".kimi-human-review"
    required_outputs = ["outputs/human-review-packet.md"]
    write_workspace_task(
        task_dir,
        task_markdown=_workspace_review_task_markdown(),
        required_outputs=required_outputs,
        contract_markdown=_workspace_review_contract(),
        inputs={"inputs/agent-review-report.json": report},
        metadata={
            "runner": "kimi-code",
            "task_type": "human-review-packet",
            "package_name": report.get("metadata", {}).get("package_name", ""),
        },
    )
    task_result = run_kimi_workspace_task(
        task_dir,
        required_outputs=required_outputs,
        model=review_model,
        timeout_seconds=timeout_seconds or DEFAULT_REVIEW_TIMEOUT_SECONDS,
        command_runner=command_runner,
    )
    content = read_workspace_text(task_result, "outputs/human-review-packet.md").strip()
    if not content:
        raise ValueError("Workspace human review packet output was empty.")
    return content + "\n"


def render_human_review_packet_with_llm(
    report: dict[str, Any],
    *,
    iteration_dir: Path,
    sender: Sender | None = None,
    command_runner: CommandRunner | None = None,
    review_model: str | None = None,
    timeout_seconds: int | None = None,
) -> str:
    resolved_model = _review_model(review_model)
    if sender is not None:
        return _render_human_review_packet_with_sender(report, sender=sender, review_model=resolved_model)
    return _render_human_review_packet_with_workspace(
        report,
        iteration_dir=iteration_dir,
        command_runner=command_runner,
        review_model=resolved_model,
        timeout_seconds=timeout_seconds,
    )


def build_human_review_packet(
    iteration_dir: Path,
    package_dir: Path,
    *,
    sender: Sender | None = None,
    command_runner: CommandRunner | None = None,
    review_model: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    report = build_agent_review_report_payload(iteration_path, package_dir)
    write_json(iteration_path / "agent-review-report.json", report)
    markdown = render_human_review_packet_with_llm(
        report,
        iteration_dir=iteration_path,
        sender=sender,
        command_runner=command_runner,
        review_model=review_model,
        timeout_seconds=timeout_seconds,
    )
    write_text(iteration_path / "human-review-packet.md", markdown)
    return report


def write_human_review_template(iteration_dir: Path, package_name: str) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    template = {
        "reviewer": "",
        "reviewed_at": "",
        "package_name": package_name,
        "iteration": iteration_path.name,
        "scores": {dimension: None for dimension in RUBRIC_DIMENSIONS},
        "decision": "hold",
        "notes": "",
    }
    write_json(iteration_path / "human-review-score.json", template)
    return template


def _current_agent_report(iteration_dir: Path) -> dict[str, Any]:
    report_path = Path(iteration_dir) / "agent-review-report.json"
    if not report_path.exists():
        return {}
    data = load_json(report_path)
    return data if isinstance(data, dict) else {}


def write_human_review_authorization_template(iteration_dir: Path, package_name: str) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    report = _current_agent_report(iteration_path)
    template = {
        "reviewer": "",
        "authorized_at": "",
        "package_name": package_name,
        "iteration": iteration_path.name,
        "agent_report_id": report.get("metadata", {}).get("report_id", ""),
        "decision": "pending",
        "notes": "",
        "authorization_source": "conversation",
    }
    write_json(iteration_path / "human-review-authorization.json", template)
    return template


def record_human_authorization(
    iteration_dir: Path,
    *,
    decision: str,
    reviewer: str = DEFAULT_CONVERSATION_REVIEWER,
    notes: str = "",
) -> dict[str, Any]:
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in FINAL_AUTHORIZATION_DECISIONS:
        raise ValueError("decision must be one of approve, revise, hold")

    iteration_path = Path(iteration_dir)
    report = _current_agent_report(iteration_path)
    report_id = str(report.get("metadata", {}).get("report_id", "")).strip()
    if not report_id:
        raise ValueError("agent-review-report.json is required before recording human authorization")

    authorization = {
        "reviewer": reviewer or DEFAULT_CONVERSATION_REVIEWER,
        "authorized_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "package_name": report.get("metadata", {}).get("package_name", ""),
        "iteration": iteration_path.name,
        "agent_report_id": report_id,
        "decision": normalized_decision,
        "notes": notes,
        "authorization_source": "conversation",
    }
    write_json(iteration_path / "human-review-authorization.json", authorization)
    return authorization


def _load_human_review_state(iteration_dir: Path) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    report = _current_agent_report(iteration_path)
    current_report_id = str(report.get("metadata", {}).get("report_id", "")).strip()

    authorization_path = iteration_path / "human-review-authorization.json"
    if authorization_path.exists():
        data = load_json(authorization_path)
        data = data if isinstance(data, dict) else {}
        decision = str(data.get("decision", "pending")).strip().lower()
        if decision not in AUTHORIZATION_DECISIONS:
            decision = "pending"
        reviewer = str(data.get("reviewer", "")).strip()
        authorized_at = str(data.get("authorized_at", "")).strip()
        report_id_matches = bool(current_report_id and str(data.get("agent_report_id", "")).strip() == current_report_id)
        completed = (
            decision in FINAL_AUTHORIZATION_DECISIONS
            and bool(reviewer)
            and bool(authorized_at)
            and report_id_matches
        )
        return {
            "source": "authorization",
            "exists": True,
            "completed": completed,
            "decision": decision,
            "report_id_matches": report_id_matches,
            "data": data,
        }

    legacy_path = iteration_path / "human-review-score.json"
    if legacy_path.exists():
        data = load_json(legacy_path)
        data = data if isinstance(data, dict) else {}
        mapped_decision = LEGACY_DECISION_MAP.get(str(data.get("decision", "")).strip().lower(), "pending")
        reviewer = str(data.get("reviewer", "")).strip()
        reviewed_at = str(data.get("reviewed_at", "")).strip()
        completed = mapped_decision in FINAL_AUTHORIZATION_DECISIONS and bool(reviewer) and bool(reviewed_at)
        return {
            "source": "legacy-human-review-score",
            "exists": True,
            "completed": completed,
            "decision": mapped_decision,
            "report_id_matches": True,
            "data": data,
        }

    return {
        "source": "missing",
        "exists": False,
        "completed": False,
        "decision": "pending",
        "report_id_matches": True,
        "data": {},
    }


def generate_release_recommendation(iteration_dir: Path) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    level3_summary = _load_optional_json(iteration_path / "level3-summary.json")
    analysis = _load_optional_json(iteration_path / "analysis.json")
    hard_gate = _load_optional_json(iteration_path / "hard-gate.json")
    quantitative = _load_optional_json(iteration_path / "quantitative-summary.json")
    deep_eval = _load_optional_json(iteration_path / "deep-eval.json")
    review_state = _load_human_review_state(iteration_path)

    hard_gate_passed = hard_gate.get("passed") if hard_gate else None
    hard_gate_failed = hard_gate and not hard_gate.get("passed", False)
    deep_signal = deep_eval.get("release_signal", {}) if deep_eval else {}
    deep_decision = deep_signal.get("decision", "revise") if deep_eval else None

    blockers: list[str] = []
    if hard_gate_failed:
        blockers.append("hard_gate_failed")
        blockers.extend(str(item) for item in hard_gate.get("blockers", []))
    if not deep_eval:
        blockers.append("deep_eval_missing")

    if hard_gate_failed:
        recommendation = "hold"
    elif deep_decision == "hold":
        recommendation = "hold"
        blockers.append("deep_eval_decision:hold")
    else:
        if not review_state.get("completed", False):
            recommendation = "pending-human-review"
            blockers.append("human_review_pending")
            if review_state.get("exists") and not review_state.get("report_id_matches", True):
                blockers.append("human_review_report_mismatch")
        else:
            manual_decision = review_state.get("decision", "pending")
            if manual_decision == "revise":
                recommendation = "revise"
                blockers.append("manual_review_decision:revise")
            elif manual_decision == "hold":
                recommendation = "hold"
                blockers.append("manual_review_decision:hold")
            elif manual_decision == "approve":
                recommendation = "promote"
            else:
                recommendation = "pending-human-review"
                blockers.append("human_review_pending")

    result = {
        "metadata": {
            "iteration": iteration_path.name,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skill_name": level3_summary.get("metadata", {}).get("skill_name", ""),
        },
        "minimum_gates": {
            "hard_gate_completed": (iteration_path / "hard-gate.json").exists(),
            "hard_gate_passed": hard_gate_passed,
            "deep_eval_completed": (iteration_path / "deep-eval.json").exists(),
            "quantitative_summary_completed": (iteration_path / "quantitative-summary.json").exists(),
            "supporting_level3_completed": (iteration_path / "level3-summary.json").exists(),
            "supporting_benchmark_completed": (iteration_path / "benchmark.json").exists(),
            "supporting_stability_completed": (iteration_path / "stability.json").exists(),
            "legacy_analysis_completed": (iteration_path / "analysis.json").exists(),
            "human_review_completed": bool(review_state.get("completed", False)),
        },
        "quality_primary_mode": deep_eval.get("metadata", {}).get("quality_primary_mode", "legacy-analysis") if deep_eval else "legacy-analysis",
        "deep_eval_release_signal": deep_signal,
        "quantitative_supporting_risks": quantitative.get("supporting_risks", []) if quantitative else [],
        "recommendation": recommendation,
        "blockers": sorted(set(blockers)),
        "human_review": {
            "source": review_state.get("source"),
            "decision": review_state.get("decision"),
            "report_id_matches": review_state.get("report_id_matches", True),
        },
        "notes": deep_eval.get("repair_recommendations", analysis.get("repair_recommendations", [])) if deep_eval else analysis.get("repair_recommendations", []),
    }
    write_json(iteration_path / "release-recommendation.json", result)
    return result
