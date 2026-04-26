from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.agent_hosts.run_host_eval import run_host_eval


def _write_package(base: Path) -> Path:
    package_dir = base / "swot-analysis"
    (package_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (package_dir / "evals").mkdir(parents=True, exist_ok=True)
    (package_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: swot-analysis",
                "description: Use this skill whenever the user needs a SWOT analysis for a decision.",
                "---",
                "",
                "# SWOT Analysis",
            ]
        ),
        encoding="utf-8",
    )
    (package_dir / "metadata" / "package.json").write_text(
        json.dumps(
            {
                "package_name": "swot-analysis",
                "skill_name": "SWOT Analysis",
                "category": "strategy",
                "status": "candidate",
                "version": "0.1.0",
                "source_mode": "demo-only",
                "candidate_origin": "demo-migration",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (package_dir / "evals" / "evals.json").write_text(
        json.dumps(
            {
                "skill_name": "SWOT Analysis",
                "evals": [
                    {
                        "id": 102,
                        "prompt": "The context is incomplete. Help me decide whether to pivot into AI work.",
                        "expected_output": "The skill should ask only for the missing information first.",
                        "files": [],
                        "expectations": [
                            {
                                "id": "ask-missing-info",
                                "type": "contains_any",
                                "text": "The output asks for missing information.",
                                "keywords": ["missing information", "need more context", "before I can"],
                            }
                        ],
                        "host_eval": {
                            "enabled": True,
                            "turn_script": [
                                {"text": "I want to pivot into AI work, but the context is still messy."},
                                {"text": "My target is to switch within 6 months and I can invest 8 hours a week."},
                            ],
                            "expected_trigger": True,
                            "expected_trigger_signals": ["proxy_skill_read", "canonical_skill_read"],
                            "expected_protocol_path": "missing-info -> ask-followup",
                        },
                    },
                    {
                        "id": 103,
                        "prompt": "Give me the SWOT result directly without a checkpoint.",
                        "expected_output": "A direct-result SWOT answer.",
                        "files": [],
                        "expectations": [
                            "The output includes strengths, weaknesses, opportunities, and threats.",
                            "The output respects the user's direct-result request.",
                        ],
                        "host_eval": {
                            "enabled": True,
                            "turn_script": [
                                {"text": "I have 3 early users already. Give me the SWOT result directly and do not pause."}
                            ],
                            "expected_trigger": True,
                            "expected_trigger_signals": ["proxy_skill_read", "canonical_skill_read"],
                            "expected_protocol_path": "direct-result -> no-checkpoint",
                        },
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return package_dir


class FakeHostAdapter:
    def __init__(self, session_root: Path) -> None:
        self.session_root = session_root

    def prepare_session(self, package_dir: Path, eval_case: dict) -> dict:
        return {
            "package_dir": str(package_dir),
            "eval_id": eval_case["id"],
            "session_dir": str(self.session_root),
            "turns": [],
            "thread_id": f"thread-{eval_case['id']}",
        }

    def send_user_turn(self, session_handle: dict, text: str) -> dict:
        eval_id = session_handle["eval_id"]
        turn_index = len(session_handle["turns"])
        if eval_id == 102 and turn_index == 0:
            assistant_text = "Before I can continue, I need two missing information points: your target role and available time."
        elif eval_id == 102:
            assistant_text = (
                "## Strengths\n- domain context\n"
                "## Weaknesses\n- limited technical depth\n"
                "## Opportunities\n- AI operator roles are growing\n"
                "## Threats\n- competition is rising\n"
                "## Strategy\n- start with a low-risk test path"
            )
        else:
            assistant_text = (
                "## Strengths\n- 3 real trial users\n"
                "## Weaknesses\n- budget is small\n"
                "## Opportunities\n- interview preparation demand exists\n"
                "## Threats\n- competition is intense\n"
                "## Strategy\n- validate demand before expanding"
            )
        turn = {
            "turn_index": turn_index + 1,
            "user_text": text,
            "assistant_text": assistant_text,
            "events": [
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": f"Get-Content '{self.session_root / '.kimi' / 'skills' / 'swot-analysis' / 'SKILL.md'}'",
                        "aggregated_output": "proxy skill text",
                    },
                },
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": f"Get-Content '{Path(session_handle['package_dir']) / 'SKILL.md'}'",
                        "aggregated_output": "canonical skill text",
                    },
                },
            ]
            if turn_index == 0
            else [],
            "command_events": [],
            "warnings": [],
            "stderr": "",
        }
        session_handle["turns"].append(turn)
        return {
            "assistant_text": assistant_text,
            "thread_id": session_handle["thread_id"],
            "events": [],
        }

    def read_transcript(self, session_handle: dict) -> dict:
        return {
            "thread_id": session_handle["thread_id"],
            "package_name": "swot-analysis",
            "package_dir": session_handle["package_dir"],
            "proxy_skill_path": str(self.session_root / ".kimi" / "skills" / "swot-analysis" / "SKILL.md"),
            "canonical_skill_path": str(Path(session_handle["package_dir"]) / "SKILL.md"),
            "turns": session_handle["turns"],
            "stderr": [],
        }

    def detect_skill_trigger(self, transcript: dict, package_name: str) -> dict:
        return {
            "package_name": package_name,
            "triggered": True,
            "false_trigger": False,
            "expected_trigger": True,
            "evidence": [
                {"type": "proxy_skill_read", "detail": transcript["proxy_skill_path"]},
                {"type": "canonical_skill_read", "detail": transcript["canonical_skill_path"]},
            ],
        }

    def close_session(self, session_handle: dict) -> dict:
        return {"closed": True, "thread_id": session_handle["thread_id"]}


def test_run_host_eval_generates_host_artifacts_and_summary(tmp_path: Path) -> None:
    package_dir = _write_package(tmp_path / "packages")
    workspace_dir = tmp_path / "workspaces"

    result = run_host_eval(
        package_dir,
        workspace_dir,
        iteration_number=1,
        adapter_factory=lambda session_root: FakeHostAdapter(session_root),
    )

    iteration_dir = workspace_dir / "iteration-1"
    host_eval_102 = iteration_dir / "host-eval-102"
    host_eval_103 = iteration_dir / "host-eval-103"
    benchmark = json.loads((iteration_dir / "host-benchmark.json").read_text(encoding="utf-8"))
    signal_report = json.loads((host_eval_102 / "host-signal-report.json").read_text(encoding="utf-8"))

    assert result["host_backend"] == "kimi-code"
    assert result["selected_eval_ids"] == [102, 103]
    assert (host_eval_102 / "host-session.json").exists()
    assert (host_eval_102 / "host-transcript.json").exists()
    assert (host_eval_102 / "host-normalized-events.json").exists()
    assert (host_eval_102 / "host-signal-report.json").exists()
    assert (host_eval_102 / "host-protocol-report.json").exists()
    assert (host_eval_102 / "host-trigger-report.json").exists()
    assert (host_eval_102 / "host-analysis-packet.json").exists()
    assert (host_eval_102 / "host-final-response.md").exists()
    assert (host_eval_102 / "host-grading.json").exists()
    assert (host_eval_103 / "host-final-response.md").exists()
    assert benchmark["trigger_summary"]["trigger_success_rate"] == 1.0
    assert benchmark["protocol_summary"]["protocol_path_match_rate"] == 1.0
    assert benchmark["protocol_summary"]["direct_result_compliance_rate"] == 1.0
    assert benchmark["protocol_summary"]["followup_precision"] == 1.0
    assert benchmark["runs"][0]["trigger_report"]["triggered"] is True
    assert benchmark["runs"][0]["path_confidence"] > 0.0
    assert signal_report["prompt_budget"]["within_budget"] is True
