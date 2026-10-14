"""What every block resolver gets: the site, the resolved window and the data source."""

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from reports.data_source import ReportDataSource
from schemas.reports.internal import ReportSiteContext


class BlockContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    site: ReportSiteContext
    window_start: datetime
    window_end: datetime
    site_timezone: ZoneInfo
    data_source: ReportDataSource

    @property
    def site_id(self) -> int:
        return self.site.site.site_id
