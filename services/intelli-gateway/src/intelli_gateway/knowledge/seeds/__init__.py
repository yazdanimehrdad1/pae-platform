"""Code-level seeds of engineer knowledge (`manage_knowledge seed`): each builds a site's knowledge
from its approved profile, then goes through the same import, checks and publish as the admin UI.
Seeds are for the simulated powerflow sites only: never real plant knowledge."""

from collections.abc import Callable
from dataclasses import dataclass

from intelli_gateway.knowledge.seeds import powerflow_2bess_1pv
from intelli_gateway.schemas.knowledge import SiteKnowledge
from intelli_gateway.schemas.site_profile import SiteCatalog


@dataclass(frozen=True)
class KnowledgeSeed:
    site_name: str  # the site it's written for, as named in backend-ot
    build: Callable[[SiteCatalog], SiteKnowledge]


SEEDS: dict[str, KnowledgeSeed] = {
    "powerflow_2bess_1pv": KnowledgeSeed(
        site_name=powerflow_2bess_1pv.SITE_NAME,
        build=powerflow_2bess_1pv.powerflow_2bess_1pv_knowledge,
    ),
}
