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
import json
import posixpath
import re
import statistics

from config import MAX_CHECKS, MAX_LEAKED_LITERALS, MIN_CHECKS

# Problem shapes where the reference agent failed fairly (behaviour over a sequence); "other" is
# allowed but must still name a sequence invariant.


def _words(text) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", str(text).lower())) - {"the", "a", "an", "of", "in", "to", "and", "is", "for"}


def _similar(a: set[str], b: set[str], threshold: float = 0.8) -> bool:
    """Two defect descriptions sharing most of their words describe the same bug."""
    return bool(a and b) and len(a & b) / len(a | b) >= threshold


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


VERIFIER_PACKAGE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?==[A-Za-z0-9.+!-]+")


def knob_gate(spec: dict) -> list[str]:
    """Every recipe: 2 to 4 difficulty knobs, each with the fairness condition that makes it fair."""
    knobs = spec.get("knobs") or []
    if not isinstance(knobs, list) or not all(isinstance(k, dict) for k in knobs):
        return ["`knobs` must be a list of knob objects"]
    problems = []
    if not 2 <= len(knobs) <= 4:
        problems.append(f"needs 2 to 4 difficulty `knobs`, has {len(knobs)}")
    unfair = [str(k.get("knob") or i) for i, k in enumerate(knobs)
              if not str(k.get("knob") or "").strip() or not str(k.get("fairness") or "").strip()]
    if unfair:
        problems.append("every knob needs `knob` and its `fairness` condition; missing on " + ", ".join(unfair[:4]))
    return problems


_APT_NAME = re.compile(r"[a-z0-9][a-z0-9.+-]+")


def seed_gate(spec: dict, seed: str) -> list[str]:
    """With a seed card, the design must carry the card's difficulty machinery: the dial, the
    quirk matrix, the public common-path tests and the anti-cheese gate."""
    if not seed:
        return []
    return [f"the seed card requires `{key}`: {why}" for key, why in (
        ("dial", "what moves the pass rate, its fair range and chosen value"),
        ("quirk_matrix", "the dimensions x levels hidden instances are drawn from, and the mix"),
        ("public_tests", "what the visible common-path tests cover"),
        ("anti_cheese", "the paired gate that stops a shortcut, and its hidden test"),
        ("graded_instances", "how graded instances differ from the practice set"),
        ("self_check_gap", "what a solution that reproduces the whole practice set can still get wrong on the graded instances"),
        ("contract", "the exact observable contract"),
        ("invisible_traps", "at least one trap with no runtime signal, stated in the instruction"),
        ("instance_plan", "the graded instances and their quirk cells"))
        if not str(spec.get(key) or "").strip() and spec.get(key) not in (0, False)] + [
        "every check needs `caught_by_tests`: the hidden test functions that must fail when it is done wrong"
        for _ in [0] if any(isinstance(c, dict) and not c.get("caught_by_tests") for c in spec.get("checks") or [])] + [
        "the seed card makes this an inferred task: set `answer_source: inferred` and list `inferred_rules`"
        for _ in [0] if re.search(r"(?m)^answer_source:\s*inferred", seed) and not inferred(spec)]


