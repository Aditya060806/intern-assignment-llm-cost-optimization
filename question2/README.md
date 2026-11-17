# Question 2 — SupportPipeline

Entry point: `SupportPipeline.handle_ticket(ticket_id)`.

```bash
python run.py
pytest -q ../tests/test_question2.py
```

Spec: [questions/question-2.md](../questions/question-2.md).

## Write-up

The baseline spent about 73,400 points per ticket on four LLM calls. Triage and audit together sent about 15,000 input tokens, mostly help-center filler, and three of the four nodes wrote ~490 tokens of reasoning each. Now only compose calls the model. The public tickets average 1,220 points (highest: 1,371 on T-1001).

- **triage** (code): ranks the help-center articles by word overlap with the ticket and order, and keeps the top 2. It's the same `top_articles` ranking Question 1 uses.
- **retrieve** (code): loads those 2 articles from `data/kb`. The rest of the expanded help center is internal routing notes, repeated until the blob passes 210k tokens, that say they don't change customer policy. None of it needs to reach the model.
- **compose** (LLM): instructions, the 2 articles, the thread and a compact order snapshot, 190–227 input tokens. It asks for `action` and `kb_article` as JSON only. The pipeline never returned `customer_reply`, so it isn't requested.
- **audit** (code): accepts the draft only if the action is one of the four and the article id exists. Anything else goes to Tier 2 instead of shipping a bad citation. This replaces a 6,700-token LLM call that rewrote the same JSON.

T-1004, REPLACE (physical fulfillment):

| Node | Before: in / out tokens | Before: points | After: in / out tokens | After: points |
|---|---|---:|---|---:|
| triage | 8,438 / 493 | 32,709 | code | 0 |
| retrieve | 603 / 36 | 2,349 | code | 0 |
| compose | 1,176 / 492 | 10,908 | 200 / 36 | 1,140 |
| audit | 6,701 / 495 | 27,528 | code | 0 |
| **Total** | | **73,494** | | **1,140** |

T-1002, SEND_ARTICLE (denial):

| Node | Before: in / out tokens | Before: points | After: in / out tokens | After: points |
|---|---|---:|---|---:|
| triage | 8,452 / 492 | 32,736 | code | 0 |
| retrieve | 603 / 39 | 2,394 | code | 0 |
| compose | 1,188 / 482 | 10,794 | 210 / 39 | 1,215 |
| audit | 6,704 / 495 | 27,537 | code | 0 |
| **Total** | | **73,461** | | **1,215** |
