from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Sequence

from toolchain.agent_hosts.codex_host import CodexHost
from toolchain.agent_hosts.event_normalizer import normalize_host_transcript
from toolchain.agent_hosts.host_benchmark import benchmark_markdown, build_host_benchmark
from toolchain.agent_hosts.kimi_code_host import KimiCodeHost
from toolchain.agent_hosts.protocol_classifier import classify_protocol_path
from toolchain.agent_hosts.signal_extractor import extract_host_signals
from toolchain.eval_factory.sync import resolve_package_evals
from toolchain.graders.capability_grader import grade_response_text


AdapterFactory = Callable[[Path], Any]
HOST_BACKENDS = {"codex", "kimi-code"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _filter_host_evals(
    evals: list[dict[str, Any]],
    *,
    eval_ids: list[int] | None = None,
    max_evals: int | None = None,
) -> list[dict[str, Any]]:
    filtered = [item for item in evals if item.get("host_eval", {}).get("enabled")]
    if eval_ids:
        selected = {int(item) for item in eval_ids}
        filtered = [item for item in filtered if int(item["id"]) in selected]
    if max_evals is not None:
        filtered = filtered[: max(0, int(max_evals))]
    return filtered


def _build_eval_metadata(eval_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "eval_id": int(eval_item["id"]),
        "eval_name": f"host-eval-{int(eval_item['id'])}",
        "prompt": eval_item.get("prompt", ""),
        "assertions": eval_item.get("expectations", []),
    }


def _turn_script(eval_item: dict[str, Any]) -> list[str]:
    script = eval_item.get("host_eval", {}).get("turn_script", [])
    if not script:
        return [str(eval_item.get("prompt", ""))]
    turns: list[str] = []
    for item in script:
        if isinstance(item, dict):
            turns.append(str(item.get("text", "")).strip())
        else:
            turns.append(str(item).strip())
    return [item for item in turns if item]


def _protocol_path_matches(expected: str, observed: str) -> bool:
    return expected.strip().lower() == observed.strip().lower()


def _normalize_host_backend(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    if normalized not in HOST_BACKENDS:
        raise ValueError(f"Unsupported host backend: {value}")
    return normalized


def _build_adapter_factory(host_backend: str, *, timeout_seconds: int | None = 180) -> AdapterFactory:
    normalized = _normalize_host_backend(host_backend)
    if normalized == "kimi-code":
        return lambda session_root: KimiCodeHost(session_root=session_root, timeout_seconds=timeout_seconds)
    return lambda session_root: CodexHost(session_root=session_root, timeout_seconds=timeout_seconds)


def _build_trigger_report(
    *,
    package_name: str,
    eval_item: dict[str, Any],
    signal_report: dict[str, Any],
) -> dict[str, Any]:
    signal_type_map = {
        "skill_proxy_read": "proxy_skill_read",
        "skill_canonical_read": "canonical_skill_read",
        "skill_meta_read": "skill_meta_read",
    }
    expected_trigger = eval_item.get("host_eval", {}).get("expected_trigger")
    triggered = bool(
        signal_report["trigger_signals"]["proxy_skill_read"]
        or signal_report["trigger_signals"]["canonical_skill_read"]
        or signal_report["trigger_signals"]["skill_meta_read"]
    )
    evidence = [
        {
            "type": signal_type_map.get(snippet["label"], snippet["label"]),
            "turn_index": snippet["turn_index"],
            "raw_ref": snippet["raw_ref"],
            "detail": snippet["text"],
        }
        for snippet in signal_report.get("evidence_snippets", [])
        if snippet["label"] in {"skill_proxy_read", "skill_canonical_read", "skill_meta_read"}
    ]
    return {
        "package_name": package_name,
        "triggered": triggered,
        "false_trigger": bool(expected_trigger is False and triggered),
        "expected_trigger": expected_trigger,
        "expected_trigger_signals": list(eval_item.get("host_eval", {}).get("expected_trigger_signals", [])),
        "trigger_turn_index": signal_report["trigger_signals"]["trigger_turn_index"],
        "first_answer_turn_index": signal_report["trigger_signals"]["first_answer_turn_index"],
        "first_skill_read_turn_index": signal_report["trigger_signals"]["first_skill_read_turn_index"],
        "skill_read_before_first_answer": signal_report["trigger_signals"]["skill_read_before_first_answer"],
        "observed_trigger_signals": {
            "proxy_skill_read": signal_report["trigger_signals"]["proxy_skill_read"],
            "canonical_skill_read": signal_report["trigger_signals"]["canonical_skill_read"],
            "skill_meta_read": signal_report["trigger_signals"]["skill_meta_read"],
            "explicit_skill_use_announcement": signal_report["trigger_signals"]["explicit_skill_use_announcement"],
        },
        "evidence": evidence,
    }


def run_host_eval(
    package_dir: str | Path,
    workspace_dir: str | Path,
    *,
    iteration_number: int,
    host_backend: str = "codex",
    adapter_factory: AdapterFactory | None = None,
    eval_ids: list[int] | None = None,
    max_evals: int | None = None,
    timeout_seconds: int | None = 180,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    workspace_path = Path(workspace_dir)
    workspace_path.mkdir(parents=True, exist_ok=True)
    iteration_dir = workspace_path / f"iteration-{iteration_number}"
    iteration_dir.mkdir(parents=True, exist_ok=True)

    package_meta = _load_json(package_path / "metadata" / "package.json")
    eval_resolution = resolve_package_evals(package_path)
    selected_evals = _filter_host_evals(
        list(eval_resolution["data"].get("evals", [])),
        eval_ids=eval_ids,
        max_evals=max_evals,
    )
    resolved_host_backend = _normalize_host_backend(host_backend)
    resolved_adapter_factory = adapter_factory or _build_adapter_factory(
        resolved_host_backend,
        timeout_seconds=timeout_seconds,
    )

    run_records: list[dict[str, Any]] = []
    for eval_item in selected_evals:
        host_eval_dir = iteration_dir / f"host-eval-{int(eval_item['id'])}"
        host_eval_dir.mkdir(parents=True, exist_ok=True)
        session_root = host_eval_dir / "session"
        adapter = resolved_adapter_factory(session_root)
        session = adapter.prepare_session(package_path, eval_item)

        for user_turn in _turn_script(eval_item):
            adapter.send_user_turn(session, user_turn)

        transcript = adapter.read_transcript(session)
        normalized_events = normalize_host_transcript(transcript)
        signal_report = extract_host_signals(transcript, normalized_events)
        protocol_report = classify_protocol_path(signal_report)
        trigger_report = _build_trigger_report(
            package_name=package_path.name,
            eval_item=eval_item,
            signal_report=signal_report,
        )
        close_result = adapter.close_session(session)
        final_response = str(transcript.get("turns", [{}])[-1].get("assistant_text", "")).strip() if transcript.get("turns") else ""

        final_response_path = host_eval_dir / "host-final-response.md"
        final_response_path.write_text(final_response, encoding="utf-8")
        _write_json(host_eval_dir / "host-session.json", {**session, "close_result": close_result})
        _write_json(host_eval_dir / "host-transcript.json", transcript)
        _write_json(host_eval_dir / "host-normalized-events.json", normalized_events)
        _write_json(host_eval_dir / "host-signal-report.json", signal_report)
        _write_json(host_eval_dir / "host-protocol-report.json", protocol_report)
        _write_json(host_eval_dir / "host-trigger-report.json", trigger_report)
        _write_json(host_eval_dir / "host-analysis-packet.json", signal_report["analysis_packet"])

        grading = grade_response_text(
            final_response,
            _build_eval_metadata(eval_item),
            output_file=str(final_response_path),
        )
        _write_json(host_eval_dir / "host-grading.json", grading)
        _write_json(host_eval_dir / "host-metrics.json", grading["execution_metrics"])

        expected_protocol_path = str(eval_item.get("host_eval", {}).get("expected_protocol_path", "")).strip()
        record = {
            "eval_id": int(eval_item["id"]),
            "eval_name": f"host-eval-{int(eval_item['id'])}",
            "host_eval_dir": str(host_eval_dir),
            "expected_trigger": eval_item.get("host_eval", {}).get("expected_trigger"),
            "expected_protocol_path": expected_protocol_path,
            "normalized_path": protocol_report.get("observed_protocol_path", ""),
            "protocol_path_match": _protocol_path_matches(
                expected_protocol_path,
                str(protocol_report.get("observed_protocol_path", "")),
            )
            if expected_protocol_path
            else False,
            "path_confidence": float(protocol_report.get("path_confidence", 0.0) or 0.0),
            "trigger_report": trigger_report,
            "signal_report": signal_report,
            "protocol_report": protocol_report,
            "signal_flags": {
                "proxy_skill_read": signal_report["trigger_signals"]["proxy_skill_read"],
                "canonical_skill_read": signal_report["trigger_signals"]["canonical_skill_read"],
                "missing_info_detected": signal_report["protocol_signals"]["missing_info_detected"],
                "direct_result_request_seen": signal_report["protocol_signals"]["direct_result_request_seen"],
                "checkpoint_count": signal_report["protocol_signals"]["checkpoint_count"],
                "swot_quadrants_present": signal_report["output_structure_signals"]["swot_quadrants_present"],
            },
            "noise_flags": {
                "plugin_sync_noise_present": signal_report["host_interference_signals"]["plugin_sync_noise_present"],
                "cloudflare_or_html_challenge_present": signal_report["host_interference_signals"]["cloudflare_or_html_challenge_present"],
                "constrained_language_warning_present": signal_report["host_interference_signals"]["constrained_language_warning_present"],
                "external_noise_before_first_answer": signal_report["host_interference_signals"]["external_noise_before_first_answer"],
            },
            "first_answer_turn_index": signal_report["trigger_signals"]["first_answer_turn_index"],
            "first_skill_read_turn_index": signal_report["trigger_signals"]["first_skill_read_turn_index"],
            "grading": grading,
            "turn_count": len(transcript.get("turns", [])),
        }
        run_records.append(record)

    benchmark = build_host_benchmark(
        package_name=package_meta.get("package_name", package_path.name),
        skill_name=package_meta.get("skill_name", package_path.name),
        iteration_dir=iteration_dir,
        runs=run_records,
    )
    _write_json(iteration_dir / "host-benchmark.json", benchmark)
    (iteration_dir / "host-benchmark.md").write_text(benchmark_markdown(benchmark), encoding="utf-8")

    return {
        "iteration_dir": str(iteration_dir),
        "host_backend": resolved_host_backend,
        "selected_eval_ids": [int(item["id"]) for item in selected_evals],
        "selected_eval_count": len(selected_evals),
        "host_benchmark_path": str(iteration_dir / "host-benchmark.json"),
        "source_mode": eval_resolution["source_mode"],
    }


def _resolve_eval_ids(value: str | None) -> list[int] | None:
    if not value:
        return None
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the host agent eval lane.")
    parser.add_argument("--package-dir", required=True, help="Path to the package directory.")
    parser.add_argument("--workspace-dir", required=True, help="Path to the package workspace directory.")
    parser.add_argument("--iteration-number", type=int, required=True, help="Iteration number to use for host artifacts.")
    parser.add_argument(
        "--host-backend",
        choices=sorted(HOST_BACKENDS),
        default="codex",
        help="Host backend to execute. Defaults to codex.",
    )
    parser.add_argument("--max-evals", type=int, default=None, help="Optional limit for host-enabled eval cases.")
    parser.add_argument("--eval-ids", default=None, help="Optional comma-separated eval ids.")
    parser.add_argument("--timeout-seconds", type=int, default=180, help="Per-turn host command timeout.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_host_eval(
        args.package_dir,
        args.workspace_dir,
        iteration_number=args.iteration_number,
        host_backend=args.host_backend,
        eval_ids=_resolve_eval_ids(args.eval_ids),
        max_evals=args.max_evals,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
