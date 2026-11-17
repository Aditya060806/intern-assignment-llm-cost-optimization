# Question 2 — SupportPipeline

Entry point: `SupportPipeline.handle_ticket(ticket_id)`.

```bash
python run.py
pytest -q ../tests/test_question2.py
```

Spec: [questions/question-2.md](../questions/question-2.md).

## Write-up

The baseline spent about 73,400 points per ticket on four LLM calls. Triage and audit took about 15,000 input tokens between them, mostly help-center filler, and three of the four nodes wrote ~490 tokens of reasoning each. Now only compose calls the model, and every public ticket costs under 1,600 points.

- **triage** (code): scores each article by word overlap with the thread messages, product title and product type. It compares 6-letter prefixes so "refunded" matches "refund", and keeps the top 3. The right article comes out on top for all five tickets (T-1004 ties with the returns article), so 3 leaves some slack.
- **retrieve** (code): loads those 3 articles from `data/kb`. The rest of the expanded help center is routing filler that says it doesn't change customer policy, so it never needs to reach the model.
- **compose** (LLM): instructions, the 3 articles, the thread and a compact order snapshot, about 250–290 input tokens. It asks for `action` and `kb_article` as JSON only. The pipeline never returned `customer_reply`, so it isn't requested.
- **audit** (code): accepts the draft only if the action is one of the four and the article id exists. Anything else goes to Tier 2 instead of shipping a bad citation. This replaces a 6,700-token LLM call that rewrote the same JSON.

T-1004, REPLACE (physical fulfillment):

| Node | Before: in / out tokens | Before: points | After: in / out tokens | After: points |
|---|---|---:|---|---:|
| triage | 8,438 / 493 | 32,709 | code | 0 |
| retrieve | 603 / 36 | 2,349 | code | 0 |
| compose | 1,176 / 492 | 10,908 | 263 / 36 | 1,329 |
| audit | 6,701 / 495 | 27,528 | code | 0 |
| **Total** | | **73,494** | | **1,329** |

T-1002, SEND_ARTICLE (denial):

| Node | Before: in / out tokens | Before: points | After: in / out tokens | After: points |
|---|---|---:|---|---:|
| triage | 8,452 / 492 | 32,736 | code | 0 |
| retrieve | 603 / 39 | 2,394 | code | 0 |
| compose | 1,188 / 482 | 10,794 | 281 / 39 | 1,428 |
| audit | 6,704 / 495 | 27,537 | code | 0 |
| **Total** | | **73,461** | | **1,428** |
