from __future__ import annotations

from dataclasses import dataclass

from shared.billing import CostSession
from shared.kb import article_ids
from shared.llm import ChatMessage, LlmClient
from shared.tools import get_order, get_ticket

from question1.agent import article_text, parse_resolution, ticket_prompt, top_articles

ACTIONS = {"REFUND", "REPLACE", "SEND_ARTICLE", "ESCALATE_TIER2"}

_INSTRUCTIONS = (
    "You are ShopAssist, Tier-1 support. Choose REFUND, REPLACE, SEND_ARTICLE (policy says no) "
    "or ESCALATE_TIER2 (manual review), and the article id that backs it.\n"
    'JSON only: {"action": "", "kb_article": ""}'
)


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

    def handle_ticket(self, ticket_id: str) -> TicketResolution:
        ticket = get_ticket(ticket_id)
        order = get_order(ticket["order_id"])

        candidates = self._triage(ticket, order)
        articles = self._retrieve(candidates)
        draft = self._compose(ticket, order, articles)
        return self._audit(draft, candidates)

    def _triage(self, ticket: dict, order: dict) -> list[str]:
        # The expanded help center is the data/kb articles plus routing notes that say
        # they don't change customer policy, so only the articles get ranked.
        return top_articles(ticket, order)

    def _retrieve(self, candidates: list[str]) -> str:
        return "\n\n".join(article_text(aid) for aid in candidates)

    def _compose(self, ticket: dict, order: dict, articles: str) -> str:
        user = ticket_prompt(ticket, order, articles)
        messages = [ChatMessage("system", _INSTRUCTIONS), ChatMessage("user", user)]
        return self.llm.chat("compose", messages)

    def _audit(self, draft: str, candidates: list[str]) -> TicketResolution:
        res = parse_resolution(draft)
        if res.action in ACTIONS and res.kb_article in article_ids():
            return TicketResolution(res.action, res.kb_article)
        # unknown action or made-up article id: let a human take it
        return TicketResolution("ESCALATE_TIER2", candidates[0])
