"""
Cheap difficulty gates (no model calls), applied before any Docker or eval spend.

They encode what made the first 6 tasks too easy (all 5/5, fault found within 3 commands):
the instruction named the broken file, the environment was 95-303 lines, there was one fault,
the fix was a 1-4 line sed, and expected outputs were pasted into instruction.md.

  spec_gate(spec)   -> problems with the design (fault count, layers, chaining, decoys)
  files_gate(files) -> problems with the written task (location leak, size, fix size, leaks)

Each returns a list of human-readable problems; empty means pass. The text goes back to the
authoring model through the existing re-spec / repair paths.
"""

import ast
import posixpath
import re
import statistics

from config import (
    CRITIC_FOUND_WITHIN,
    DISCOVERY,
    MAX_FAULTS,
    MAX_LEAKED_LITERALS,
    MIN_ENV_LINES,
    MIN_FAULT_LAYERS,
    MIN_FAULTS,
    MIN_SOLVE_LINES,
)

LAYERS = {"build", "code", "config", "data", "runtime"}
# Problem shapes where the reference agent failed fairly (behaviour over a sequence); "other" is
# allowed but must still name a sequence invariant.
CHALLENGE_KINDS = {"incremental_state", "resume_after_interruption", "retry_idempotency",
                   "ordering_and_duplicates", "cache_invalidation", "format_migration",
                   "streaming_boundaries", "other"}


def _words(text) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", str(text).lower())) - {"the", "a", "an", "of", "in", "to", "and", "is", "for"}


def _similar(a: set[str], b: set[str], threshold: float = 0.8) -> bool:
    """Two defect descriptions sharing most of their words describe the same bug."""
    return bool(a and b) and len(a & b) / len(a | b) >= threshold


def discovery_eval(spec: dict) -> dict:
    """Grade the critic's estimate of WHEN the agent finds each fault.

    Gaps are the steps between consecutive discoveries. Rejected as too easy if the first fault
    is found before CRITIC_FOUND_WITHIN or any gap is below min_gap (two faults falling to the
    same look). Otherwise graded by the median gap; above too_hard_above it is only flagged.
    """
    d = DISCOVERY
    steps = []
    for f in spec.get("faults") or []:
        try:
            steps.append(float((f or {}).get("discovered_at_step")))
        except (TypeError, ValueError):
            return {"grade": "unknown", "problem": "every fault needs a numeric `discovered_at_step` "
                    "(the agent step at which it would be found)"}
    if len(steps) < 2:
        return {"grade": "unknown", "problem": "need at least 2 faults with `discovered_at_step`"}
    steps.sort()
    gaps = [b - a for a, b in zip(steps, steps[1:])]
    median, smallest = statistics.median(gaps), min(gaps)
    horizon = steps[-1]
    out = {"first": steps[0], "median_gap": median, "min_gap": smallest, "horizon": horizon,
           "timeout_risk": horizon > d["timeout_risk_steps"], "problem": ""}
    if steps[0] < CRITIC_FOUND_WITHIN or smallest < d["min_gap"]:
        out["grade"] = "too_easy"
        out["problem"] = (f"discovery too fast: first fault at step {steps[0]:g} (needs >= {CRITIC_FOUND_WITHIN}), "
                          f"smallest gap between finds {smallest:g} (needs >= {d['min_gap']}); "
                          "faults must be found one at a time, spaced out")
    elif median > d["too_hard_above"]:
        out["grade"] = "too_hard"
    elif median >= d["very_hard_gap"]:
        out["grade"] = "very_hard"
    elif median >= d["hard_gap"]:
        out["grade"] = "hard"
    else:
        out["grade"] = "moderate"
    return out


# Spec/eval vocabulary that must never appear in what the solving agent sees (instruction.md and
# environment/). Word boundaries keep "DEFAULT 0" or "critical" from matching.
_META = re.compile(
    r"discovered_at_step|expected_agent_steps|hidden_edge_cases|why_not_textbook|depends_on"
    r"|\bdecoys?\b|\bred[- ]herrings?\b|\bplanted\b|\btoo[_ ]easy\b|\bcritic\b"
    r"|\bfault\s*#?\s*\d+\b|\bbug\s*#\s*\d+\b"
    r"|\b(intentional|deliberate)(ly)?\s+(introduced\s+)?(bug|broken|wrong|incorrect|fault)"
    r"|\binjected\s+(bug|fault)", re.I)


