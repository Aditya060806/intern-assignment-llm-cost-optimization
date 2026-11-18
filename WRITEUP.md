# How I cut ShopAssist's cost per ticket

Aditya Pandey · write-up for both questions of the LLM cost optimization assignment

## Results

| | Baseline | Now | Cut | Highest ticket | Target |
|---|---:|---:|---:|---:|---:|
| **Q1**, one call per ticket | ~8,900 | **1,244** | −86% (7× cheaper) | 1,395 | 3,000 |
| **Q2**, four-node pipeline | ~73,400 | **1,220** | −98% (60× cheaper) | 1,371 | 2,500 |

Average points per ticket over T-1001–T-1004. Every graded field (`action`, `kb_article`) still matches the reference on all four tickets and on the T-1091 holdout, and `pytest -q` passes.

Billing is `uncached input × 3 + cached input × 0.3 + output × 15` points, so one output token costs as much as five input tokens. That's where I looked first.

## What made the difference

1. **The model no longer writes out its reasoning.** Both baselines asked for step-by-step reasoning: about 490 output tokens per call, roughly 7,400 points of text nobody reads. Both prompts now ask for the JSON only. On T-1004 in Q1, that's 6,825 of the 7,725 points saved.
2. **Only two help articles reach the model.** Code ranks the articles against the ticket and sends the best two, about 60 tokens of policy text. Q2's baseline sent about 17,000 input tokens per ticket across its four calls, mostly help-center filler.
3. **Q2 makes one model call instead of four.** Triage, retrieve and audit are plain code now. On T-1004, dropping those three calls saved 62,586 of the 72,354 points.

## Question 1: one call per ticket

### Where T-1004's tokens went

| Part of the prompt | Before | After |
|---|---:|---:|
| Random run id | 26 | 0 |
| Few-shot examples | 111 | 0 |
| Role and instructions | 45 | 65 |
| Help-center articles | 195 (all five) | 61 (top two) |
| `TICKET_ID` line | 9 | 0 |
| Thread | 23 | 23 |
| Order snapshot | 82 | 43 |
| Labels and separators | 17 | 16 |
| **Input tokens** | **508** | **208** |
| **Output tokens** | **491** | **36** |
| **Points** | **8,889** | **1,164** |

- The instructions grew by 20 tokens. They now carry the action list and the JSON shape that the few-shot examples used to show.
- The run id was a fresh UUID on every call. It told the model nothing, and on a real API a unique first line also stops prefix caching.
- The snapshot is compact JSON without `order_id` and `sku`, which don't change the policy outcome. Markdown bold is stripped from the articles because it only adds tokens.

### The whole call

The exact prompt T-1004 sends, 208 tokens:

```text
SYSTEM:
You are ShopAssist, Tier-1 support. Choose REFUND, REPLACE, SEND_ARTICLE (policy says no) or ESCALATE_TIER2 (manual review), and the article id that backs it.
JSON only: {"action": "", "kb_article": "", "customer_reply": "<one sentence>"}

USER:
ARTICLES:
# damage-replacement-7-days

Standard catalog items reported damaged within 7 days of delivery qualify for a free replacement shipment.

# returns-within-30-days

Physical items in resalable condition may be refunded within 30 days of delivery. Opened items follow the opened-goods article.

THREAD:
[CUSTOMER] Warehouse mug (not custom) showed up cracked. Delivered 2 days ago. Replacement?

ORDER_SNAPSHOT:
{"title":"Ceramic mug","product_type":"physical","delivered_days_ago":2,"opened":true,"license_revealed":false,"customized":false,"damage_reported":true}
END_SNAPSHOT
```

The answer, 36 tokens:

```json
{
  "action": "REPLACE",
  "kb_article": "damage-replacement-7-days",
  "customer_reply": "A replacement is on the way."
}
```

### Every ticket

