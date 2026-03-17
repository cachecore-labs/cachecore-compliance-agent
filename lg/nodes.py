"""LangGraph node functions for Agent C.

Each node uses AsyncOpenAI + CacheCore transport directly (NOT ChatOpenAI)
because LangChain's ChatOpenAI wrapper does not expose HTTP response headers,
which are required to read the X-Cache status from CacheCore.
"""

from __future__ import annotations

import operator
import time
from typing import Annotated, Any, TypedDict

import httpx
from openai import AsyncOpenAI

from cachecore import CacheCoreClient, CacheStatus
from shared.config import CACHECORE_GATEWAY_URL, MODEL
from shared.models import SubAgentResult
from shared.prompts import SYSTEM_PROMPT


# ── Graph state ───────────────────────────────────────────────────────────


class ContractAssignment(TypedDict):
    agent_id: int
    contract_name: str
    contract_text: str
    question_id: str
    variant_idx: int
    variant_label: str
    question_text: str


class AgentCState(TypedDict):
    """Top-level graph state passed between nodes."""

    assignments: list[ContractAssignment]  # all agent assignments
    results: Annotated[list[SubAgentResult], operator.add]  # accumulated
    seed_complete: bool


class SubAgentState(TypedDict):
    """State for a single parallel sub-agent branch."""

    assignment: ContractAssignment
    results: Annotated[list[SubAgentResult], operator.add]


# ── LLM call (shared by all nodes) ───────────────────────────────────────


async def call_cachecore(
    assignment: ContractAssignment,
    cc_client: CacheCoreClient,
) -> SubAgentResult:
    """Make one LLM call via CacheCore and capture cache headers."""
    oai = AsyncOpenAI(
        api_key="not-needed",
        base_url=f"{CACHECORE_GATEWAY_URL}/v1",
        http_client=httpx.AsyncClient(transport=cc_client.transport),
    )

    user_message = (
        f"Contract excerpt:\n{assignment['contract_text']}\n\n"
        f"Question: {assignment['question_text']}"
    )

    t0 = time.perf_counter()
    raw = await oai.chat.completions.with_raw_response.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_completion_tokens=256,
    )
    latency_ms = (time.perf_counter() - t0) * 1000

    cs = CacheStatus.from_headers(raw.http_response.headers)
    completion = raw.parse()
    ns_hint = raw.http_response.headers.get("x-cachecore-namespace-hint", "")

    return SubAgentResult(
        contract_name=assignment["contract_name"],
        question_id=assignment["question_id"],
        variant_used=assignment["variant_label"],
        question_text=assignment["question_text"],
        answer=completion.choices[0].message.content or "",
        cache_status=cs.status,
        similarity=cs.similarity,
        latency_ms=round(latency_ms, 1),
        agent_id=assignment["agent_id"],
        input_tokens=completion.usage.prompt_tokens if completion.usage else 0,
        output_tokens=completion.usage.completion_tokens if completion.usage else 0,
        namespace_hint=ns_hint,
    )