def meta_leaks(files: dict[str, str]) -> list[str]:
    """Lines in instruction.md or environment/ that expose the spec or the difficulty eval
    (fault numbers, discovery-step estimates, decoy labels, "intentional bug" comments)."""
    hits = []
    for path, body in files.items():
        if path != "instruction.md" and not path.startswith("environment/"):
            continue
        for n, line in enumerate(body.splitlines(), 1):
            if "terminal-bench-canary" in line:
                continue
            m = _META.search(line)
            if m:
                hits.append(f"{path}:{n}: '{m.group(0)}' in: {line.strip()[:100]}")
    return hits


def spec_gate(spec: dict) -> list[str]:
    faults = spec.get("faults") or []
    if not isinstance(faults, list):
        return ["`faults` must be a list of fault objects"]
    problems = []
    if len(faults) < MIN_FAULTS:
        problems.append(f"needs at least {MIN_FAULTS} different faults, has {len(faults)}")
    layers = {str(f.get("layer", "")).lower() for f in faults if isinstance(f, dict)} & LAYERS
    if len(layers) < MIN_FAULT_LAYERS:
        problems.append(f"faults must span at least {MIN_FAULT_LAYERS} layers of "
                        f"{sorted(LAYERS)}, found {sorted(layers) or 'none'}")
    # "One fault repeated" means the same KIND of bug fixed in several places (e.g. one sed in
    # four files), not several different bugs that happen to share a file or view.
    whats = [_words(f.get("what", "")) for f in faults if isinstance(f, dict)]
    if any(_similar(a, b) for i, a in enumerate(whats) for b in whats[i + 1:]):
        problems.append("faults must be different bugs, not the same fix repeated in several places")
    if not spec.get("hidden_edge_cases"):
        problems.append("needs at least one hidden edge case the tests check")
    if len(faults) > MAX_FAULTS:
        problems.append(f"has {len(faults)} faults; at most {MAX_FAULTS} (more faults make a longer "
                        "proofreading list, not a harder task)")
    trap_keys = ("wrong_fix", "counterexample", "caught_by_test")
    traps = [f for f in faults if isinstance(f, dict) and all(str(f.get(k) or "").strip() for k in trap_keys)]
    if len(traps) < min(2, len(faults)):
        problems.append("at least 2 central faults need `wrong_fix` (the plausible incomplete fix a strong "
                        "agent tries first), `counterexample` (the exact input or sequence on which it is "
                        "wrong) and `caught_by_test` (the hidden test that runs it)")
    kind = str(spec.get("challenge_kind") or "").strip().lower()
    if kind not in CHALLENGE_KINDS:
        problems.append(f"`challenge_kind` must be one of {sorted(CHALLENGE_KINDS)}; build the task around "
                        "a defect that shows only over a sequence of runs or events, not a named technique")
    for key, why in (("static_read", "what reading the code alone reveals, and why it is not enough"),
                     ("crux", "the domain insight the complete fix depends on"),
                     ("sequence_invariant", "the invariant over sequences that instruction.md states"),
                     ("nameable_fix", "the shortest phrase an expert would use for the whole fix"),
                     ("self_check_blind_spot", "the re-test the agent will run, and why the partial fix passes it")):
        if not str(spec.get(key) or "").strip():
            problems.append(f"needs `{key}`: {why}")
    return problems


def solve_paths(solve_sh: str) -> set[str]:
    """Absolute file paths that solve.sh mentions (what it reads or edits)."""
    return {p.rstrip(".,;:'\")") for p in re.findall(r"(?<![\w$])(/(?:app|etc|opt|srv|var|usr/local)/[\w./-]+)", solve_sh)}


# Input data is fine to name (the agent must know what to process); source, build and config
# files are not. Bare words without a dot ("default") are only checked for known build files.
DATA_EXTS = {".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".db", ".sqlite", ".sqlite3", ".txt",
             ".log", ".png", ".jpg", ".jpeg", ".gif", ".parquet", ".xml", ".graph", ".dat", ".bin", ".gz"}
