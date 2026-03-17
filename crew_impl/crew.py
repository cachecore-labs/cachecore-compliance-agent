"""CrewAI agent and crew definitions for Agent C.

Uses a single ComplianceAnalyst agent definition with a custom tool that
calls the LLM via CacheCore directly (bypassing LiteLLM) to capture
response headers for cache status reporting.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from openai import OpenAI

from cachecore import CacheStatus
from crew_impl.sync_transport import SyncCacheCoreTransport
from shared.config import CACHECORE_GATEWAY_URL, MODEL
from shared.models import SubAgentResult
from shared.prompts import SYSTEM_PROMPT


# Module-level results store — populated by the tool, read by the orchestrator
results_store: dict[str, SubAgentResult] = {}


def analyze_contract_sync(
    *,
    task_key: str,
    agent_id: int,
    contract_name: str,
    contract_text: str,
    question_id: str,
    variant_label: str,
    question_text: str,
    jwt: str,
) -> str:
    """Call LLM via CacheCore (sync) and store the result with cache headers.

    This function is called from CrewAI task execution. It uses the sync
    OpenAI client with a custom transport rather than going through
    LiteLLM/CrewAI's LLM abstraction, because we need access to HTTP
    response headers (X-Cache, X-Cache-Similarity) which LiteLLM does
    not expose.
    """
    transport = SyncCacheCoreTransport(jwt=jwt)
    client = OpenAI(
        api_key="not-needed",
        base_url=f"{CACHECORE_GATEWAY_URL}/v1",
        http_client=httpx.Client(transport=transport),
    )

    user_message = f"Contract excerpt:\n{contract_text}\n\nQuestion: {question_text}"

    t0 = time.perf_counter()
    raw = client.chat.completions.with_raw_response.create(
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
    answer = completion.choices[0].message.content or ""

    results_store[task_key] = SubAgentResult(
        contract_name=contract_name,
        question_id=question_id,
        variant_used=variant_label,
        question_text=question_text,
        answer=answer,
        cache_status=cs.status,
        similarity=cs.similarity,
        latency_ms=round(latency_ms, 1),
        agent_id=agent_id,
        input_tokens=completion.usage.prompt_tokens if completion.usage else 0,
        output_tokens=completion.usage.completion_tokens if completion.usage else 0,
        namespace_hint=ns_hint,
    )

    transport.close()
    return answer
