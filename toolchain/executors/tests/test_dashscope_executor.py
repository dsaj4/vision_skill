from __future__ import annotations

import json
from pathlib import Path
import sys
import urllib.error

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.executors.dashscope_executor import (
    build_messages,
    execute_iteration,
    execute_run,
    _post_chat_completion,
    _resolve_api_key,
    _resolve_endpoint,
    _resolve_model,
)


def write_package(base: Path) -> Path:
    package_dir = base / "swot-analysis"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: SWOT 分析",
                "description: 使用 SWOT 结构分析决策。",
                "---",
                "",
                "# SWOT 分析",
                "## 交互模式",
                "分步执行；支持直接要结果。",
            ]
        ),
        encoding="utf-8",
    )
    return package_dir


def write_iteration(base: Path) -> Path:
    iteration_dir = base / "iteration-1"
    eval_dir = iteration_dir / "eval-1-swot"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "swot",
                "prompt": "请直接给我一个 SWOT 结果。",
                "expected_output": "完整 SWOT 结果",
                "files": [],
                "assertions": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    for configuration in ("with_skill", "without_skill"):
        run_dir = eval_dir / configuration / "run-1" / "outputs"
        run_dir.mkdir(parents=True, exist_ok=True)
    return iteration_dir


def fake_sender(payload: dict, endpoint: str, api_key: str, timeout_seconds: int) -> dict:
    system_content = ""
    if payload["messages"][0]["role"] == "system":
        system_content = payload["messages"][0]["content"]
    if "<SKILL_MD>" in system_content:
        content = "\n".join(
            [
                "## Strengths",
                "- 用户洞察",
                "## Weaknesses",
                "- 预算有限",
                "## Opportunities",
                "- 市场机会",
                "## Threats",
                "- 竞争加剧",
                "## Strategy",
                "- 先验证需求。",
            ]
        )
    else:
        content = "可以考虑这个方向，但还需要补充更多信息。"

    return {
        "id": "chatcmpl-test",
        "model": payload["model"],
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    }


def test_build_messages_includes_skill_only_for_with_skill() -> None:
    with_skill = build_messages("User prompt", skill_text="# Skill")
    without_skill = build_messages("User prompt", skill_text=None)

    assert with_skill[0]["role"] == "system"
    assert "<SKILL_MD>" in with_skill[0]["content"]
    assert without_skill == [{"role": "user", "content": "User prompt"}]


def test_execute_run_writes_artifacts_and_uses_skill_context(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")
    run_dir = iteration_dir / "eval-1-swot" / "with_skill" / "run-1"

    result = execute_run(
        run_dir,
        package_dir,
        configuration="with_skill",
        sender=fake_sender,
        api_key="test-key",
        model="qwen-test",
    )

    final_response = (run_dir / "outputs" / "final_response.md").read_text(encoding="utf-8")
    request_payload = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
    timing = json.loads((run_dir / "timing.json").read_text(encoding="utf-8"))

    assert "## Strengths" in final_response
    assert request_payload["model"] == "qwen-test"
    assert request_payload["messages"][0]["role"] == "system"
    assert timing["total_tokens"] == 150
    assert result["configuration"] == "with_skill"


def test_execute_iteration_runs_both_configurations(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    result = execute_iteration(
        iteration_dir,
        package_dir,
        sender=fake_sender,
        api_key="test-key",
        model="qwen-test",
    )

    assert result["total_runs"] == 2
    assert (iteration_dir / "eval-1-swot" / "with_skill" / "run-1" / "raw_response.json").exists()
    assert (iteration_dir / "eval-1-swot" / "without_skill" / "run-1" / "outputs" / "final_response.md").exists()


def test_execute_iteration_skips_completed_runs_when_requested(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")
    completed_run_dir = iteration_dir / "eval-1-swot" / "with_skill" / "run-1"
    (completed_run_dir / "raw_response.json").write_text(json.dumps({"choices": [{"message": {"content": "done"}}]}), encoding="utf-8")
    (completed_run_dir / "transcript.json").write_text(json.dumps({"assistant_response": "done"}), encoding="utf-8")
    (completed_run_dir / "timing.json").write_text(json.dumps({"total_tokens": 10, "total_duration_seconds": 1.0}), encoding="utf-8")
    (completed_run_dir / "outputs" / "final_response.md").write_text("done", encoding="utf-8")

    result = execute_iteration(
        iteration_dir,
        package_dir,
        sender=fake_sender,
        api_key="test-key",
        model="qwen-test",
        skip_completed=True,
    )

    assert result["total_runs"] == 2
    assert len(result["completed_runs"]) == 1
    assert len(result["skipped_runs"]) == 1
    assert result["skipped_runs"][0]["run_dir"] == str(completed_run_dir)


def test_post_chat_completion_retries_on_urlerror(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")

    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] < 3:
            raise urllib.error.URLError("temporary eof")
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("toolchain.executors.dashscope_executor.time.sleep", lambda _: None)

    response = _post_chat_completion({"model": "qwen-test", "messages": []}, "https://example.com", "test-key", 30)

    assert response["choices"][0]["message"]["content"] == "ok"
    assert calls["count"] == 3


def test_resolve_kimi_code_provider_defaults(monkeypatch) -> None:
    monkeypatch.setenv("VISION_LLM_PROVIDER", "kimi-code")
    monkeypatch.setenv("KIMI_CODE_API_KEY", "test-kimi-key")
    monkeypatch.delenv("KIMI_CODE_BASE_URL", raising=False)
    monkeypatch.delenv("KIMI_CODE_MODEL", raising=False)

    assert _resolve_model(None) == "kimi-for-coding"
    assert _resolve_endpoint(None) == "https://api.kimi.com/coding/v1/chat/completions"
    assert _resolve_api_key(None) == "test-kimi-key"


def test_resolve_moonshot_provider_defaults(monkeypatch) -> None:
    monkeypatch.setenv("VISION_LLM_PROVIDER", "moonshot")
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-moonshot-key")
    monkeypatch.delenv("MOONSHOT_BASE_URL", raising=False)
    monkeypatch.delenv("MOONSHOT_MODEL", raising=False)

    assert _resolve_model(None) == "kimi-k2.6"
    assert _resolve_endpoint(None) == "https://api.moonshot.ai/v1/chat/completions"
    assert _resolve_api_key(None) == "test-moonshot-key"