def spec_gate(spec: dict, genre: str = "") -> list[str]:
    """The design gate (one recipe for every topic): enough independent checks, each tied to a
    sentence the agent can see and evaluated on inputs it never sees; ground truth computed by code;
    2 to 4 difficulty knobs with their fairness conditions."""
    checks = spec.get("checks") or []
    if not isinstance(checks, list) or not all(isinstance(c, dict) for c in checks):
        return ["`checks` must be a list of check objects"] + knob_gate(spec)
    problems = []
    if not MIN_CHECKS <= len(checks) <= MAX_CHECKS:
        problems.append(f"needs {MIN_CHECKS} to {MAX_CHECKS} independent `checks`, has {len(checks)}")
    keys = ("requirement", "assumed_instead", "hidden_test_input", "why_missed")
    incomplete = [str(i) for i, c in enumerate(checks) if not all(str(c.get(k) or "").strip() for k in keys)]
    if incomplete:
        problems.append("every check needs " + ", ".join(f"`{k}`" for k in keys) + "; missing on " + ", ".join(incomplete[:5]))
    # Several checks may quote the same sentence ("stay within tolerance for every unseen
    # condition") and differ in their hidden input; a duplicate repeats both.
    req = [_words(c.get("requirement", "")) for c in checks]
    inp = [_words(c.get("hidden_test_input", "")) for c in checks]
    same = [(i, j) for i in range(len(checks)) for j in range(i + 1, len(checks))
            if _similar(req[i], req[j], 0.8) and _similar(inp[i], inp[j], 0.6)]
    if same:
        problems.append("checks must be independent (a check that repeats another's requirement AND hidden input "
                        "adds nothing): " + ", ".join(f"{i}~{j}" for i, j in same[:4]))
    for key, why in (("shape", "the kind of work the topic names"),
                     ("hidden_evaluation", "what the tests check that the agent cannot fully reproduce"),
                     ("ground_truth", "how the tests compute every expected value with code")):
        if not str(spec.get(key) or "").strip():
            problems.append(f"needs `{key}`: {why}")
    bad = [p for p in spec.get("verifier_packages") or [] if not VERIFIER_PACKAGE.fullmatch(str(p).strip())]
    if bad:
        problems.append(f"`verifier_packages` must be exact name==version pins: {bad[:3]}")
    bad = [p for p in spec.get("verifier_apt") or [] if not _APT_NAME.fullmatch(str(p).strip())]
    if bad:
        problems.append(f"`verifier_apt` must be Debian package names: {bad[:3]}")
    return problems + knob_gate(spec) + reference_gate(spec) + answer_gate(spec)


def inferred(spec: dict | None) -> bool:
    return str((spec or {}).get("answer_source") or "").strip().lower().startswith("inferred")


def answer_gate(spec: dict) -> list[str]:
    """Stated vs inferred: an inferred task names every rule the agent must infer and the training
    examples that show it (fair), so the files gate can check none of them is written down."""
    source = str(spec.get("answer_source") or "").strip().lower().split()[:1]
    if source not in (["stated"], ["inferred"]):
        return ["needs `answer_source`: stated (the agent implements rules it is told) or inferred (it infers "
                "rules or fits a model from data)"]
    if source != ["inferred"]:
        return []
    rules = spec.get("inferred_rules")
    if not isinstance(rules, list) or not rules:
        return ["an inferred task needs `inferred_rules`: every rule the agent must infer, with `shown_by`"]
    bare = [str(i) for i, r in enumerate(rules) if not (isinstance(r, dict) and str(r.get("rule") or "").strip()
                                                          and str(r.get("shown_by") or "").strip())]
    if bare:
        return ["every inferred rule needs `rule` and `shown_by` (the training examples that show it); missing on "
                + ", ".join(bare[:5])]
    return stated_fact_repeats(spec)


_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.]*\d)")
_SENTENCE = re.compile(r"(?<=[.!?:;])\s+|\n+")


_ORDER = re.compile(r"\b(before|after|prior to|followed by|precedence|takes priority|first\b.{0,40}\bthen)\b", re.I)
_MAPPING = re.compile(r"(→|->|=>|^\s*\|)")


def _rule_words(text) -> set[str]:
    return {w for w in _words(text) if len(w) > 2 and w not in _COMMON}


def _rule_texts(spec: dict) -> list[str]:
    return [str(r.get("rule") if isinstance(r, dict) else r) for r in spec.get("inferred_rules") or []]


def _fact_texts(spec: dict) -> list[str]:
    return [json.dumps(f) if isinstance(f, dict) else str(f) for f in spec.get("stated_facts") or []]


def _restates(rule_words: set[str], text_words: set[str]) -> bool:
    return len(rule_words) >= 3 and len(rule_words & text_words) >= max(3, 0.6 * len(rule_words))


