"""database_is_reachable against the throwaway Postgres (`make test-integration`), and against an
address where nothing listens: it answers False instead of raising."""

from intelli_gateway.services.postgres.database import create_database_engine, database_is_reachable


class TestDatabaseIsReachable:
    async def test_true_for_the_running_database(self, database_url: str) -> None:
        engine = create_database_engine(database_url)
        try:
            assert await database_is_reachable(engine)
        finally:
            await engine.dispose()

    async def test_false_when_nothing_listens(self, database_url: str) -> None:
        del database_url  # only ties this test to the integration run (it opens a real socket)
        engine = create_database_engine("postgresql+asyncpg://user:password@127.0.0.1:1/none")
        try:
            assert not await database_is_reachable(engine)
        finally:
            await engine.dispose()
