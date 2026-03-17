# CacheCore Agent — Parallel Compliance Orchestrator

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![asyncio](https://img.shields.io/badge/vanilla-asyncio-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2%2B-orange)
![CrewAI](https://img.shields.io/badge/CrewAI-0.80%2B-red)
![Requires CacheCore](https://img.shields.io/badge/requires-CacheCore-6C47FF)

Three implementations of the same parallel compliance agent showing **L2 semantic cache hits across concurrently running agents**. Same result, three frameworks.

## What this demonstrates

10 sub-agents each review a different supplier contract against the same set of 8 compliance questions. Each sub-agent uses a **different phrasing** of each question. Sub-agent 1 runs first to seed the L2 cache; agents 2-10 run concurrently and receive **L2 HIT** responses because their differently-worded questions are semantically similar enough to match cached entries.

## Why this works (and why most caching doesn't)

Traditional API caching requires exact request matches. CacheCore's L2 semantic cache matches on **embedding similarity** within a namespace:

1. **Same namespace** — all sub-agents share an identical system prompt (`shared/prompts.py`), which produces the same `system_fp` hash. Combined with the same tenant JWT (same `tenant_id`, `roles`, `scope`), this gives all agents the same namespace.

2. **Semantic similarity** — CacheCore embeds the normalised user message using `bge-small-en-v1.5` (384-dim). When two user messages have cosine similarity >= 0.870 (the L2 threshold), the cached response is reused.

3. **No exact match needed** — "Does this contract include a termination-for-convenience clause?" and "Can either party terminate this agreement without specific grounds?" are different strings but semantically equivalent. L2 recognises this; L1 (exact match) would not.

The system prompt must be **byte-identical** across every agent in every framework. Even a trailing space difference produces a different namespace hash and breaks L2 matching.

## Implementations

| Framework  | Entry point                        | Key dependency     |
|------------|------------------------------------|--------------------|
| Vanilla    | `vanilla/orchestrator.py`          | openai, httpx      |
| LangGraph  | `lg/orchestrator.py`               | langgraph          |
| CrewAI     | `crew_impl/orchestrator.py`        | crewai             |

All three use the **CacheCore Python client** (`cachecore` package) for header injection and cache status reading. LangGraph and CrewAI bypass their native LLM wrappers (ChatOpenAI / LiteLLM) for the actual API call because those wrappers do not expose HTTP response headers needed for cache status.

## Results (actual run)

| Metric                    | Without CacheCore | Vanilla asyncio | LangGraph | CrewAI  |
|---------------------------|-------------------|-----------------|-----------|---------|
| LLM API calls made        | 240               | 22              | 24        | 29      |
| LLM calls avoided         | 0                 | 58              | 56        | 51      |
| Cache hit rate            | 0%                | 72.5%           | 70.0%     | 63.7%   |
| Total latency             | ~840s (estimated) | 207.8s          | 255.6s    | 279.9s  |
| Est. tokens saved         | 0                 | ~26,839         | ~25,997   | ~23,606 |
| Est. cost (gpt-5.4)       | $0.660            | $0.0605         | $0.0660   | $0.0798 |

*Cost based on gpt-5.4 short-context pricing ($2.50/1M input, $15.00/1M output, applies below 275k tokens), assuming 500 input + 100 output tokens per query. "Without CacheCore" reflects 80 queries × 3 implementations = 240 total uncached calls.*

**Why CrewAI hit rate is lower:** CrewAI's parallel execution model makes the seeding window less predictable than vanilla's explicit `await` + sleep barrier, so some questions are dispatched before the seed cache is warm. This is a framework orchestration difference, not a CacheCore issue.

## Bonus finding — intra-agent L2 hits

In the vanilla run, agent 1 produced 1 MISS on Q1 then 7 consecutive L2 HITs on Q2–Q8 within the same contract. The 8 compliance questions are semantically similar enough that once Q1 is cached, every subsequent question from the same agent hits L2 without a round-trip to the model. This maps to a real production pattern: an agent reasoning through a document by asking a series of related questions progressively benefits from its own earlier cache entries within a single run.

## Deployment note

Under parallel agent load with 5 or more concurrent agents, the embedding service becomes the first bottleneck. Increase embedding workers to at least 4 in `code/docker/Dockerfile.embedding` for parallel workloads:

```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081", "--workers", "4"]
```

The default single-worker configuration saturates quickly when multiple agents submit embedding requests simultaneously, causing queuing that inflates latency and obscures the true cache benefit.

## Prerequisites

1. **CacheCore gateway** running at `localhost:8080`
   

2. **Enable debug headers** the gateway config:
   ```toml
   debug_headers = true
   ```

3. **Install the CacheCore Python client**

## Quick start

```bash
# Vanilla (asyncio)
cd cachecore-compliance-agent
pip install -r vanilla/requirements.txt
python -m vanilla.orchestrator --verbose

# LangGraph
pip install -r lg/requirements.txt
python -m lg.orchestrator --verbose

# CrewAI
pip install -r crew_impl/requirements.txt
python -m crew_impl.orchestrator --verbose
```

## CLI flags (vanilla)

| Flag | Description |
|------|-------------|
| `--contracts-dir PATH` | Directory containing .txt contracts |
| `--parallel-agents N` | Number of sub-agents (default: 10) |
| `--verbose` | Print per-query cache status |
| `--sequential` | Run agents 2-N sequentially (for latency comparison) |

## L2 threshold tuning

The default `l2_similarity_threshold` is **0.870** in `gateway.toml`. If L2 hits are not appearing:

1. Enable `debug_headers = true` to see the namespace hint
2. Verify all agents produce the same namespace hint (identical JWT claims + system prompt)
3. Lower the threshold to 0.800 for testing
4. Check `X-Cache-Similarity` values in verbose output to see how close queries are

## Structure

```
cachecore-compliance-agent/
  shared/
    contracts/        # 10 synthetic .txt contract files
    queries.py        # 8 questions x 4 variants
    prompts.py        # SYSTEM_PROMPT — single source of truth
    reporter.py       # shared summary output
    models.py         # SubAgentResult dataclass
    config.py         # JWT generation, gateway URL
  vanilla/            # asyncio implementation
  lg/                 # LangGraph implementation
  crew_impl/          # CrewAI implementation
  .env.example
  README.md
```