def stated_rule_leaks(files: dict[str, str], spec: dict | None) -> list[str]:
    """On an inferred task, instruction.md or a document must not hand over a rule the agent has to
    infer. Four signs, each checked against the design's `inferred_rules`: a rule's value (a
    threshold, a port) next to its words; a sentence that restates most of a rule's words; an
    ordering sentence (before, after, precedence) naming rule words; a mapping line (table row or
    arrow) built from one rule's tokens. Text that repeats a `stated_facts` entry is allowed.
    The address task's README passed the value check alone: its rules were words and orderings."""
    if not inferred(spec):
        return []
    facts = _fact_texts(spec)
    allowed = set(_NUMBER.findall(" ".join(facts)))
    fact_words = [_rule_words(f) for f in facts]
    rules = _rule_texts(spec)
    rwords = [_rule_words(r) for r in rules]
    rtokens = [set(_words(r)) - _COMMON for r in rules]
    union = set().union(*rwords) if rwords else set()
    texts = {"instruction.md": files.get("instruction.md", "")}
    texts.update({p: b for p, b in files.items() if p.startswith("environment/") and p.endswith(_SPEC_DOC_EXTS)})
    hits = []
    for path, body in texts.items():
        units = [u for line in body.splitlines() for u in ([line] if _MAPPING.search(line) else _SENTENCE.split(line)) if u.strip()]
        for sent in units:
            sw, st = _rule_words(sent), set(_words(sent)) - _COMMON
            if any(_restates(fw, sw) for fw in fact_words):
                continue
            why = ""
            for rule, rw, rt in zip(rules, rwords, rtokens):
                nums = {n for n in _NUMBER.findall(rule) if (len(n.lstrip("-").replace(".", "")) >= 2 or "." in n)} - allowed
                found = nums & set(_NUMBER.findall(sent))
                if found and len(rw & sw) >= 2:
                    why = f"gives {sorted(found)[0]} from rule {rule[:50]!r}"
                elif _restates(rw, sw):
                    why = f"restates rule {rule[:50]!r}"
                elif _MAPPING.search(sent) and len(rt & st) >= 2 and len(rt & st) >= 0.5 * len(st):
                    why = f"maps tokens of rule {rule[:50]!r}"
                if why:
                    break
            if not why and _ORDER.search(sent) and len(union & sw) >= 2:
                why = "states an order between inferred rules"
            if why:
                hits.append(f"{path}: {sent.strip()[:100]!r} {why}")
    return hits[:8]


def stated_fact_repeats(spec: dict) -> list[str]:
    """A stated fact may only be something the data cannot show; one that restates an inferred rule
    hands the rule over (a 'style guide' that lists the rules)."""
    if not inferred(spec):
        return []
    rules = _rule_texts(spec)
    return [f"`stated_facts` entry {i} restates inferred rule {next(r for r in rules if _restates(_rule_words(r), _rule_words(f)))[:60]!r}; "
            "drop it: the agent must infer that rule from the data"
            for i, f in enumerate(_fact_texts(spec)) if any(_restates(_rule_words(r), _rule_words(f)) for r in rules)]


REFERENCE_ACCESS = ("none", "frozen_examples", "runnable")


def reference_gate(spec: dict) -> list[str]:
    """The agent never runs code whose output answers the graded question (a mawk port with mawk
    installed was solved every time). `runnable` needs the reason matching is not the hard part, and
    every graded quirk names the file in the environment that shows it."""
    access = str(spec.get("reference_access") or "").strip()
    kind, _, reason = access.partition(":")
    kind = kind.strip().lower().replace(" ", "_")
    problems = []
    if kind not in REFERENCE_ACCESS:
        problems.append("needs `reference_access`: none, frozen_examples, or runnable: <why matching the "
                        "reference is not the hard part>")
    elif kind == "runnable" and len(reason.strip()) < 15:
        problems.append("`reference_access: runnable` needs its reason (a speed, memory or load target), "
                        "or ship frozen practice examples instead")
    if str(spec.get("quirk_matrix") or "").strip():
        ev = spec.get("quirk_evidence")
        if not isinstance(ev, list) or not ev:
            problems.append("needs `quirk_evidence`: for every graded quirk, the environment file that shows it")
        else:
            bare = [str(i) for i, e in enumerate(ev) if not (isinstance(e, dict) and str(e.get("evidence") or "").strip())]
            if bare:
                problems.append("every `quirk_evidence` entry needs `evidence` (the file that shows it); missing on "
                                + ", ".join(bare[:5]))
    return problems


