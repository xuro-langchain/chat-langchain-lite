"""LangSmith Context Hub helpers.

The local context/AGENTS.md is the source of truth. Engine modifies it via
PR; the next `scripts.setup` run syncs the change to Context Hub. At
runtime, agent.py calls load_agents_md() to pull it back from the hub.

The two raw-REST calls below exist only because the Python SDK doesn't yet
expose `source` on push_agent or a workspace-handle setter. When the SDK
catches up, this file collapses to a single push_agent() call.
"""

import os
from pathlib import Path

import requests
from langsmith import Client
from langsmith.schemas import FileEntry

CONTEXT_HUB_REPO = "chat-langchain-lite-agent"
LOCAL_AGENTS_MD = Path(__file__).parent.parent / "context" / "AGENTS.md"

_API = "https://api.smith.langchain.com/api/v1"


def load_agents_md() -> str:
    """Pull AGENTS.md from Context Hub; fall back to the local file."""
    try:
        return Client().pull_agent(CONTEXT_HUB_REPO).files["AGENTS.md"].content
    except Exception:
        return LOCAL_AGENTS_MD.read_text() if LOCAL_AGENTS_MD.exists() else ""


def push_agents_md() -> None:
    """Push the local context/AGENTS.md to Context Hub.

    Does three things the SDK can't do on its own:
      1. Sets a workspace tenant_handle if missing (the UI listing filter
         hides repos with owner=null).
      2. Creates the repo with source="internal" (the marker the UI listing
         filters on; SDK's push_agent doesn't expose it).
      3. Commits the file via the SDK.
    """
    print(f"\n[*] Pushing AGENTS.md to Context Hub repo '{CONTEXT_HUB_REPO}'...")

    if not LOCAL_AGENTS_MD.exists():
        print(f"  No local file at {LOCAL_AGENTS_MD}. Skipping.")
        return

    headers = {
        "x-api-key": os.getenv("LANGSMITH_API_KEY"),
        "Content-Type": "application/json",
    }
    if ws := os.getenv("LANGSMITH_WORKSPACE_ID", "").strip():
        headers["X-Tenant-Id"] = ws

    # 1. tenant_handle (only if not already set)
    settings = requests.get(f"{_API}/settings", headers=headers).json()
    if not settings.get("tenant_handle"):
        handle = (os.getenv("DEMO_USER", "engine-demo").strip() or "engine-demo").lower().replace(" ", "-")
        requests.post(f"{_API}/settings/handle", headers=headers, json={"tenant_handle": handle})
        print(f"  Set workspace tenant_handle to '{handle}'.")

    # 2. Repo with source=internal (idempotent — 409 if it already exists, which is fine)
    requests.post(
        f"{_API}/repos/",
        headers=headers,
        json={
            "repo_handle": CONTEXT_HUB_REPO,
            "repo_type": "agent",
            "source": "internal",
            "is_public": False,
            "description": "Chat LangChain Lite agent instructions (buggy, for Engine demo)",
        },
    )

    # 3. Commit the file
    content = LOCAL_AGENTS_MD.read_text()
    Client().push_agent(CONTEXT_HUB_REPO, files={"AGENTS.md": FileEntry(content=content)})
    print(f"  Pushed {len(content)} chars.")
