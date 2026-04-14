# Eval Factory Tooling

This module is the lightweight bridge between `eval-factory/` data files and the rest of the mainline.

Current responsibilities:

- index the file-based `eval-factory/` skeleton
- validate that a certified bundle is internally consistent
- export a certified bundle into package-style `evals.json` shape
- sync a package to its declared certified bundle
- resolve package evals for mainline readers
- preserve optional `host_eval` blocks when exporting certified candidates

Current public functions:

- `load_factory(factory_dir)`
- `validate_certified_bundle(bundle_path, factory_dir=None)`
- `export_certified_bundle(bundle_path, output_path, factory_dir=None)`
- `sync_package_evals(package_dir)`
- `resolve_package_evals(package_dir)`

This is intentionally small for `v0.1`. It does not own calibration execution yet. It makes the eval-factory auditable and lets packages default to certified eval consumption without changing the downstream file contract.
