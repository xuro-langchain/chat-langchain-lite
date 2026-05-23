"""Evaluators for the Chat LangChain Lite demo.

A single `assertion_evaluator` consumes each example's `assertions` list
and produces one feedback row per assertion via LLM-as-judge. This matches
the format Engine emits when proposing generated examples to a dataset,
so anything Engine adds is scored the same way.
"""

from anthropic import Anthropic

_anthropic_client = None


def _get_anthropic_client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic()
    return _anthropic_client


def _judge_assertion(criterion: str, output: str, tools_called: list[str]) -> float:
    """LLM-as-judge: does the agent response satisfy the criterion?

    Returns 1.0 if 'yes', 0.0 otherwise.
    """
    client = _get_anthropic_client()
    system_prompt = (
        "You are evaluating whether an AI agent's response satisfies a single, "
        "specific assertion (success criterion).\n\n"
        "You receive:\n"
        "  - The assertion text (the criterion the response must meet)\n"
        "  - The list of tools the agent called for this run (may be empty)\n"
        "  - The agent's final response text\n\n"
        "Answer ONLY 'yes' if the response satisfies the assertion, or 'no' if it does not. "
        "Be strict: the assertion must be clearly met in the response."
    )
    user_msg = (
        f"Assertion: {criterion}\n\n"
        f"Tools called: {', '.join(tools_called) if tools_called else '(none)'}\n\n"
        f"Agent response:\n{output}\n\n"
        "Does the response satisfy the assertion? Answer ONLY 'yes' or 'no'."
    )
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=16,
        system=system_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )
    answer = response.content[0].text.strip().lower()
    return 1.0 if answer.startswith("yes") else 0.0


def assertion_evaluator(run, example) -> list[dict]:
    """Score each assertion in example.outputs.assertions against the agent output.

    Returns a list of {key, score} dicts — one per assertion. Each becomes
    its own feedback row in the LangSmith experiment, so the dashboard
    shows pass-rate per assertion key.
    """
    output = (run.outputs or {}).get("output") or ""
    tools_called = (run.outputs or {}).get("tools_called") or []
    assertions = (example.outputs or {}).get("assertions") or []
    if not assertions:
        return [{"key": "missing_assertions", "score": 0.0}]

    results = []
    for a in assertions:
        key = a.get("key", "assertion")
        criterion = a.get("comment", "")
        score = _judge_assertion(criterion, output, tools_called)
        results.append({"key": key, "score": score})
    return results
