"""Who is asking, about which site. Built by the auth layer, passed to every tool call."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class RequestContext:
    user_id: str
    roles: frozenset[str]
    # Sites this user may access. None means every site (the v1 dev user).
    site_ids: frozenset[int] | None
    request_id: str
    # The site this request is about. Tools read data for this site only.
    site_id: int | None = None

    def can_access_site(self, site_id: int) -> bool:
        return self.site_ids is None or site_id in self.site_ids

    def for_site(self, site_id: int) -> "RequestContext":
        return replace(self, site_id=site_id)
