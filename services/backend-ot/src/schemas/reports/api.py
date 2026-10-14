"""Request and response models of /api/reports: templates, runs and the builder's catalog."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.api_models.types import DeviceType
from schemas.reports.definition import BlockKind, PointStat, ReportDefinition, ReportWindow
from schemas.reports.schedules import ReportCadence
from schemas.reports.snapshot import ReportSnapshot
from schemas.site_profiles import EndpointOutput, FunctionKind

ReportRunStatus = Literal["queued", "running", "succeeded", "failed"]
ReportRunTrigger = Literal["manual", "schedule"]

MAX_WINDOW_DAYS = 92


# --- Templates ---------------------------------------------------------------------------


class ReportTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=150, description="Unique per site, ignoring case")
    description: str = Field("", max_length=2000)
    definition: ReportDefinition


class ReportTemplateUpdateRequest(BaseModel):
    """Omitted fields keep their value. Changing the definition bumps the version."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=2000)
    definition: ReportDefinition | None = None


class ReportTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    name: str
    description: str
    definition: ReportDefinition
    version: int = Field(..., description="Starts at 1; +1 each time the definition changes")
    created_at: datetime
    updated_at: datetime


# --- Runs --------------------------------------------------------------------------------


class ReportRunCreateRequest(BaseModel):
    """Generate a report from a template, or from a definition given inline (an ad-hoc report).
    `window` replaces the definition's window for this run only (e.g. a custom time range)."""

    model_config = ConfigDict(extra="forbid")

    template_id: int | None = Field(None, description="Generate from this template (exactly one of template_id and definition)")
    definition: ReportDefinition | None = Field(None, description="Generate from this definition (exactly one of template_id and definition)")
    window: ReportWindow | None = Field(None, description="Overrides the definition's window for this run")
    name: str | None = Field(None, min_length=1, max_length=150, description="Defaults to the template's name, or 'Custom report'")

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.template_id is None) == (self.definition is None):
            raise ValueError("Give exactly one of template_id and definition")
        return self


class ReportRunSummary(BaseModel):
    """A run without its report data (for lists)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    template_id: int | None = Field(None, description="Null for an ad-hoc report, or when its template was deleted")
    template_version: int | None = None
    schedule_id: int | None = Field(None, description="The schedule that generated it; null for one requested by hand")
    name: str
    status: ReportRunStatus
    trigger: ReportRunTrigger
    window_start: datetime
    window_end: datetime
    requested_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = Field(None, description="Why the run failed; null otherwise")


class ReportRunsDeleteResponse(BaseModel):
    deleted: int = Field(..., description="How many reports were deleted")


class ReportRunResponse(ReportRunSummary):
    """A run with what it was generated from and, once it succeeded, the report itself."""

    definition: ReportDefinition
    result: ReportSnapshot | None = Field(None, description="The report; set once the run succeeded")


# --- Catalog (what the builder can offer for a site) -------------------------------------


class ReportSiteFunction(BaseModel):
    name: str
    kind: FunctionKind = Field(..., description="device functions need a device_id")
    output: EndpointOutput = Field(..., description="series: usable in a chart block")
    summary: str
    device_types: list[DeviceType] = Field(default_factory=list, description="Device functions only; empty means every device")
    numeric_fields: list[str] = Field(
        default_factory=list, description="Top-level numeric fields of the result, usable as KPI items"
    )


class ReportTextVariable(BaseModel):
    name: str
    description: str


class ReportTextVariables(BaseModel):
    """What a text block can fill in: {<site variable>}, {device:<id>.<field>}, {point:<id>.<field>}."""

    site: list[ReportTextVariable] = Field(default_factory=list, description="Written {name}, e.g. {site_name}")
    device_fields: list[ReportTextVariable] = Field(default_factory=list, description="Written {device:<id>.<name>}, e.g. {device:12.name}")
    point_fields: list[ReportTextVariable] = Field(
        default_factory=list, description="Written {point:<id>.<name>}, e.g. {point:34.max}; statistics cover the report's period",
    )


class ReportCatalogResponse(BaseModel):
    site_id: int
    timezone: str
    block_kinds: list[BlockKind]
    point_stats: list[PointStat]
    max_window_days: int = MAX_WINDOW_DAYS
    site_functions: list[ReportSiteFunction] = Field(default_factory=list)
    text_variables: ReportTextVariables = Field(default_factory=ReportTextVariables)


# --- Schedules ---------------------------------------------------------------------------


class ReportScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    template_id: int
    template_name: str
    cadence: ReportCadence
    window_override: ReportWindow | None = None
    enabled: bool
    keep_last: int | None = None
    keep_days: int | None = None
    next_run_at: datetime | None = Field(None, description="When it next generates (UTC); null while disabled")
    last_run_at: datetime | None = Field(None, description="When it last queued a report")
    timezone: str = Field(..., description="The site's time zone the cadence is in")
    created_at: datetime
    updated_at: datetime
