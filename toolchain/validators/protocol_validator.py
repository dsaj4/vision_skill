from __future__ import annotations

import re
from pathlib import Path
from typing import Any


STEP_HEADER_PATTERN = re.compile(r"^### Step (\d+):\s*(.+)$", re.MULTILINE)
REQUIRED_TOP_LEVEL_SECTIONS = [
    "## 适用任务范围",
    "## 模型介绍",
    "## 与相近模型的区别",
    "## 内部执行流（仅用于推理，不在对用户输出中显示阶段编号）",
]
REQUIRED_TASK_SCOPE_BLOCKS = [
    "**适用场景（一句话）**",
    "**适用任务**",
    "**不适用任务**",
]
REQUIRED_MODEL_BLOCKS = [
    "**前提假设**",
    "**核心命题（一句话介绍）**",
]
REQUIRED_STEP_BLOCKS = [
    "**最小可用输入（MVI）**",
    "判定规则",
    "**处理方法**",
    "**输出**",
]


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
        rf"^### Step {step_number}:\s*.*?(?=^### Step \d+:\s*.*|^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    return match.group(0) if match else None


def _section_positions(content: str) -> list[int]:
    positions: list[int] = []
    for heading in REQUIRED_TOP_LEVEL_SECTIONS:
        position = content.find(heading)
        if position < 0:
            return []
        positions.append(position)
    return positions


def _validate_required_sections(content: str, issues: list[dict[str, str]]) -> None:
    positions = _section_positions(content)
    if not positions:
        for heading in REQUIRED_TOP_LEVEL_SECTIONS:
            if heading not in content:
                issues.append(_issue("missing_required_section", f"Missing required section: {heading}"))
        return
    if positions != sorted(positions):
        issues.append(_issue("invalid_section_order", "Required level-2 sections must follow the fixed optimized-skill order."))

    for marker in REQUIRED_TASK_SCOPE_BLOCKS:
        if marker not in content:
            issues.append(_issue("missing_task_scope_block", f"Missing task-scope block: {marker}"))
    for marker in REQUIRED_MODEL_BLOCKS:
        if marker not in content:
            issues.append(_issue("missing_model_block", f"Missing model-introduction block: {marker}"))


def _validate_protocol_clauses(content: str, issues: list[dict[str, str]]) -> None:
    required_phrases = [
        "默认按完整内部流程逐步输出",
        "快速模式",
        "完整内部流程",
        "不再逐步暂停",
        "不使用“Step 1/Step 2/阶段 X”等编号词",
        "禁止要求用户按固定编号模板回复",
        "禁止在信息不足时重复追问已提供信息",
    ]
    for phrase in required_phrases:
        if phrase not in content:
            issues.append(_issue("missing_protocol_clause", f"Missing optimized protocol clause: {phrase}"))


def _validate_steps(content: str, issues: list[dict[str, str]]) -> None:
    steps = [(int(match.group(1)), match.group(2).strip()) for match in STEP_HEADER_PATTERN.finditer(content)]
    if not steps:
        issues.append(_issue("missing_step", "SKILL.md must include Step 1 to Step N sections."))
        return

    step_numbers = [number for number, _ in steps]
    expected_numbers = list(range(1, max(step_numbers) + 1))
    if step_numbers != expected_numbers:
        issues.append(_issue("invalid_step_sequence", f"Steps must be consecutive from Step 1 to Step N; found {step_numbers}."))

    final_step = max(step_numbers)
    if final_step < 3:
        issues.append(_issue("too_few_steps", "Optimized skill protocol should include at least three steps."))

    for step_number, step_name in steps:
        step_content = _extract_step_section(content, step_number)
        if step_content is None:
            issues.append(_issue("missing_step", f"Missing required Step {step_number} section."))
            continue

        for marker in REQUIRED_STEP_BLOCKS:
            if marker not in step_content:
                issues.append(_issue("missing_step_block", f"Step {step_number} is missing required block: {marker}"))

        has_pause = "**输出后暂停**" in step_content
        if step_number < final_step:
            if not has_pause:
                issues.append(_issue("missing_step_pause", f"Step {step_number} must include a pause block."))
                continue
            required_pause_phrases = [
                f"以上是 Step {step_number} {step_name}",
                "回复“继续”",
                "回复“不对”",
                "回复“直接要结果”",
            ]
            for phrase in required_pause_phrases:
                if phrase not in step_content:
                    issues.append(_issue("missing_step_branch", f"Step {step_number} pause block is missing: {phrase}"))
        elif has_pause:
            issues.append(_issue("final_step_has_pause", f"Final Step {step_number} must not include a pause block."))


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

    _validate_required_sections(content, issues)
    _validate_protocol_clauses(content, issues)
    _validate_steps(content, issues)

    return {
        "package_path": str(package_dir),
        "valid": len(issues) == 0,
        "issues": issues,
        "summary": {
            "errors": len([issue for issue in issues if issue["severity"] == "error"]),
            "warnings": len([issue for issue in issues if issue["severity"] == "warning"]),
        },
    }
