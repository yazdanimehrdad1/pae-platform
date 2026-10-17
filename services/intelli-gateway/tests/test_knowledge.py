"""Site knowledge: deterministic text (prompt cache), size tracking, cached token counts."""

from fakes import ScriptedLLMClient

from intelli_gateway.fake_data.knowledge_store import InMemoryKnowledgeStore
from intelli_gateway.knowledge.loader import KnowledgeLoader, estimate_tokens


class CountingTokenCounter:
    def __init__(self, result: int | None) -> None:
        self.calls = 0
        self._result = result

    async def count_tokens(self, text: str) -> int | None:
        self.calls += 1
        return self._result


class TestKnowledgeLoader:
    async def test_text_contains_every_kind_of_document(
        self, knowledge_store: InMemoryKnowledgeStore
    ) -> None:
        knowledge = await KnowledgeLoader(knowledge_store, ScriptedLLMClient(), 1000).load(1)
        assert "## Manuals" in knowledge.text
        assert "## Device information model (IM) scripts" in knowledge.text
        assert "## Engineers' experience notes" in knowledge.text
        assert "Windridge" not in knowledge.text

    async def test_text_is_identical_across_loads(
        self, knowledge_store: InMemoryKnowledgeStore
    ) -> None:
        loader = KnowledgeLoader(knowledge_store, ScriptedLLMClient(), 1000)
        first, second = await loader.load(1), await loader.load(1)
        assert first.text == second.text
        assert first.version == second.version

    async def test_exact_count_is_used_and_cached_per_version(
        self, knowledge_store: InMemoryKnowledgeStore
    ) -> None:
        counter = CountingTokenCounter(1234)
        loader = KnowledgeLoader(knowledge_store, counter, 150_000)
        knowledge = await loader.load(1)
        await loader.load(1)
        assert knowledge.token_count == 1234
        assert knowledge.token_count_exact
        assert counter.calls == 1

    async def test_falls_back_to_an_estimate(self, knowledge_store: InMemoryKnowledgeStore) -> None:
        knowledge = await KnowledgeLoader(knowledge_store, CountingTokenCounter(None), 10).load(1)
        assert knowledge.token_count == estimate_tokens(knowledge.text)
        assert not knowledge.token_count_exact

    async def test_site_without_documents(self) -> None:
        knowledge = await KnowledgeLoader(InMemoryKnowledgeStore([]), ScriptedLLMClient(), 10).load(
            9
        )
        assert "no knowledge documents" in knowledge.text
