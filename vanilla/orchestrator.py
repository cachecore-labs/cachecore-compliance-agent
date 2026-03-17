#!/usr/bin/env python3
"""Vanilla asyncio orchestrator for Agent C.

Runs 10 sub-agents — agent 1 first (seeds the cache), then agents 2-10
concurrently — demonstrating L2 semantic cache hits across varied phrasings.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Ensure agent_c package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cachecore import CacheCoreClient
from shared.config import (
    CACHECORE_GATEWAY_URL,
    SEED_DELAY_MS,
    generate_tenant_jwt,
)
from shared.queries import QUESTIONS, VARIANT_LABELS
from shared.reporter import print_report
from vanilla.sub_agent import run_sub_agent


CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "shared" / "contracts"


def load_contracts(directory: Path) -> list[tuple[str, str]]:
    """Return sorted list of (name, text) for all .txt contracts."""
    contracts = []
    for p in sorted(directory.glob("*.txt")):
        contracts.append((p.stem, p.read_text()))
    return contracts


async def run_agent_questions(
    *,
    agent_id: int,
    contract_name: str,
    contract_text: str,
    variant_idx: int,
    cc_client: CacheCoreClient,
    verbose: bool = False,
):
    """Run all 8 questions for one agent/contract/variant."""
    from shared.models import SubAgentResult

    results: list[SubAgentResult] = []
    question_keys = list(QUESTIONS.keys())
    variant_label = VARIANT_LABELS[variant_idx]

    for qkey in question_keys:
        question_text = QUESTIONS[qkey][variant_idx]
        result = await run_sub_agent(
            agent_id=agent_id,
            contract_name=contract_name,
            contract_text=contract_text,
            question_id=qkey,
            variant_label=variant_label,
            question_text=question_text,
            cc_client=cc_client,
            verbose=verbose,
        )
        results.append(result)
    return results


async def main(args: argparse.Namespace) -> None:
    jwt = generate_tenant_jwt()
    cc = CacheCoreClient(
        gateway_url=CACHECORE_GATEWAY_URL,
        tenant_jwt=jwt,
        debug=args.verbose,
    )

    contracts = load_contracts(Path(args.contracts_dir))
    if not contracts:
        print(f"No contracts found in {args.contracts_dir}", file=sys.stderr)
        sys.exit(1)

    num_agents = min(args.parallel_agents, len(contracts))
    print(f"\n--- Agent C (vanilla) | {num_agents} agents | "
          f"{len(QUESTIONS)} questions | model={args.model or 'default'} ---\n")

    all_results = []

    # Phase A: seed — agent 1 runs all 8 questions with variant 0
    print("Phase A: Seeding cache (agent 1, variant A) ...")
    seed_results = await run_agent_questions(
        agent_id=1,
        contract_name=contracts[0][0],
        contract_text=contracts[0][1],
        variant_idx=0,
        cc_client=cc,
        verbose=args.verbose,
    )
    all_results.extend(seed_results)

    # Brief delay for L2 vector write propagation
    await asyncio.sleep(SEED_DELAY_MS / 1000)

    # Phase B: concurrent — agents 2-N with variant cycling
    if args.sequential:
        print("Phase B: Running agents 2-N sequentially ...")
        for i in range(1, num_agents):
            variant_idx = (i % len(VARIANT_LABELS))
            results = await run_agent_questions(
                agent_id=i + 1,
                contract_name=contracts[i][0],
                contract_text=contracts[i][1],
                variant_idx=variant_idx,
                cc_client=cc,
                verbose=args.verbose,
            )
            all_results.extend(results)
    else:
        print(f"Phase B: Launching agents 2-{num_agents} concurrently ...")
        tasks = []
        for i in range(1, num_agents):
            variant_idx = (i % len(VARIANT_LABELS))
            tasks.append(
                run_agent_questions(
                    agent_id=i + 1,
                    contract_name=contracts[i][0],
                    contract_text=contracts[i][1],
                    variant_idx=variant_idx,
                    cc_client=cc,
                    verbose=args.verbose,
                )
            )
        concurrent_results = await asyncio.gather(*tasks)
        for batch in concurrent_results:
            all_results.extend(batch)

    print_report(all_results, framework="vanilla/asyncio")
    await cc.aclose()


def cli() -> None:
    parser = argparse.ArgumentParser(description="Agent C — vanilla orchestrator")
    parser.add_argument(
        "--contracts-dir",
        default=str(CONTRACTS_DIR),
        help="Path to contracts directory",
    )
    parser.add_argument(
        "--parallel-agents",
        type=int,
        default=10,
        help="Number of sub-agents (default: 10)",
    )
    parser.add_argument("--verbose", action="store_true", help="Print per-query details")
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run agents 2-N sequentially instead of concurrently",
    )
    parser.add_argument("--model", default=None, help="Override LLM model name")
    args = parser.parse_args()
    asyncio.run(main(args))


if __name__ == "__main__":
    cli()
