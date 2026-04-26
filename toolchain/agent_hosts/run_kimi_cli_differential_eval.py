from __future__ import annotations

from toolchain.agent_hosts.kimi_cli_differential import (
    _parse_judge_decision,
    _slugify,
    _trim_for_judge,
    build_parser,
    main,
    run_kimi_cli_differential_eval,
)


__all__ = [
    "_parse_judge_decision",
    "_slugify",
    "_trim_for_judge",
    "build_parser",
    "main",
    "run_kimi_cli_differential_eval",
]


if __name__ == "__main__":
    raise SystemExit(main())
