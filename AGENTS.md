# Repository Instructions

This repository contains one Codex paper-writing router and six focused skills.
Read `catalog.json` and the relevant `skills/<name>/SKILL.md` before editing or using a module.
For a research request, follow `skills/research-starter-paper/SKILL.md` and load only relevant modules.

## Scope And Sources

- Keep edits scoped to the requested module and its source mapping.
- Preserve factual distinctions between observations, hypotheses, completed work, and plans.
- Never fabricate data, references, mechanisms, reviewer comments, or completed experiments.
- Keep original tutorial summaries distinct from independent adaptations.
- Do not mark new or changed sources as read unless their actual body and necessary figures have been reviewed.
- Preserve upstream attribution. Do not copy raw tutorials, figures, credentials, unpublished user materials, or local filesystem paths into this repository.
- Historical tool commands, scholarships, venue conventions, and numerical heuristics are not current universal rules.

## File Safety

- Do not bulk-delete files or directories. No recursive deletion commands or cleanup routines.
- If deletion is required, identify one explicit file at a time; ask the user to handle bulk cleanup.
- On this user's Windows machines, put temporary scripts, downloads, caches, tests, builds and previews under `D:\Codex\work\<task>`; use E if D is unavailable. Do not fall back to C silently.
- Final installed skills and required persistent configuration belong in their designated locations.
- Use an explicit non-C work location for repository development and process-local temporary/cache variables. Do not move or clean existing files automatically.

## Validation And Installation

Run `python scripts/validate_skills.py` and `python -m unittest discover -s tests -v` after meaningful changes.
Also run `python -O scripts/validate_skills.py`; validation must never depend on removable assertions.
Run `python scripts/validate_behavior_eval.py` to check recorded evaluation integrity, not model accuracy.
If skill or fixture changes affect recorded tasks, retain prior outputs and re-evaluate the affected cases with the user's authorization; never refresh hashes to disguise stale results.
Development validation requires the packages in `requirements-dev.txt`; installing the skills does not.
The installer refuses existing skill directories unless `--update` is explicitly used with `--backup-dir`.
It preserves unrelated installed files and never deletes obsolete ones automatically.

Keep all seven skill folders as siblings when installing. Router links depend on that layout.
Original public PNGs require `docs/images/manifest.json` with origin, generation source, dimensions and SHA-256.
Keep synthetic teaching data and illustrative outputs distinct from actual experiments and recorded model runs.
Use `--dry-run` to preview installation and `--check` for read-only content comparison.
Keep package and citation versions consistent; preserve the maintainer's choice not to add a new license.
GitHub is the shared source of truth; local installed copies are updated separately.
Do not change remote visibility, push, publish releases, overwrite branches or modify account configuration without the user's corresponding request.
Changing the Codex account does not grant GitHub write permission.
