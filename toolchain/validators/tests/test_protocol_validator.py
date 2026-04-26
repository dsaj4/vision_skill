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

## 适用任务范围

**适用场景（一句话）**
当用户需要结构化分析并形成行动方案时，使用本模型。

**适用任务**
- 分析问题

**不适用任务**
- 单纯闲聊

## 模型介绍

**前提假设**
- 用户愿意调整行动

**核心命题（一句话介绍）**
用结构化流程把现象推进到行动。

## 与相近模型的区别
- 与其他模型：本模型更关注可执行方案。

## 内部执行流（仅用于推理，不在对用户输出中显示阶段编号）

**执行协议**
- 默认按完整内部流程逐步输出，除最后一步外，每一步完成后等待用户确认。
- 若用户回复“直接要结果”，立即切换快速模式：内部走完整内部流程，对外一次性给出完整可执行方案，不再逐步暂停。
- 对用户可见输出中，不使用“Step 1/Step 2/阶段 X”等编号词，只保留自然语言标题与结论。

**禁止事项**
- 禁止要求用户按固定编号模板回复。
- 禁止在信息不足时重复追问已提供信息。
- 禁止只给抽象建议，必须给出动作、节奏与验证方式。

### Step 1: 第一阶段

**最小可用输入（MVI）**
- 主题（必需）

判定规则：主题存在，即通过本步 MVI。

**处理方法**
- 收敛主题。

**输出**
- 主题

**输出后暂停**
> ────────
> 以上是 Step 1 第一阶段。请确认：回复“继续”进入下一步，回复“不对”+说明修改要求，回复“直接要结果”跳过后续暂停。
> ────────

### Step 2: 第二阶段

**最小可用输入（MVI）**
- 第一阶段结果（必需）

判定规则：已有结果，即通过本步 MVI。

**处理方法**
- 分析结构。

**输出**
- 结构

**输出后暂停**
> ────────
> 以上是 Step 2 第二阶段。请确认：回复“继续”进入下一步，回复“不对”+说明修改要求，回复“直接要结果”跳过后续暂停。
> ────────

### Step 3: 第三阶段

**最小可用输入（MVI）**
- 第二阶段结果（必需）

判定规则：已有结构，即通过本步 MVI。

**处理方法**
- 形成行动。

**输出**
- 行动
"""


def write_skill(package_dir: Path, content: str) -> None:
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "SKILL.md").write_text(content, encoding="utf-8")


def test_validate_protocol_accepts_current_swot_package() -> None:
    package_dir = Path(r"E:\Project\vision-lab\vision-skill\packages\swot-analysis")

    result = validate_protocol(package_dir)

    assert result["valid"] is True
    assert result["summary"]["errors"] == 0


def test_validate_protocol_rejects_missing_internal_flow(tmp_path: Path) -> None:
    package_dir = tmp_path / "example-package"
    write_skill(package_dir, VALID_SKILL.replace("## 内部执行流（仅用于推理，不在对用户输出中显示阶段编号）", "## 其他说明"))

    result = validate_protocol(package_dir)

    assert result["valid"] is False
    assert any(issue["code"] == "missing_required_section" for issue in result["issues"])


def test_validate_protocol_rejects_missing_mvi_in_step_2(tmp_path: Path) -> None:
    package_dir = tmp_path / "example-package"
    write_skill(package_dir, VALID_SKILL.replace("**最小可用输入（MVI）**\n- 第一阶段结果（必需）\n\n", ""))

    result = validate_protocol(package_dir)

    assert result["valid"] is False
    assert any(issue["code"] == "missing_step_block" for issue in result["issues"])


def test_validate_protocol_rejects_missing_pause_block_in_non_final_step(tmp_path: Path) -> None:
    package_dir = tmp_path / "example-package"
    write_skill(
        package_dir,
        VALID_SKILL.replace(
            """**输出后暂停**
> ────────
> 以上是 Step 2 第二阶段。请确认：回复“继续”进入下一步，回复“不对”+说明修改要求，回复“直接要结果”跳过后续暂停。
> ────────
""",
            "",
        ),
    )

    result = validate_protocol(package_dir)

    assert result["valid"] is False
    assert any(issue["code"] == "missing_step_pause" for issue in result["issues"])


def test_validate_protocol_rejects_pause_block_in_final_step(tmp_path: Path) -> None:
    package_dir = tmp_path / "example-package"
    write_skill(package_dir, VALID_SKILL + "\n**输出后暂停**\n> 不应出现。\n")

    result = validate_protocol(package_dir)

    assert result["valid"] is False
    assert any(issue["code"] == "final_step_has_pause" for issue in result["issues"])
