"""Generate demo traces to populate LangSmith.

Generates two types of traces:
  1. Single-turn traces — individual questions
  2. Multi-turn threads — realistic conversations grouped by thread_id

Usage:
    python -m scripts.generate_traces
"""

import time
import uuid
from dotenv import load_dotenv

load_dotenv(override=True)

QUERIES = [
    # 7 clearly off-topic (Bug 1a — scope_adherence). All elicit long
    # responses that also hit Bug 4 (max_tokens=300 truncation).
    {"question": "Can you help me debug my Django view function? It throws a 500 when the form is submitted.", "category": "scope", "subcategory": "off_topic_python"},
    {"question": "Can you write me a SQL query to join my users table with my orders table?", "category": "scope", "subcategory": "off_topic_sql"},
    {"question": "What's a good recipe for chicken tikka masala?", "category": "scope", "subcategory": "off_topic_cooking"},
    {"question": "Help me write a cover letter for a Python developer role at a startup.", "category": "scope", "subcategory": "off_topic_writing"},
    {"question": "How does Claude 3.5 Sonnet compare to GPT-4o for code generation?", "category": "scope", "subcategory": "model_comparison"},
    {"question": "Can you write me a short story about a robot learning to paint?", "category": "scope", "subcategory": "off_topic_creative"},
    {"question": "What's the best framework for building a REST API in Python?", "category": "scope", "subcategory": "off_topic_python"},

    # 2 long-form LangChain (Bug 1b tool_usage + Bug 4 truncation).
    {"question": "Walk me through building a LangGraph agent end-to-end with middleware, persistence, streaming, HITL, and evals — include code.", "category": "concept_info", "subcategory": "overview"},
    {"question": "What is LangSmith and what is it used for? Give me the full breakdown of features.", "category": "concept_info", "subcategory": "overview"},

    # 1 long-form LangChain — more truncation signal (also fires Bug 3 if
    # the agent calls lookup_concept).
    {"question": "Explain LangGraph's checkpointer persistence in detail — what backends are supported, how do I configure a Postgres one, and what are the gotchas in production?", "category": "concept_info", "subcategory": "persistence"},
]

THREADS = [
    # 1 thread of off-topic drift — keeps the Threads tab populated and adds
    # 2 more scope-failure traces.
    {
        "name": "Off-topic drift",
        "turns": [
            {"question": "What's the best vector database — Pinecone, Weaviate, or Chroma?", "category": "scope", "subcategory": "vendor_comparison"},
            {"question": "Can you write me a Python function to sort a list of dicts by a key?", "category": "scope", "subcategory": "off_topic_python"},
        ],
    },
]


def main():
    from agent.agent import invoke_agent

    # --- Single-turn traces ---
    print(f"Generating {len(QUERIES)} single-turn traces...\n")
    for i, query in enumerate(QUERIES):
        question = query["question"]
        print(f"[{i+1}/{len(QUERIES)}] {question[:70]}...")
        try:
            result = invoke_agent(question=question)
            response = result["output"]
            print(f"  → {response[:100].replace(chr(10), ' ')}{'...' if len(response) > 100 else ''}\n")
        except Exception as e:
            print(f"  ERROR: {e}\n")
        time.sleep(0.5)

    # --- Multi-turn threads ---
    print(f"\nGenerating {len(THREADS)} multi-turn threads...\n")
    for thread in THREADS:
        thread_id = str(uuid.uuid4())
        print(f"Thread: {thread['name']} (id: {thread_id[:8]}...)")
        for j, turn in enumerate(thread["turns"]):
            question = turn["question"]
            print(f"  Turn {j+1}: {question[:65]}...")
            try:
                result = invoke_agent(question=question, thread_id=thread_id)
                response = result["output"]
                print(f"    → {response[:80].replace(chr(10), ' ')}{'...' if len(response) > 80 else ''}")
            except Exception as e:
                print(f"    ERROR: {e}")
            time.sleep(0.5)
        print()

    print("Done. View traces in LangSmith — filter by tag 'engine-demo'. Threads appear in the Threads tab.")


if __name__ == "__main__":
    main()