| Ticket | Case | Answer | Before: in / out → points | After: in / out → points |
|---|---|---|---:|---:|
| T-1001 | Unopened headphones, wants a refund | REFUND · `returns-within-30-days` | 526 / 491 → 8,943 | 235 / 46 → 1,395 |
| T-1002 | Ebook, license key already shown | SEND_ARTICLE · `digital-license-no-refund` | 519 / 480 → 8,757 | 218 / 39 → 1,239 |
| T-1003 | Personalized mug arrived cracked | ESCALATE_TIER2 · `custom-items-no-replace` | 509 / 494 → 8,937 | 198 / 39 → 1,179 |
| T-1004 | Stock mug arrived cracked | REPLACE · `damage-replacement-7-days` | 508 / 491 → 8,889 | 208 / 36 → 1,164 |
| T-1091 (holdout) | Annual plan cancelled on day 38 | SEND_ARTICLE · `subscription-cooling-off` | 515 / 495 → 8,970 | 210 / 38 → 1,200 |

T-1001 is the most expensive ticket: it has the longest thread (there's an agent reply in it), the two longest articles and the longest answer. Baseline numbers move by a few points from run to run because of the random ids in its prompt and output.

### How the two articles are picked

`top_articles` in `question1/agent.py` counts the words each article shares with the ticket and keeps the top two.

- The query is the thread messages, the product title and type, and the names of the order's true flags (`damage_reported` becomes "damage reported").
- Words are lowercased, 4+ letters, and cut to their first 6 letters, so "refunded" matches "refund" and "replacement" matches "replace".
- Ties keep the help center's alphabetical order.

The flags are in the query because they're what the policies are about: damage, customization, licenses, opened boxes. On all five tickets the right article ranks first (T-1003 on a tie). The public tickets only cover some of the policy branches, so I also wrote nine made-up tickets for the others:

| Made-up ticket | Reference answer | Rank | Rank without flag words |
|---|---|---:|---:|
| Annual plan cancelled on day 12 | REFUND · `subscription-cooling-off` | 1 | 1 |
| Blender arrived broken, delivered 12 days ago | ESCALATE_TIER2 · `returns-within-30-days` | 2 | 1 |
| Opened keyboard, wants a refund on day 5 | ESCALATE_TIER2 · `returns-within-30-days` | 1 | 1 |
| Unopened lamp, delivered 45 days ago | ESCALATE_TIER2 · `returns-within-30-days` | 1 | 1 |
| Online course, license never revealed | ESCALATE_TIER2 · `returns-within-30-days` | 2 | 2 |
| Engraved pen, customer changed their mind | ESCALATE_TIER2 · `returns-within-30-days` | 1 | **3** |
| Ebook already downloaded, wants a refund | SEND_ARTICLE · `digital-license-no-refund` | 1 | 1 |
| Glass vase chipped on day 3 | REPLACE · `damage-replacement-7-days` | 1 | 1 |
| Engraved glass arrived broken | ESCALATE_TIER2 · `custom-items-no-replace` | 2 | 1 |

With the flag words, the reference article is always in the top two. Without them, the engraved pen ranks it third, and two articles wouldn't be enough.

## Question 2: four-node pipeline

The pipeline keeps all four nodes, but only compose calls the model.

- **triage** (code): ranks the articles with the same `top_articles` as Question 1 and keeps the top two. The expanded help center is the five `data/kb` articles plus internal routing notes, repeated until the blob passes 210k tokens, that say they don't change customer policy. Only the articles get ranked.
- **retrieve** (code): loads the text of those two articles.
- **compose** (LLM): the instructions, the two articles, the thread and the compact snapshot, 190–227 input tokens. It asks only for `action` and `kb_article`, since the pipeline never returned `customer_reply`.
- **audit** (code): accepts the draft only if the action is one of the four and the article id exists. Anything else goes to Tier 2 instead of shipping a bad citation. This replaces a 6,700-token model call that rewrote the same JSON.

### T-1004, REPLACE (physical fulfillment)

| Node | Before: in / out tokens | Before: points | After: in / out tokens | After: points |
|---|---|---:|---|---:|
| triage | 8,438 / 493 | 32,709 | code | 0 |
| retrieve | 603 / 36 | 2,349 | code | 0 |
| compose | 1,176 / 492 | 10,908 | 200 / 36 | 1,140 |
| audit | 6,701 / 495 | 27,528 | code | 0 |
| **Total** | | **73,494** | | **1,140** |

### T-1002, SEND_ARTICLE (denial)

| Node | Before: in / out tokens | Before: points | After: in / out tokens | After: points |
|---|---|---:|---|---:|
| triage | 8,452 / 492 | 32,736 | code | 0 |
| retrieve | 603 / 39 | 2,394 | code | 0 |
| compose | 1,188 / 482 | 10,794 | 210 / 39 | 1,215 |
| audit | 6,704 / 495 | 27,537 | code | 0 |
| **Total** | | **73,461** | | **1,215** |

### Every ticket

| Ticket | Before: 4 calls | After: compose in / out → points |
|---|---:|---:|
| T-1001 | 73,389 | 227 / 46 → 1,371 |
| T-1002 | 73,461 | 210 / 39 → 1,215 |
| T-1003 | 73,221 | 190 / 39 → 1,155 |
| T-1004 | 73,494 | 200 / 36 → 1,140 |
| T-1091 (holdout) | 73,239 | 202 / 38 → 1,176 |

## What I ruled out

- **Prompt caching.** Cached input costs a tenth, but only for an identical prefix of 1,024+ tokens. The fixed part of my prompts is the 57–65-token instruction block. Padding it to 1,024 tokens would cost about 307 points per call even on a cache hit, more than the 171–195 those instructions cost now.
- **Caching Q2's help center instead of cutting it.** Without the baseline's random trace id, triage's 8,289-token help-center prefix could be cached. It would still cost 2,487 points per call, nearly the whole 2,500 budget before any output.
- **One article instead of two.** That saves 27–36 input tokens (81–108 points) per ticket, but three of the nine made-up tickets had the right article in second place.
- **Sending only the order snapshot.** The simulator decides from the snapshot alone, so a snapshot-only prompt scores about 800 points. A real model can't apply a policy it hasn't seen, so I didn't count that as a saving.
- **No model at all.** The policy is simple enough that rules on the order facts could pick the action for 0 points. I kept one call per ticket: the assignment measures an LLM agent, and the model also reads free-text threads and drafts the reply.

## On a real API

- The simulator always answers with indented JSON that includes a `customer_reply`. Asking a real model for single-line JSON, or using structured outputs, would save 9 tokens (135 points) on each Q1 answer. Q2's answer without a reply would be 16–19 tokens instead of 36–46.
- The simulator switches to its ~490-token reasoning answer whenever a phrase like "double-check" or "step by step" appears anywhere in the prompt, including the customer's message. None of these tickets has one. On a real API I'd cap `max_tokens` so a customer's wording can't blow up the cost.
- I'd log how often audit falls back to Tier 2, and how often the cited article isn't the top-ranked one. Those are the early signs of retrieval misses.

## Verification

- `pytest -q`: 6 passed. The repo's two `test_baseline_cost_is_high` tests asserted the baseline was expensive, which any optimization breaks. I replaced them with `test_cost_per_ticket_within_target`, which checks every public ticket against 3,000 points (Q1) and 2,500 (Q2).
- The T-1091 holdout resolves correctly in both agents.
- Audit: with the model's reply stubbed to a made-up article id, and then to an unknown action, the pipeline returned `ESCALATE_TIER2` both times.
- These numbers are from Windows. On Linux and macOS, T-1001's em dash decodes differently, so the four-ticket totals come out 6 points lower.

## Reproduce

```bash
pip install -r requirements.txt
python question1/run.py   # total_points: 4977 (4971 on Linux/macOS)
python question2/run.py   # total_points: 4881 (4875 on Linux/macOS)
pytest -q                 # a few minutes, almost all of it the help-center size test
```

`test_help_center_exceeds_context` is slow because `expanded_help_center_blob()` in `shared/kb.py` re-tokenizes the whole blob every time it adds a chunk. The agents never build that blob, and I left `shared/` unchanged.

## Files changed

| File | Change |
|---|---|
| `question1/agent.py` | JSON-only prompt, article ranking (`top_articles`), compact prompt builder (`ticket_prompt`) |
| `question2/agent.py` | One model call; triage, retrieve and audit in code using Q1's helpers. 119 → 47 non-blank lines |
| `tests/test_question1.py`, `tests/test_question2.py` | Per-ticket target checks instead of "baseline is expensive" checks |
| `README.md` | Results table |
