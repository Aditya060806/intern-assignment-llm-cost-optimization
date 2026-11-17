from __future__ import annotations

import json
import re
from dataclasses import dataclass

from shared.billing import CostSession
from shared.kb import article_ids, load_article
from shared.llm import ChatMessage, LlmClient
from shared.tools import format_thread, get_order, get_ticket


@dataclass
class TicketResolution:
    action: str
    kb_article: str
    customer_reply: str
    raw_completion: str


def parse_resolution(text: str) -> TicketResolution:
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError(f"No JSON in model output:\n{text[:400]}")
    data = json.loads(m.group())
    return TicketResolution(
        action=str(data["action"]).upper(),
        kb_article=str(data["kb_article"]),
        customer_reply=str(data.get("customer_reply", "")),
        raw_completion=text,
    )


TOP_K = 2

# JSON only, no reasoning: output tokens cost 5x input.
_INSTRUCTIONS = (
    "You are ShopAssist, Tier-1 support. Choose REFUND, REPLACE, SEND_ARTICLE (policy says no) "
    "or ESCALATE_TIER2 (manual review), and the article id that backs it.\n"
    'JSON only: {"action": "", "kb_article": "", "customer_reply": "<one sentence>"}'
)


def _terms(text: str) -> set[str]:
    # 6-letter prefixes, so "refunded" matches "refund" and "replacement" matches "replace"
    return {w[:6] for w in re.findall(r"[a-z]{4,}", text.lower())}


def article_text(aid: str) -> str:
    return load_article(aid).replace("**", "").strip()  # bold markers are just extra tokens


def top_articles(ticket: dict, order: dict, k: int = TOP_K) -> list[str]:
    """Articles that share the most words with the thread, the product and its true flags."""
    words = [m["text"] for m in ticket["messages"]]
    words += [order.get("title", ""), order.get("product_type", "")]
    words += [key.replace("_", " ") for key, value in order.items() if value is True]
    query = _terms(" ".join(words))
    overlap = {aid: len(query & _terms(article_text(aid))) for aid in article_ids()}
    return sorted(overlap, key=overlap.get, reverse=True)[:k]


def ticket_prompt(ticket: dict, order: dict, articles: str) -> str:
    # order id and sku don't change the policy outcome
    facts = {key: value for key, value in order.items() if key not in ("order_id", "sku")}
    snapshot = json.dumps(facts, separators=(",", ":"))
    return (
        f"ARTICLES:\n{articles}\n\nTHREAD:\n{format_thread(ticket)}\n\n"
        f"ORDER_SNAPSHOT:\n{snapshot}\nEND_SNAPSHOT"
    )


class SupportCopilot:
    """
    ShopAssist Tier-1 copilot.

    Given a support ticket + order snapshot, choose an action, cite the help-center
    article, and draft the customer reply.
    """

    def __init__(self, session: CostSession | None = None):
        self.session = session or CostSession()
        self.llm = LlmClient(self.session)

    def build_messages(self, ticket_id: str) -> list[ChatMessage]:
        ticket = get_ticket(ticket_id)
        order = get_order(ticket["order_id"])
        articles = "\n\n".join(article_text(aid) for aid in top_articles(ticket, order))
        user = ticket_prompt(ticket, order, articles)
        return [ChatMessage("system", _INSTRUCTIONS), ChatMessage("user", user)]

    def handle_ticket(self, ticket_id: str) -> TicketResolution:
        messages = self.build_messages(ticket_id)
        completion = self.llm.chat("handle_ticket", messages)
        return parse_resolution(completion)
