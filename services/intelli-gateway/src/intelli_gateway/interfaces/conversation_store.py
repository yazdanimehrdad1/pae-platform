"""Where AI conversations are kept: the raw history the agent continues from, one turn record per
question (what the AI read, tokens, feedback). Postgres in the service
(services/postgres/conversation_store.py); in memory in tests (tests/doubles/). A conversation
is kept until its user deletes it (no automatic retention yet)."""

from datetime import datetime
from typing import Protocol

from intelli_gateway.schemas.agent import Conversation
from intelli_gateway.schemas.conversations import ConversationSummary, Feedback, NewTurn, Turn


class ConversationStore(Protocol):
    async def get(self, conversation_id: str) -> Conversation | None: ...

    async def save(self, conversation: Conversation, turn: NewTurn) -> Turn:
        """Stores the conversation (new or updated history) and appends the turn, numbered
        after the conversation's earlier turns."""
        ...

    async def list_for_user(
        self, user_id: int, site_id: int | None = None
    ) -> list[ConversationSummary]:
        """The user's conversations (for one site, or all), most recently updated first."""
        ...

    async def turns(self, conversation_id: str) -> list[Turn]:
        """The conversation's turns in the order asked."""
        ...

    async def set_feedback(
        self,
        conversation_id: str,
        turn_id: int,
        feedback: Feedback | None,
        comment: str | None,
        at: datetime,
    ) -> Turn | None:
        """Sets (or with None clears) a turn's feedback; None if the turn is not in that
        conversation."""
        ...

    async def rename(self, conversation_id: str, title: str) -> ConversationSummary | None:
        """Sets the conversation's title (later questions keep it); updated_at is unchanged, so
        the list order stays. None if there is no such conversation."""
        ...

    async def delete(self, conversation_id: str) -> bool:
        """Deletes the conversation and its turns for good; False if there was none."""
        ...