_SPEC_DOC_EXTS = (".md", ".rst", ".txt", ".adoc")


def spec_docs(files: dict[str, str], spec: dict | None = None) -> dict[str, str]:
    """The spec document(s) the rules live in: the spec's `spec_document`, plus any shipped
    document instruction.md names by path or file name. Keys are paths under environment/."""
    instruction = files.get("instruction.md", "")
    wanted = str((spec or {}).get("spec_document") or "").strip().lstrip("/")
    out = {}
    for path, body in files.items():
        if not path.startswith("environment/") or not path.lower().endswith(_SPEC_DOC_EXTS):
            continue
        rel = path[len("environment/"):]
        named = re.search(rf"(?<![\w.-]){re.escape(posixpath.basename(rel))}(?![\w-])", instruction)
        if (wanted and (path == wanted or rel == wanted or path.endswith("/" + wanted))) or named:
            out[path] = body
    return out


def _doc_names(docs: dict[str, str]) -> set[str]:
    names = set()
    for p in docs:
        rel = p[len("environment/"):]
        names |= {rel, posixpath.basename(rel), "/app/" + rel}
    return names


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


def location_leaks(instruction: str, files: dict[str, str], allowed: set[str] = frozenset()) -> list[str]:
    """Shipped files (sources, configs, scripts) that instruction.md names. Naming them points
    the agent at the fault. Output files the agent creates are fine to name: they aren't shipped.
    Directories (e.g. "the project in /app/thumbgen") are fine too."""
    leaks = set()
    for name in shipped_names(files):
        if not name.startswith("/") and not is_code_or_config(name):
            continue
        if name in allowed or posixpath.basename(name) in allowed:
            continue  # the spec document the instruction tells the agent to follow
        if _run_as_command(posixpath.basename(name), instruction):
            continue  # the tool's entry point (how you run it) is interface, not a hint
        pattern = re.escape(name) if name.startswith("/") else rf"(?<![\w.-]){re.escape(name)}(?![\w-])"
        if re.search(pattern, instruction):
            leaks.add(name)
    return sorted(leaks)


def _run_as_command(basename: str, instruction: str) -> bool:
    """True if instruction.md runs this file (`python3 /app/ledger.py verify`, `./build.sh`)."""
    return bool(re.search(rf"(?:\b(?:python3?|bash|sh|node|ruby|perl|php)\s+|\./)[\w./-]*"
                          rf"(?<![\w-]){re.escape(basename)}(?![\w-])", instruction))


def _test_literals(tests_py: str) -> set[str]:
    """String and float constants in the tests that look like expected values."""
    try:
        tree = ast.parse(tests_py)
    except SyntaxError:
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            v = node.value.strip() if isinstance(node.value, str) else ""
            path_like = bool(v) and not re.search(r"\s", v) and ("/" in v or re.search(r"\.\w{1,5}$", v))
            name_like = bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", v))  # a field, key, option or column name: interface, not a value
            if isinstance(node.value, str) and len(v) >= 12 and "\n" not in node.value \
                    and not node.value.startswith("/") and not path_like and not name_like:
                out.add(node.value.strip())
            elif isinstance(node.value, float):
                out.add(repr(node.value))
    return out


