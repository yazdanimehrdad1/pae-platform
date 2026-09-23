"""
Models for the development seed data in `tests/seed_db/`.

TEST-ONLY: used by the seeder and its mock data. App code must never import
`schemas.tests_models`.
"""

from pydantic import BaseModel, Field

from schemas.api_models.requests import DeviceCreateRequest


class SeedDevice(BaseModel):
    """A device to seed, tied to its site by name (resolved to site_id at seed time)."""

    site_name: str = Field(..., min_length=1)
    device: DeviceCreateRequest
