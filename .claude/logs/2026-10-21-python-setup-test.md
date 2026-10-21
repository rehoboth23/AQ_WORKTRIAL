# Python setup test — 2026-10-21

| Check | Command | Result |
|---|---|---|
| venv Python | `.venv/bin/python --version` | Python 3.12.15 — pass |
| Packages | `uv pip show harbor openai pydantic toml` | harbor 0.24.0, openai 2.54.0, pydantic 2.14.1, toml 0.10.2 — pass |
| Harbor CLI | `.venv/bin/harbor --help` | prints usage — pass |
| Harbor cross-check importable | `.venv/bin/python -c "from harbor.models.task.config import TaskConfig"` | ok — pass |
| Validator via script (no activation) | `bash scripts/validate.sh "$PWD/examples/fix-git"` | PASSED, exit 0, no "harbor not importable" warning — pass |
| Generator via script | `bash scripts/generate.sh "smoke test"` | exit 0, created `output/smoke-test/` (stub) — pass; folder removed |

## Found (pre-existing, not fixed)
`bash scripts/validate.sh examples/fix-git` run from the repo root fails ("Directory does not exist").
The script only makes the path absolute when it *doesn't* exist relative to the caller, then `cd`s into
`validator/`, breaking relative paths. Works with absolute paths or when called from outside the repo.
