#!/usr/bin/env python3
"""CrewAI orchestrator for Agent C.

Demonstrates CacheCore L2 semantic caching with CrewAI's agent framework.

CrewAI's LLM abstraction (LiteLLM) does not expose HTTP response headers,
so we bypass it for the actual LLM call. CrewAI provides the orchestration
structure (Agent/Task definitions); the LLM call goes directly through
the CacheCore Python client's sync transport to capture X-Cache headers.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import (
    CACHECORE_GATEWAY_URL,
    SEED_DELAY_MS,
    generate_tenant_jwt,
)
from shared.models import SubAgentResult
from shared.queries import QUESTIONS, VARIANT_LABELS
from shared.reporter import print_report

# Import after sys.path fix — the crew module holds the results store
from crew_impl.crew import analyze_contract_sync, results_store


CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "shared" / "contracts"


def load_contracts(directory: Path) -> list[tuple[str, str]]:
    contracts = []
    for p in sorted(directory.glob("*.txt")):
        contracts.append((p.stem, p.read_text()))
    return contracts


def build_assignments(
    contracts: list[tuple[str, str]],
    num_agents: int,
) -> list[dict]:
    """Create all agent × question assignments with variant cycling."""
    assignments = []
    question_keys = list(QUESTIONS.keys())

    for i in range(num_agents):
        agent_id = i + 1
        contract_name, contract_text = contracts[i]
        variant_idx = 0 if agent_id == 1 else (i % len(VARIANT_LABELS))

        for qkey in question_keys:
            assignments.append({
                "agent_id": agent_id,
                "contract_name": contract_name,
                "contract_text": contract_text,
                "question_id": qkey,
                "variant_idx": variant_idx,
                "variant_label": VARIANT_LABELS[variant_idx],
                "question_text": QUESTIONS[qkey][variant_idx],
            })
    return assignments


def run_agent_batch(
    assignments: list[dict],
    jwt: str,
    verbose: bool = False,
) -> list[SubAgentResult]:
    """Run a batch of assignments synchronously, storing results in results_store."""
    results = []
    for a in assignments:
        task_key = f"agent_{a['agent_id']}_{a['question_id']}"
        answer = analyze_contract_sync(
            task_key=task_key,
            agent_id=a["agent_id"],
            contract_name=a["contract_name"],
            contract_text=a["contract_text"],
            question_id=a["question_id"],
            variant_label=a["variant_label"],
            question_text=a["question_text"],
            jwt=jwt,
        )
        result = results_store[task_key]
        if verbose:
            icon = "+" if result.cache_status.startswith("HIT") else "-"
            print(
                f"  [{icon}] agent {result.agent_id:>2d}  "
                f"{result.contract_name}  "
                f"{result.question_id}/{result.variant_used}  "
                f"{result.cache_status}  {result.latency_ms:.0f}ms"
            )
        results.append(result)
    return results


async def main(args: argparse.Namespace) -> None:
    jwt = generate_tenant_jwt()

    contracts = load_contracts(Path(args.contracts_dir))
    if not contracts:
        print(f"No contracts found in {args.contracts_dir}", file=sys.stderr)
        sys.exit(1)

    num_agents = min(args.parallel_agents, len(contracts))
    print(f"\n--- Agent C (CrewAI) | {num_agents} agents | "
          f"{len(QUESTIONS)} questions ---\n")

    all_assignments = build_assignments(contracts, num_agents)

    # Separate seed (agent 1) from concurrent
    seed = [a for a in all_assignments if a["agent_id"] == 1]
    concurrent = [a for a in all_assignments if a["agent_id"] != 1]

    # Phase A: seed — agent 1 runs sequentially
    print("Phase A: Seeding cache (agent 1, variant A) ...")
    all_results = run_agent_batch(seed, jwt, verbose=args.verbose)

    # Brief delay for L2 vector write propagation
    await asyncio.sleep(SEED_DELAY_MS / 1000)

    # Phase B: concurrent — agents 2-N in parallel threads
    print(f"Phase B: Launching agents 2-{num_agents} concurrently ...")

    # Group by agent_id for parallel execution
    agent_batches: dict[int, list[dict]] = {}
    for a in concurrent:
        agent_batches.setdefault(a["agent_id"], []).append(a)

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=num_agents - 1) as pool:
        futures = [
            loop.run_in_executor(
                pool,
                run_agent_batch,
                batch,
                jwt,
                args.verbose,
            )
            for batch in agent_batches.values()
        ]
        batch_results = await asyncio.gather(*futures)
        for batch in batch_results:
            all_results.extend(batch)

    print_report(all_results, framework="CrewAI")


def cli() -> None:
    parser = argparse.ArgumentParser(description="Agent C — CrewAI orchestrator")
    parser.add_argument(
        "--contracts-dir",
        default=str(CONTRACTS_DIR),
        help="Path to contracts directory",
    )
    parser.add_argument("--parallel-agents", type=int, default=10)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args))


if __name__ == "__main__":
    cli()
