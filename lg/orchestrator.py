#!/usr/bin/env python3
"""LangGraph orchestrator for Agent C.

Uses a StateGraph with Send-based fan-out for parallel sub-agent execution.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cachecore import CacheCoreClient
from shared.config import CACHECORE_GATEWAY_URL, generate_tenant_jwt
from shared.queries import QUESTIONS, VARIANT_LABELS

# Import after sys.path fix
from lg.graph import build_graph
from lg.nodes import ContractAssignment

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "shared" / "contracts"


def load_contracts(directory: Path) -> list[tuple[str, str]]:
    contracts = []
    for p in sorted(directory.glob("*.txt")):
        contracts.append((p.stem, p.read_text()))
    return contracts


def build_assignments(
    contracts: list[tuple[str, str]],
    num_agents: int,
) -> list[ContractAssignment]:
    """Create all agent × question assignments with variant cycling."""
    assignments: list[ContractAssignment] = []
    question_keys = list(QUESTIONS.keys())

    for i in range(num_agents):
        agent_id = i + 1
        contract_name, contract_text = contracts[i]
        # Agent 1 always gets variant 0; others cycle 1-3 then back to 0
        variant_idx = 0 if agent_id == 1 else (i % len(VARIANT_LABELS))

        for qkey in question_keys:
            assignments.append(
                ContractAssignment(
                    agent_id=agent_id,
                    contract_name=contract_name,
                    contract_text=contract_text,
                    question_id=qkey,
                    variant_idx=variant_idx,
                    variant_label=VARIANT_LABELS[variant_idx],
                    question_text=QUESTIONS[qkey][variant_idx],
                )
            )
    return assignments


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
    print(f"\n--- Agent C (LangGraph) | {num_agents} agents | "
          f"{len(QUESTIONS)} questions ---\n")

    assignments = build_assignments(contracts, num_agents)
    graph = build_graph(cc, verbose=args.verbose)

    await graph.ainvoke({
        "assignments": assignments,
        "results": [],
        "seed_complete": False,
    })

    await cc.aclose()


def cli() -> None:
    parser = argparse.ArgumentParser(description="Agent C — LangGraph orchestrator")
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
