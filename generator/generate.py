"""
Task generator — generates a Harbor (Terminal-Bench 2) task from a topic string.

This is a stub. Implement it so that, given a topic, it produces a complete
task directory in the standard Harbor layout (study examples/ and the scaffold
at harbor/src/harbor/cli/template-task/):

    <task-name>/
    ├── task.toml            # [task] / [metadata] / [verifier] / [agent] / [environment]
    ├── instruction.md       # the prompt the agent sees (lead with the canary line)
    ├── environment/
    │   └── Dockerfile       # builds the task environment (no pre-built docker_image)
    ├── solution/
    │   └── solve.sh         # deterministic reference solution (the Oracle runs this)
    └── tests/
        ├── test.sh          # installs deps, runs the checks, writes the reward
        └── test_outputs.py  # pytest checks over the final container state

The reward contract: tests/test.sh must write `1` (pass) or `0` (fail) to
`/logs/verifier/reward.txt`. See harbor/src/harbor/verifier/verifier.py.
"""

import os
import sys

from config import CANARY_LINE, OUTPUT_DIR


def generate_task(topic: str, output_dir: str | None = None) -> dict:
    """Generate a Harbor task for the given topic.

    Args:
        topic: A short description of the task to generate
            (e.g. "fix a memory bug in a C ring buffer").
        output_dir: Where to write the generated task files.
            Defaults to output/<slugified-topic>.

    Returns:
        dict with at least {"task_dir": <path>, "status": <str>}.
    """
    slug = topic.lower().replace(" ", "-").replace("/", "-")[:60]

    if output_dir is None:
        output_dir = os.path.join(OUTPUT_DIR, slug)

    os.makedirs(output_dir, exist_ok=True)

    # TODO: implement task generation.
    #   1. Prompt the authoring model (config.MODEL via OpenRouter) for an
    #      instruction, a Dockerfile, a reference solution, and tests.
    #   2. Write task.toml, instruction.md, environment/Dockerfile,
    #      solution/solve.sh, tests/test.sh, tests/test_outputs.py. Stamp the
    #      CANARY_LINE into solve.sh / Dockerfile / test_outputs.py (Harbor
    #      strips it from instruction.md, so the convention is to leave it out
    #      of the prompt the agent sees).
    #   3. Hand the directory to the validator, then to the band evaluator.
    _ = CANARY_LINE  # stamp me into solve.sh / Dockerfile / tests
    pass


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "fix a broken Python CLI"
    result = generate_task(topic)
    if result:
        print(f"Generated task at: {result['task_dir']}")
