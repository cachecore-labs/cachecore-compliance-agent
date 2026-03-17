"""Shared result dataclass used by all three Agent C implementations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SubAgentResult:
    """One LLM query result from a sub-agent."""

    contract_name: str  # e.g. "contract_01"
    question_id: str  # "Q1"–"Q8"
    variant_used: str  # "A"/"B"/"C"/"D"
    question_text: str
    answer: str
    cache_status: str  # HIT_L1, HIT_L2, MISS, BYPASS, UNKNOWN
    similarity: float  # from X-Cache-Similarity header
    latency_ms: float
    agent_id: int  # 1-10
    input_tokens: int
    output_tokens: int
    namespace_hint: str = ""  # first 12 hex chars from X-CacheCore-Namespace-Hint
