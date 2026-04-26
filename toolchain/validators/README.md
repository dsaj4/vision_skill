# Validators

Validators provide fast local checks before a package enters expensive model evaluation.

Current validators:

- `package_validator.py`
  - checks package structure, metadata, eval files, and required package assets
- `protocol_validator.py`
  - checks whether `SKILL.md` includes the required interaction protocol pieces

These checks are intentionally conservative. They catch contract violations and obvious drift, but they do not prove skill quality. Quality is judged through the Kimi Code evaluation mainline, Kimi host validation, and human review.
