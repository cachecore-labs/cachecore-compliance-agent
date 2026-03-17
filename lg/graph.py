"""LangGraph graph definition for Agent C.

Graph flow:
  seed_node → fan_out → [parallel sub_agent_nodes via Send] → collect → report
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from cachecore import CacheCoreClient
from shared.config import SEED_DELAY_MS
from shared.models import SubAgentResult
from shared.queries import QUESTIONS, VARIANT_LABELS
from shared.reporter import print_report

from lg.nodes import (
    AgentCState,
    ContractAssignment,
    SubAgentState,
    call_cachecore,
)


def build_graph(cc_client: CacheCoreClient, verbose: bool = False) -> Any:
    """Build and compile the Agent C LangGraph."""

    # ── Node: seed ────────────────────────────────────────────────────
    async def seed_node(state: AgentCState) -> dict:
        """Run agent 1 (variant 0) sequentially to prime the L2 cache."""
        seed_assignments = [a for a in state["assignments"] if a["agent_id"] == 1]
        results: list[SubAgentResult] = []
        for assignment in seed_assignments:
            result = await call_cachecore(assignment, cc_client)
            if verbose:
                icon = "+" if result.cache_status.startswith("HIT") else "-"
                print(f"  [{icon}] seed  {result.contract_name}  "
                      f"{result.question_id}/{result.variant_used}  "
                      f"{result.cache_status}  {result.latency_ms:.0f}ms")
            results.append(result)
        # Brief delay for L2 vector write propagation
        await asyncio.sleep(SEED_DELAY_MS / 1000)
        return {"results": results, "seed_complete": True}

    # ── Conditional edge: fan out via Send ────────────────────────────
    def fan_out(state: AgentCState) -> list[Send]:
        """Dispatch one Send per non-seed agent."""
        concurrent = [a for a in state["assignments"] if a["agent_id"] != 1]
        # Group by agent_id
        agents: dict[int, list[ContractAssignment]] = {}
        for a in concurrent:
            agents.setdefault(a["agent_id"], []).append(a)
        return [
            Send("sub_agent_node", {"assignment_batch": batch})
            for batch in agents.values()
        ]

    # ── Node: sub-agent (parallel branch) ─────────────────────────────
    async def sub_agent_node(state: dict) -> dict:
        """Process all questions for one agent/contract."""
        batch = state["assignment_batch"]
        results: list[SubAgentResult] = []
        for assignment in batch:
            result = await call_cachecore(assignment, cc_client)
            if verbose:
                icon = "+" if result.cache_status.startswith("HIT") else "-"
                print(f"  [{icon}] agent {result.agent_id:>2d}  "
                      f"{result.contract_name}  "
                      f"{result.question_id}/{result.variant_used}  "
                      f"{result.cache_status}  {result.latency_ms:.0f}ms")
            results.append(result)
        return {"results": results}

    # ── Node: report ──────────────────────────────────────────────────
    async def report_node(state: AgentCState) -> dict:
        print_report(state["results"], framework="LangGraph")
        return {}

    # ── Build graph ───────────────────────────────────────────────────
    workflow = StateGraph(AgentCState)
    workflow.add_node("seed_node", seed_node)
    workflow.add_node("sub_agent_node", sub_agent_node)
    workflow.add_node("report_node", report_node)

    workflow.set_entry_point("seed_node")
    workflow.add_conditional_edges("seed_node", fan_out, ["sub_agent_node"])
    workflow.add_edge("sub_agent_node", "report_node")
    workflow.add_edge("report_node", END)

    return workflow.compile()
