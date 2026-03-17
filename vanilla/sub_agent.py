"""Vanilla sub-agent: one contract + one question → one CacheCore LLM call."""

from __future__ import annotations

import time

import httpx
from openai import AsyncOpenAI

from cachecore import CacheCoreClient, CacheStatus
from shared.config import CACHECORE_GATEWAY_URL, MODEL
from shared.models import SubAgentResult
from shared.prompts import SYSTEM_PROMPT


async def run_sub_agent(
    *,
    agent_id: int,
    contract_name: str,
    contract_text: str,
    question_id: str,
    variant_label: str,
    question_text: str,
    cc_client: CacheCoreClient,
    model: str = MODEL,
    verbose: bool = False,
) -> SubAgentResult:
    """Execute a single compliance question against a contract via CacheCore.

    Uses ``with_raw_response`` to access HTTP headers for cache status.
    """
    oai = AsyncOpenAI(
        api_key="not-needed",
        base_url=f"{CACHECORE_GATEWAY_URL}/v1",
        http_client=httpx.AsyncClient(transport=cc_client.transport),
    )

    user_message = f"Contract excerpt:\n{contract_text}\n\nQuestion: {question_text}"

    t0 = time.perf_counter()
    raw_response = await oai.chat.completions.with_raw_response.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_completion_tokens=256,
    )
    latency_ms = (time.perf_counter() - t0) * 1000

    cs = CacheStatus.from_headers(raw_response.http_response.headers)
    completion = raw_response.parse()

    ns_hint = raw_response.http_response.headers.get(
        "x-cachecore-namespace-hint", ""
    )

    answer = completion.choices[0].message.content or ""
    usage = completion.usage

    if verbose:
        status_icon = "+" if cs.status.startswith("HIT") else "-"
        print(
            f"  [{status_icon}] Agent {agent_id:>2d}  {contract_name}  "
            f"{question_id}/{variant_label}  {cs.status:<8s}  "
            f"sim={cs.similarity:.3f}  {latency_ms:>7.0f}ms"
        )

    return SubAgentResult(
        contract_name=contract_name,
        question_id=question_id,
        variant_used=variant_label,
        question_text=question_text,
        answer=answer,
        cache_status=cs.status,
        similarity=cs.similarity,
        latency_ms=round(latency_ms, 1),
        agent_id=agent_id,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        namespace_hint=ns_hint,
    )
