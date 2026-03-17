"""Shared results collection and summary output for all Agent C implementations."""

from __future__ import annotations

from shared.models import SubAgentResult


def print_report(
    results: list[SubAgentResult],
    framework: str,
) -> None:
    """Print the per-contract table and summary block.

    Identical format across all three implementations.
    """
    miss_results = [r for r in results if r.cache_status == "MISS"]
    l2_results = [r for r in results if r.cache_status == "HIT_L2"]
    l1_results = [r for r in results if r.cache_status.startswith("HIT_L1")]
    other_results = [
        r for r in results
        if r.cache_status not in ("MISS", "HIT_L2") and not r.cache_status.startswith("HIT_L1")
    ]

    total = len(results)
    miss_count = len(miss_results)
    l2_count = len(l2_results)
    l1_count = len(l1_results)

    total_latency_s = sum(r.latency_ms for r in results) / 1000
    total_input_tokens = sum(r.input_tokens for r in results)
    total_output_tokens = sum(r.output_tokens for r in results)
    est_tokens_saved = sum(r.input_tokens + r.output_tokens for r in l2_results)

    # Per-contract table
    print(f"\n{'Impl':<12s} | {'Contract':<14s} | {'Question':<4s} | "
          f"{'Var':<3s} | {'Cache':<8s} | {'Latency':>8s} | {'Answer (60 chars)'}")
    print("-" * 100)
    for r in results:
        answer_short = (r.answer[:57] + "...") if len(r.answer) > 60 else r.answer
        answer_short = answer_short.replace("\n", " ")
        print(
            f"{framework:<12s} | {r.contract_name:<14s} | {r.question_id:<4s} | "
            f"  {r.variant_used:<1s} | {r.cache_status:<8s} | {r.latency_ms:>7.0f}ms | "
            f"{answer_short}"
        )

    # Namespace hint check
    hints = {r.namespace_hint for r in results if r.namespace_hint}
    if len(hints) == 1:
        ns_hint_line = f"{hints.pop()} (identical across all agents)"
    elif len(hints) > 1:
        ns_hint_line = f"{', '.join(sorted(hints))} -- NAMESPACE MISMATCH -- L2 hits may be lower than expected"
    else:
        ns_hint_line = "(not available — set debug_headers=true in gateway.toml)"

    # Summary block
    llm_avoided = l2_count + l1_count
    avoid_pct = (llm_avoided / total * 100) if total > 0 else 0.0

    print(f"\n  === CacheCore Agent C -- {framework} ===")
    print(f"  Contracts analysed  : {len({r.contract_name for r in results})}")
    print(f"  Sub-agents          : {len({r.agent_id for r in results})} (parallel)")
    print(f"  Total queries       : {total}")
    print(f"  {'─' * 49}")
    print(f"  Cache results:")
    print(f"    MISS              : {miss_count:<4d} (sub-agent 1 seeds cache)")
    print(f"    L2 HIT            : {l2_count:<4d} (semantic match on varied phrasing)")
    print(f"    L1 HIT            : {l1_count:<4d} (expected -- no exact duplicates)")
    if other_results:
        print(f"    OTHER             : {len(other_results):<4d}")
    print(f"  {'─' * 49}")
    print(f"  LLM calls avoided   : {llm_avoided}  ({avoid_pct:.1f}%)")
    print(f"  Total latency       : {total_latency_s:.1f}s")
    print(f"  Est. tokens saved   : ~{est_tokens_saved:,}")
    print(f"  {'─' * 49}")
    print(f"  Namespace hint      : {ns_hint_line}")
    print(f"  =================================================\n")