BUILD_FILES = {"Makefile", "GNUmakefile", "CMakeLists.txt", "Dockerfile", "Gemfile", "Rakefile", "Procfile", "Justfile"}


def is_code_or_config(name: str) -> bool:
    ext = posixpath.splitext(name)[1].lower()
    return name in BUILD_FILES or (bool(ext) and ext not in DATA_EXTS)


_COPY = re.compile(r"^\s*(?:COPY|ADD)\s+(?:--\S+\s+)*(\S+)\s+(\S+)\s*$", re.M | re.I)


def shipped_names(files: dict[str, str]) -> set[str]:
    """Names of files the image ships: environment/ basenames plus explicit COPY destinations
    (e.g. `COPY nginx-default /etc/nginx/sites-available/default`)."""
    names = {posixpath.basename(p) for p in files
             if p.startswith("environment/") and p != "environment/Dockerfile"}
    for _, dest in _COPY.findall(files.get("environment/Dockerfile", "")):
        if dest.startswith("/") and not dest.endswith("/"):
            names.update({dest, posixpath.basename(dest)})
    return {n for n in names if n and n not in (".", "..")}


def location_leaks(instruction: str, files: dict[str, str]) -> list[str]:
    """Shipped files (sources, configs, scripts) that instruction.md names. Naming them points
    the agent at the fault. Output files the agent creates are fine to name: they aren't shipped.
    Directories (e.g. "the project in /app/thumbgen") are fine too."""
    leaks = set()
    for name in shipped_names(files):
        if not name.startswith("/") and not is_code_or_config(name):
            continue
        pattern = re.escape(name) if name.startswith("/") else rf"(?<![\w.-]){re.escape(name)}(?![\w-])"
        if re.search(pattern, instruction):
            leaks.add(name)
    return sorted(leaks)


def _test_literals(tests_py: str) -> set[str]:
    """String and float constants in the tests that look like expected values."""
    try:
        tree = ast.parse(tests_py)
    except SyntaxError:
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) and len(node.value.strip()) >= 12 and "\n" not in node.value \
                    and not node.value.startswith("/"):
                out.add(node.value.strip())
            elif isinstance(node.value, float):
                out.add(repr(node.value))
    return out


def leaked_literals(instruction: str, tests_py: str) -> list[str]:
    return sorted(l for l in _test_literals(tests_py) if l in instruction)


def env_lines(files: dict[str, str]) -> int:
    return sum(sum(1 for l in body.splitlines() if l.strip())
               for p, body in files.items() if p.startswith("environment/"))


def solve_lines(solve_sh: str) -> int:
    return sum(1 for l in solve_sh.splitlines() if l.strip() and not l.strip().startswith("#"))


# Assertions that pin an exact textual form. Fine when instruction.md states that form; otherwise
# a correct solution can fail on spelling (today's case: `href.count('../') == 2` failed `../..`).
_FORMAT_ASSERTS = [
    # `dotdot = href.count('../')` then `assert dotdot == 2`: the count itself is the pin.
    (re.compile(r"""\.count\(\s*['"](\.\./|\.\.|/|\\n)['"]\s*\)"""), "counts a path/separator substring"),
    (re.compile(r"""\.(endswith|startswith)\(\s*['"]/['"]\s*\)"""), "requires a leading/trailing slash"),
    (re.compile(r"""assert\s+\w+(\.\w+)*\s*==\s*['"][^'"]*\.\./[^'"]*['"]"""), "compares a relative path literally"),
]


def format_assertions(tests_py: str, instruction: str) -> list[str]:
    """Format-pinning assertions in the tests whose form instruction.md never mentions."""
    hits = []
    for n, line in enumerate(tests_py.splitlines(), 1):
        for pat, why in _FORMAT_ASSERTS:
            if pat.search(line):
                token = "../" if "../" in line else "/" if "'/'" in line or '"/"' in line else None
                stated = token is not None and (f"`{token}`" in instruction or f"'{token}'" in instruction
                                                or ("trailing slash" in instruction.lower()))
                if not stated:
                    hits.append(f"tests/test_outputs.py:{n}: {why} ({line.strip()[:80]}); "
                                "instruction.md does not state that form")
    return hits


