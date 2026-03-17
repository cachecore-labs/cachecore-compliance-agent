"""CrewAI task definitions for Agent C.

Creates one Task per contract × question combination. Each task directly
calls analyze_contract_sync rather than relying on CrewAI's LLM routing,
because we need HTTP response headers for cache status reporting.
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, Crew, Process, Task

from crew_impl.crew import analyze_contract_sync


def build_tasks_and_crew(
    assignments: list[dict[str, Any]],
    jwt: str,
    verbose: bool = False,
) -> Crew:
    """Build a CrewAI Crew with one task per assignment.

    Each task's action function calls the CacheCore LLM directly.
    The Crew uses sequential process since actual parallelism is
    managed by the orchestrator via asyncio.
    """
    agent = Agent(
        role="Contract Compliance Analyst",
        goal="Answer compliance questions about supplier contracts accurately and concisely",
        backstory=(
            "You review supplier contracts for compliance with procurement policies. "
            "You are precise, cite specific clauses, and never fabricate information."
        ),
        verbose=verbose,
        allow_delegation=False,
    )

    tasks = []
    for a in assignments:
        task_key = f"agent_{a['agent_id']}_{a['question_id']}"

        # Capture assignment in closure
        def make_callback(assignment: dict, key: str):
            def callback(output):
                # The actual LLM call happens here, not through CrewAI's LLM
                analyze_contract_sync(
                    task_key=key,
                    agent_id=assignment["agent_id"],
                    contract_name=assignment["contract_name"],
                    contract_text=assignment["contract_text"],
                    question_id=assignment["question_id"],
                    variant_label=assignment["variant_label"],
                    question_text=assignment["question_text"],
                    jwt=jwt,
                )
            return callback

        task = Task(
            description=(
                f"Review the following contract and answer the compliance question.\n\n"
                f"Contract excerpt:\n{a['contract_text']}\n\n"
                f"Question: {a['question_text']}"
            ),
            expected_output="A concise 1-2 sentence compliance analysis.",
            agent=agent,
        )
        tasks.append((task, task_key, a))

    # For CrewAI, we'll execute tasks manually in the orchestrator
    # rather than using Crew.kickoff(), to maintain control over
    # the LLM call path and header capture.
    return tasks
