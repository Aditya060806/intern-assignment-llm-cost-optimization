# Question 1 — SupportCopilot

Entry point: `SupportCopilot.handle_ticket(ticket_id)`.

```bash
python run.py
pytest -q ../tests/test_question1.py
```

Use `get_ticket` / `get_order` for ticket data. Spec: [questions/question-1.md](../questions/question-1.md).

## Write-up

Points per ticket went from about 8,900 to an average of 1,244 on T-1001–T-1004 (highest: 1,395 on T-1001). `action` and `kb_article` are unchanged, and the T-1091 holdout still resolves.

T-1004, one call:

| | Input tokens | Output tokens | Points |
|---|---:|---:|---:|
| Before | 508 | 491 | 508 × 3 + 491 × 15 = 8,889 |
| After | 208 | 36 | 208 × 3 + 36 × 15 = 1,164 |

Output was most of the cost. The prompt asked the model to think step by step, write full reasoning and quote articles, so it wrote ~490 tokens nobody reads. At 15 points a token that was 7,365 of the 8,889 points. The prompt now asks for the JSON only, with a one-sentence `customer_reply`. The 36 tokens left are just the JSON answer.

Input went from 508 to 208 tokens:

- Only the 2 best-matching articles go in: 61 tokens instead of the 195-token help center. `top_articles` ranks articles by word overlap with the thread, the product title and type, and the order's true flags (`damage_reported`, `customized`, ...). The right article is in the top 2 on all five tickets.
- The few-shot examples (111 tokens) and the "think step by step" text are gone. The instructions are 65 tokens and list the four actions.
- Removed the random run id at the top of the system prompt (~29 tokens) and the `TICKET_ID` line. Neither helps the decision, and on a real API a unique first line also breaks prefix caching.
- Compact order snapshot without `order_id` and `sku`: 82 → 43 tokens.
- Markdown bold is stripped from the articles; it only adds tokens.

Prompt caching doesn't help here. It needs an identical prefix of at least 1,024 tokens, and the only static part of this prompt is the 65-token instruction block.
