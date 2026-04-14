from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from toolchain.eval_factory.catalog import export_certified_bundle


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _package_metadata(package_dir: Path) -> dict[str, Any]:
    return _load_json(package_dir / "metadata" / "package.json")


def _resolve_bundle_path(package_dir: Path, bundle_path: str) -> Path:
    candidate = Path(bundle_path)
    if candidate.is_absolute():
        return candidate
    return (package_dir / bundle_path).resolve()


def sync_package_evals(package_path: str | Path) -> dict[str, Any]:
    package_dir = Path(package_path)
    package_meta = _package_metadata(package_dir)
    eval_source = package_meta.get("eval_source", {})

    if eval_source.get("mode") != "certified-bundle":
        return {
            "synced": False,
            "source_mode": "package-local",
            "eval_path": str(package_dir / "evals" / "evals.json"),
        }

    bundle_path = _resolve_bundle_path(package_dir, str(eval_source.get("bundle_path", "")))
    output_path = package_dir / eval_source.get("sync_output", "evals/evals.json")
    export = export_certified_bundle(bundle_path, output_path)
    sync_metadata = {
        "source_mode": "certified-bundle",
        "bundle_id": export["bundle_id"],
        "bundle_path": str(bundle_path),
        "output_path": str(output_path),
        "exported_eval_count": export["exported_eval_count"],
    }
    _write_json(package_dir / "evals" / "eval-sync.json", sync_metadata)

    return {
        "synced": True,
        "source_mode": "certified-bundle",
        "bundle_id": export["bundle_id"],
        "eval_path": str(output_path),
        "sync_metadata_path": str(package_dir / "evals" / "eval-sync.json"),
    }


def resolve_package_evals(package_path: str | Path) -> dict[str, Any]:
    package_dir = Path(package_path)
    package_meta = _package_metadata(package_dir)
    eval_source = package_meta.get("eval_source", {})

    if eval_source.get("mode") == "certified-bundle" and eval_source.get("sync_on_read", True):
        sync_result = sync_package_evals(package_dir)
        eval_path = Path(sync_result["eval_path"])
        return {
            "data": _load_json(eval_path),
            "eval_path": str(eval_path),
            "source_mode": "certified-bundle",
            "sync_result": sync_result,
        }

    eval_path = package_dir / "evals" / "evals.json"
    return {
        "data": _load_json(eval_path),
        "eval_path": str(eval_path),
        "source_mode": "package-local",
        "sync_result": {
            "synced": False,
            "source_mode": "package-local",
            "eval_path": str(eval_path),
        },
    }