def _looks_computed(literal: str) -> bool:
    """A test constant that looks like a computed result rather than a stated rule constant or
    output label: a spec task must state "overtime after 40.0 hours" and "print FLAGGED ENTRIES:",
    but must not paste 1806.25. Strings count only if they contain a digit; floats only with at
    least 5 characters once trailing zeros are dropped (1806.25, 12.75; not 40.0, 0.25, 7.5)."""
    if re.fullmatch(r"-?\d+\.\d+(e[+-]?\d+)?", literal):
        return len(literal.rstrip("0").rstrip(".")) >= 5
    return bool(re.search(r"\d", literal))


def leaked_literals(instruction: str, tests_py: str) -> list[str]:
    """Computed-looking test constants that instruction.md repeats as a whole token (so 0.0 does
    not match inside 40.0)."""
    return sorted(l for l in _test_literals(tests_py) if _looks_computed(l)
                  and re.search(r"(?<![\w.])" + re.escape(l) + r"(?![\w])", instruction))


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
    lines = tests_py.splitlines()
    for n, line in enumerate(lines, 1):
        if "assert" not in line:  # a helper line counts only if its result is asserted later
            m = re.match(r"\s*(\w+)\s*=", line)
            if not m or not any(re.search(rf"\bassert\b.*\b{re.escape(m.group(1))}\b", later)
                                for later in lines[n:n + 15]):
                continue
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
_INTENT = re.compile(r"\b(should|must|always|never|required?|expected|correctly|intended|so that|"
                     r"supposed to|needs? to|ensure)\b", re.I)
_LABEL = re.compile(r"\b(not (used|loaded|imported|called|enabled)|unused|deprecated|legacy|"
                    r"workaround|hack|fixme|todo|xxx|known (bug|issue))\b", re.I)
_COMMON = {"code", "file", "files", "value", "values", "function", "returns", "return", "when",
           "which", "with", "from", "that", "this", "only", "not", "are", "but", "all", "each",
           "used", "uses", "use", "data", "one", "some", "other", "before", "after", "into"}


def _fault_words(spec: dict) -> list[set[str]]:
    out = []
    for f in (spec.get("faults") or []) + (spec.get("requirements") or []):
        if isinstance(f, dict):
            words = {w for w in _words(f"{f.get('what', '')} {f.get('wrong_fix', '')} {f.get('rule', '')}")
                     if len(w) > 3 and w not in _COMMON}
            if words:
                out.append(words)
    return out


def answer_key_leaks(files: dict[str, str], spec: dict | None, skip: set[str] = frozenset()) -> list[str]:
    """Prose in environment/ that confesses: a rule-stating comment that shares >= 3 distinctive
    words with a fault, or a label that marks a module unused/legacy/a workaround."""
    faults = _fault_words(spec or {})
    hits = []
    for path, body in files.items():
        if not path.startswith("environment/") or path == "environment/Dockerfile" or path in skip:
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


def pointer_leaks(instruction: str, allowed: set[str] = frozenset()) -> list[str]:
    """Phrases in instruction.md that point at where the answer is written down (pointing at the
    spec document the task asks the agent to follow is fine)."""
    return sorted({m.group(0) for m in _POINTER.finditer(instruction)
                   if not any(a and a in instruction[m.start():m.end() + 80] for a in allowed)})


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


_ORACLE_CMD = re.compile(r"""(?:add_parser|add_command|subparsers?\.add_parser|choices\s*=\s*\[[^\]]*|command\s*==|cmd\s*==|args?\.command\s*==|case\s+)\s*['"]?(verify|check|validate|compare|diff|selftest|self-test|lint)['"]?\b""", re.I)
_ORACLE_FILE = re.compile(r"(^|/)(verify|check|validate|compare|selftest|self_test|expected[_-]?output|reference)[\w.-]*$", re.I)
_ORACLE_INSTR = re.compile(r"\b(run|use|until)\b[^.\n]{0,80}\b(verify|check|validate|compare|diff|self-?test)\b[^.\n]{0,60}\b(ok|pass|clean|match|no (mismatch|discrepanc|error))", re.I)


