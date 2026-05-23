import logging
from pathlib import Path

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langsmith import Client

from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.backends.context_hub import ContextHubBackend

from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOLS

logger = logging.getLogger(__name__)

# LangSmith Context Hub agent repo where AGENTS.md lives.
# scripts/setup.py is responsible for pushing the local agent/AGENTS.md to
# this repo so the agent can pull it at runtime.
CONTEXT_HUB_REPO = "chat-langchain-lite-agent"


def _load_agents_md() -> str:
    """Pull AGENTS.md from LangSmith Context Hub.

    Context Hub is the source of truth at runtime; the local file is only the
    fallback when the hub is unreachable (offline development, CI without
    LangSmith credentials, etc.). When you fix AGENTS.md, edit the local file,
    commit, and the next `scripts.setup` run will push the new version to the
    hub.
    """
    try:
        client = Client()
        repo = client.pull_agent(CONTEXT_HUB_REPO)
        content = repo.files["AGENTS.md"].content
        logger.info(f"Loaded AGENTS.md from Context Hub repo '{CONTEXT_HUB_REPO}'")
        return content
    except Exception as e:
        logger.warning(
            f"Failed to pull from Context Hub ({e}); falling back to local AGENTS.md"
        )
        local = Path(__file__).parent / "AGENTS.md"
        return local.read_text() if local.exists() else ""


_AGENTS_MD = _load_agents_md()


def build_agent():
    # AGENTS.md is prepended to the system prompt so it shapes every response.
    # FilesystemMiddleware additionally exposes ls/read_file/etc. tools backed
    # by the same Context Hub repo, in case the agent needs to consult other
    # files (skills, policies, references) on demand.
    system_prompt = SYSTEM_PROMPT
    if _AGENTS_MD:
        system_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"## Context from LangSmith Context Hub\n\n"
            f"{_AGENTS_MD}"
        )

    return create_agent(
        model=ChatAnthropic(model="claude-haiku-4-5-20251001", max_tokens=300),
        tools=TOOLS,
        system_prompt=system_prompt,
        middleware=[
            FilesystemMiddleware(backend=ContextHubBackend(CONTEXT_HUB_REPO)),
        ],
    )


def _make_config(extra_metadata: dict = None) -> RunnableConfig:
    metadata = {"demo": "true", "demo_type": "chat-langchain-lite"}
    if extra_metadata:
        metadata.update(extra_metadata)
    return RunnableConfig(
        run_name="chat-langchain-lite-demo",
        metadata=metadata,
        tags=["engine-demo", "chat-langchain-lite-agent"],
    )


def invoke_agent(question: str, extra_metadata: dict = None, thread_id: str = None) -> dict:
    """Invoke the agent and return the full conversation as messages plus a flat tools_called list.

    The messages list (input, tool calls, tool results, final response) is stored
    in run.outputs so the trace shows the complete trajectory.
    tools_called is a flat list of tool names so evaluators can check it directly.
    """
    agent = build_agent()
    merged_metadata = {**(extra_metadata or {})}
    if thread_id:
        merged_metadata["thread_id"] = thread_id
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        _make_config(merged_metadata or None),
    )
    output = ""
    for msg in reversed(result["messages"]):
        if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content:
            output = msg.content
            break
    tools_called = [msg.name for msg in result["messages"] if isinstance(msg, ToolMessage)]
    return {
        "output": output,
        "messages": result["messages"],
        "tools_called": tools_called,
    }


def stream_agent(question: str, extra_metadata: dict = None, thread_id: str = None):
    """Stream the agent response token by token. Yields str chunks."""
    result = invoke_agent(question, extra_metadata, thread_id=thread_id)
    yield from result["output"]
