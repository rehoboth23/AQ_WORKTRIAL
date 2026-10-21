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


def chat(system: str, user: str, parse, log=None, label: str = "call"):
    """Call the model and return (parsed, raw_text, usage).

    `parse` turns the reply text into a value or raises ValueError; a parse
    failure counts as a failed attempt and is retried. `log(label, record)` is
    called once per attempt with the raw reply and usage, for the audit trail.
    """
    last_err = None
    for attempt in range(LLM_MAX_RETRIES + 1):
        started = time.time()
        text, usage = "", {}
        try:
            resp = _get_client().chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            text = resp.choices[0].message.content or ""
            if resp.usage is not None:
                usage = {
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens,
                }
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


def parse_json_object(text: str) -> dict:
    """Pull the first JSON object out of a reply (fenced or bare)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    if not candidate:
        raise ValueError("no JSON object in reply")
    try:
        obj = json.loads(candidate)
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