def build_stage_only(files: dict[str, str]) -> set[str]:
    """Paths under environment/ that the Dockerfile only uses in an earlier build stage: the final
    stage (after the last FROM) never COPYs them, so they are not in the image the agent gets.
    That is how an executable-reference task compiles its black box."""
    df = files.get("environment/Dockerfile", "")
    stages = re.split(r"(?im)^\s*FROM\s", df)
    if len(stages) < 3:  # text before the first FROM, then at least two stages
        return set()
    final = "\n".join(l for l in stages[-1].splitlines() if not re.search(r"--from=", l, re.I))
    out = set()
    for path in files:
        if path.startswith("environment/") and path != "environment/Dockerfile":
            rel = path[len("environment/"):]
            copied = re.search(rf"(?im)^\s*(COPY|ADD)\s[^\n]*(?<![\w./-])(\.?/?{re.escape(rel)}|{re.escape(posixpath.dirname(rel) or '.')}/?|\.)(?=\s)", final)
            if not copied:
                out.add(path)
    return out


def oracle_leaks(files: dict[str, str], skip: set[str] = frozenset()) -> list[str]:
    """Commands, files or instructions that hand the agent a pass/fail oracle for the graded result.
    `skip`: build-stage-only sources of an executable-reference task (they never reach the image)."""
    hits = []
    for path, body in files.items():
        if not path.startswith("environment/") or path == "environment/Dockerfile" or path in skip:
            continue
        name = path[len("environment/"):]
        if re.search(r"(^|/)tests?_public/|(^|/)public_tests?/", name):
            continue  # common-path public tests the design ships on purpose (seed card `public_tests`)
        code = is_code_or_config(posixpath.basename(name)) and posixpath.splitext(name)[1].lower() not in _DOC_EXTS
        if (code and _ORACLE_FILE.search(name)) or re.search(r"expected[_-]?output", name, re.I):
            hits.append(f"{path}: file name suggests a reference or self-check")
            continue
        if code:
            for n, line in enumerate(body.splitlines(), 1):
                m = _ORACLE_CMD.search(line)
                if m:
                    hits.append(f"{path}:{n}: exposes a '{m.group(1)}' command: {line.strip()[:80]}")
                    break
    m = _ORACLE_INSTR.search(files.get("instruction.md", ""))
    if m and re.search(r"public|tests?_public", m.group(0), re.I):
        m = None  # telling the agent how to run its public common-path tests is allowed
    if m:
        hits.append(f"instruction.md tells the agent how to confirm completion: '{m.group(0)[:90]}'")
    return hits


def rule_coverage(instruction: str, spec: dict | None) -> list[str]:
    """Requirements whose distinctive words are mostly absent from instruction.md: the tests would
    check a rule the agent was never told (unfair by construction)."""
    missing = []
    inst = _words(instruction)
    for i, r in enumerate((spec or {}).get("checks") or []):
        if not isinstance(r, dict):
            continue
        words = {w for w in _words(r.get("requirement", "")) if len(w) > 3 and w not in _COMMON}
        if len(words) >= 3 and len(words & inst) < len(words) * 0.5:
            missing.append(f"check {i}: {str(r.get('requirement'))[:90]}")
    return missing


