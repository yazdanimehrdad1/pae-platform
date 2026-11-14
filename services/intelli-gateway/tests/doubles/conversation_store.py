"""In-memory ConversationStore for tests: the same contract as the Postgres one
(tests/conversation_store_contract.py)."""

import asyncio
import copy
from datetime import datetime

from intelli_gateway.schemas.agent import Conversation
from intelli_gateway.schemas.conversations import ConversationSummary, Feedback, NewTurn, Turn


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._turns: dict[str, list[Turn]] = {}
        self._next_turn_id = 1
        self._lock = asyncio.Lock()

    async def get(self, conversation_id: str) -> Conversation | None:
        async with self._lock:
            found = self._conversations.get(conversation_id)
            return copy.deepcopy(found) if found is not None else None

    async def save(self, conversation: Conversation, turn: NewTurn) -> Turn:
        async with self._lock:
            self._conversations[conversation.conversation_id] = copy.deepcopy(conversation)
            turns = self._turns.setdefault(conversation.conversation_id, [])
            stored = Turn(**turn.model_dump(), turn_id=self._next_turn_id, position=len(turns))
            self._next_turn_id += 1
            turns.append(stored)
            return stored

    async def list_for_user(
        self, user_id: int, site_id: int | None = None
    ) -> list[ConversationSummary]:
        async with self._lock:
            mine = [
                ConversationSummary(
                    conversation_id=conversation.conversation_id,
                    site_id=conversation.site_id,
                    title=conversation.title,
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                    turns=len(self._turns.get(conversation.conversation_id, [])),
                )
                for conversation in self._conversations.values()
                if conversation.user_id == user_id
                and (site_id is None or conversation.site_id == site_id)
            ]
        return sorted(mine, key=lambda summary: summary.updated_at, reverse=True)

    async def turns(self, conversation_id: str) -> list[Turn]:
        async with self._lock:
            return list(self._turns.get(conversation_id, []))

    async def set_feedback(
        self,
        conversation_id: str,
        turn_id: int,
        feedback: Feedback | None,
        comment: str | None,
        at: datetime,
    ) -> Turn | None:
        async with self._lock:
            turns = self._turns.get(conversation_id, [])
            for index, turn in enumerate(turns):
                if turn.turn_id == turn_id:
                    updated = turn.model_copy(
                        update={
                            "feedback": feedback,
                            "feedback_comment": comment if feedback is not None else None,
                            "feedback_at": at if feedback is not None else None,
                        }
                    )
                    turns[index] = updated
                    return updated
        return None

    async def rename(self, conversation_id: str, title: str) -> ConversationSummary | None:
        async with self._lock:
            found = self._conversations.get(conversation_id)
            if found is None:
                return None
            found.title = title
            return ConversationSummary(
                conversation_id=found.conversation_id,
                site_id=found.site_id,
                title=title,
                created_at=found.created_at,
                updated_at=found.updated_at,
                turns=len(self._turns.get(conversation_id, [])),
            )

    async def delete(self, conversation_id: str) -> bool:
        async with self._lock:
            self._turns.pop(conversation_id, None)
            return self._conversations.pop(conversation_id, None) is not None