_HASH_COMMENT = {".py", ".sh", ".bash", ".toml", ".yaml", ".yml", ".cfg", ".ini", ".conf", ".rb",
                 ".pl", ".r", ".mk", ".cmake", ".env", ".properties", ""}
_SLASH_COMMENT = {".js", ".ts", ".jsx", ".tsx", ".c", ".h", ".cc", ".cpp", ".hpp", ".go", ".java",
                  ".rs", ".cs", ".kt", ".swift", ".scala", ".php", ".css", ".scss"}
_DASH_COMMENT = {".sql", ".lua", ".hs"}
_DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}


def comment_lines(path: str, body: str):
    """(line number, text) of the prose in a file: comments, Python docstrings, doc files.
    Crude by design: a '#' inside a string counts as a comment too."""
    ext = posixpath.splitext(path)[1].lower()
    name = posixpath.basename(path)
    in_doc = False
    for n, line in enumerate(body.splitlines(), 1):
        s = line.strip()
        if ext in _DOC_EXTS:
            yield n, s
            continue
        if ext == ".py" and (in_doc or s.startswith(('"""', "'''"))):
            yield n, s.strip("\"' ")
            if (s.count('"""') + s.count("'''")) % 2:  # an unclosed opening, or the closing line
                in_doc = not in_doc
            continue
        if ext in _HASH_COMMENT or name in BUILD_FILES:
            if "#" in line:
                yield n, line.split("#", 1)[1].strip()
        elif ext in _SLASH_COMMENT:
            if "//" in line:
                yield n, line.split("//", 1)[1].strip()
            elif s.startswith(("/*", "*")):
                yield n, s.lstrip("/* ")
        elif ext in _DASH_COMMENT and "--" in line:
            yield n, line.split("--", 1)[1].strip()


# A comment that states a rule ("must be normalised before comparing") next to code that breaks
# it is an answer key; one that labels a module "unused" or "legacy" announces a decoy.
_INTENT = re.compile(r"\b(should|must|always|never|required?|expected|correct(ly)?|intended|so that|"
                     r"supposed to|needs? to|ensure)\b", re.I)
_LABEL = re.compile(r"\b(not (used|loaded|imported|called|enabled)|unused|deprecated|legacy|"
                    r"workaround|hack|fixme|todo|xxx|known (bug|issue))\b", re.I)
_COMMON = {"code", "file", "files", "value", "values", "function", "returns", "return", "when",
           "which", "with", "from", "that", "this", "only", "not", "are", "but", "all", "each",
           "used", "uses", "use", "data", "one", "some", "other", "before", "after", "into"}


def _fault_words(spec: dict) -> list[set[str]]:
    out = []
    for f in spec.get("faults") or []:
        if isinstance(f, dict):
            words = {w for w in _words(f"{f.get('what', '')} {f.get('wrong_fix', '')}")
                     if len(w) > 3 and w not in _COMMON}
            if words:
                out.append(words)
    return out


def answer_key_leaks(files: dict[str, str], spec: dict | None) -> list[str]:
    """Prose in environment/ that confesses: a rule-stating comment that shares >= 3 distinctive
    words with a fault, or a label that marks a module unused/legacy/a workaround."""
    faults = _fault_words(spec or {})
    hits = []
    for path, body in files.items():
        if not path.startswith("environment/") or path == "environment/Dockerfile":
            continue
        for n, text in comment_lines(path, body):
            if not text or "terminal-bench-canary" in text:
                continue
            label = _LABEL.search(text)
            if label:
                hits.append(f"{path}:{n}: labels code '{label.group(0)}': {text[:90]}")
                continue
            if _INTENT.search(text):
                words = _words(text)
                if any(len(words & fw) >= 3 for fw in faults):
                    hits.append(f"{path}:{n}: states the rule a fault breaks: {text[:90]}")
    return hits


_POINTER = re.compile(r"\b(see|consult|refer to|check|read|look (at|in))\s+(the\s+)?"
                      r"(docs?|documentation|readme|comments?|changelog|notes|wiki|runbook|"
                      r"[\w./-]+\.(md|rst|txt))\b", re.I)


