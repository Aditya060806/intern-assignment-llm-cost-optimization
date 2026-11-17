from __future__ import annotations

import json
import re
from dataclasses import dataclass

from shared.billing import CostSession
from shared.kb import article_ids, load_article
from shared.llm import ChatMessage, LlmClient
from shared.tools import format_thread, get_order, get_ticket

from question1.agent import parse_resolution

ACTIONS = {"REFUND", "REPLACE", "SEND_ARTICLE", "ESCALATE_TIER2"}
TOP_K = 3

_INSTRUCTIONS = """You are ShopAssist, a Tier-1 support copilot. Resolve the ticket from the order snapshot and the articles given.
Actions: REFUND, REPLACE, SEND_ARTICLE (policy denies the request), ESCALATE_TIER2 (needs manual review).
Reply with JSON only: {"action": "...", "kb_article": "<article id>"}"""


def _terms(text: str) -> set[str]:
    # 6-letter prefixes, so "refunded" matches "refund" and "replacement" matches "replace"
    return {w[:6] for w in re.findall(r"[a-z]{4,}", text.lower())}


@dataclass
class TicketResolution:
    action: str
    kb_article: str


class SupportPipeline:
    """Same product as Question 1 — triage, retrieve, compose, audit.

    Only compose calls the LLM; the other three nodes are plain code.
    """

    def __init__(self, session: CostSession | None = None):
        self.session = session or CostSession()
        self.llm = LlmClient(self.session)
        self.articles = {aid: load_article(aid).strip() for aid in article_ids()}
        self.index = {aid: _terms(text) for aid, text in self.articles.items()}

    def handle_ticket(self, ticket_id: str) -> TicketResolution:
        ticket = get_ticket(ticket_id)
        order = get_order(ticket["order_id"])

        candidates = self._triage(ticket, order)
        articles = self._retrieve(candidates)
        draft = self._compose(ticket, order, articles)
        return self._audit(draft, candidates)

    def _triage(self, ticket: dict, order: dict) -> list[str]:
        text = " ".join(m["text"] for m in ticket["messages"])
        query = _terms(f"{text} {order.get('title', '')} {order.get('product_type', '')}")
        ranked = sorted(self.index, key=lambda aid: len(query & self.index[aid]), reverse=True)
        return ranked[:TOP_K]

    def _retrieve(self, candidates: list[str]) -> str:
        return "\n\n".join(self.articles[aid] for aid in candidates)

    def _compose(self, ticket: dict, order: dict, articles: str) -> str:
        snapshot = json.dumps(order, separators=(",", ":"))
        user = (
            f"ARTICLES:\n{articles}\n\nTHREAD:\n{format_thread(ticket)}\n\n"
            f"ORDER_SNAPSHOT:\n{snapshot}\nEND_SNAPSHOT"
        )
        messages = [ChatMessage("system", _INSTRUCTIONS), ChatMessage("user", user)]
        return self.llm.chat("compose", messages)

    def _audit(self, draft: str, candidates: list[str]) -> TicketResolution:
        res = parse_resolution(draft)
        if res.action in ACTIONS and res.kb_article in self.articles:
            return TicketResolution(res.action, res.kb_article)
        # unknown action or made-up article id: let a human take it
        return TicketResolution("ESCALATE_TIER2", candidates[0])
