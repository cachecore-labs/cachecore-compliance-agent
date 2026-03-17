# Agent C — Usage Guide & Testing Examples

## Prerequisites

### 1. Start the CacheCore gateway
```bash
cd /path/to/cachecore/code/docker
OPENAI_API_KEY=your-key docker compose up -d
```

### 2. Enable debug headers (required for namespace verification)
Edit `code/config/gateway.toml`:
```toml
debug_headers = true
```
Then restart the gateway.

### 3. Install the CacheCore Python client
```bash
pip install -e /path/to/cachecore/client/cachecore-python
```

### 4. Set environment (optional — defaults work for local dev)
```bash
cd agent_c
cp .env.example .env
# Edit if your gateway is not at localhost:8080
```

---

## Running Each Implementation

All commands assume you're in the `agent_c/` directory.

### Vanilla (asyncio)

```bash
pip install -r vanilla/requirements.txt

# Full run — 10 agents, 8 questions each, concurrent
python -m vanilla.orchestrator

# Verbose — see per-query cache status and latency
python -m vanilla.orchestrator --verbose

# Sequential — agents 2-10 run one at a time (for latency comparison)
python -m vanilla.orchestrator --verbose --sequential

# Fewer agents for quick testing
python -m vanilla.orchestrator --verbose --parallel-agents 3
```

### LangGraph

```bash
pip install -r lg/requirements.txt

# Full run
python -m lg.orchestrator

# Verbose with fewer agents
python -m lg.orchestrator --verbose --parallel-agents 3
```

### CrewAI

```bash
pip install -r crew_impl/requirements.txt

# Full run
python -m crew_impl.orchestrator

# Verbose with fewer agents
python -m crew_impl.orchestrator --verbose --parallel-agents 3
```

---

## CLI Flags

| Flag | Vanilla | LangGraph | CrewAI | Description |
|------|:-------:|:---------:|:------:|-------------|
| `--verbose` | Y | Y | Y | Print per-query cache status |
| `--parallel-agents N` | Y | Y | Y | Number of sub-agents (default: 10) |
| `--contracts-dir PATH` | Y | Y | Y | Custom contracts directory |
| `--sequential` | Y | - | - | Run agents sequentially (vanilla only) |
| `--model NAME` | Y | - | - | Override LLM model (vanilla only) |

---

## Test Scenarios

### Test 1: Quick smoke test (3 agents)

Fastest way to verify the setup works:

```bash
python -m vanilla.orchestrator --verbose --parallel-agents 3
```

**Expected output:**
- Agent 1 (variant A): 8 MISS results (seeding the cache)
- Agent 2 (variant B): 8 results, most should be HIT_L2
- Agent 3 (variant C): 8 results, most should be HIT_L2
- Total: 24 queries, ~8 MISS, ~16 HIT_L2

### Test 2: Full 10-agent run

```bash
python -m vanilla.orchestrator --verbose
```

**Expected output:**
- 80 total queries
- 8 MISS (agent 1 seeds)
- Up to 72 HIT_L2 (agents 2-10)
- 90% cache hit rate

### Test 3: Sequential vs concurrent latency comparison

```bash
# Sequential baseline
python -m vanilla.orchestrator --verbose --sequential 2>&1 | tail -20

# Concurrent (default)
python -m vanilla.orchestrator --verbose 2>&1 | tail -20
```

Compare the "Total latency" line. Concurrent should be significantly faster because agents 2-10 run in parallel and L2 hits return in ~15-25ms.

### Test 4: Cross-framework consistency

Run all three back-to-back and compare the summary blocks:

```bash
python -m vanilla.orchestrator 2>&1 | grep -A 15 "=== CacheCore"
python -m lg.orchestrator 2>&1 | grep -A 15 "=== CacheCore"
python -m crew_impl.orchestrator 2>&1 | grep -A 15 "=== CacheCore"
```

The namespace hint should be **identical** across all three. Cache hit counts should be similar (small timing differences may cause slight variation).

### Test 5: Namespace verification

```bash
python -m vanilla.orchestrator --verbose 2>&1 | grep "Namespace hint"
```

If the output shows:
```
Namespace hint      : abc123def456 (identical across all agents)
```
All agents share the same namespace. If you see a mismatch warning, the system prompt or JWT claims differ between agents.

### Test 6: Single agent (no caching expected)

```bash
python -m vanilla.orchestrator --parallel-agents 1 --verbose
```

