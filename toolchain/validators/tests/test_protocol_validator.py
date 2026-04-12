from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.validators.protocol_validator import validate_protocol


VALID_SKILL = """---
name: Example Skill
description: Example description
---

# Example Skill

## 交互模式

**分步执行**：每步分析完成后，暂停并询问用户确认（继续/修改/直接要结果）。
**跳过机制**：若用户输入包含"直接要结果"、"跳过检查"、"不用确认"等表达，直接输出完整分析。

## 工作流程

### Step 0: 信息完整度判断

**追问后重新检测**：用户回答追问后，重新执行 Step 0 检测，直到信息充分。

### Step 1: 第一阶段

内容。

**输出后暂停**：
> 以上是 Step 1 第一阶段。请确认：回复"继续"进入下一步，回复"不对"+ 说明要求修改，回复"直接要结果"跳过检查。

### Step 2: 第二阶段

内容。

**输出后暂停**：
> 以上是 Step 2 第二阶段。请确认：回复"继续"进入下一步，回复"不对"+ 说明要求修改，回复"直接要结果"跳过检查。

### Step 3: 第三阶段

内容。

**输出后暂停**：
> 以上是 Step 3 第三阶段。请确认：回复"继续"进入下一步，回复"不对"+ 说明要求修改，回复"直接要结果"跳过检查。

## 规则

1. 信息充分时禁止重复提问
2. 信息不足时只补问缺失项
3. 每步完成后必须暂停确认
4. 用户要求修改时，根据反馈重新分析
5. 若用户处于高压、失控、濒临崩溃状态，优先建议减压、降载和重建承载力

## 使用说明

**分步交互模式（默认）**：
1. 用户输入后，AI 先执行 Step 0 信息检测

**直接输出模式**：
用户输入包含"直接要结果"时，跳过所有中间暂停。
"""


def write_skill(package_dir: Path, content: str) -> None:
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "SKILL.md").write_text(content, encoding="utf-8")


def test_validate_protocol_accepts_current_swot_package() -> None:
    package_dir = Path(r"E:\Project\vision-lab\vision-skill\packages\swot-analysis")

    result = validate_protocol(package_dir)

    assert result["valid"] is True
    assert result["summary"]["errors"] == 0


def test_validate_protocol_rejects_missing_interaction_mode(tmp_path: Path) -> None:
    package_dir = tmp_path / "example-package"
    write_skill(package_dir, VALID_SKILL.replace("## 交互模式", "## 其他说明"))

    result = validate_protocol(package_dir)

    assert result["valid"] is False
    assert any(issue["code"] == "missing_protocol_section" for issue in result["issues"])


def test_validate_protocol_rejects_missing_pause_block_in_step_2(tmp_path: Path) -> None:
    package_dir = tmp_path / "example-package"
    write_skill(
        package_dir,
        VALID_SKILL.replace(
            """### Step 2: 第二阶段

内容。

**输出后暂停**：
> 以上是 Step 2 第二阶段。请确认：回复"继续"进入下一步，回复"不对"+ 说明要求修改，回复"直接要结果"跳过检查。
""",
            """### Step 2: 第二阶段

内容。
""",
        ),
    )

    result = validate_protocol(package_dir)

    assert result["valid"] is False
    assert any(issue["code"] == "missing_step_pause" for issue in result["issues"])


def test_validate_protocol_rejects_missing_high_pressure_guardrail(tmp_path: Path) -> None:
    package_dir = tmp_path / "example-package"
    write_skill(
        package_dir,
        VALID_SKILL.replace(
            "5. 若用户处于高压、失控、濒临崩溃状态，优先建议减压、降载和重建承载力\n",
            "",
        ),
    )

    result = validate_protocol(package_dir)

    assert result["valid"] is False
    assert any(issue["code"] == "missing_high_pressure_rule" for issue in result["issues"])


def test_validate_protocol_rejects_missing_direct_output_mode(tmp_path: Path) -> None:
    package_dir = tmp_path / "example-package"
    write_skill(
        package_dir,
        VALID_SKILL.replace(
            """## 使用说明

**分步交互模式（默认）**：
1. 用户输入后，AI 先执行 Step 0 信息检测

**直接输出模式**：
用户输入包含"直接要结果"时，跳过所有中间暂停。
""",
            """## 使用说明

**分步交互模式（默认）**：
1. 用户输入后，AI 先执行 Step 0 信息检测
""",
        ),
    )

    result = validate_protocol(package_dir)

    assert result["valid"] is False
    assert any(issue["code"] == "missing_usage_mode" for issue in result["issues"])