def pointer_leaks(instruction: str) -> list[str]:
    """Phrases in instruction.md that point at where the answer is written down."""
    return sorted({m.group(0) for m in _POINTER.finditer(instruction)})


_IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\b")


def fault_identifier_leaks(instruction: str, spec: dict | None) -> list[str]:
    """Code symbols from the faults' `where` (snake_case, camelCase, dotted names) that
    instruction.md repeats. File names are handled by location_leaks."""
    leaks = set()
    for f in (spec or {}).get("faults") or []:
        if not isinstance(f, dict):
            continue
        for ident in _IDENT.findall(str(f.get("where", ""))):
            if len(ident) < 4 or posixpath.splitext(ident)[1].lower() in DATA_EXTS | {".py", ".sh"}:
                continue
            looks_like_code = "_" in ident or "." in ident or re.search(r"[a-z][A-Z]", ident)
            if looks_like_code and re.search(rf"(?<![\w.]){re.escape(ident)}(?![\w])", instruction):
                leaks.add(ident)
    return sorted(leaks)


_REF_PATH = re.compile(r"(^|/)\.git(/|$)|\.(orig|rej|bak\d*|pristine|old)$|~$", re.I)
_REF_DOCKER = re.compile(r"\bgit\s+(init|clone|commit|add|stash|checkout)\b|COPY\s+\S*\.git\b|"
                         r"\bpip\s+download\b", re.I)


def reference_copies(files: dict[str, str]) -> list[str]:
    """Places the environment keeps the correct code: git history, backup/original files."""
    hits = [p for p in files if p.startswith("environment/") and _REF_PATH.search(p)]
    for n, line in enumerate(files.get("environment/Dockerfile", "").splitlines(), 1):
        if _REF_DOCKER.search(line):
            hits.append(f"environment/Dockerfile:{n}: {line.strip()[:80]}")
    return hits


def files_gate(files: dict[str, str], spec: dict | None = None) -> list[str]:
    instruction = files.get("instruction.md", "")
    solve_sh = files.get("solution/solve.sh", "")
    tests_py = files.get("tests/test_outputs.py", "")
    problems = []
    leaks = location_leaks(instruction, files)
    if leaks:
        problems.append("instruction.md names shipped source/config files (" + ", ".join(leaks) + "); "
                        "which points the agent at the fault; describe the symptom and goal "
                        "instead and let the agent find the location")
    n = env_lines(files)
    if n < MIN_ENV_LINES:
        problems.append(f"environment/ has {n} non-blank lines; needs at least {MIN_ENV_LINES} "
                        "(a realistic project the agent must search, with a decoy)")
    n = solve_lines(solve_sh)
    if n < MIN_SOLVE_LINES:
        problems.append(f"solve.sh has {n} meaningful lines; needs at least {MIN_SOLVE_LINES} "
                        "(the fix should be real work across several faults, not a few seds)")
    fa = format_assertions(tests_py, instruction)
    if fa:
        problems.append("tests pin an exact textual form the instruction never states, so a correct "
                        "solution can fail on spelling; test the meaning (resolve paths, parse values, "
                        "accept equivalent forms) or state the form in instruction.md: " + "; ".join(fa[:4]))
    lits = leaked_literals(instruction, tests_py)
    if len(lits) > MAX_LEAKED_LITERALS:
        problems.append(f"instruction.md pastes {len(lits)} expected values from the tests "
                        f"(e.g. {lits[:3]}); state the rule that produces them instead")
    keys = answer_key_leaks(files, spec)
    if keys:
        problems.append("comments or docs in environment/ give the answer away; describe what the code "
                        "does, never the rule it breaks, and never label code unused/legacy/a "
                        "workaround: " + "; ".join(keys[:5]))
    ptr = pointer_leaks(instruction)
    if ptr:
        problems.append(f"instruction.md points at where the answer is written ({', '.join(ptr)}); remove it")
    ids = fault_identifier_leaks(instruction, spec)
    if ids:
        problems.append(f"instruction.md names code symbols where faults live ({', '.join(ids)}); "
                        "describe behaviour, not code")
    refs = reference_copies(files)
    if refs:
        problems.append("the environment keeps a reference copy of the correct code (git history, "
                        "backups, originals); remove it: " + "; ".join(refs[:4]))
    return problems
