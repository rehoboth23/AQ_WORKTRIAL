# Changelog

Document what you did, why, and any design tradeoffs here.

## 2026-10-21: Pinned Python environment with uv

**What:** Python 3.12 (installed by uv) in a gitignored `.venv` at the repo root, with the generator deps and `harbor` installed. `scripts/generate.sh` and `scripts/validate.sh` now use `.venv/bin/python` when it exists and fall back to `python` otherwise.

**Why:** The host had only macOS `python3` 3.9.6 (too old for `tomllib` and 3.12+ code) and no bare `python`, so both scripts failed. Without `harbor` installed, the validator also silently skipped Harbor's own schema check.

**Tradeoffs:**
- *uv venv vs. a Docker "tools" container.* A container would isolate more, but `harbor run` starts its own containers. The tools container would then need the host Docker socket (root-level access to Docker) and the repo mounted at the same absolute path so Harbor's bind mounts resolve. uv is lighter and avoids that setup, and Docker stays dedicated to task containers.
- *Venv inside the repo vs. outside.* Inside is uv's convention and keeps the project self-contained. `.gitignore` already excludes `.venv/`, so the ~240 MB never gets committed.

## 2026-10-21: validate.sh path fix and environment review

**validate.sh relative paths.** `bash scripts/validate.sh examples/fix-git` failed when run from the repo root ("Directory does not exist"). The script only rewrote the path when it *didn't* exist relative to the caller, then `cd`'d into `validator/`, which broke the relative path. It now makes the path absolute before the `cd`. It checks the caller's folder first, then the repo root, and passes missing paths through so the validator reports them. Tested from the repo root, `examples/`, `/tmp`, with an absolute path, with `.`, and with a missing folder (exit 1). `generate.sh` takes a topic, not a path, and the generator builds `output/` from its own file location, so it never had this bug.

**Validator rules kept as-is.** `validator/validate.py` is unchanged from the starter repo. Its rules (agent `timeout_sec` ≥ 3600, `[task].name` in `org/name` form, `[metadata].difficulty` set) come from there, and the 3600 matches all six examples. The one-hour floor is how the starter repo enforces the README's "timeouts don't count as the model failing", so relaxing it would let tasks fail on time alone.

**Scaffold vs. validator.** Harbor's scaffold (`harbor/src/harbor/cli/template-task/`) fails the validator as-is: agent timeout 900, no name, no difficulty, and its pytest files sit in `pytest-tests/` instead of `tests/`. Decision: treat the scaffold only as a starting point. The generator overwrites the values that break the validator, and `harbor/` stays unedited so it keeps matching the installed Harbor version.

**Environment findings, recorded in CLAUDE.md:**
- Claude's shell doesn't load `~/.zprofile`, so `docker` isn't on its PATH, and Harbor calls `docker compose` as a subprocess. Harbor commands therefore need `PATH="$HOME/.docker/bin:$PATH"`. Verified with `harbor run -p examples/fix-git -a oracle` → reward 1.0.
- `OPENROUTER_API_KEY` / `OPENROUTER_API_BASE` must be exported in the terminal that launches the editor/Claude.
- There are no unit tests or linters; the checks are validate.sh plus oracle/nop. `harbor run` output goes to `jobs/`.

## 2026-10-21: API key via .env

**What:** The key lives in a repo-root `.env`, which is gitignored (the starter `.gitignore` already listed it) and `chmod 600`. `generator/config.py` loads it with python-dotenv (now in `generator/requirements.txt`), and `harbor run` gets it through `--env-file .env`. `.env.example` documents the two variables with no values. In CLAUDE.md, "never store secrets in files" became "never read, print, or copy `.env`".

**Why:** Shell exports depend on which profile a shell loads. Claude's shell skips `~/.zprofile`, so the key wasn't reaching it, and an unattended or resumed batch run needs the key no matter how it's launched.

**Tradeoffs:** macOS Keychain avoids keeping the key in plain text on disk, but it only reaches processes whose shell profile runs. That's fragile for this pipeline. `.env` is the convention the starter repo planned for; the file is gitignored and readable only by its owner, and the key is budget-capped and can be rotated. Exported variables override the file (`load_dotenv` defaults to `override=False`).

## 2026-10-21: Inference endpoint set only in .env

**What:** `OPENROUTER_API_BASE` now comes only from `.env`. The hard-coded fallback in `generator/config.py` and the value in `.env.example` were removed. `.gitignore` now ignores `.env*` (keeping `.env.example`), so backups of `.env` can't be committed.

**Why:** The README's gateway returned 401 for the provided key. With the endpoint set in `.env`, both glm-5.1 (generator, openai client) and glm-5.3-flash (evaluator, through LiteLLM as Harbor calls it) responded. Keeping the URL out of code and docs means a wrong default can't silently send the key to the wrong endpoint, and changing the endpoint is a one-line edit to `.env`.

**Tradeoff:** If `.env` is missing the endpoint, model calls fail instead of falling back. That's intended: failing loudly is better than sending the key to an unintended server.
