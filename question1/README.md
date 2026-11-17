# Question 1 — SupportCopilot

Entry point: `SupportCopilot.handle_ticket(ticket_id)`.

```bash
python run.py
pytest -q ../tests/test_question1.py
```

Use `get_ticket` / `get_order` for ticket data. Spec: [questions/question-1.md](../questions/question-1.md).

## Write-up

Points per ticket went from about 8,900 to under 1,800 on all four public tickets. `action` and `kb_article` are unchanged, and the T-1091 holdout still resolves.

T-1004, one call:

| | Input tokens | Output tokens | Points |
|---|---:|---:|---:|
| Before | 508 | 491 | 508 × 3 + 491 × 15 = 8,889 |
| After | 337 | 36 | 337 × 3 + 36 × 15 = 1,551 |

Most of the cost was output. The prompt asked the model to think step by step, write full reasoning and quote articles, so it wrote ~490 tokens nobody reads. At 15 points a token that was 7,365 of the 8,889 points. The prompt now asks for the JSON only, with a one-sentence `customer_reply`.

Input dropped by about 170 tokens:

- Swapped the few-shot examples (111 tokens) for one line listing the four actions (27 tokens). The help center already covers the rules; the model only needs the action names.
- Removed the random run id at the top of the system prompt (~29 tokens) and the `TICKET_ID` line. Neither helps the decision, and on a real API a unique first line also breaks prefix caching.
- Compact order snapshot: `separators=(",", ":")` instead of `indent=2`, 82 → 58 tokens.
- Built the help center from the articles directly. `all_articles_blob()` puts a `--- id ---` line above each article, which already starts with `# id` (195 → 159 tokens).

I didn't use prompt caching. The whole prompt is under 400 tokens, well below the 1,024-token minimum. Padding it to qualify only pays off on cache hits; on a real API the first call is a miss, and a padded prompt would put that ticket over the 3,000 target.