def _interface_names(files: dict[str, str], spec: dict | None) -> tuple[dict, set[str], set[str], list[str]]:
    """The spec documents, the names instruction.md may use (documents, a reference binary, its
    sample), the build-stage-only sources, and any blocking problem with them."""
    problems = []
    docs = spec_docs(files, spec)
    want = str((spec or {}).get("spec_document") or "").strip()
    if want and not docs:
        problems.append(f"the spec document `{want}` is not among the files; ship it under environment/ "
                        "and name it in instruction.md")
    allowed = _doc_names(docs)
    build_only = set()
    runnable = str((spec or {}).get("reference_access") or "").strip().lower().startswith("runnable")
    if str((spec or {}).get("reference_binary") or "").strip() and not runnable:
        problems.append("a reference binary would reach the agent's image, but `reference_access` is not "
                        "`runnable`; keep the reference in tests/ and ship frozen practice examples")
    elif str((spec or {}).get("reference_binary") or "").strip():  # runnable: matching is not the hard part
        for key in ("reference_binary", "sample_file"):
            v = str((spec or {}).get(key) or "").strip()
            if v:
                allowed |= {v, posixpath.basename(v)}
        build_only = build_stage_only(files)
        shipped_src = [p for p in files if p.startswith("environment/") and p.endswith((".c", ".h")) and p not in build_only]
        if shipped_src:
            problems.append("the reference source would reach the agent's image (" + ", ".join(shipped_src[:3]) + "); compile it "
                            "in a build stage (FROM ... AS build) and COPY only the stripped binary into the final stage")
    return docs, allowed, build_only, problems


def files_gate(files: dict[str, str], spec: dict | None = None) -> list[str]:
    """Blocking checks: cheap, reliable, and each one protects the task (a missing document, a
    reference that would reach the agent, an oracle or a copy of the answer in the environment).
    Judgement calls about the text are in files_warnings() and go to the instruction review."""
    _, _, build_only, problems = _interface_names(files, spec)
    oracle = oracle_leaks(files, build_only)
    if oracle:
        problems.append("the environment or instruction gives the agent an oracle for the graded result; remove it "
                        "(no verify/check/diff/self-test commands, no expected output, no reference): " + "; ".join(oracle[:4]))
    refs = reference_copies(files)
    if refs:
        problems.append("the environment keeps a reference copy of the correct code (git history, "
                        "backups, originals); remove it: " + "; ".join(refs[:4]))
    if inferred(spec) and "def test_practice_covers_hidden_cases" not in files.get("tests/test_outputs.py", ""):
        problems.append("an inferred task needs `test_practice_covers_hidden_cases` in tests/test_outputs.py: it reads the "
                        "shipped practice data and fails if any hidden case kind has fewer than 3 examples")
    stated = stated_rule_leaks(files, spec)
    if stated:
        problems.append("an inferred task states rules the agent must infer from the data (the answer key); "
                        "remove the values, or list a fact the data cannot show under `stated_facts`: " + "; ".join(stated))
    return problems


def files_warnings(files: dict[str, str], spec: dict | None = None) -> list[str]:
    """Pattern-scan hints for the instruction review, not blockers: as blockers they caused most
    false-alarm repair rounds (rule constants taken for pasted answers, a reference binary taken
    for a leaked file name). The review decides whether each one is real."""
    instruction = files.get("instruction.md", "")
    tests_py = files.get("tests/test_outputs.py", "")
    docs, allowed, _, _ = _interface_names(files, spec)
    hints = []
    leaks = location_leaks(instruction, files, allowed)
    if leaks:
        hints.append("instruction.md names shipped source/config files: " + ", ".join(leaks))
    fa = format_assertions(tests_py, instruction)
    if fa:
        hints.append("tests may pin a textual form the instruction never states: " + "; ".join(fa[:4]))
    lits = leaked_literals(instruction, tests_py)
    if len(lits) > MAX_LEAKED_LITERALS:
        hints.append(f"instruction.md may paste expected values from the tests: {lits[:3]}")
    keys = answer_key_leaks(files, spec, set(docs))
    if keys:
        hints.append("comments in environment/ may state a rule or label code: " + "; ".join(keys[:5]))
    ptr = pointer_leaks(instruction, allowed)
    if ptr:
        hints.append(f"instruction.md may point at where an answer is written: {', '.join(ptr)}")
    # On an inferred task the training data states the rules; asking for them in words leaks them.
    uncovered = [] if inferred(spec) else rule_coverage(instruction + "\n" + "\n".join(docs.values()), spec)
    if uncovered:
        hints.append("these checks may not be stated anywhere the agent can see: " + "; ".join(uncovered[:5]))
    return hints
