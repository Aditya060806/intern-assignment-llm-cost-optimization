# ShopAssist — support copilot cost lab

**ShopAssist** is a Tier-1 support agent for an e-commerce company. For each ticket it:

1. Reads the customer thread (`data/tickets/`)
2. Loads order facts (`data/orders/` via `shared/tools.py`)
3. Picks an action (`REFUND`, `REPLACE`, `SEND_ARTICLE`, `ESCALATE_TIER2`)
4. Cites the help-center article that backs the decision (`data/kb/`)

| Track | Code | Spec |
|-------|------|------|
| Q1 — single call | [question1/agent.py](question1/agent.py) | [questions/question-1.md](questions/question-1.md) |
| Q2 — pipeline | [question2/agent.py](question2/agent.py) | [questions/question-2.md](questions/question-2.md) |

## Results

| | Baseline | Average now | Highest ticket | Target |
|---|---:|---:|---:|---:|
| Q1 points per ticket | ~8,900 | 1,244 | 1,395 | 3,000 |
| Q2 points per ticket | ~73,400 | 1,220 | 1,371 | 2,500 |

Measured on T-1001–T-1004. `action` and `kb_article` still match on all four and on the T-1091 holdout. Per-call breakdowns and write-ups: [Question 1](question1/README.md), [Question 2](question2/README.md).

`pytest -q` passes. Most of its runtime is `test_help_center_exceeds_context`, which builds the 210k-token help center and takes several minutes; the agents never build it.

## Run

```bash
pip install -r requirements.txt
pytest -q
python question1/run.py
python question2/run.py
```

`shared/llm.py` provides a local `LlmClient` with the same billing accounting you would use against a hosted chat API. Do not import `eval/reference.py` from your agent.

## Billing

| Input | Cached input | Output |
|------:|-------------:|-------:|
| 3 | 0.3 | 15 |

Cached input = identical prefix ≥ 1024 tokens across calls.

```
points = uncached_input × 3 + cached_input × 0.3 + output × 15
```

Per-call details are in `shared/billing.py` (`CostSession` on your agent).
