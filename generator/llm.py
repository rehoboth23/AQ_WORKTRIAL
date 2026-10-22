"""
Thin wrapper around the authoring model (config.MODEL) on the OpenAI-compatible
gateway, plus parsers for the two reply formats the generator asks for:

  * a JSON object (the task spec), optionally inside a ```json fence
  * delimited file blocks (task files), because code inside JSON escapes badly:

        <<<FILE environment/Dockerfile>>>
        FROM python:3.12-slim-bookworm
        ...
        <<<END>>>
"""

import json
import re
import time

from openai import OpenAI

from config import (
    LLM_MAX_RETRIES,
    LLM_TIMEOUT_SEC,
    MODEL,
    OPENROUTER_API_BASE,
    OPENROUTER_API_KEY,
)


class LLMError(RuntimeError):
    """The model call failed or its reply could not be parsed after retries."""


_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not OPENROUTER_API_KEY or not OPENROUTER_API_BASE:
            raise LLMError("OPENROUTER_API_KEY and OPENROUTER_API_BASE must be set in .env")
        _client = OpenAI(
            base_url=OPENROUTER_API_BASE,
            api_key=OPENROUTER_API_KEY,
            timeout=LLM_TIMEOUT_SEC,
            max_retries=0,  # we retry ourselves so parse failures are retried too
        )
    return _client


def reasoning_body(effort: str | None, budget: int | None) -> dict:
    """OpenRouter-style reasoning control: effort and/or a hidden-token budget; empty when neither is set."""
    r = {}
    if effort:
        r["effort"] = effort
    if budget:
        r["max_tokens"] = int(budget)
    return {"extra_body": {"reasoning": r}} if r else {}


def chat(system: str, user: str, parse, log=None, label: str = "call", reasoning: str | None = None,
         model: str | None = None, reasoning_budget: int | None = None):
    """Call the model and return (parsed, raw_text, usage).

    `parse` turns the reply text into a value or raises ValueError; a parse
    failure counts as a failed attempt and is retried. `log(label, record)` is
    called once per attempt with the raw reply and usage, for the audit trail,
    and once before each attempt with {"phase": "start"} so live status can show
    calls in flight.
    """
    model = model or MODEL
    last_err = None
    for attempt in range(LLM_MAX_RETRIES + 1):
        started = time.time()
        text, usage = "", {}
        if log:
            log(label, {"phase": "start", "attempt": attempt, "model": model, "reasoning": reasoning})
        try:
            # OpenRouter-style reasoning control; omitted entirely unless a stage sets it.
            extra = reasoning_body(reasoning, reasoning_budget)
            resp = _get_client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **extra,
            )
            text = resp.choices[0].message.content or ""
            if resp.usage is not None:
                usage = {
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens,
                }
                details = getattr(resp.usage, "completion_tokens_details", None)
                if getattr(details, "reasoning_tokens", None):
                    usage["reasoning_tokens"] = details.reasoning_tokens
                cost = (getattr(resp.usage, "model_extra", None) or {}).get("cost")
                if isinstance(cost, (int, float)):  # OpenRouter-style gateways report it
                    usage["cost_usd"] = float(cost)
            # "length" means the reply was cut off at the output limit (often after long
            # hidden reasoning); "stop" means the model finished on its own.
            usage["finish_reason"] = resp.choices[0].finish_reason
            parsed = parse(text)
        except Exception as e:  # network, API or parse error
            last_err = e
            if log:
                log(label, {"attempt": attempt, "error": repr(e), "raw": text, "usage": usage,
                            "seconds": round(time.time() - started, 1)})
            continue
        if log:
            log(label, {"attempt": attempt, "raw": text, "usage": usage,
                        "seconds": round(time.time() - started, 1)})
        return parsed, text, usage
    raise LLMError(f"{label} failed after {LLM_MAX_RETRIES + 1} attempts: {last_err!r}")


def _relax_json(text: str) -> str:
    """Remove trailing commas (`,}` / `,]`) and // or /* */ comments, outside string literals.
    One stray comma at the end of a 20k-token reply shouldn't throw the whole reply away."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_str = False
                if _missing_comma(text, i + 1):
                    out.append(",")
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        elif c == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1
                continue
            out.append(c)
        elif c in "}]":
            out.append(c)
            if _missing_comma(text, i + 1):
                out.append(",")
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _missing_comma(text: str, j: int) -> bool:
    """True when a value just ended at text[j-1] and, after whitespace that includes a newline, the
    next value starts (a string, object or array): the model dropped the comma between two list
    items or two pairs (four 10-20 minute replies were lost to this on 22 Oct). A newline is
    required so `"a" "b"` on one line (not a JSON slip we have seen) is left alone."""
    k = j
    while k < len(text) and text[k] in " \t\r\n":
        k += 1
    return "\n" in text[j:k] and k < len(text) and text[k] in '"{['


def parse_json_object(text: str) -> dict:
    """Pull the first JSON object out of a reply (fenced or bare)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    if not candidate:
        raise ValueError("no JSON object in reply")
    try:
        obj = json.loads(candidate, strict=False)
    except json.JSONDecodeError:
        try:  # common model slips: trailing commas, // or /* */ comments
            obj = json.loads(_relax_json(candidate), strict=False)
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise ValueError("reply JSON is not an object")
    return obj


_FILE_BLOCK = re.compile(r"<<<FILE\s+(?P<path>[^>\s]+)\s*>>>\n(?P<body>.*?)\n?<<<END>>>", re.S)


def parse_file_blocks(text: str) -> dict[str, str]:
    """Return {relative_path: content} for every file block in the reply."""
    files = {m.group("path").strip(): m.group("body") for m in _FILE_BLOCK.finditer(text)}
    if not files:
        raise ValueError("no <<<FILE path>>> ... <<<END>>> blocks in reply")
    return {p: (body if body.endswith("\n") else body + "\n") for p, body in files.items()}