**Expected:** All 8 queries are MISS (only agent 1, no concurrent agents to benefit from cache).

### Test 7: Custom contracts directory

Create your own contracts and test:

```bash
mkdir /tmp/my_contracts
# Create a short contract file
cat > /tmp/my_contracts/test_contract.txt << 'EOF'
SERVICE AGREEMENT between TestCorp and DemoCo.
1. TERM: 12 months from signing.
2. PAYMENT: Net 30 days. Late fee: 1.5% per month.
3. LIABILITY: Capped at $500,000. No consequential damages.
4. TERMINATION: Either party may terminate with 30 days notice.
5. CONFIDENTIALITY: 2 year obligation post-termination.
6. IP: All work product owned by DemoCo.
7. DISPUTES: Binding arbitration in New York.
8. FORCE MAJEURE: Standard clause, 60 day suspension limit.
9. GOVERNING LAW: State of New York.
EOF

python -m vanilla.orchestrator --contracts-dir /tmp/my_contracts --parallel-agents 1 --verbose
```

### Test 8: Model override (vanilla only)

```bash
# Use a different model
python -m vanilla.orchestrator --model gpt-4o --parallel-agents 2 --verbose
```

Note: The model name is passed to CacheCore gateway, which forwards it to the upstream provider.

---

## Understanding the Output

### Per-query line (verbose mode)

```
  [+] Agent  2  contract_02  Q1/B  HIT_L2   sim=0.923    19ms
```

| Field | Meaning |
|-------|---------|
| `[+]` / `[-]` | Cache hit (+) or miss (-) |
| `Agent 2` | Sub-agent number |
| `contract_02` | Contract file being analyzed |
| `Q1/B` | Question 1, variant B |
| `HIT_L2` | L2 semantic cache hit |
| `sim=0.923` | Cosine similarity score (0.0–1.0) |
| `19ms` | Request latency |

### Summary block

```
Cache results:
  MISS              : 8    (sub-agent 1 seeds cache)
  L2 HIT            : 72   (semantic match on varied phrasing)
  L1 HIT            : 0    (expected -- no exact duplicates)
```

- **MISS** = LLM was actually called (costs money, takes time)
- **L2 HIT** = semantically similar query matched in cache (free, fast)
- **L1 HIT** = exact same query matched (not expected since variants differ)

### Namespace hint

```
Namespace hint      : a1b2c3d4e5f6 (identical across all agents)
```

This is the first 12 hex chars of `SHA256(tenant_id || perm_hash || system_fp || toolset_fp || policy_version)`. All agents must produce the same hint for L2 to work across them.

---

## Troubleshooting

### All queries return MISS (no L2 hits)

1. **Check namespace hints** — run with `--verbose` and look for mismatch warnings
2. **Enable debug headers** — set `debug_headers = true` in `gateway.toml`
3. **Check similarity scores** — the `sim=` value shows how close queries are. If all are below 0.870, the L2 threshold may need lowering
4. **Lower the threshold** — edit `gateway.toml`:
   ```toml
   l2_similarity_threshold = 0.800
   ```
   Restart the gateway and re-run

### Connection refused / timeout

```bash
# Check if gateway is running
curl http://localhost:8080/health
```

### "No contracts found" error

Make sure you're running from the `agent_c/` directory, or pass `--contracts-dir` explicitly:
```bash
python -m vanilla.orchestrator --contracts-dir ./shared/contracts
```

### CrewAI import errors

CrewAI has many transitive dependencies. Install in a clean venv:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r crew_impl/requirements.txt
pip install -e /path/to/cachecore/client/cachecore-python
```

---

## Architecture: How Header Access Works

Each framework bypasses its native LLM wrapper to read CacheCore response headers:

| Framework | LLM Client | Header Access Method |
|-----------|-----------|---------------------|
| Vanilla | `AsyncOpenAI` | `with_raw_response()` → `raw.http_response.headers` |
| LangGraph | `AsyncOpenAI` (NOT ChatOpenAI) | Same `with_raw_response()` pattern |
| CrewAI | `OpenAI` (sync, NOT LiteLLM) | Same pattern + `SyncCacheCoreTransport` |

LangChain's `ChatOpenAI` and CrewAI's `LiteLLM` do not expose HTTP response headers. All three implementations use the OpenAI SDK's `with_raw_response` API directly, which returns the raw `httpx.Response` including CacheCore's `X-Cache`, `X-Cache-Similarity`, and `X-CacheCore-Namespace-Hint` headers.
