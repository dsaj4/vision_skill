from __future__ import annotations

import re
from pathlib import Path
from typing import Any


STEP_HEADER_PATTERN = re.compile(r"^### Step (\d+):?.*$", re.MULTILINE)


def _issue(code: str, message: str, severity: str = "error") -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "path": "SKILL.md",
        "message": message,
    }


def _read_skill(package_path: Path, issues: list[dict[str, str]]) -> str | None:
    skill_path = package_path / "SKILL.md"
    if not skill_path.exists():
        issues.append(_issue("missing_file", "SKILL.md is missing from the package."))
        return None
    return skill_path.read_text(encoding="utf-8")


def _extract_step_section(content: str, step_number: int) -> str | None:
    pattern = re.compile(
        rf"^### Step {step_number}:?.*?(?=^### Step \d+:?.*|^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    return match.group(0) if match else None


def validate_protocol(package_path: str | Path) -> dict[str, Any]:
    package_dir = Path(package_path)
    issues: list[dict[str, str]] = []

    if not package_dir.exists():
        issues.append(_issue("missing_package", f"Package path does not exist: {package_dir}"))
        return {
            "package_path": str(package_dir),
            "valid": False,
            "issues": issues,
            "summary": {"errors": len(issues), "warnings": 0},
        }

    content = _read_skill(package_dir, issues)
    if content is None:
        return {
            "package_path": str(package_dir),
            "valid": False,
            "issues": issues,
            "summary": {"errors": len(issues), "warnings": 0},
        }

    if "## 交互模式" not in content:
        issues.append(_issue("missing_protocol_section", "Missing required '## 交互模式' section."))
    else:
        if "分步执行" not in content:
            issues.append(_issue("missing_protocol_clause", "The interaction mode section must describe step-by-step execution."))
        if "跳过机制" not in content:
            issues.append(_issue("missing_protocol_clause", "The interaction mode section must describe direct-result skip behavior."))

    if not re.search(r"^### Step 0:?", content, re.MULTILINE):
        issues.append(_issue("missing_step", "Missing required Step 0 section."))
    elif "重新执行 Step 0" not in content and "追问后重新检测" not in content:
        issues.append(_issue("missing_step0_redetect", "Step 0 must describe follow-up re-detection behavior."))

    for step_number in (1, 2, 3):
        step_content = _extract_step_section(content, step_number)
        if step_content is None:
            issues.append(_issue("missing_step", f"Missing required Step {step_number} section."))
            continue

        if "**输出后暂停**" not in step_content:
            issues.append(_issue("missing_step_pause", f"Step {step_number} must include a pause block."))
            continue

        missing_branches = [
            phrase
            for phrase in ('回复"继续"', '回复"不对"', '回复"直接要结果"')
            if phrase not in step_content
        ]
        if missing_branches:
            issues.append(
                _issue(
                    "missing_step_branch",
                    f"Step {step_number} pause block is missing protocol branch text: {', '.join(missing_branches)}.",
                )
            )

    if "## 规则" not in content:
        issues.append(_issue("missing_rules_section", "Missing required '## 规则' section."))
    else:
        if "信息充分时禁止重复提问" not in content:
            issues.append(_issue("missing_rule", "Rules must include no-repeat-question behavior for sufficient information."))
        if "信息不足时只补问缺失项" not in content:
            issues.append(_issue("missing_rule", "Rules must include missing-info follow-up behavior."))
        if "每步完成后必须暂停确认" not in content:
            issues.append(_issue("missing_rule", "Rules must require pause confirmation after each step."))
        if "根据反馈重新分析" not in content:
            issues.append(_issue("missing_rule", "Rules must describe how to handle user modification feedback."))

        high_pressure_signals = ("高压", "濒临崩溃", "减压", "稳定基础", "重建承载力")
        if not any(signal in content for signal in high_pressure_signals):
            issues.append(_issue("missing_high_pressure_rule", "Rules must include a high-pressure or fragile-state guardrail."))

    if "## 使用说明" not in content:
        issues.append(_issue("missing_usage_section", "Missing required '## 使用说明' section."))
    else:
        if "分步交互模式" not in content:
            issues.append(_issue("missing_usage_mode", "Usage section must include staged interaction mode guidance."))
        if "直接输出模式" not in content:
            issues.append(_issue("missing_usage_mode", "Usage section must include direct-output mode guidance."))

    return {
        "package_path": str(package_dir),
        "valid": len(issues) == 0,
        "issues": issues,
        "summary": {
            "errors": len([issue for issue in issues if issue["severity"] == "error"]),
            "warnings": len([issue for issue in issues if issue["severity"] == "warning"]),
        },
    }
